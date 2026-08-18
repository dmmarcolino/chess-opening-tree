"""
Baixa partidas de um usuario do Chess.com em formato PGN, usando a API
publica (arquivos mensais).

Doc: https://www.chess.com/news/view/published-data-api

Uso:
    python fetch_chesscom.py <username> [--output data/raw/chesscom.pgn] [--since AAAA-MM]

Quando --since e usado E ja existe um arquivo no caminho de --output, o
resultado NAO sobrescreve esse arquivo -- as partidas baixadas agora sao
mescladas com as que ja estavam la (sem duplicar, usando a URL da
partida como identificador -- ver scripts/pgn_merge.py). Isso importa
especialmente aqui porque a granularidade da Chess.com e por MES: o
arquivo do mes atual e sempre baixado por inteiro de novo (pra pegar
partidas jogadas depois da ultima busca), entao sem a fusao com
deduplicacao ele apareceria duplicado.

A Chess.com exige um User-Agent identificavel (com contato) para evitar
bloqueios 403. Defina CHESSCOM_CONTACT_EMAIL no ambiente, ou passe --email.
"""
import argparse
import os
import sys

import requests

from pgn_merge import merge_and_dedupe


def fetch_chesscom_games(username, download_path, contact_email, since=None):
    headers = {
        "User-Agent": f"chess-opening-tree/1.0 (contato: {contact_email})"
    }
    username = username.lower()

    archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    print(f"Buscando lista de arquivos mensais de {username} no Chess.com...")
    sys.stdout.flush()
    resp = requests.get(archives_url, headers=headers, timeout=30)
    resp.raise_for_status()
    archive_urls = resp.json().get("archives", [])

    if since:
        # archive_urls terminam em .../games/AAAA/MM -- inclui o mes de "since"
        # por inteiro (pode ter partidas novas desde a ultima busca)
        archive_urls = [
            u for u in archive_urls if "/".join(u.split("/")[-2:]) >= since.replace("-", "/")
        ]

    print(f"{len(archive_urls)} arquivo(s) mensal(is) a processar" + (f" (desde {since})" if since else "") + ".")
    sys.stdout.flush()

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
        sys.stdout.flush()

    os.makedirs(os.path.dirname(download_path) or ".", exist_ok=True)
    with open(download_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_pgns))

    print(f"Download concluido: {len(all_pgns)} partidas")
    return len(all_pgns)


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
        help="Buscar apenas a partir deste mes (AAAA-MM). Se ja existir um "
        "arquivo em --output, o resultado e mesclado com ele (sem duplicar) "
        "em vez de sobrescrever.",
    )
    args = parser.parse_args()

    if not args.email:
        print(
            "Aviso: nenhum e-mail de contato definido (--email ou CHESSCOM_CONTACT_EMAIL).\n"
            "A Chess.com pode bloquear a requisicao com erro 403 sem isso.",
            file=sys.stderr,
        )
        args.email = "nao-informado@exemplo.com"

    incremental = bool(args.since) and os.path.exists(args.output)
    download_target = args.output + ".incoming" if incremental else args.output

    try:
        fetch_chesscom_games(args.username, download_target, args.email, since=args.since)
    except requests.HTTPError as e:
        print(f"Erro ao buscar partidas do Chess.com: {e}", file=sys.stderr)
        sys.exit(1)

    if incremental:
        n_old, n_new, n_total = merge_and_dedupe(args.output, download_target, args.output)
        os.remove(download_target)
        print(f"Mesclado com o historico existente: {n_old} que ja tinha + {n_new} buscadas agora "
              f"= {n_total} partidas unicas em {args.output} (duplicatas descartadas automaticamente)")
    else:
        print(f"Salvo em {args.output}")
