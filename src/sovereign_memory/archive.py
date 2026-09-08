from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from .models import file_sha256


def archive_raw_file(
    source: Path,
    source_root: Path,
    archive_root: Path,
    vendor: str,
    *,
    expected_sha256: str | None = None,
) -> tuple[Path, str, bool]:
    source_hash = file_sha256(source)
    if expected_sha256 is not None and source_hash != expected_sha256:
        raise ValueError("source changed since parsing; raw archive was not updated")
    try:
        relative = source.resolve().relative_to(source_root.resolve())
    except ValueError:
        relative = Path(source.name)
    destination = archive_root / vendor / relative
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Path.mkdir(mode=...) only applies `mode` to the leaf directory it creates;
    # any newly created intermediate parents get the process umask instead, so
    # walk up explicitly to keep the whole archive tree private end to end.
    archive_root_resolved = archive_root.resolve()
    directory = destination.parent.resolve()
    while directory != archive_root_resolved and archive_root_resolved in directory.parents:
        os.chmod(directory, 0o700)
        directory = directory.parent
    hash_path = destination.with_name(destination.name + ".sha256.json")

    if destination.exists() and file_sha256(destination) == source_hash:
        return destination, source_hash, False

    temporary = destination.with_name(destination.name + ".tmp")
    shutil.copy2(source, temporary)
    if file_sha256(temporary) != source_hash:
        temporary.unlink(missing_ok=True)
        raise OSError(f"hash mismatch while archiving {source}")
    os.chmod(temporary, 0o400)
    os.replace(temporary, destination)
    hash_payload = {
        "algorithm": "sha256",
        "digest": source_hash,
        "source_ref": relative.as_posix(),
        "vendor": vendor,
    }
    hash_temporary = hash_path.with_name(hash_path.name + ".tmp")
    hash_temporary.write_text(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(hash_temporary, 0o400)
    os.replace(hash_temporary, hash_path)
    return destination, source_hash, True
