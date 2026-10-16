# lode/cli.py
"""
lode serve [--port 8000]
lode build --url <url>  --read-as <owl|rdf|skos> [--out ./docs] [--lang en] [--artefact-name index] [--imported] [--closure]
lode build --file <path> --read-as <owl|rdf|skos> [--out ./docs] [--lang en] [--artefact-name index] [--imported] [--closure]
"""

import argparse
import sys
from pathlib import Path

def cmd_serve(args):
    """Start the FastAPI web service with uvicorn.

    uvicorn is imported lazily because it belongs to the optional [server]
    extra: the build command must keep working without it. Blocks until the
    server is stopped; binds to all interfaces so it works inside Docker.
    """
    try:
        import uvicorn
    except ImportError:
        sys.exit("Server dependencies missing: pip install oc-lode[server]")
    uvicorn.run("lode.api:app", host="0.0.0.0", port=args.port, reload=False)


def cmd_build(args):
    """Generate the static HTML documentation for one artefact.

    Reader and builder are imported lazily so that `lode serve` and `--help`
    do not pay their import cost. Creates the output directory if missing and
    overwrites existing pages in it. Prints the output path on success.
    """
    from lode.reader import Reader
    from lode.builder import build_html
    from lode.helpers.formats import check_format_enabled, ReadAsFormat

    check_format_enabled(ReadAsFormat(args.read_as))

    source = args.url or args.file
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    reader = Reader()
    reader.load_instances(
        source, args.read_as,
        imported=args.imported or None,
        closure=args.closure or None,
        partial_import=args.partial_import or None,
        warnings=args.warnings,
    )
    viewer = reader.get_viewer()
    build_html(viewer, out_dir, lang=args.lang, reader=reader,
               artefact_name=args.artefact_name)
    if args.warnings:
        warnings = viewer.format_warnings(reader.get_warnings())
        for w in warnings:
            print(f"[{w['code']}] {w['message']}")
        if warnings:
            print(f"Warnings report -> {out_dir / 'report.txt'}")
        else:
            print("No reader warnings")
    print(f"Done -> {out_dir}")


def main():
    """Parse the command line and dispatch to the chosen subcommand.

    Entry point of the `lode` script declared in pyproject.toml. Adds no logic
    of its own: serve and build are thin adapters over the core.
    """
    parser =argparse.ArgumentParser(prog="lode")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- serve ---
    p_serve = sub.add_parser("serve", help="Start the FastAPI web service")
    p_serve.add_argument("--port", type=int, default=8000)

    # --- build ---
    p_build = sub.add_parser("build", help="Generate static HTML documentation")
    src = p_build.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file")
    p_build.add_argument("--read-as", required=True, choices=["owl", "rdf", "skos"])
    p_build.add_argument("--out", default="./lode_output")
    p_build.add_argument("--lang", default="en")
    p_build.add_argument("--artefact-name", default="index",
                         help="File stem of the root page and its serializations (default: index)")
    p_build.add_argument("--imported", action="store_true")
    p_build.add_argument("--closure", action="store_true")
    p_build.add_argument("--partial-import", action="store_true")
    p_build.add_argument("--warnings", action="store_true",
                         help="Print reader warnings and write them to report.txt in the output folder")

    args = parser.parse_args()
    {"serve": cmd_serve, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()