"""Pipeline CLI: python -m pipeline <command>."""

import argparse

from pipeline import download, ingest
from pipeline.db import init_db


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="fetch raw StatsBomb JSON")
    sub.add_parser("init-db", help="create database schema")
    p_ingest = sub.add_parser("ingest", help="load raw JSON into Postgres")
    p_ingest.add_argument("--limit", type=int, default=None, help="only first N matches")
    p_verify = sub.add_parser("verify", help="check DB against raw JSON for one match")
    p_verify.add_argument("--match-id", type=int, required=True)
    p_derive = sub.add_parser("derive", help="compute derived metric tables")
    p_derive.add_argument("--skip-xt", action="store_true",
                          help="derive everything except xT-dependent tables")

    args = parser.parse_args()
    if args.command == "download":
        download.download_all()
    elif args.command == "init-db":
        init_db()
    elif args.command == "ingest":
        ingest.ingest_all(limit=args.limit)
    elif args.command == "verify":
        ingest.verify(args.match_id)
    elif args.command == "derive":
        from pipeline import derive
        derive.derive_all(skip_xt=args.skip_xt)


if __name__ == "__main__":
    main()
