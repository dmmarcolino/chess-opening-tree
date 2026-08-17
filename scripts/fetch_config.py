"""
Busca a lista de nicks cadastrados (via o painel no site) na planilha,
atraves do Web App do Apps Script, e salva em data/config.json.

Uso:
    python fetch_config.py --apps-script-url "https://script.google.com/.../exec"
"""
import argparse
import json
import sys

import requests


def fetch_config(apps_script_url, output_path):
    resp = requests.get(apps_script_url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    nicks = data.get("nicks", [])

    config = {"lichess": [], "chesscom": []}
    for entry in nicks:
        platform = entry.get("platform")
        nick = entry.get("nick")
        if platform in config and nick:
            config[platform].append(nick)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"Nicks encontrados -> lichess: {config['lichess']} | chesscom: {config['chesscom']}")
    print(f"Salvo em {output_path}")
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Busca nicks cadastrados no Apps Script")
    parser.add_argument("--apps-script-url", required=True)
    parser.add_argument("--output", default="data/config.json")
    args = parser.parse_args()

    try:
        config = fetch_config(args.apps_script_url, args.output)
    except requests.HTTPError as e:
        print(f"Erro ao buscar configuracao: {e}", file=sys.stderr)
        sys.exit(1)

    if not config["lichess"] and not config["chesscom"]:
        print(
            "Aviso: nenhum nick cadastrado ainda. Adicione ao menos um nick "
            "pelo painel de configuracao do site antes de esperar dados na arvore.",
            file=sys.stderr,
        )
