"""
Baixa partidas de um usuario do Lichess em formato PGN, usando a API
publica de exportacao de jogos.

Doc: https://lichess.org/api#operation/apiGamesUser

Uso:
    python fetch_lichess.py <username> [--output data/raw/lichess.pgn] [--since AAAA-MM-DD]

Quando --since e usado E ja existe um arquivo no caminho de --output, o
resultado NAO sobrescreve esse arquivo -- as partidas novas sao
mescladas com as que ja estavam la (sem duplicar, usando a URL da
partida como identificador -- ver scripts/pgn_merge.py). Sem --since, o
comportamento e o de sempre: baixa tudo e sobrescreve.

Variavel de ambiente opcional:
    LICHESS_TOKEN  -> token pessoal (nao obrigatorio para dados publicos,
                       mas evita rate limit mais agressivo)
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import requests

from pgn_merge import merge_and_dedupe

LICHESS_API_URL = "https://lichess.org/api/games/user/{username}"
PROGRESS_EVERY_BYTES = 1_000_000  # imprime uma linha de progresso a cada ~1 MB baixado


def date_to_ms(date_str):
    """Converte 'AAAA-MM-DD' para timestamp em milissegundos (UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_lichess_games(username, download_path, token=None, since=None):
    headers = {"Accept": "application/x-chess-pgn"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {
        "opening": "true",  # inclui tag [ECO] e [Opening] no PGN
        "evals": "false",
        "clocks": "false",
        "moves": "true",
        "tags": "true",
    }
    if since:
        params["since"] = date_to_ms(since)

    url = LICHESS_API_URL.format(username=username)
    print(f"Buscando partidas de {username} no Lichess" + (f" desde {since}" if since else "") + "...")
    sys.stdout.flush()

    resp = requests.get(url, headers=headers, params=params, stream=True, timeout=300)
    resp.raise_for_status()

    os.makedirs(os.path.dirname(download_path) or ".", exist_ok=True)
    total_bytes = 0
    next_report_at = PROGRESS_EVERY_BYTES
    t0 = time.time()
    with open(download_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            total_bytes += len(chunk)
            if total_bytes >= next_report_at:
                elapsed = time.time() - t0
                print(f"  ... {total_bytes / 1_000_000:.1f} MB baixados ate agora ({elapsed:.0f}s)")
                sys.stdout.flush()
                next_report_at += PROGRESS_EVERY_BYTES

    elapsed = time.time() - t0
    print(f"Download concluido: {total_bytes / 1024:.1f} KB em {elapsed:.0f}s")
    return total_bytes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa partidas do Lichess em PGN")
    parser.add_argument("username", help="Nome de usuario no Lichess")
    parser.add_argument("--output", default="data/raw/lichess.pgn")
    parser.add_argument("--token", default=os.environ.get("LICHESS_TOKEN"))
    parser.add_argument(
        "--since",
        default=None,
        help="Buscar apenas partidas a partir desta data (AAAA-MM-DD). "
        "Se ja existir um arquivo em --output, o resultado e mesclado com "
        "ele (sem duplicar) em vez de sobrescrever.",
    )
    args = parser.parse_args()

    incremental = bool(args.since) and os.path.exists(args.output)
    download_target = args.output + ".incoming" if incremental else args.output

    try:
        fetch_lichess_games(args.username, download_target, token=args.token, since=args.since)
    except requests.HTTPError as e:
        print(f"Erro ao buscar partidas do Lichess: {e}", file=sys.stderr)
        sys.exit(1)

    if incremental:
        n_old, n_new, n_total = merge_and_dedupe(args.output, download_target, args.output)
        os.remove(download_target)
        print(f"Mesclado com o historico existente: {n_old} que ja tinha + {n_new} buscadas agora "
              f"= {n_total} partidas unicas em {args.output} (duplicatas descartadas automaticamente)")
