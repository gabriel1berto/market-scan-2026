#!/usr/bin/env python3
"""
extract_pncp.py — Piloto market-scan-2026: extrai contratações públicas do
PNCP (UF=RJ, publicadas 01/01/2026-31/01/2026), filtra itens com resultado
homologado e grava 1 linha por (item, resultado) em `itens_pncp` (Supabase).

Endpoints e formato dos parâmetros confirmados ao vivo contra o swagger oficial
(https://pncp.gov.br/api/consulta/swagger-ui/index.html) e por teste real na
API antes de escrever este script — ver README.md "Achados da verificação de
API". Projeto isolado do licit por design (ver README.md "Isolamento") — código
inspirado em analise/coletor_pncp.py e coletor_pncp_detalhe.py do licit, mas
escrito do zero aqui, sem import nem dependência de runtime daquele repo.

Uso:
    python extract_pncp.py                                  # RJ, jan/2026 (default)
    python extract_pncp.py --uf SP                           # roda pra outra UF
    python extract_pncp.py --data-inicial 20260201 --data-final 20260228  # fev/2026
    python extract_pncp.py --limite 20                      # só as 20 primeiras (teste)
    python extract_pncp.py --status                         # conta linhas já gravadas

Extração de meses além de jan/2026 roda via GitHub Actions (.github/workflows/extract.yml,
trigger manual) pra não competir com o resto do trabalho local — ver README "Rodando extração
no GitHub Actions".
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Configuração — escopo fixado no README, UF/data parametrizáveis via CLI ─

DATA_INICIAL_PADRAO = "20260101"
DATA_FINAL_PADRAO = "20260131"
MODALIDADES = list(range(1, 15))  # 1-14 — todas testadas válidas p/ RJ/jan-2026, não existe "todas" no endpoint
TAM_PAGINA = 50  # máximo aceito pela API

PAUSA_ENTRE_PAGINAS = 2.5
PAUSA_ENTRE_CHAMADAS = 1.5
PAUSA_APOS_ERRO_BASE = 15.0
MAX_TENTATIVAS = 6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

CONSULTA_BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_BASE = "https://pncp.gov.br/api/pncp/v1/orgaos"

LOG_PATH = Path(__file__).parent / "extract_pncp.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("extract_pncp")


# ── Banco (Supabase/Postgres) ────────────────────────────────────────────

def conectar_db() -> tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor]:
    con = psycopg2.connect(os.environ["DATABASE_URL"])
    return con, con.cursor()


# ── Chamada à API com retry/backoff ──────────────────────────────────────

def chamar_api(url: str, params: dict | None = None):
    """Retorna JSON parseado, None se a API respondeu "sem conteúdo" (204/404/410
    — permanente, não transitório), ou levanta RuntimeError depois de esgotar
    as tentativas num erro transitório (timeout, 5xx, conexão)."""
    espera = PAUSA_APOS_ERRO_BASE
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (204, 404, 410):
                return None
            log.warning(f"{url}: HTTP {r.status_code} (tentativa {tentativa}/{MAX_TENTATIVAS})")
        except Exception as e:
            log.warning(f"{url}: erro '{e}' (tentativa {tentativa}/{MAX_TENTATIVAS})")
        time.sleep(espera)
        espera *= 1.6
    raise RuntimeError(f"Falhou {MAX_TENTATIVAS}x em {url}")


# ── Fase 1: busca de contratações publicadas (14 modalidades × páginas) ──

def buscar_contratacoes(uf: str, data_inicial: str, data_final: str) -> list[dict]:
    encontradas = []
    for modalidade in MODALIDADES:
        pagina = 1
        while True:
            params = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": modalidade,
                "uf": uf,
                "pagina": pagina,
                "tamanhoPagina": TAM_PAGINA,
            }
            try:
                resp = chamar_api(f"{CONSULTA_BASE}/contratacoes/publicacao", params)
            except RuntimeError as e:
                log.error(f"modalidade={modalidade} pág={pagina}: {e} — abortando essa modalidade, sigo pras outras.")
                break

            if resp is None:
                break  # 204: sem resultado nessa modalidade/página

            dados = resp.get("data", [])
            if not dados:
                break

            encontradas.extend(dados)
            total_paginas = resp.get("totalPaginas", pagina)
            log.info(
                f"modalidade={modalidade} pág={pagina}/{total_paginas}: "
                f"+{len(dados)} contratações (total modalidade={resp.get('totalRegistros')})"
            )
            if pagina >= total_paginas:
                break
            pagina += 1
            time.sleep(PAUSA_ENTRE_PAGINAS)

    log.info(f"Fase 1 concluída: {len(encontradas)} contratações encontradas em {uf}, {data_inicial}-{data_final}.")
    return encontradas


# ── Fase 2: itens + resultado de cada contratação ────────────────────────

def codigo_catalogo_de(item: dict) -> str | None:
    # 3 nomes candidatos testados ao vivo (ver README) — 100% null na amostra,
    # gravamos o primeiro não-nulo pra medir cobertura real na base inteira.
    # Achado 25/jul/2026: em produção (não só na amostra de 5 itens testada antes),
    # esses campos às vezes vêm como objeto {"codigo":.., "nome":..} (mesmo padrão de
    # outros campos categóricos do PNCP, ex: reservaRemanescente), não só string/null —
    # coluna é text, psycopg2 não adapta dict direto (quebrou o piloto na contratação
    # ~1900/2715). Serializa se vier objeto, preserva o dado em vez de perder.
    valor = item.get("catalogo") or item.get("categoriaItemCatalogo") or item.get("catalogoCodigoItem")
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return valor


def gravar_item_resultado(cur: psycopg2.extensions.cursor, uf: str, contratacao: dict, item: dict, resultado: dict) -> None:
    tipo = "produto" if item.get("materialOuServico") == "M" else "servico"
    data_resultado = resultado.get("dataResultado")
    data_homologacao = data_resultado[:10] if data_resultado else None

    cur.execute("""
        INSERT INTO itens_pncp (
            processo_pncp, uf, tipo, codigo_catalogo, descricao_item,
            valor_homologado, valor_estimado, cnpj_vencedor, data_homologacao, raw_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        contratacao["numeroControlePNCP"], uf, tipo, codigo_catalogo_de(item), item.get("descricao"),
        resultado.get("valorTotalHomologado"), item.get("valorTotal"),
        resultado.get("niFornecedor"), data_homologacao,
        json.dumps({"contratacao": contratacao, "item": item, "resultado": resultado}, ensure_ascii=False),
    ))


def ja_processada(cur: psycopg2.extensions.cursor, numero_controle: str) -> bool:
    # Resumibilidade (achado 25/jul/2026, script crashou na volta ~1900/2715 por bug
    # de tipo — sem isso, rerodar do zero duplicaria as ~1900 já gravadas, já que o
    # INSERT não tem upsert/dedupe). Só pula quem JÁ TEM linha gravada — contratação
    # sem nenhum item homologado+resultado nunca aparece aqui, então é sempre
    # re-checada (custo baixo, é só 1 SELECT, sem chamada de API).
    cur.execute("SELECT 1 FROM itens_pncp WHERE processo_pncp = %s LIMIT 1", (numero_controle,))
    return cur.fetchone() is not None


def processar_contratacao(con: psycopg2.extensions.connection, cur: psycopg2.extensions.cursor,
                           uf: str, contratacao: dict) -> tuple[int, int]:
    """Retorna (n_itens_processados, n_linhas_gravadas)."""
    if ja_processada(cur, contratacao["numeroControlePNCP"]):
        return 0, 0

    cnpj = contratacao["orgaoEntidade"]["cnpj"]
    ano = contratacao["anoCompra"]
    seq = contratacao["sequencialCompra"]

    itens = chamar_api(f"{PNCP_BASE}/{cnpj}/compras/{ano}/{seq}/itens") or []
    time.sleep(PAUSA_ENTRE_CHAMADAS)

    n_gravados = 0
    for item in itens:
        if item.get("situacaoCompraItemNome") != "Homologado":
            continue
        if not item.get("temResultado"):
            continue

        numero_item = item.get("numeroItem")
        resultados = chamar_api(
            f"{PNCP_BASE}/{cnpj}/compras/{ano}/{seq}/itens/{numero_item}/resultados"
        ) or []
        time.sleep(PAUSA_ENTRE_CHAMADAS)

        for resultado in resultados:
            gravar_item_resultado(cur, uf, contratacao, item, resultado)
            n_gravados += 1

    con.commit()
    return len(itens), n_gravados


# ── Orquestração ──────────────────────────────────────────────────────────

def rodar_piloto(uf: str, limite: int | None, data_inicial: str, data_final: str) -> None:
    con, cur = conectar_db()

    cur.execute("SELECT COUNT(*) FROM itens_pncp WHERE uf = %s", (uf,))
    n_existente = cur.fetchone()[0]
    if n_existente:
        log.info(
            f"itens_pncp já tem {n_existente} linha(s) pra UF={uf} — contratações já "
            f"processadas são puladas (resumível, sem duplicar). Truncar antes se a "
            f"intenção é refazer do zero mesmo assim."
        )

    inicio = time.time()
    contratacoes = buscar_contratacoes(uf, data_inicial, data_final)
    if limite:
        contratacoes = contratacoes[:limite]
        log.info(f"--limite {limite}: processando só as {len(contratacoes)} primeiras contratações.")

    n_erros = 0
    n_itens_total = 0
    n_gravados_total = 0
    for i, contratacao in enumerate(contratacoes, start=1):
        try:
            n_itens, n_gravados = processar_contratacao(con, cur, uf, contratacao)
            n_itens_total += n_itens
            n_gravados_total += n_gravados
        except RuntimeError as e:
            n_erros += 1
            log.error(f"{contratacao.get('numeroControlePNCP')}: {e} — pulando, sigo pras próximas.")
            con.rollback()

        if i % 50 == 0:
            log.info(f"Progresso: {i}/{len(contratacoes)} contratações, {n_gravados_total} linhas gravadas, {n_erros} erros.")

    duracao = time.time() - inicio
    log.info(
        f"Piloto concluído em {duracao/60:.1f}min. UF={uf}. {len(contratacoes)} contratações, "
        f"{n_itens_total} itens inspecionados, {n_gravados_total} linhas gravadas em itens_pncp, "
        f"{n_erros} contratações com erro (puladas)."
    )
    cur.close()
    con.close()


def mostrar_status() -> None:
    con, cur = conectar_db()
    cur.execute("SELECT COUNT(*) FROM itens_pncp")
    print(f"Linhas em itens_pncp: {cur.fetchone()[0]}")
    cur.execute("SELECT uf, tipo, COUNT(*) FROM itens_pncp GROUP BY uf, tipo ORDER BY uf, tipo")
    for uf, tipo, n in cur.fetchall():
        print(f"  {uf} {tipo}: {n}")
    cur.close()
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="só mostra contagem já gravada, não roda")
    parser.add_argument("--uf", type=str, default="RJ", help="UF a extrair (default RJ)")
    parser.add_argument("--limite", type=int, default=None, help="processa só as N primeiras contratações (teste)")
    parser.add_argument("--data-inicial", type=str, default=DATA_INICIAL_PADRAO, help="AAAAMMDD (default jan/2026)")
    parser.add_argument("--data-final", type=str, default=DATA_FINAL_PADRAO, help="AAAAMMDD (default jan/2026)")
    args = parser.parse_args()

    if args.status:
        mostrar_status()
    else:
        rodar_piloto(args.uf.upper(), args.limite, args.data_inicial, args.data_final)
