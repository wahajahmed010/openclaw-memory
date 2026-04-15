"""CLI interface for the OpenClaw Memory System."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .continuity import ContinuityManager
from .core import MemoryStore
from .index import MemoryIndex
from .search import MemorySearch


def _store(args: argparse.Namespace) -> MemoryStore:
    return MemoryStore(Path(args.base_dir).expanduser())


def cmd_write(args: argparse.Namespace) -> None:
    store = _store(args)
    tags = args.tags.split(",") if args.tags else []
    refs = args.refs.split(",") if args.refs else []
    entry = store.write(text=args.text, type_=args.type, tags=tags, refs=refs)
    print(json.dumps(entry, indent=2))


def cmd_read(args: argparse.Namespace) -> None:
    store = _store(args)
    if args.date:
        entries = store.read_bucket(args.date)
    else:
        entries = list(store.iter_all_entries())
    for e in entries:
        print(json.dumps(e, indent=2))


def cmd_search(args: argparse.Namespace) -> None:
    base = Path(args.base_dir).expanduser()
    ms = MemorySearch(base)
    results = ms.search(
        query=args.query,
        mode=args.mode,
        type_=args.type or None,
        tag=args.tag or None,
        limit=args.limit,
    )
    for r in results:
        print(json.dumps(r, indent=2))


def cmd_index(args: argparse.Namespace) -> None:
    base = Path(args.base_dir).expanduser()
    mi = MemoryIndex(base)
    count = mi.rebuild()
    print(f"Indexed {count} entries.")


def cmd_export(args: argparse.Namespace) -> None:
    base = Path(args.base_dir).expanduser()
    cm = ContinuityManager(base)
    cm.export(Path(args.output).expanduser())
    print(f"Exported to {args.output}")


def cmd_import(args: argparse.Namespace) -> None:
    base = Path(args.base_dir).expanduser()
    cm = ContinuityManager(base)
    count = cm.import_(Path(args.input).expanduser())
    print(f"Imported {count} entries.")


def cmd_link(args: argparse.Namespace) -> None:
    base = Path(args.base_dir).expanduser()
    mi = MemoryIndex(base)
    mi.add_link(args.src, args.dst)
    print(f"Linked {args.src} -> {args.dst}")


def cmd_recover(args: argparse.Namespace) -> None:
    base = Path(args.base_dir).expanduser()
    cm = ContinuityManager(base)
    mi = MemoryIndex(base)
    count = cm.recover(mi)
    print(f"Recovered {count} entries.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openclaw-memory", description="OpenClaw Memory System CLI"
    )
    parser.add_argument("--base-dir", default="~/.openclaw/workspace")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("write", help="Write a new memory entry")
    p.add_argument("text")
    p.add_argument("--type", default="note")
    p.add_argument("--tags", default="")
    p.add_argument("--refs", default="")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("read", help="Read entries (all or by date)")
    p.add_argument("--date", default="")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("search", help="Search entries")
    p.add_argument("query")
    p.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    p.add_argument("--type", default="")
    p.add_argument("--tag", default="")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("index", help="Rebuild the SQLite index from source")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("export", help="Export all entries to JSONL")
    p.add_argument("output")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="Import entries from JSONL backup")
    p.add_argument("input")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("link", help="Manually link two entries")
    p.add_argument("src")
    p.add_argument("dst")
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("recover", help="Recover from compaction snapshot")
    p.set_defaults(func=cmd_recover)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())