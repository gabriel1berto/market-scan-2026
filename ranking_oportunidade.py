"""Ranking de oportunidade: pra cada item (categoria + desc_norm), mede
concentracao de mercado como % de orgaos onde 1 fornecedor ganhou 100% das
compras daquele item (>=2 compras no orgao) -- metrica corrigida contra o
erro de fracao ingenua fornecedor/item (mascara monopolio local), ja
documentada nas sessoes anteriores do projeto. So usa linha com
valor_confiavel=true (exclui outlier de dado corrompido tipo cebola-bilhao).
Benchmark: pneu = 30,8% de monopolio local (mercado onde a empresa ja
compete e ganha).
"""
import duckdb

DB_PATH = "market_scan_local.duckdb"
CATEGORIA_TABLE = "categoria_regex_v15"
BENCHMARK_PNEU = 30.8
MIN_ORGAOS = 10


def main():
    con = duckdb.connect(DB_PATH)

    con.execute(f"""
        CREATE OR REPLACE TABLE ranking_nacional AS
        WITH base AS (
            SELECT c.categoria, lower(trim(i.descricao_item)) AS item,
                   i.orgao_cnpj, i.cnpj_vencedor, i.valor_homologado
            FROM itens_pncp i
            JOIN {CATEGORIA_TABLE} c ON c.id_item = i.id
            JOIN valor_confiavel v ON v.id = i.id
            WHERE v.valor_confiavel
              AND c.categoria NOT LIKE 'Outros%' AND c.categoria != 'Servico'
              AND i.orgao_cnpj IS NOT NULL AND i.cnpj_vencedor IS NOT NULL
              AND i.valor_homologado > 0
        ),
        orgao_item AS (
            SELECT categoria, item, orgao_cnpj,
                   count(*) AS n_compras,
                   count(DISTINCT cnpj_vencedor) AS n_fornecedores
            FROM base
            GROUP BY categoria, item, orgao_cnpj
            HAVING count(*) >= 2
        ),
        concentracao AS (
            SELECT categoria, item,
                   count(*) AS orgaos_qualificados,
                   sum(CASE WHEN n_fornecedores = 1 THEN 1 ELSE 0 END) AS orgaos_monopolio,
                   round(100.0 * sum(CASE WHEN n_fornecedores = 1 THEN 1 ELSE 0 END) / count(*), 1) AS pct_monopolio
            FROM orgao_item
            GROUP BY categoria, item
            HAVING count(*) >= {MIN_ORGAOS}
        ),
        valor_item AS (
            SELECT categoria, item,
                   round(sum(valor_homologado)::numeric, 0) AS valor_total,
                   count(*) AS n_compras_total,
                   count(DISTINCT orgao_cnpj) AS orgaos_total,
                   count(DISTINCT cnpj_vencedor) AS fornecedores_total
            FROM base GROUP BY categoria, item
        )
        SELECT c.categoria, c.item, v.valor_total, v.n_compras_total,
               v.orgaos_total, v.fornecedores_total,
               c.orgaos_qualificados, c.orgaos_monopolio, c.pct_monopolio
        FROM concentracao c
        JOIN valor_item v ON v.categoria = c.categoria AND v.item = c.item
        ORDER BY v.valor_total DESC
    """)

    total = con.execute("SELECT count(*) FROM ranking_nacional").fetchone()[0]
    abaixo_benchmark = con.execute(
        f"SELECT count(*) FROM ranking_nacional WHERE pct_monopolio < {BENCHMARK_PNEU}"
    ).fetchone()[0]
    print(f"itens candidatos (>= {MIN_ORGAOS} orgaos qualificados): {total}")
    print(f"abaixo do benchmark pneu ({BENCHMARK_PNEU}%): {abaixo_benchmark}")

    top = con.execute(f"""
        SELECT categoria, item, valor_total, orgaos_qualificados, pct_monopolio
        FROM ranking_nacional
        WHERE pct_monopolio < {BENCHMARK_PNEU}
        ORDER BY valor_total DESC
        LIMIT 50
    """).fetchdf()
    with open('_ranking_top50.txt', 'w', encoding='utf-8') as f:
        f.write(top.to_string())
    print("top 50 escrito em _ranking_top50.txt")

    # por UF
    con.execute(f"""
        CREATE OR REPLACE TABLE ranking_por_uf AS
        WITH base AS (
            SELECT c.categoria, lower(trim(i.descricao_item)) AS item, i.uf,
                   i.orgao_cnpj, i.cnpj_vencedor, i.valor_homologado
            FROM itens_pncp i
            JOIN {CATEGORIA_TABLE} c ON c.id_item = i.id
            JOIN valor_confiavel v ON v.id = i.id
            WHERE v.valor_confiavel
              AND c.categoria NOT LIKE 'Outros%' AND c.categoria != 'Servico'
              AND i.orgao_cnpj IS NOT NULL AND i.cnpj_vencedor IS NOT NULL
              AND i.valor_homologado > 0 AND i.uf IS NOT NULL
        ),
        orgao_item AS (
            SELECT uf, categoria, item, orgao_cnpj,
                   count(*) AS n_compras, count(DISTINCT cnpj_vencedor) AS n_fornecedores
            FROM base GROUP BY uf, categoria, item, orgao_cnpj HAVING count(*) >= 2
        ),
        concentracao AS (
            SELECT uf, categoria, item,
                   count(*) AS orgaos_qualificados,
                   round(100.0 * sum(CASE WHEN n_fornecedores = 1 THEN 1 ELSE 0 END) / count(*), 1) AS pct_monopolio
            FROM orgao_item GROUP BY uf, categoria, item HAVING count(*) >= 5
        ),
        valor_item AS (
            SELECT uf, categoria, item, round(sum(valor_homologado)::numeric, 0) AS valor_total
            FROM base GROUP BY uf, categoria, item
        )
        SELECT c.uf, c.categoria, c.item, v.valor_total, c.orgaos_qualificados, c.pct_monopolio
        FROM concentracao c JOIN valor_item v ON v.uf=c.uf AND v.categoria=c.categoria AND v.item=c.item
        ORDER BY v.valor_total DESC
    """)
    top_uf = con.execute(f"""
        SELECT uf, categoria, item, valor_total, orgaos_qualificados, pct_monopolio
        FROM ranking_por_uf WHERE pct_monopolio < {BENCHMARK_PNEU}
        ORDER BY valor_total DESC LIMIT 50
    """).fetchdf()
    with open('_ranking_top50_uf.txt', 'w', encoding='utf-8') as f:
        f.write(top_uf.to_string())
    print("top 50 por UF escrito em _ranking_top50_uf.txt")
    con.close()


if __name__ == "__main__":
    main()
