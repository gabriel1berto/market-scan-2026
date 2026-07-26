#!/usr/bin/env python3
"""
rodar_resto_brasil.py — Roda extract_pncp.py (jan/2026) pras 26 UFs restantes
(tudo exceto RJ, já coberta no piloto original), respeitando um teto de horário
combinado com o usuário (25/jul/2026: "se sobrar tempo, rode pro resto do
Brasil", dentro da janela de 4h já autorizada pra essa sessão).

Para antes de iniciar uma UF nova se o teto já foi ultrapassado — não corta UF
no meio (cada contratação já commita individualmente em extract_pncp.py, mas
simplifica o corte por UF inteira). Roda uma UF por vez (sequencial, mesmo
rate limit do script principal) — não paraleliza pra não estourar o WAF do PNCP.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract_pncp import rodar_piloto, log  # noqa: E402

DEADLINE = datetime(2026, 7, 25, 18, 25, 0)  # 4h a partir do início do piloto RJ (14:25)

TODAS_UFS_MENOS_RJ = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]


def main() -> None:
    log.info(f"Iniciando resto do Brasil (26 UFs, jan/2026) — teto {DEADLINE.isoformat()}")
    for uf in TODAS_UFS_MENOS_RJ:
        if datetime.now() >= DEADLINE:
            log.warning(f"Teto de horário atingido antes de {uf} — parando aqui. UFs não rodadas: "
                        f"{TODAS_UFS_MENOS_RJ[TODAS_UFS_MENOS_RJ.index(uf):]}")
            break
        log.info(f"=== Iniciando UF={uf} ===")
        rodar_piloto(uf, None)
    else:
        log.info("Todas as 26 UFs restantes processadas dentro do teto.")


if __name__ == "__main__":
    main()
