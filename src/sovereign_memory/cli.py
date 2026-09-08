from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from .adapters import ADAPTERS
from .archive import archive_raw_file
from .context import build_context_pack
from .paths import archive_root, memory_root, private_dir, source_roots
from .redact import redact_secrets
from .store import MemoryStore


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def selected_vendors(values: list[str] | None) -> list[str]:
    return values or list(ADAPTERS)


def command_status(args: argparse.Namespace) -> int:
    roots = source_roots()
    payload: dict[str, object] = {"sources": {}, "index": {}}
    for vendor in selected_vendors(args.vendor):
        root = roots[vendor]
        files = list(ADAPTERS[vendor].discover(root)) if root.exists() else []
        size = sum(path.stat().st_size for path in files)
        payload["sources"][vendor] = {
            "root": str(root),
            "exists": root.exists(),
            "sessions": len(files),
            "bytes": size,
        }
    store = MemoryStore(private_dir())
    payload["index"] = store.counts()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("Local source inventory")
    for vendor, details in payload["sources"].items():
        state = "found" if details["exists"] else "missing"
        print(
            f"- {vendor}: {details['sessions']} sessions, "
            f"{format_bytes(details['bytes'])} ({state})"
        )
    counts = payload["index"]
    print(f"Index: {counts['sessions']} sessions, {counts['messages']} messages")
    return 0


def command_ingest(args: argparse.Namespace) -> int:
    raw_root = Path(args.raw_root).expanduser() if args.raw_root else archive_root()
    roots = source_roots()
    store = MemoryStore(private_dir())
    store.initialize()
    totals = {"sessions": 0, "messages": 0, "warnings": 0, "archived": 0, "errors": 0}

    for vendor in selected_vendors(args.vendor):
        root = roots[vendor]
        if not root.exists():
            print(f"{vendor}: source root missing: {root}", file=sys.stderr)
            totals["errors"] += 1
            continue
        files = list(ADAPTERS[vendor].discover(root))
        if args.limit is not None:
            files = sorted(files, key=lambda path: (path.stat().st_mtime_ns, str(path)))[-args.limit :]
        valid_source_ids: set[str] = set()
        vendor_errors = 0
        for path in files:
            try:
                session = ADAPTERS[vendor].parse(path, root)
                if args.archive_raw:
                    _, _, copied = archive_raw_file(
                        path, root, raw_root, vendor, expected_sha256=session.source_sha256
                    )
                    totals["archived"] += int(copied)
                store.ingest(session)
                valid_source_ids.add(session.source_id)
                totals["sessions"] += 1
                totals["messages"] += len(session.messages)
                totals["warnings"] += len(session.warnings)
            except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
                totals["errors"] += 1
                vendor_errors += 1
                print(f"{vendor}: failed {path.name}: {exc}", file=sys.stderr)
        if args.limit is None and vendor_errors == 0:
            store.prune_normalized(vendor, valid_source_ids)
        print(f"{vendor}: processed {len(files)} source sessions")

    print(
        "Imported {sessions} sessions / {messages} messages; "
        "warnings={warnings}, archived={archived}, errors={errors}".format(**totals)
    )
    if args.archive_raw:
        print(f"Raw archive: {raw_root}")
    return 1 if totals["errors"] else 0


def command_search(args: argparse.Namespace) -> int:
    store = MemoryStore(private_dir())
    results = store.search(args.query, args.limit)
    if args.json:
        safe_results = []
        for result in results:
            result = dict(result)
            result["text"] = redact_secrets(result["text"])
            safe_results.append(result)
        print(json.dumps(safe_results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            citation = f"{result['vendor']}:{result['session_id']}:{result['id']}"
            timestamp = result.get("timestamp") or "timestamp unavailable"
            print(f"[{citation}] {result['role']} | {timestamp}")
            print(redact_secrets(result["text"]).strip())
            print()
    return 0


def command_context(args: argparse.Namespace) -> int:
    store = MemoryStore(private_dir())
    pack = build_context_pack(
        args.query,
        store,
        memory_root(),
        limit=args.limit,
        max_chars=args.max_chars,
    )
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Atomic replacement avoids following a destination symlink and never
        # exposes an intermediate file with permissive default permissions.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                             prefix=".sam-context-", delete=False) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(pack)
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(output)
    else:
        print(pack, end="")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    del args
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0]))
    with sqlite3.connect(":memory:") as connection:
        has_fts = any(
            row[0] == "ENABLE_FTS5" for row in connection.execute("PRAGMA compile_options")
        )
    checks.append(("SQLite FTS5", has_fts, sqlite3.sqlite_version))
    for vendor, root in source_roots().items():
        print(f"INFO {vendor} source: {'found' if root.is_dir() else 'missing (optional)'}: {root}")
    print(f"INFO runtime path: {private_dir()}")
    print(f"INFO core memory path: {memory_root()}")
    print(f"INFO raw archive path (opt-in): {archive_root()}")
    print("INFO storage: plaintext local index; secret masking is best-effort output filtering, not encryption.")
    if sys.platform == "darwin":
        try:
            result = subprocess.run(["fdesetup", "status"], capture_output=True, text=True, timeout=5)
            detail = result.stdout.strip() or "status unavailable"
            print(f"INFO FileVault: {detail}")
        except (OSError, subprocess.TimeoutExpired):
            print("INFO FileVault: status unavailable")
    else:
        print("INFO disk encryption: not checked on this platform")

    failed = False
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
        failed = failed or not passed
    return 1 if failed else 0


def positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def nonempty_query(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("query must not be empty")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sam", description="Sovereign AI Memory command line interface"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="inventory local source sessions")
    status.add_argument("--vendor", action="append", choices=ADAPTERS)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    ingest = subparsers.add_parser("ingest", help="normalize and index sessions")
    ingest.add_argument("--vendor", action="append", choices=ADAPTERS)
    ingest.add_argument("--limit", type=positive_int, help="newest N source files per vendor")
    raw = ingest.add_mutually_exclusive_group()
    raw.add_argument("--archive-raw", action="store_true", default=False,
                     help="opt in to a local copy of original session files (may include secrets and tool traces)")
    raw.add_argument("--no-archive-raw", dest="archive_raw", action="store_false",
                     help="do not copy originals (default; compatibility option)")
    ingest.add_argument(
        "--raw-root",
        help="raw archive destination (default: SAM_ARCHIVE_ROOT or runtime/raw-archive)",
    )
    ingest.set_defaults(func=command_ingest)

    search = subparsers.add_parser("search", help="search indexed history")
    search.add_argument("query", type=nonempty_query)
    search.add_argument("--limit", type=positive_int, default=10)
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_search)

    context = subparsers.add_parser("context", help="build a bounded context pack")
    context.add_argument("query", type=nonempty_query)
    context.add_argument("--limit", type=positive_int, default=8)
    context.add_argument("--max-chars", type=positive_int, default=16000)
    context.add_argument("--output")
    context.set_defaults(func=command_context)

    doctor = subparsers.add_parser("doctor", help="check local prerequisites")
    doctor.set_defaults(func=command_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"sam: {type(exc).__name__}: operation failed; check paths and local index", file=sys.stderr)
        return 1
