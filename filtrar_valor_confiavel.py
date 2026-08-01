"""Marca valor_homologado como confiavel ou nao, comparando cada item contra
outros itens com o MESMO desc_norm (mesmo texto exato de descricao). Um saco
de cebola custando R$11,5bi ao lado de milhares de outros custando R$300-2000
e' outlier obvio dentro do proprio grupo -- o flag valor_suspeito existente
nao pega nada disso (confirmado: 0/14809 itens acima de R$1mi flagados).
"""
import duckdb

DB_PATH = "market_scan_local.duckdb"


def main():
    con = duckdb.connect(DB_PATH)
    con.execute("""
        CREATE OR REPLACE TABLE valor_confiavel AS
        WITH base AS (
            SELECT id, lower(trim(descricao_item)) AS desc_norm, valor_homologado,
                   log(nullif(valor_homologado, 0)) AS log_valor
            FROM itens_pncp
            WHERE valor_homologado > 0
        ),
        stats AS (
            SELECT desc_norm, avg(log_valor) AS media, stddev(log_valor) AS desvio,
                   count(*) AS n
            FROM base
            GROUP BY desc_norm
            HAVING count(*) >= 5
        )
        SELECT b.id,
               CASE
                   WHEN s.desvio IS NULL OR s.desvio = 0 THEN true
                   WHEN abs((b.log_valor - s.media) / s.desvio) > 4 THEN false
                   ELSE true
               END AS valor_confiavel
        FROM base b
        LEFT JOIN stats s ON s.desc_norm = b.desc_norm
    """)
    total = con.execute("SELECT count(*) FROM valor_confiavel").fetchone()[0]
    suspeitos = con.execute(
        "SELECT count(*), sum(i.valor_homologado) FROM valor_confiavel v "
        "JOIN itens_pncp i ON i.id = v.id WHERE NOT v.valor_confiavel"
    ).fetchone()
    print(f"total avaliado: {total}")
    print(f"marcados NAO confiavel (outlier dentro do proprio desc_norm): "
          f"{suspeitos[0]} itens, R$ {suspeitos[1]:,.0f} excluido do valor agregado")
    con.close()


if __name__ == "__main__":
    main()
