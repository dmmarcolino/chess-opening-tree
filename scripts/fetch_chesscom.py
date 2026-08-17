"""
Baixa todas as partidas de um usuario do Chess.com em formato PGN,
usando a API publica (arquivos mensais).

Doc: https://www.chess.com/news/view/published-data-api

Uso:
    python fetch_chesscom.py <username> [--output data/raw/chesscom.pgn] [--since AAAA-MM]

A Chess.com exige um User-Agent identificavel (com contato) para evitar
bloqueios 403. Defina CHESSCOM_CONTACT_EMAIL no ambiente, ou passe --email.
"""
import argparse
import os
import sys

import requests


def fetch_chesscom_games(username, output_path, contact_email, since=None):
    headers = {
        "User-Agent": f"chess-opening-tree/1.0 (contato: {contact_email})"
    }
    username = username.lower()

    archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    print(f"Buscando lista de arquivos mensais de {username} no Chess.com...")
    resp = requests.get(archives_url, headers=headers, timeout=30)
    resp.raise_for_status()
    archive_urls = resp.json().get("archives", [])

    if since:
        # archive_urls terminam em .../games/AAAA/MM
        archive_urls = [
            u for u in archive_urls if "/".join(u.split("/")[-2:]) >= since.replace("-", "/")
        ]

    print(f"{len(archive_urls)} arquivo(s) mensal(is) a processar.")

    all_pgns = []
    for i, url in enumerate(archive_urls, 1):
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        games = r.json().get("games", [])
        for g in games:
            if "pgn" in g:
                all_pgns.append(g["pgn"])
        print(f"  [{i}/{len(archive_urls)}] {url.split('/')[-2]}/{url.split('/')[-1]}: "
              f"{len(games)} partida(s)")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_pgns))

    print(f"Salvo em {output_path} ({len(all_pgns)} partidas no total)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa partidas do Chess.com em PGN")
    parser.add_argument("username", help="Nome de usuario no Chess.com")
    parser.add_argument("--output", default="data/raw/chesscom.pgn")
    parser.add_argument(
        "--email",
        default=os.environ.get("CHESSCOM_CONTACT_EMAIL"),
        help="Seu e-mail de contato, exigido pela Chess.com no User-Agent",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Buscar apenas a partir deste mes (AAAA-MM). Use para atualizacoes incrementais.",
    )
    args = parser.parse_args()

    if not args.email:
        print(
            "Aviso: nenhum e-mail de contato definido (--email ou CHESSCOM_CONTACT_EMAIL).\n"
            "A Chess.com pode bloquear a requisicao com erro 403 sem isso.",
            file=sys.stderr,
        )
        args.email = "nao-informado@exemplo.com"

    try:
        fetch_chesscom_games(args.username, args.output, args.email, since=args.since)
    except requests.HTTPError as e:
        print(f"Erro ao buscar partidas do Chess.com: {e}", file=sys.stderr)
        sys.exit(1)
