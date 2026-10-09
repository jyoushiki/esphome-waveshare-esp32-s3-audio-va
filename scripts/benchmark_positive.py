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
"""Measure relative wake-word recall on the synthetic positive corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numba import njit
from pymicro_features import MicroFrontend
from scipy.signal import fftconvolve, resample_poly

from benchmark_dipco import (
    CORPUS_FILES,
    DEFAULT_CACHE as DEFAULT_DIPCO_CACHE,
    FEATURE_STEP_MS,
    MIN_FEATURE_SLICES_BEFORE_DETECTION,
    MODEL_FILES,
    SAMPLE_RATE,
    SAMPLES_PER_FEATURE,
    SLIDING_WINDOW,
    StreamingModel,
    VAD_CUTOFF,
    rolling_detected,
    verify,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIVE_CACHE = REPO_ROOT / ".benchmark-cache" / "positive"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "benchmarks" / "positive"
PRE_ROLL_SECONDS = 1.5
POST_ROLL_SECONDS = 1.0
DETECTION_GRACE_SECONDS = 0.5
TARGET_SPEECH_DBFS = -24.0
DISPLAY_CUTOFFS = {
    "okay_nabu": (143, 176, 217, 224, 234),
    "hey_jarvis": (212, 235, 247, 252),
    "alexa": (128, 191, 230, 245, 248, 251),
    "hey_mycroft": (237, 242, 253, 254),
}
PRESET_COMPARISONS = {
    "okay_nabu": (217, 224),
    "hey_jarvis": (247, 252),
    "alexa": (230, 245),
    "hey_mycroft": (253, 254),
}
CONDITIONS = ("clean", "room", "dipco_20db", "dipco_10db", "dipco_0db")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_dry_sample(path: Path, expected_sha256: str) -> np.ndarray:
    if sha256_file(path) != expected_sha256:
        raise RuntimeError(f"Generated sample failed SHA-256 verification: {path}")
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
            1,
            2,
            22_050,
            "NONE",
        ):
            raise RuntimeError(f"Unexpected generated WAV format: {path}")
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
    return resample_poly(pcm, 320, 441)


def rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if samples.size else 0.0


def set_rms(samples: np.ndarray, target_dbfs: float) -> np.ndarray:
    current = rms(samples)
    if current == 0:
        raise RuntimeError("Cannot normalize a silent positive sample")
    return samples * (10 ** (target_dbfs / 20.0) / current)


def room_response() -> np.ndarray:
    response = np.zeros(int(0.24 * SAMPLE_RATE), dtype=np.float64)
    response[0] = 1.0
    for delay_ms, gain in ((23, 0.36), (51, -0.20), (87, 0.16), (143, -0.10), (211, 0.06)):
        response[int(delay_ms * SAMPLE_RATE / 1000)] = gain
    return response


def read_background(cache: Path, sample_index: int, condition_index: int, frames: int) -> np.ndarray:
    artifact = CORPUS_FILES[(sample_index * 3 + condition_index) % len(CORPUS_FILES)]
    path = cache / "audio" / artifact.filename
    with wave.open(str(path), "rb") as wav:
        max_start = wav.getnframes() - frames
        if max_start < 0:
            raise RuntimeError(f"Background file is shorter than a trial: {path}")
        seed = 20_261_009 + sample_index * 101 + condition_index
        start = seed % (max_start + 1)
        wav.setpos(start)
        return np.frombuffer(wav.readframes(frames), dtype="<i2").astype(np.float64) / 32768.0


def build_trial(
    dry: np.ndarray,
    condition: str,
    sample_index: int,
    dipco_cache: Path,
) -> tuple[np.ndarray, float, float]:
    speech = set_rms(dry, TARGET_SPEECH_DBFS)
    if condition != "clean":
        speech = fftconvolve(speech, room_response(), mode="full")
        speech = set_rms(speech, TARGET_SPEECH_DBFS)

    pre_frames = int(PRE_ROLL_SECONDS * SAMPLE_RATE)
    post_frames = int(POST_ROLL_SECONDS * SAMPLE_RATE)
    trial = np.zeros(pre_frames + speech.size + post_frames, dtype=np.float64)
    trial[pre_frames : pre_frames + speech.size] = speech

    if condition.startswith("dipco_"):
        snr_db = float(condition.removeprefix("dipco_").removesuffix("db"))
        condition_index = CONDITIONS.index(condition)
        background = read_background(dipco_cache, sample_index, condition_index, trial.size)
        background = set_rms(background, TARGET_SPEECH_DBFS - snr_db)
        trial += background

    peak = float(np.max(np.abs(trial)))
    if peak > 0.98:
        trial *= 0.98 / peak
    pcm = np.rint(np.clip(trial, -1.0, 1.0) * 32767.0).astype("<i2")
    phrase_start = PRE_ROLL_SECONDS
    phrase_end = PRE_ROLL_SECONDS + speech.size / SAMPLE_RATE
    return pcm, phrase_start, phrase_end


def infer_trial(pcm: np.ndarray, models: dict[str, StreamingModel]) -> dict[str, np.ndarray]:
    for model in models.values():
        model.reset()
    frontend = MicroFrontend()
    probabilities: dict[str, list[int]] = {name: [] for name in models}
    usable = pcm.size - pcm.size % SAMPLES_PER_FEATURE

    for offset in range(0, usable, SAMPLES_PER_FEATURE):
        block = pcm[offset : offset + SAMPLES_PER_FEATURE].tobytes()
        frontend_result = frontend.process_samples(block)
        if not frontend_result.features:
            continue
        outputs = {name: model.feed(frontend_result.features) for name, model in models.items()}
        if all(value is not None for value in outputs.values()):
            for name, value in outputs.items():
                probabilities[name].append(value)
        elif any(value is not None for value in outputs.values()):
            raise RuntimeError("Model strides are not aligned")

    return {name: np.asarray(values, dtype=np.uint8) for name, values in probabilities.items()}


@njit
def score_cutoffs(
    probabilities: np.ndarray,
    vad: np.ndarray,
    phrase_start_s: float,
    phrase_end_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    detected = np.zeros(255, dtype=np.bool_)
    pre_phrase_events = np.zeros(255, dtype=np.uint16)
    recent = np.zeros((255, SLIDING_WINDOW), dtype=np.uint16)
    ignore_slices = np.full(255, -MIN_FEATURE_SLICES_BEFORE_DETECTION, dtype=np.int16)
    previous = np.zeros(255, dtype=np.uint16)

    for index in range(probabilities.size):
        probability = int(probabilities[index])
        ring_index = index % SLIDING_WINDOW
        event_time_s = (index + 1) * 3 * FEATURE_STEP_MS / 1000.0
        for cutoff in range(1, 255):
            if previous[cutoff] < cutoff:
                ignore_slices[cutoff] = min(ignore_slices[cutoff] + 2, 0)
            recent[cutoff, ring_index] = probability
            previous[cutoff] = probability
            if probability < cutoff:
                ignore_slices[cutoff] = min(ignore_slices[cutoff] + 1, 0)

            accepted = (
                ignore_slices[cutoff] >= 0
                and recent[cutoff].sum() > cutoff * SLIDING_WINDOW
                and vad[index]
            )
            if not accepted:
                continue
            if event_time_s < phrase_start_s:
                pre_phrase_events[cutoff] += 1
            elif event_time_s <= phrase_end_s + DETECTION_GRACE_SECONDS:
                detected[cutoff] = True

            recent[cutoff].fill(0)
            previous[cutoff] = 0
            ignore_slices[cutoff] = -MIN_FEATURE_SLICES_BEFORE_DETECTION

    return detected, pre_phrase_events


def cluster_bootstrap_intervals(
    outcomes: np.ndarray,
    speaker_ids: np.ndarray,
    seed: int,
    iterations: int = 10_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Bootstrap recall across speakers while keeping their variants grouped."""
    speakers = np.unique(speaker_ids)
    cluster_means = np.stack([outcomes[speaker_ids == speaker].mean(axis=0) for speaker in speakers])
    generator = np.random.default_rng(seed)
    weights = generator.multinomial(
        speakers.size, np.full(speakers.size, 1.0 / speakers.size), size=iterations
    )
    distribution = weights @ cluster_means / speakers.size
    return np.percentile(distribution, 2.5, axis=0), np.percentile(distribution, 97.5, axis=0)


def evaluate(manifest_path: Path, dipco_cache: Path, split: str, output: Path) -> dict:
    manifest_path = manifest_path.resolve()
    dipco_cache = dipco_cache.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_name = manifest["model"]
    if model_name not in DISPLAY_CUTOFFS:
        raise RuntimeError(f"Unsupported wake-word model in manifest: {model_name}")
    model_paths = {
        name: dipco_cache / "models" / f"{name}.tflite" for name in (model_name, "vad")
    }
    for name, path in model_paths.items():
        artifact = MODEL_FILES[name]
        if not path.is_file() or path.stat().st_size != artifact.size or sha256_file(path) != artifact.sha256:
            raise RuntimeError(f"Missing or invalid pinned model; run the DiPCo prepare command: {path}")
    for artifact in CORPUS_FILES:
        path = dipco_cache / "audio" / artifact.filename
        if not verify(path, artifact):
            raise RuntimeError(f"Missing or invalid pinned DiPCo background: {path}")
    models = {name: StreamingModel(path) for name, path in model_paths.items()}

    counts = {
        condition: {
            "trials": 0,
            "detected": np.zeros(255, dtype=np.uint32),
            "pre_phrase_events": np.zeros(255, dtype=np.uint32),
            "outcomes": [],
        }
        for condition in CONDITIONS
    }
    selected_samples = [sample for sample in manifest["samples"] if sample["split"] == split]

    for sample_index, sample in enumerate(selected_samples):
        dry = read_dry_sample(manifest_path.parent / sample["file"], sample["sha256"])
        for condition in CONDITIONS:
            pcm, phrase_start, phrase_end = build_trial(dry, condition, sample_index, dipco_cache)
            probabilities = infer_trial(pcm, models)
            vad = rolling_detected(probabilities["vad"], VAD_CUTOFF)
            detections, early = score_cutoffs(probabilities[model_name], vad, phrase_start, phrase_end)
            counts[condition]["trials"] += 1
            counts[condition]["detected"] += detections
            counts[condition]["pre_phrase_events"] += early
            counts[condition]["outcomes"].append(detections)
        print(f"[{sample_index + 1}/{len(selected_samples)}] {sample['file']}")

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic_relative_recall",
        "model": model_name,
        "split": split,
        "corpus": {
            "manifest": str(manifest_path.relative_to(REPO_ROOT)),
            "manifest_sha256": sha256_file(manifest_path),
            "phrase": manifest["phrase"],
            "seed": manifest["seed"],
            "voice": manifest["voice"],
            "speakers": manifest["speakers"],
            "variants_per_speaker": manifest["variants_per_speaker"],
            "samples": len(manifest["samples"]),
        },
        "method": {
            "pre_roll_seconds": PRE_ROLL_SECONDS,
            "post_roll_seconds": POST_ROLL_SECONDS,
            "detection_grace_seconds": DETECTION_GRACE_SECONDS,
            "target_speech_dbfs": TARGET_SPEECH_DBFS,
            "conditions": list(CONDITIONS),
            "vad_cutoff_uint8": VAD_CUTOFF,
        },
        "cutoffs": {},
        "candidate_comparison": {},
    }

    speaker_ids = np.asarray([sample["speaker_id"] for sample in selected_samples], dtype=np.int16)
    for condition_index, (condition, values) in enumerate(counts.items()):
        trials = values["trials"]
        outcomes = np.stack(values["outcomes"])
        lower, upper = cluster_bootstrap_intervals(
            outcomes, speaker_ids, seed=20_261_009 + condition_index
        )
        result["cutoffs"][condition] = []
        for cutoff in range(1, 255):
            successes = int(values["detected"][cutoff])
            result["cutoffs"][condition].append(
                {
                    "uint8": cutoff,
                    "probability": cutoff / 255.0,
                    "trials": trials,
                    "detected": successes,
                    "recall": successes / trials,
                    "speaker_cluster_bootstrap_95": [float(lower[cutoff]), float(upper[cutoff])],
                    "pre_phrase_events": int(values["pre_phrase_events"][cutoff]),
                }
            )
        baseline, candidate = PRESET_COMPARISONS[model_name]
        difference = outcomes[:, candidate].astype(np.int8) - outcomes[:, baseline].astype(np.int8)
        difference_lower, difference_upper = cluster_bootstrap_intervals(
            difference[:, np.newaxis], speaker_ids, seed=20_262_009 + condition_index
        )
        result["candidate_comparison"][condition] = {
            "baseline_uint8": baseline,
            "candidate_uint8": candidate,
            "baseline_detected": int(values["detected"][baseline]),
            "candidate_detected": int(values["detected"][candidate]),
            "recall_difference": float(difference.mean()),
            "speaker_cluster_bootstrap_95": [
                float(difference_lower[0]),
                float(difference_upper[0]),
            ],
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_markdown(result, output.with_suffix(".md"))
    return result


def cutoff_row(result: dict, condition: str, cutoff: int) -> dict:
    return result["cutoffs"][condition][cutoff - 1]


def write_markdown(result: dict, path: Path) -> None:
    def signed_percent(value: float) -> str:
        return "0.0%" if abs(value) < 0.0005 else f"{value:+.1%}"

    lines = [
        f"# {result['model']} synthetic positive results: {result['split']}",
        "",
        "> These results measure synthetic relative recall. The hardware check is documented separately.",
        "",
        "| Condition | Cutoff | Detected | Recall (speaker-cluster bootstrap 95%) | Early events |",
        "|---|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        for cutoff in DISPLAY_CUTOFFS[result["model"]]:
            row = cutoff_row(result, condition, cutoff)
            interval = row["speaker_cluster_bootstrap_95"]
            lines.append(
                f"| `{condition}` | {cutoff}/255 ({row['probability']:.3f}) "
                f"| {row['detected']}/{row['trials']} "
                f"| {row['recall']:.1%} ({interval[0]:.1%}–{interval[1]:.1%}) "
                f"| {row['pre_phrase_events']} |"
            )
    lines.extend(
        (
            "",
            "## Fixed candidate comparison",
            "",
            "| Condition | Baseline detected | Candidate detected | Recall change (speaker-cluster bootstrap 95%) |",
            "|---|---:|---:|---:|",
        )
    )
    for condition in CONDITIONS:
        comparison = result["candidate_comparison"][condition]
        interval = comparison["speaker_cluster_bootstrap_95"]
        lines.append(
            f"| `{condition}` | {comparison['baseline_detected']} @ {comparison['baseline_uint8']} "
            f"| {comparison['candidate_detected']} @ {comparison['candidate_uint8']} "
            f"| {signed_percent(comparison['recall_difference'])} "
            f"({signed_percent(interval[0])}–{signed_percent(interval[1])}) |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=tuple(DISPLAY_CUTOFFS), default="alexa")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--dipco-cache", type=Path, default=DEFAULT_DIPCO_CACHE)
    parser.add_argument("--split", choices=("calibration", "validation"), default="calibration")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = args.manifest or (
        DEFAULT_POSITIVE_CACHE / "dry" / f"{args.model}-vctk-109x3" / "manifest.json"
    )
    output = args.output or DEFAULT_OUTPUT_DIR / f"results-{args.model}-{args.split}.json"
    result = evaluate(manifest, args.dipco_cache, args.split, output)
    trials = next(iter(result["cutoffs"].values()))[0]["trials"]
    print(f"wrote {output} ({trials} {args.split} trials per condition)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
