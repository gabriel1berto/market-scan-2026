#!/usr/bin/env python3
"""
extract_pncp_sem_oferta.py -- piloto: extrai itens de contratacao PNCP cujo
resultado NAO foi "Homologado" (ex: Deserto = ninguem deu lance, Fracassado =
teve lance mas todos desclassificados) -- sinal de demanda sem oferta
atendida, o oposto do que extract_pncp.py grava.

Reaproveita a mesma Fase 1 (busca de contratacoes) do extract_pncp.py, mas
pula a chamada de /resultados (nao existe resultado pra item sem vencedor) --
mais barato por contratacao que o script original.

Escreve LOCAL (DuckDB), nao no Supabase (ainda em read-only por cota) --
zero risco de escrita externa.

Uso:
    python extract_pncp_sem_oferta.py --uf RJ --data-inicial 20260601 --data-final 20260630
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import duckdb
import requests

MODALIDADES = list(range(1, 15))
TAM_PAGINA = 50
PAUSA_ENTRE_PAGINAS = 2.5
PAUSA_ENTRE_CHAMADAS = 1.0
PAUSA_APOS_ERRO_BASE = 15.0
MAX_TENTATIVAS = 6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

CONSULTA_BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_BASE = "https://pncp.gov.br/api/pncp/v1/orgaos"
DB_PATH = Path(__file__).parent / "market_scan_sem_oferta.duckdb"
LOG_PATH = Path(__file__).parent / "extract_pncp_sem_oferta.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("extract_sem_oferta")


def chamar_api(url: str, params: dict | None = None):
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


def buscar_contratacoes(uf: str, data_inicial: str, data_final: str) -> list[dict]:
    encontradas = []
    for modalidade in MODALIDADES:
        pagina = 1
        while True:
            params = {
                "dataInicial": data_inicial, "dataFinal": data_final,
                "codigoModalidadeContratacao": modalidade, "uf": uf,
                "pagina": pagina, "tamanhoPagina": TAM_PAGINA,
            }
            try:
                resp = chamar_api(f"{CONSULTA_BASE}/contratacoes/publicacao", params)
            except RuntimeError as e:
                log.error(f"modalidade={modalidade} pag={pagina}: {e} -- abortando modalidade.")
                break
            if resp is None:
                break
            dados = resp.get("data", [])
            if not dados:
                break
            encontradas.extend(dados)
            total_paginas = resp.get("totalPaginas", pagina)
            log.info(f"modalidade={modalidade} pag={pagina}/{total_paginas}: +{len(dados)}")
            if pagina >= total_paginas:
                break
            pagina += 1
            time.sleep(PAUSA_ENTRE_PAGINAS)
    log.info(f"Fase 1: {len(encontradas)} contratacoes em {uf}, {data_inicial}-{data_final}.")
    return encontradas


def conectar_db():
    con = duckdb.connect(str(DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS itens_sem_oferta (
            processo_pncp TEXT, uf TEXT, tipo TEXT, descricao_item TEXT,
            valor_estimado DOUBLE, situacao TEXT, modalidade INTEGER,
            orgao_cnpj TEXT, criado_em TIMESTAMP DEFAULT current_timestamp
        )
    """)
    return con


def ja_processada(con, numero_controle: str) -> bool:
    r = con.execute(
        "SELECT 1 FROM itens_sem_oferta WHERE processo_pncp = ? LIMIT 1", [numero_controle]
    ).fetchone()
    return r is not None


def processar_contratacao(con, uf: str, contratacao: dict, modalidade: int) -> tuple[int, int]:
    if ja_processada(con, contratacao["numeroControlePNCP"]):
        return 0, 0
    cnpj = contratacao["orgaoEntidade"]["cnpj"]
    ano = contratacao["anoCompra"]
    seq = contratacao["sequencialCompra"]

    itens = chamar_api(f"{PNCP_BASE}/{cnpj}/compras/{ano}/{seq}/itens") or []
    time.sleep(PAUSA_ENTRE_CHAMADAS)

    n_gravados = 0
    for item in itens:
        situacao = item.get("situacaoCompraItemNome")
        if situacao in ("Homologado", None):
            continue
        tipo = "produto" if item.get("materialOuServico") == "M" else "servico"
        con.execute(
            "INSERT INTO itens_sem_oferta (processo_pncp, uf, tipo, descricao_item, "
            "valor_estimado, situacao, modalidade, orgao_cnpj) VALUES (?,?,?,?,?,?,?,?)",
            [contratacao["numeroControlePNCP"], uf, tipo, item.get("descricao"),
             item.get("valorTotal"), situacao, modalidade, cnpj],
        )
        n_gravados += 1

    # marca a contratacao como processada mesmo se 0 itens sem-oferta (evita re-scan)
    if n_gravados == 0:
        con.execute(
            "INSERT INTO itens_sem_oferta (processo_pncp, uf, tipo, descricao_item, "
            "valor_estimado, situacao, modalidade, orgao_cnpj) VALUES (?,?,?,?,?,?,?,?)",
            [contratacao["numeroControlePNCP"], uf, None, None, None, "_sem_item_sem_oferta_", modalidade, cnpj],
        )
    return len(itens), n_gravados


def rodar(uf: str, data_inicial: str, data_final: str, limite: int | None) -> None:
    con = conectar_db()
    inicio = time.time()
    contratacoes = buscar_contratacoes(uf, data_inicial, data_final)
    if limite:
        contratacoes = contratacoes[:limite]

    n_erros = 0
    n_itens_total = 0
    n_gravados_total = 0
    for i, contratacao in enumerate(contratacoes, start=1):
        try:
            n_itens, n_gravados = processar_contratacao(con, uf, contratacao, contratacao.get("modalidadeId", 0))
            n_itens_total += n_itens
            n_gravados_total += n_gravados
        except RuntimeError as e:
            n_erros += 1
            log.error(f"{contratacao.get('numeroControlePNCP')}: {e} -- pulando.")
        if i % 50 == 0:
            log.info(f"Progresso: {i}/{len(contratacoes)} contratacoes, {n_gravados_total} itens sem-oferta, {n_erros} erros.")

    duracao = time.time() - inicio
    log.info(
        f"Concluido em {duracao/60:.1f}min. UF={uf}. {len(contratacoes)} contratacoes, "
        f"{n_itens_total} itens inspecionados, {n_gravados_total} itens sem-oferta gravados, {n_erros} erros."
    )
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uf", type=str, default="RJ")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--data-inicial", type=str, required=True)
    parser.add_argument("--data-final", type=str, required=True)
    args = parser.parse_args()
    rodar(args.uf.upper(), args.data_inicial, args.data_final, args.limite)
