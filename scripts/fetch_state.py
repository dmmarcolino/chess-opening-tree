"""
Guarda, por nick, ate que data ja buscamos as partidas dele -- pra so
pedir partidas novas na proxima execucao, em vez do historico inteiro
de novo. O estado fica em data/fetch_state.json (arquivo comitado no
repositorio, entao persiste entre execucoes do workflow).

Uso:
    python fetch_state.py get lichess Epictetus81       -> imprime a data guardada (ou nada, se for a primeira vez)
    python fetch_state.py set lichess Epictetus81 2026-08-18
"""
import argparse
import json
import os

STATE_PATH = "data/fetch_state.json"


def load():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(state):
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guarda/le o estado de ultima busca por nick")
    parser.add_argument("action", choices=["get", "set"])
    parser.add_argument("platform", choices=["lichess", "chesscom"])
    parser.add_argument("nick")
    parser.add_argument("value", nargs="?", help="Obrigatorio para 'set' (AAAA-MM-DD)")
    args = parser.parse_args()

    key = f"{args.platform}:{args.nick}"
    state = load()

    if args.action == "get":
        print(state.get(key, ""))
    else:
        if not args.value:
            raise SystemExit("valor obrigatorio para 'set'")
        state[key] = args.value
        save(state)
