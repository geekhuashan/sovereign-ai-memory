# Data handling

## What stays on your machine

`ingest` reads supported session files and writes a SQLite index plus normalized user/assistant text to the runtime directory. `search` and `context` read that index. The core has no network client or model-service dependency.

By default, runtime data lives under `~/.local/share/sovereign-ai-memory` (or the configured `XDG_DATA_HOME`). Use `SAM_PRIVATE_DIR` to choose another directory, including an encrypted volume. Curated Markdown lives in `memory/core/` beneath that runtime directory unless `SAM_MEMORY_ROOT` is set.

Raw copying is disabled by default. `--archive-raw` makes a local copy with SHA-256 checking; it does not encrypt that copy. An opt-in raw archive may include source events excluded from the visible-message index. Choose the destination deliberately with `--raw-root` or `SAM_ARCHIVE_ROOT`.

## Sharing results

Search text and context packs receive best-effort secret masking. That filtering cannot remove every sensitive value, private fact, source name or identifier. Review output before sharing. JSON result metadata and source references may identify a project even when a message is masked.

Context packs are written with restrictive permissions on POSIX platforms. Permissions are not a replacement for disk encryption or a Windows ACL policy. The CLI reports disk-encryption information only when available; a successful `doctor` check verifies prerequisites, not complete confidentiality.

## Deletion and retention

Re-ingestion replaces messages belonging to each successfully parsed source. It is not a comprehensive deletion or backup-retention system. Existing exported context, optional archives and copies elsewhere are independent artifacts.

To rebuild without removed source material, stop consumers, retain any needed recovery copy privately, choose a fresh `SAM_PRIVATE_DIR`, and ingest only the intended source roots. Review older indexes, normalized records, context packs and raw archives separately before disposing of them. Do not infer secure erasure from removing a file, especially on SSDs and backed-up volumes.

The public repository includes only code, documentation and fabricated examples; it is not a place to store personal source histories.
