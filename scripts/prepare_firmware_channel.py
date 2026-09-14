#!/usr/bin/env python3
"""Prepare a self-contained ESPHome web-install and managed-OTA channel."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    checksum = hashlib.new(algorithm)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def find_manifest(source: Path) -> Path:
    manifests = sorted(source.rglob("manifest.json"))
    manifests.extend(sorted(source.rglob("*.manifest.json")))
    manifests = list(dict.fromkeys(manifests))
    if len(manifests) != 1:
        raise ValueError(
            f"expected exactly one firmware manifest below {source}, found {len(manifests)}"
        )
    return manifests[0]


def referenced_files(manifest: dict) -> list[tuple[dict, str]]:
    references: list[tuple[dict, str]] = []
    for build in manifest.get("builds", []):
        ota = build.get("ota")
        if ota:
            references.append((ota, "ota"))
        for part in build.get("parts", []):
            references.append((part, "part"))
    if not references:
        raise ValueError("manifest contains no firmware files")
    return references


def prepare(source: Path, output: Path) -> None:
    manifest_path = find_manifest(source)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if not manifest.get("name") or not manifest.get("version"):
        raise ValueError("manifest must contain a project name and version")

    output.mkdir(parents=True, exist_ok=True)
    for reference, kind in referenced_files(manifest):
        source_name = Path(reference["path"]).name
        matches = sorted(source.rglob(source_name))
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one {source_name} below {source}, found {len(matches)}"
            )

        firmware = matches[0]
        for algorithm in ("md5", "sha256"):
            expected = reference.get(algorithm)
            if expected and digest(firmware, algorithm) != expected:
                raise ValueError(f"{algorithm} mismatch for {firmware}")

        destination = output / source_name
        shutil.copy2(firmware, destination)
        reference["path"] = source_name

        # Managed updates require an integrity hash for the OTA image. The web
        # installer also benefits from hashes even if an older build omitted
        # them from its manifest.
        if kind == "ota" or "md5" in reference:
            reference["md5"] = digest(destination, "md5")
        if kind == "ota" or "sha256" in reference:
            reference["sha256"] = digest(destination, "sha256")

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)


if __name__ == "__main__":
    main()
