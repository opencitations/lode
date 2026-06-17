# lode/cli.py
"""
lode serve [--port 8000]
lode build --url <url>  --read-as <owl|rdf|skos> [--out ./docs] [--lang en] [--imported] [--closure]
lode build --file <path> --read-as <owl|rdf|skos> [--out ./docs] [--lang en] [--imported] [--closure]
"""

import argparse
import sys
from pathlib import Path


def cmd_serve(args):
    import uvicorn
    uvicorn.run("lode.api:app", host="0.0.0.0", port=args.port, reload=False)


def cmd_build(args):
    from lode.reader import Reader
    from lode.builder import build_html 

    source = args.url or args.file
    if not source:
        print("ERROR: --url o --file richiesto", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    reader = Reader()
    reader.load_instances(
        source,
        args.read_as,
        imported=args.imported or None,
        closure=args.closure or None,
    )
    viewer = reader.get_viewer()

    build_html(viewer, out_dir, lang=args.lang)
    print(f"Done -> {out_dir}")


def main():
    parser = argparse.ArgumentParser(prog="lode")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- serve ---
    p_serve = sub.add_parser("serve", help="Avvia il server FastAPI")
    p_serve.add_argument("--port", type=int, default=8000)

    # --- build ---
    p_build = sub.add_parser("build", help="Genera HTML statici")
    src = p_build.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file")
    p_build.add_argument("--read-as", required=True, choices=["owl", "rdf", "skos"])
    p_build.add_argument("--out", default="./lode_output")
    p_build.add_argument("--lang", default="en")
    p_build.add_argument("--imported", action="store_true")
    p_build.add_argument("--closure", action="store_true")

    args = parser.parse_args()
    {"serve": cmd_serve, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()