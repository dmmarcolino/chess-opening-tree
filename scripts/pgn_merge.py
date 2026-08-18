"""
Mescla um PGN "novo" (baixado numa busca incremental, com --since) com um
PGN "existente" (o historico que ja tinhamos), sem duplicar partidas.

A chave de deduplicacao e a URL da partida (tag [Site]), que tanto o
Lichess quanto o Chess.com preenchem com um link unico por partida. Se
por algum motivo essa tag nao existir, cai para uma chave composta
(brancas + pretas + data + hora), conservadora o suficiente pra nao
descartar partidas diferentes por engano.
"""
import os

import chess.pgn


def game_key(game):
    site = (game.headers.get("Site") or "").strip()
    if site and site not in ("?", ""):
        return site
    return "|".join([
        game.headers.get("White", "?"),
        game.headers.get("Black", "?"),
        game.headers.get("Date", "?"),
        game.headers.get("UTCTime", game.headers.get("Time", "?")),
    ])


def read_games(path):
    games = []
    if not path or not os.path.exists(path):
        return games
    with open(path, encoding="utf-8") as f:
        while True:
            try:
                game = chess.pgn.read_game(f)
            except Exception:
                continue
            if game is None:
                break
            games.append(game)
    return games


def merge_and_dedupe(existing_path, new_path, output_path):
    """
    Junta as partidas de existing_path + new_path, remove duplicatas (pela
    URL da partida) e escreve o resultado em output_path. Retorna
    (n_existentes, n_novas, n_apos_fusao) pra fins de log.
    """
    existing_games = read_games(existing_path)
    new_games = read_games(new_path)

    seen = set()
    merged = []
    for game in existing_games + new_games:
        key = game_key(game)
        if key in seen:
            continue
        seen.add(key)
        merged.append(game)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for i, game in enumerate(merged):
            if i > 0:
                f.write("\n\n")
            print(game, file=f)

    return len(existing_games), len(new_games), len(merged)
