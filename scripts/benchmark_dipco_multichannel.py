#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "ai-edge-litert==2.1.2",
#   "numba==0.62.1",
#   "numpy==2.3.4",
#   "pymicro-features==2.0.2",
#   "scipy==1.16.3",
# ]
# ///
"""Run the DiPCo cutoff benchmark over every far-field microphone channel."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numba import njit

import benchmark_dipco as base


DEFAULT_ARCHIVE = base.DEFAULT_CACHE / "DipCo.tgz"
DEFAULT_OUTPUT = base.REPO_ROOT / "benchmarks" / "dipco" / "all_channels.json"
ARCHIVE_URL = "https://zenodo.org/api/records/8122551/files/DipCo.tgz/content"
ARCHIVE_SIZE = 13_415_522_146
ARCHIVE_MD5 = "2297eb9334f3b90e02b54b708e501b24"
ARCHIVE_SHA256 = "b7679824adb96544e1fd6e69e97d3bdebd444d5af22adaa27681a3db4a3aeb5d"
EXPECTED_SESSIONS = {f"S{number:02d}" for number in range(1, 11)}
EXPECTED_CHANNELS = {f"U{unit:02d}.CH{channel}" for unit in range(1, 6) for channel in range(1, 8)}
MEMBER_RE = re.compile(
    r"(?:^|/)audio/(?P<split>dev|eval)/"
    r"(?P<session>S\d{2})_(?P<unit>U\d{2})\.(?P<channel>CH\d)\.wav$"
)
CACHE_SCHEMA = 1
SLIDING_WINDOW = base.SLIDING_WINDOW
MIN_FEATURE_SLICES_BEFORE_DETECTION = base.MIN_FEATURE_SLICES_BEFORE_DETECTION


def archive_digests(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            md5.update(block)
            sha256.update(block)
    return md5.hexdigest(), sha256.hexdigest()


def verify_archive(path: Path) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == ARCHIVE_SIZE
        and archive_digests(path) == (ARCHIVE_MD5, ARCHIVE_SHA256)
    )


def download_archive(path: Path) -> None:
    if verify_archive(path):
        print(f"verified {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > ARCHIVE_SIZE:
        partial.unlink()
        offset = 0
    headers = {"User-Agent": "waveshare-va-dipco-benchmark/1"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(ARCHIVE_URL, headers=headers)
    action = "resuming" if offset else "downloading"
    print(f"{action} {path.name} at {offset / 1_000_000_000:.2f}/{ARCHIVE_SIZE / 1_000_000_000:.2f} GB")
    with urllib.request.urlopen(request) as response:
        if offset and response.status != 206:
            raise RuntimeError("DiPCo server ignored the resume range; remove the partial file and retry")
        with partial.open("ab" if offset else "wb") as output:
            while block := response.read(4 * 1024 * 1024):
                output.write(block)
    if not verify_archive(partial):
        partial.unlink(missing_ok=True)
        raise RuntimeError("Downloaded DiPCo archive failed its published size/MD5 verification")
    partial.replace(path)


def prepare(cache: Path, archive: Path) -> None:
    download_archive(archive)
    model_dir = cache / "models"
    for name, artifact in base.MODEL_FILES.items():
        url = f"https://github.com/{base.MODEL_REPO}/raw/{base.MODEL_REVISION}/{artifact.path}"
        base.download(url, model_dir / f"{name}.tflite", artifact)
    for artifact in base.TRANSCRIPT_FILES:
        url = f"https://huggingface.co/datasets/{base.CORPUS_REPO}/resolve/{base.CORPUS_REVISION}/{artifact.path}"
        base.download(url, cache / "transcriptions" / artifact.filename, artifact)


def cache_fingerprint() -> str:
    encoded = json.dumps(
        {
            "schema": CACHE_SCHEMA,
            "archive_md5": ARCHIVE_MD5,
            "base_fingerprint": base.cache_fingerprint(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def prediction_dir(cache: Path, max_seconds: float | None) -> Path:
    run = "full" if max_seconds is None else f"smoke-{max_seconds:g}s"
    return cache / "predictions-all-channels" / cache_fingerprint() / run


def channel_key(match: re.Match[str]) -> str:
    return f"{match.group('session')}_{match.group('unit')}.{match.group('channel')}"


def process_extracted_channel(
    audio_path: Path,
    display_name: str,
    model_paths: dict[str, Path],
    max_seconds: float | None,
    output_path: Path,
) -> tuple[float, float]:
    started = time.monotonic()
    try:
        probabilities, duration_s = base.generate_session_probabilities(
            audio_path,
            model_paths,
            max_seconds,
            display_name=display_name,
        )
        np.savez_compressed(
            output_path,
            fingerprint=np.asarray(cache_fingerprint()),
            duration_s=np.asarray(duration_s),
            **probabilities,
        )
        return duration_s, time.monotonic() - started
    finally:
        audio_path.unlink(missing_ok=True)


def inference(
    cache: Path,
    archive: Path,
    max_seconds: float | None,
    workers: int,
) -> dict[str, float]:
    if not verify_archive(archive):
        raise RuntimeError(f"Missing or invalid archive: {archive}; run prepare first")
    model_paths = {name: cache / "models" / f"{name}.tflite" for name in base.MODEL_FILES}
    predictions = prediction_dir(cache, max_seconds)
    predictions.mkdir(parents=True, exist_ok=True)
    temporary = cache / "multichannel-working"
    temporary.mkdir(parents=True, exist_ok=True)
    durations: dict[str, float] = {}
    seen: set[str] = set()
    index = 0
    pending: dict[concurrent.futures.Future[tuple[float, float]], tuple[int, str]] = {}

    def collect(done: set[concurrent.futures.Future[tuple[float, float]]]) -> None:
        for future in done:
            item_index, item_key = pending.pop(future)
            duration_s, elapsed_s = future.result()
            durations[item_key] = duration_s
            print(f"[{item_index}/350] {item_key}: {duration_s / 60:.1f} min in {elapsed_s:.1f}s")

    # The archive is decompressed once. Only a bounded queue of temporary WAVs
    # is materialized, allowing parallel inference without retaining ~22 GB of
    # extracted PCM.
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        with tarfile.open(archive, mode="r:gz") as tar:
            for member in tar:
                match = MEMBER_RE.search(member.name)
                if match is None or not member.isfile():
                    continue
                key = channel_key(match)
                if key in seen:
                    raise RuntimeError(f"Duplicate far-field channel in archive: {key}")
                seen.add(key)
                index += 1
                output_path = predictions / f"{key}.npz"
                if output_path.exists():
                    with np.load(output_path) as cached:
                        if str(cached["fingerprint"]) != cache_fingerprint():
                            raise RuntimeError(f"Stale prediction cache: {output_path}")
                        durations[key] = float(cached["duration_s"])
                    print(f"[{index}/350] cached {key}")
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"Could not read {member.name}")
                temporary_path = temporary / f"{key}.wav"
                temporary_path.unlink(missing_ok=True)
                with temporary_path.open("wb") as output_handle:
                    shutil.copyfileobj(extracted, output_handle, length=4 * 1024 * 1024)
                future = executor.submit(
                    process_extracted_channel,
                    temporary_path,
                    member.name,
                    model_paths,
                    max_seconds,
                    output_path,
                )
                pending[future] = (index, key)
                if len(pending) >= workers * 2:
                    done, _ = concurrent.futures.wait(
                        pending,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    collect(done)
        for future in concurrent.futures.as_completed(tuple(pending)):
            collect({future})

    expected = {f"{session}_{channel}" for session in EXPECTED_SESSIONS for channel in EXPECTED_CHANNELS}
    missing = sorted(expected - seen)
    unexpected = sorted(seen - expected)
    if missing or unexpected:
        raise RuntimeError(f"Unexpected archive inventory; missing={missing}, unexpected={unexpected}")
    return durations


@njit
def detection_indices(probabilities: np.ndarray, vad: np.ndarray, cutoff: int) -> list[int]:
    """Replay one cutoff and retain event timestamps for synchronized clustering."""
    recent = np.zeros(SLIDING_WINDOW, dtype=np.uint16)
    ignore_slices = -MIN_FEATURE_SLICES_BEFORE_DETECTION
    previous = 0
    events: list[int] = []
    for index, probability_u8 in enumerate(probabilities):
        probability = int(probability_u8)
        if previous < cutoff:
            ignore_slices = min(ignore_slices + 2, 0)
        recent[index % SLIDING_WINDOW] = probability
        previous = probability
        if probability < cutoff:
            ignore_slices = min(ignore_slices + 1, 0)
        if ignore_slices < 0 or recent.sum() <= cutoff * SLIDING_WINDOW or not vad[index]:
            continue
        events.append(index)
        recent.fill(0)
        previous = 0
        ignore_slices = -MIN_FEATURE_SLICES_BEFORE_DETECTION
    return events


def clustered_count(indices: list[int], tolerance_predictions: int) -> int:
    if not indices:
        return 0
    ordered = sorted(indices)
    clusters = 1
    cluster_end = ordered[0]
    for index in ordered[1:]:
        if index - cluster_end > tolerance_predictions:
            clusters += 1
        cluster_end = index
    return clusters


def evaluate_trace(path: Path) -> tuple[str, float, dict[str, dict[str, np.ndarray]], dict[str, dict[str, list[int]]]]:
    key = path.stem
    modes: dict[str, dict[str, np.ndarray]] = {}
    preset_events: dict[str, dict[str, list[int]]] = {}
    with np.load(path) as trace:
        if str(trace["fingerprint"]) != cache_fingerprint():
            raise RuntimeError(f"Stale prediction cache: {path}")
        duration_s = float(trace["duration_s"])
        vad = base.rolling_detected(trace["vad"], base.VAD_CUTOFF)
        for name in (model for model in base.MODEL_FILES if model != "vad"):
            probabilities = trace[name]
            raw_counts = base.count_firmware_detections(
                probabilities, np.empty(0, dtype=np.bool_)
            )
            gated_counts = base.count_firmware_detections(probabilities, vad)
            modes[name] = {"model_only": raw_counts, "vad_gated": gated_counts}
            preset_events[name] = {}
            for preset, preset_models in base.PRESETS.items():
                cutoff = preset_models[name]
                events = detection_indices(probabilities, vad, cutoff)
                if len(events) != int(gated_counts[cutoff]):
                    raise RuntimeError(f"Detection replay mismatch for {key}/{name}/{preset}")
                preset_events[name][preset] = list(events)
    return key, duration_s, modes, preset_events


def evaluate(
    cache: Path,
    output: Path,
    max_seconds: float | None,
    workers: int,
) -> dict:
    predictions = prediction_dir(cache, max_seconds)
    model_names = [name for name in base.MODEL_FILES if name != "vad"]
    aggregate = {
        name: {"model_only": np.zeros(255, dtype=np.uint32), "vad_gated": np.zeros(255, dtype=np.uint32)}
        for name in model_names
    }
    identity_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    recording_results: dict[str, dict] = {}
    session_seconds: dict[str, float] = {}
    session_events: dict[str, dict[str, dict[str, list[int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    detector_seconds = 0.0

    paths = [
        predictions / f"{session}_{identity}.npz"
        for session in sorted(EXPECTED_SESSIONS)
        for identity in sorted(EXPECTED_CHANNELS)
    ]
    missing_paths = [str(path) for path in paths if not path.is_file()]
    if missing_paths:
        raise RuntimeError(f"Missing prediction traces: {missing_paths}")

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(evaluate_trace, paths, chunksize=1)
        for index, (key, duration_s, modes, preset_events) in enumerate(results, start=1):
            session, identity = key.split("_", maxsplit=1)
            detector_seconds += duration_s
            previous_duration = session_seconds.setdefault(session, duration_s)
            if abs(previous_duration - duration_s) > 1.0:
                raise RuntimeError(f"Channel duration mismatch in {session}: {key}")
            session_seconds[session] = max(previous_duration, duration_s)
            recording_results[key] = {"duration_s": duration_s, "presets": {}}
            for name in model_names:
                aggregate[name]["model_only"] += modes[name]["model_only"]
                aggregate[name]["vad_gated"] += modes[name]["vad_gated"]
                recording_results[key]["presets"][name] = {}
                for preset in base.PRESETS:
                    events = preset_events[name][preset]
                    count = len(events)
                    recording_results[key]["presets"][name][preset] = count
                    identity_counts[identity][name][preset] += count
                    session_events[session][name][preset].extend(events)
            if index % 25 == 0 or index == len(paths):
                print(f"evaluated {index}/{len(paths)} traces")

    unique_seconds = sum(session_seconds.values())
    detector_hours = detector_seconds / 3600.0
    unique_hours = unique_seconds / 3600.0
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "smoke_test": max_seconds is not None,
        "method": {
            "base_fingerprint": base.cache_fingerprint(),
            "channels_per_session": len(EXPECTED_CHANNELS),
            "recordings": len(recording_results),
            "unique_conversation_hours": unique_hours,
            "detector_channel_hours": detector_hours,
            "synchronized_cluster_tolerance_ms": 1_000,
        },
        "corpus": {
            "record": "https://zenodo.org/records/8122551",
            "archive": {
                "filename": "DipCo.tgz",
                "size": ARCHIVE_SIZE,
                "md5": ARCHIVE_MD5,
                "sha256": ARCHIVE_SHA256,
            },
            "transcript_target_phrase_matches": base.transcript_phrase_matches(cache),
        },
        "cutoffs": {},
        "presets": {},
        "channel_identities": identity_counts,
        "recordings": recording_results,
    }

    for name, modes in aggregate.items():
        result["cutoffs"][name] = {}
        for mode, values in modes.items():
            result["cutoffs"][name][mode] = [
                {
                    "uint8": cutoff,
                    "probability": cutoff / 255.0,
                    "events": int(events),
                    "false_accepts_per_detector_hour": float(events / detector_hours),
                }
                for cutoff, events in enumerate(values)
            ]

    tolerance = round(1_000 / (base.FEATURE_STEP_MS * 3))
    for preset, preset_models in base.PRESETS.items():
        result["presets"][preset] = {}
        for name, cutoff in preset_models.items():
            per_identity = [identity_counts[identity][name][preset] / unique_hours for identity in sorted(EXPECTED_CHANNELS)]
            clustered = sum(
                clustered_count(session_events[session][name][preset], tolerance)
                for session in EXPECTED_SESSIONS
            )
            clustered_interval = base.poisson_interval(clustered, unique_hours)
            aggregate_entry = result["cutoffs"][name]["vad_gated"][cutoff]
            result["presets"][preset][name] = {
                "cutoff_uint8": cutoff,
                "events": aggregate_entry["events"],
                "false_accepts_per_detector_hour": aggregate_entry["false_accepts_per_detector_hour"],
                "per_channel_fah": {
                    "minimum": float(np.min(per_identity)),
                    "median": float(np.median(per_identity)),
                    "p90": float(np.percentile(per_identity, 90)),
                    "maximum": float(np.max(per_identity)),
                },
                "synchronized_acoustic_events": clustered,
                "synchronized_acoustic_events_per_unique_hour": clustered / unique_hours,
                "synchronized_poisson_95": clustered_interval,
            }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_markdown(result, output.with_suffix(".md"))
    return result


def write_markdown(result: dict, path: Path) -> None:
    method = result["method"]
    lines = [
        "# Multichannel DiPCo cutoff results",
        "",
        f"Unique conversation duration: {method['unique_conversation_hours']:.3f} hours.",
        f"Detector exposure across 35 synchronized channels: {method['detector_channel_hours']:.3f} channel-hours.",
        "",
        "| Preset | Model | Cutoff | Aggregate FA/channel-hour | Channel median | Channel p90 | Channel maximum | Synchronized events | Synchronized FA/h |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for preset, models in result["presets"].items():
        for name, values in models.items():
            distribution = values["per_channel_fah"]
            lines.append(
                f"| {preset} | `{name}` | {values['cutoff_uint8']}/255 "
                f"| {values['false_accepts_per_detector_hour']:.3f} "
                f"| {distribution['median']:.3f} | {distribution['p90']:.3f} "
                f"| {distribution['maximum']:.3f} | {values['synchronized_acoustic_events']} "
                f"| {values['synchronized_acoustic_events_per_unique_hour']:.3f} |"
            )
    if result["smoke_test"]:
        lines.extend(("", "> **Smoke test only:** truncated audio; do not use these rates to select cutoffs."))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "infer", "evaluate", "all"))
    parser.add_argument("--cache-dir", type=Path, default=base.DEFAULT_CACHE)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_seconds is not None and args.max_seconds <= 0:
        raise SystemExit("--max-seconds must be positive")
    if args.workers <= 0:
        raise SystemExit("--workers must be positive")
    output = args.output
    if args.max_seconds is not None and output == DEFAULT_OUTPUT:
        output = args.cache_dir / "reports" / f"all-channels-smoke-{args.max_seconds:g}s.json"
    if args.command in ("prepare", "all"):
        prepare(args.cache_dir, args.archive)
    if args.command in ("infer", "all"):
        inference(args.cache_dir, args.archive, args.max_seconds, args.workers)
    if args.command in ("evaluate", "all"):
        result = evaluate(args.cache_dir, output, args.max_seconds, args.workers)
        print(
            f"wrote {output} ({result['method']['unique_conversation_hours']:.3f} unique hours; "
            f"{result['method']['detector_channel_hours']:.3f} channel-hours)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
