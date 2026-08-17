"""
Le todos os PGNs baixados (Lichess + Chess.com, podendo ter varios nicks
por plataforma), identifica as partidas do usuario entre qualquer um dos
seus nicks cadastrados, e constroi um GRAFO DE POSICOES para cada cor --
ver a explicacao completa sobre transposicoes no README.

IMPORTANTE sobre o formato de saida
------------------------------------
Cada posicao (no do grafo) e serializada UMA UNICA VEZ no JSON, num mapa
plano `positions`, independente de quantas ordens de lance diferentes
levam ate ela. O site monta a navegacao (a "arvore" que voce ve) fazendo
consultas a esse mapa sob demanda, a medida que voce expande os nos.

Isso substitui uma versao anterior que serializava uma arvore aninhada,
duplicando a subarvore inteira toda vez que uma posicao transposta
aparecia em mais de um lugar -- o que causava uma explosao combinatorial
em repertorios com muitas transposicoes na abertura seguidas de um
meio-jogo longo (exatamente o caso comum: partidas de verdade, com anos
de historico). O formato de grafo achatado tem custo proporcional ao
numero de posicoes e arestas, nunca ao numero de caminhos possiveis.

Uso (um ou mais nicks por plataforma):
    python build_tree.py \
        --lichess-username nick1 nick2 \
        --chesscom-username outroNick \
        --lichess-pgn-glob "data/raw/lichess_*.pgn" \
        --chesscom-pgn-glob "data/raw/chesscom_*.pgn" \
        --output-dir data
"""
import argparse
import glob
import json
import re
import sys
from datetime import datetime, timezone

import chess
import chess.pgn

DATE_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})$")


def normalized_fen(board):
    """
    Os 4 primeiros campos do FEN definem a posicao em si (posicao das
    pecas, quem joga, direitos de roque, alvo de en passant). Os 2
    ultimos campos (contador de lances sem captura/movimento de peao, e
    numero do lance) NAO fazem parte da posicao -- por isso sao
    descartados aqui. E exatamente isso que faz 1.d4 d5 2.c4 e6 e
    1.d4 e6 2.c4 d5 caírem no mesmo no.
    """
    return " ".join(board.fen().split(" ")[:4])


def parse_pgn_date(headers):
    """Prefere UTCDate (mais confiavel) e cai pra Date. Retorna 'AAAA-MM-DD' ou None."""
    for tag in ("UTCDate", "Date"):
        raw = headers.get(tag)
        if not raw:
            continue
        m = DATE_RE.match(raw)
        if m and "?" not in raw:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def result_for_user(result_tag, user_is_white):
    if result_tag == "1-0":
        return "win" if user_is_white else "loss"
    if result_tag == "0-1":
        return "loss" if user_is_white else "win"
    if result_tag == "1/2-1/2":
        return "draw"
    return None  # partida abandonada/inacabada ("*") - ignorada nas estatisticas


def new_position():
    return {"parents": set(), "children": {}}  # children: san -> {"to": fen, "game_ids": set()}


def add_game_to_graph(positions, game, game_id):
    board = game.board()
    current_fen = normalized_fen(board)
    positions.setdefault(current_fen, new_position())

    for move in game.mainline_moves():
        san = board.san(move)
        parent_fen = current_fen
        board.push(move)
        child_fen = normalized_fen(board)

        positions.setdefault(child_fen, new_position())
        positions[child_fen]["parents"].add(parent_fen)

        edge = positions[parent_fen]["children"].setdefault(san, {"to": child_fen, "game_ids": set()})
        edge["game_ids"].add(game_id)  # um set ja evita duplicar se a partida repetir o mesmo trecho

        current_fen = child_fen


def build_graphs(pgn_paths_by_source, usernames_by_source):
    """
    Retorna, para cada cor: positions, start_fen, games (catalogo)
    """
    graphs = {
        "white": {"positions": {}, "start_fen": None, "games": []},
        "black": {"positions": {}, "start_fen": None, "games": []},
    }

    stats = {"lidas": 0, "usadas": 0, "ignoradas_outro_jogador": 0,
              "ignoradas_sem_resultado": 0, "ignoradas_variante": 0, "erros_parsing": 0}

    for source, paths in pgn_paths_by_source.items():
        usernames = usernames_by_source.get(source) or set()
        if not usernames:
            continue

        for path in paths:
            try:
                f = open(path, encoding="utf-8")
            except FileNotFoundError:
                print(f"Aviso: arquivo nao encontrado, pulando: {path}", file=sys.stderr)
                continue

            with f:
                while True:
                    try:
                        game = chess.pgn.read_game(f)
                    except Exception as e:
                        stats["erros_parsing"] += 1
                        print(f"Aviso: erro ao ler uma partida em {path}: {e}", file=sys.stderr)
                        continue
                    if game is None:
                        break
                    stats["lidas"] += 1

                    variant = game.headers.get("Variant", "Standard")
                    if variant not in ("Standard", "From Position"):
                        stats["ignoradas_variante"] += 1
                        continue

                    white = game.headers.get("White", "").strip().lower()
                    black = game.headers.get("Black", "").strip().lower()

                    if white in usernames:
                        color, user_is_white, nick = "white", True, game.headers.get("White", "").strip()
                    elif black in usernames:
                        color, user_is_white, nick = "black", False, game.headers.get("Black", "").strip()
                    else:
                        stats["ignoradas_outro_jogador"] += 1
                        continue

                    outcome = result_for_user(game.headers.get("Result", "*"), user_is_white)
                    if outcome is None:
                        stats["ignoradas_sem_resultado"] += 1
                        continue

                    g = graphs[color]
                    game_id = len(g["games"])
                    g["games"].append({
                        "date": parse_pgn_date(game.headers),
                        "site": source,
                        "nick": nick,
                        "result": outcome,
                    })

                    try:
                        add_game_to_graph(g["positions"], game, game_id)
                    except Exception as e:
                        g["games"].pop()  # desfaz o registro no catalogo, a partida nao entrou no grafo
                        stats["erros_parsing"] += 1
                        print(f"Aviso: erro ao processar uma partida em {path}: {e}", file=sys.stderr)
                        continue

                    stats["usadas"] += 1
                    if g["start_fen"] is None:
                        g["start_fen"] = normalized_fen(game.board())

    return graphs, stats


def serialize_graph(positions, start_fen, total_games):
    """
    Serializa o grafo num formato compacto: `positions` vira uma LISTA (o
    indice na lista E o identificador da posicao -- nao precisa mais
    escrever um hash de 10 caracteres em todo lugar que uma posicao e
    referenciada). Cada aresta vira um par posicional [indice_do_filho,
    lista_de_partidas] em vez de um objeto com os nomes dos campos
    escritos por extenso. Isso corta uma fatia grande do tamanho do
    arquivo em repertorios com muitas posicoes (centenas de milhares,
    no caso de anos de partidas reais).

    O sinalizador de transposicao NAO vai mais no JSON -- o navegador
    calcula isso sozinho (uma posicao e transposicao se tem mais de um
    pai distinto), a partir do mesmo grafo, sem custo extra relevante.
    """
    ordered_fens = list(positions.keys())
    fen_to_idx = {fen: i for i, fen in enumerate(ordered_fens)}

    out_positions = []
    for fen in ordered_fens:
        node = positions[fen]
        children = {
            san: [fen_to_idx[edge["to"]], sorted(edge["game_ids"])]
            for san, edge in node["children"].items()
        }
        out_positions.append({"c": children})

    start_id = fen_to_idx.get(start_fen) if start_fen is not None else None
    if start_id is not None:
        # a posicao inicial "contem" todas as partidas, por definicao --
        # nao ha aresta de entrada nela, entao guardamos isso a parte
        out_positions[start_id]["g"] = list(range(total_games))

    return {"start_id": start_id, "positions": out_positions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Constroi o grafo de posicoes (formato achatado, sem duplicacao)")
    parser.add_argument("--lichess-username", nargs="*", default=[],
                         help="Um ou mais nicks do Lichess (separados por espaco)")
    parser.add_argument("--chesscom-username", nargs="*", default=[],
                         help="Um ou mais nicks do Chess.com (separados por espaco)")
    parser.add_argument("--lichess-pgn-glob", default="data/raw/lichess_*.pgn",
                         help="Padrao glob dos PGNs do Lichess (um arquivo por nick)")
    parser.add_argument("--chesscom-pgn-glob", default="data/raw/chesscom_*.pgn",
                         help="Padrao glob dos PGNs do Chess.com (um arquivo por nick)")
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    if not args.lichess_username and not args.chesscom_username:
        print("Informe pelo menos --lichess-username ou --chesscom-username", file=sys.stderr)
        sys.exit(1)

    pgn_paths = {
        "lichess": sorted(glob.glob(args.lichess_pgn_glob)),
        "chesscom": sorted(glob.glob(args.chesscom_pgn_glob)),
    }
    usernames = {
        "lichess": {u.strip().lower() for u in args.lichess_username},
        "chesscom": {u.strip().lower() for u in args.chesscom_username},
    }

    for source, paths in pgn_paths.items():
        if usernames[source] and not paths:
            print(f"Aviso: nenhum arquivo PGN encontrado para {source} "
                  f"(procurado com o padrao configurado)", file=sys.stderr)

    graphs, stats = build_graphs(pgn_paths, usernames)

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for color in ("white", "black"):
        g = graphs[color]
        graph_json = serialize_graph(g["positions"], g["start_fen"], len(g["games"]))
        output = {
            "generated_at": generated_at,
            "games": g["games"],
            "start_id": graph_json["start_id"],
            "positions": graph_json["positions"],
        }
        with open(f"{args.output_dir}/tree_{color}.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    n_transp_white = sum(1 for p in graphs["white"]["positions"].values() if len(p["parents"]) > 1)
    n_transp_black = sum(1 for p in graphs["black"]["positions"].values() if len(p["parents"]) > 1)

    print(
        f"Partidas lidas: {stats['lidas']} | usadas: {stats['usadas']} | "
        f"de outro jogador: {stats['ignoradas_outro_jogador']} | "
        f"sem resultado: {stats['ignoradas_sem_resultado']} | "
        f"variante (ignoradas): {stats['ignoradas_variante']} | "
        f"erros de parsing: {stats['erros_parsing']}"
    )
    print(f"tree_white.json: {len(graphs['white']['games'])} partidas de brancas, "
          f"{len(graphs['white']['positions'])} posicoes distintas, {n_transp_white} com transposicao")
    print(f"tree_black.json: {len(graphs['black']['games'])} partidas de pretas, "
          f"{len(graphs['black']['positions'])} posicoes distintas, {n_transp_black} com transposicao")
