"""Exporta itens_pncp/gabarito_nicho/classificacao_categoria do Supabase (só leitura)
pra um arquivo DuckDB local, extraindo orgao_cnpj/modalidade do raw_json no servidor
(sem trafegar o blob inteiro pela rede)."""
import os
import time
import duckdb
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
DB_PATH = os.path.join(os.path.dirname(__file__), "market_scan_local.duckdb")

BATCH = 20000


def main():
    t0 = time.time()
    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS itens_pncp")
    con.execute("""
        CREATE TABLE itens_pncp (
            id INTEGER PRIMARY KEY,
            processo_pncp TEXT,
            uf TEXT,
            tipo TEXT,
            codigo_catalogo TEXT,
            descricao_item TEXT,
            valor_homologado DOUBLE,
            valor_estimado DOUBLE,
            cnpj_vencedor TEXT,
            data_homologacao DATE,
            criado_em TIMESTAMP,
            nicho_llm TEXT,
            valor_suspeito BOOLEAN,
            item_valor_total_estimado DOUBLE,
            orgao_cnpj TEXT,
            modalidade TEXT
        )
    """)

    pg = psycopg2.connect(DATABASE_URL)
    pg.set_session(readonly=True, autocommit=False)
    cur = pg.cursor(name="export_itens_pncp", cursor_factory=psycopg2.extras.DictCursor)
    cur.itersize = BATCH
    cur.execute("""
        SELECT id, processo_pncp, uf, tipo, codigo_catalogo, descricao_item,
               valor_homologado, valor_estimado, cnpj_vencedor, data_homologacao,
               criado_em, nicho_llm, valor_suspeito, item_valor_total_estimado,
               raw_json->'contratacao'->'orgaoEntidade'->>'cnpj' AS orgao_cnpj,
               raw_json->'contratacao'->>'modalidadeNome' AS modalidade
        FROM itens_pncp
        ORDER BY id
    """)

    total = 0
    insert_sql = "INSERT INTO itens_pncp VALUES (" + ",".join(["?"] * 16) + ")"
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        con.executemany(insert_sql, [tuple(r) for r in rows])
        total += len(rows)
        print(f"itens_pncp: {total} linhas ({time.time()-t0:.0f}s)", flush=True)
    cur.close()

    for tabela in ("gabarito_nicho", "classificacao_categoria"):
        cur2 = pg.cursor()
        cur2.execute(f"SELECT * FROM {tabela}")
        colnames = [d[0] for d in cur2.description]
        rows = cur2.fetchall()
        cur2.close()
        con.execute(f"DROP TABLE IF EXISTS {tabela}")
        cols_ddl = ", ".join(f'"{c}" TEXT' for c in colnames)
        con.execute(f"CREATE TABLE {tabela} ({cols_ddl})")
        placeholders = ",".join(["?"] * len(colnames))
        con.executemany(f"INSERT INTO {tabela} VALUES ({placeholders})",
                         [tuple(str(v) if v is not None else None for v in r) for r in rows])
        print(f"{tabela}: {len(rows)} linhas", flush=True)

    pg.rollback()
    pg.close()
    con.close()
    print(f"OK — total {time.time()-t0:.0f}s, arquivo: {DB_PATH}")


if __name__ == "__main__":
    main()
