#!/usr/bin/env python3
"""
clusterizar_nicho.py — Agrupa as descrições de item de itens_pncp por
similaridade de texto (TF-IDF + KMeans), sem chamar nenhuma API paga (zero
custo — decisão 25/jul/2026, ver README "Achados da verificação de API" e a
troca de decisão sobre o classificador de nicho).

Não nomeia os clusters sozinho — grava só o número do cluster em
`nicho_llm` e imprime uma amostra de cada cluster (termos top TF-IDF +
3 descrições reais) pra quem for nomear (humano ou Claude na sessão,
lendo a saída) decidir o rótulo. `atualizar_nicho.py` aplica os rótulos
finais depois de decididos.

Uso:
    python clusterizar_nicho.py --n-clusters 30
"""

import argparse
import json
import os
from collections import defaultdict

import numpy as np
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv()

# Achado 25/jul/2026 (1ª rodada, n_clusters=30): boilerplate administrativo
# ("contratacao", "empresa especializada", "descricao", "prestacao servicos"
# etc — presente em editais de qualquer nicho) dominava a distância TF-IDF e
# jogou 88% dos itens (5.151/5.856) num cluster genérico só. Lista ampliada
# pra filtrar esse ruído e deixar o vocabulário específico do produto/serviço
# pesar mais na clusterização.
STOPWORDS_PT = [
    "de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "para",
    "com", "por", "no", "na", "nos", "nas", "um", "uma", "uns", "umas",
    "que", "ao", "aos", "à", "às", "sob", "sobre", "ou", "se",
    "aquisição", "aquisicao", "contratação", "contratacao", "contrato",
    "prestação", "prestacao", "empresa", "especializada", "especializado",
    "descrição", "descricao", "servico", "serviço", "serviços", "servicos",
    "material", "materiais", "tipo", "aplicação", "aplicacao", "conforme",
    "referente", "diversos", "diversas", "outros", "outras", "objeto",
    "fornecimento", "execução", "execucao", "unidade", "und", "item",
    "conjunto", "origem", "pessoa", "juridica", "jurídica", "física", "fisica",
]


def conectar_db():
    con = psycopg2.connect(os.environ["DATABASE_URL"])
    return con, con.cursor()


def clusterizar(n_clusters: int) -> None:
    con, cur = conectar_db()
    cur.execute("SELECT id, descricao_item FROM itens_pncp WHERE descricao_item IS NOT NULL")
    linhas = cur.fetchall()
    ids = [r[0] for r in linhas]
    textos = [r[1] for r in linhas]
    print(f"{len(textos)} linhas com descrição, {len(set(textos))} descrições distintas.")

    vectorizer = TfidfVectorizer(max_features=5000, stop_words=STOPWORDS_PT, ngram_range=(1, 2),
                                  min_df=2, sublinear_tf=True)
    X = vectorizer.fit_transform(textos)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    # grava número do cluster (provisório) em nicho_llm — nome real vem depois.
    # Bulk update (1 round-trip) em vez de 1 UPDATE por linha — a 1ª rodada
    # (30 clusters) levou ~15-20min só nisso pra 5.856 linhas.
    valores = [(int(id_), f"cluster_{int(cluster)}") for id_, cluster in zip(ids, labels)]
    execute_values(cur, """
        UPDATE itens_pncp AS t SET nicho_llm = v.nicho
        FROM (VALUES %s) AS v(id, nicho)
        WHERE t.id = v.id
    """, valores)
    con.commit()

    # amostra + top termos por cluster, pra nomear
    termos = np.array(vectorizer.get_feature_names_out())
    amostras = defaultdict(list)
    for texto, cluster in zip(textos, labels):
        if len(amostras[cluster]) < 5:
            amostras[cluster].append(texto[:150])

    resumo = []
    for c in range(n_clusters):
        centro = km.cluster_centers_[c]
        top_idx = centro.argsort()[-10:][::-1]
        n_itens = int((labels == c).sum())
        resumo.append({
            "cluster": c,
            "n_itens": n_itens,
            "top_termos": termos[top_idx].tolist(),
            "amostras": amostras[c],
        })

    resumo.sort(key=lambda r: -r["n_itens"])
    with open("clusters_resumo.json", "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)

    print(f"Clusterização concluída: {n_clusters} clusters, resumo em clusters_resumo.json")
    cur.close()
    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-clusters", type=int, default=30)
    args = parser.parse_args()
    clusterizar(args.n_clusters)
