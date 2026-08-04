"""Tabela de cobertura UF x mes da extracao sem-oferta. Rodar sempre que
o usuario pedir status de download do market-scan-2026."""
import os

MESES = {
    "jan": ("20260101", "20260131"), "fev": ("20260201", "20260228"),
    "mar": ("20260301", "20260331"), "abr": ("20260401", "20260430"),
    "mai": ("20260501", "20260531"), "jun": ("20260601", "20260630"),
    "jul": ("20260701", "20260731"),
}
UFS = "AC AL AM AP BA CE DF ES GO MA MS MT MG PA PB PR PE PI RN RJ RO RR RS SC SP SE TO".split()


def status(uf, mes):
    ini, fim = MESES[mes]
    if mes == "jun" and uf == "RJ":
        fname = "extract_pncp_sem_oferta.log"
    elif mes == "jun":
        fname = f"extract_pncp_sem_oferta_{uf}.log"
    else:
        fname = f"extract_pncp_sem_oferta_{uf}_{ini}_{fim}.log"
    if not os.path.exists(fname):
        return "."
    with open(fname, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return "X" if "Concluido em" in content else "~"


if __name__ == "__main__":
    print("UF  | " + "  ".join(MESES))
    for uf in UFS:
        row = "   ".join(status(uf, m) for m in MESES)
        print(f"{uf:<3} |  {row}")
    print("\nX = concluido | ~ = em andamento/incompleto | . = nao iniciado")
