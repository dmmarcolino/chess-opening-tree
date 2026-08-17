"""
Baixa todas as partidas de um usuario do Lichess em formato PGN,
usando a API publica de exportacao de jogos.

Doc: https://lichess.org/api#operation/apiGamesUser

Uso:
    python fetch_lichess.py <username> [--output data/raw/lichess.pgn] [--since AAAA-MM-DD]

Variavel de ambiente opcional:
    LICHESS_TOKEN  -> token pessoal (nao obrigatorio para dados publicos,
                       mas evita rate limit mais agressivo)
"""
import argparse
import os
import sys
from datetime import datetime, timezone

import requests

LICHESS_API_URL = "https://lichess.org/api/games/user/{username}"


def date_to_ms(date_str):
    """Converte 'AAAA-MM-DD' para timestamp em milissegundos (UTC)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_lichess_games(username, output_path, token=None, since=None):
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
    print(f"Buscando partidas de {username} no Lichess...")

    resp = requests.get(url, headers=headers, params=params, stream=True, timeout=120)
    resp.raise_for_status()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    total_bytes = 0
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            total_bytes += len(chunk)

    print(f"Salvo em {output_path} ({total_bytes / 1024:.1f} KB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa partidas do Lichess em PGN")
    parser.add_argument("username", help="Nome de usuario no Lichess")
    parser.add_argument("--output", default="data/raw/lichess.pgn")
    parser.add_argument("--token", default=os.environ.get("LICHESS_TOKEN"))
    parser.add_argument(
        "--since",
        default=None,
        help="Buscar apenas partidas a partir desta data (AAAA-MM-DD). "
        "Use para atualizacoes incrementais.",
    )
    args = parser.parse_args()

    try:
        fetch_lichess_games(args.username, args.output, token=args.token, since=args.since)
    except requests.HTTPError as e:
        print(f"Erro ao buscar partidas do Lichess: {e}", file=sys.stderr)
        sys.exit(1)
