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
"""Validate the firmware's microWakeWord cutoffs against raw DiPCo audio.

The implementation intentionally mirrors ESPHome's quantized streaming path:
10 ms frontend features, three features per model invocation, uint8 model
probabilities, a five-prediction rolling sum and a strict ``>`` cutoff test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
import wave
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable

import numpy as np
from ai_edge_litert.interpreter import Interpreter
from numba import njit
from pymicro_features import MicroFrontend
from scipy.stats import chi2


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPO_ROOT / ".benchmark-cache" / "dipco"
DEFAULT_JSON = REPO_ROOT / "benchmarks" / "dipco" / "results.json"

CORPUS_REPO = "huckiyang/DiPCo"
CORPUS_REVISION = "e2b29d3d0d88692c744feb15e290f7316b68014e"
MODEL_REPO = "esphome/micro-wake-word-models"
MODEL_REVISION = "05b65922cc433c9df13e98e32a7fe520758c837e"

SAMPLE_RATE = 16_000
FEATURE_STEP_MS = 10
SAMPLES_PER_FEATURE = SAMPLE_RATE * FEATURE_STEP_MS // 1000
SLIDING_WINDOW = 5
MIN_FEATURE_SLICES_BEFORE_DETECTION = 100
VAD_CUTOFF = 127  # int(0.5 * 255), exactly as ESPHome code generation.
CACHE_SCHEMA = 2


@dataclass(frozen=True)
class Artifact:
    path: str
    size: int
    sha256: str

    @property
    def filename(self) -> str:
        return Path(self.path).name


CORPUS_FILES = (
    Artifact("audio/eval/S01_U01.CH1.wav", 91_047_044, "c8684d10e216ed328ab0bb1f12f75af694f69b64aa49a069fd56b0c624c8d81f"),
    Artifact("audio/dev/S02_U01.CH1.wav", 57_618_044, "ba50a6772a195aba58afa651d840b137024e06f0f3d0c3e8cfdd74630d92725c"),
    Artifact("audio/eval/S03_U04.CH1.wav", 89_497_044, "56d626f444c522b362e6746678ad49e5eee9db119c0be0e33552d2f2c9fdf066"),
    Artifact("audio/dev/S04_U01.CH1.wav", 88_168_044, "aadaea7aa4ee0aae7dd2baa65c69a777ee839334b3f5943348fd8bd78ef437b1"),
    Artifact("audio/dev/S05_U04.CH1.wav", 86_917_044, "e6547cc9d9703e06652348578063dbc59f7d162413e82ea3f7c28f4fb7b71118"),
    Artifact("audio/eval/S06_U04.CH1.wav", 38_527_044, "bd02fbe45b47806e68c9ad1d66a134df7b23ff2d7204d9145a51f171844d8502"),
    Artifact("audio/eval/S07_U01.CH1.wav", 50_408_044, "57c90c94da96cbb4799892ac424cad57216e014c3c4b9dc3c992f87c3bbf73aa"),
    Artifact("audio/eval/S08_U01.CH1.wav", 30_364_044, "4fe5be05178306035d735e694550ba670dc0eb2eae995f888038609a0d1b08b9"),
    Artifact("audio/dev/S09_U04.CH1.wav", 43_328_044, "62cba96d17269abd371a9723e38381a4a34116843b942e36ef3502d065342543"),
    Artifact("audio/dev/S10_U04.CH1.wav", 38_718_044, "b3a4a27485aaa1c8b226da901fee7e200add317f23f75089418c9cc61d7bb7f3"),
)

TRANSCRIPT_FILES = (
    Artifact("transcriptions/eval/S01.json", 461_507, "8de69551abbce18d7729d0bdfc83c167775627e1dc099074b0dc76495a5e120e"),
    Artifact("transcriptions/dev/S02.json", 233_422, "595e77a50e8107738b85651229a8c1d4ccf2b8e4f1df00a03db61a210c3c3408"),
    Artifact("transcriptions/eval/S03.json", 572_175, "47395f6468603ff876258b20e220106fda17238a65dc344bb811b4a502c2c666"),
    Artifact("transcriptions/dev/S04.json", 640_121, "b0e4ba3e7453c7cf0630ad0a76325c40f62dec8b38eb8e0285fc0c4626ec0712"),
    Artifact("transcriptions/dev/S05.json", 509_968, "1ff3c23387283bb0319d7a628e77d2535b068a6fdce923e3ccf522f8a3699e55"),
    Artifact("transcriptions/eval/S06.json", 233_053, "e51d553a7e9f8b508bf4a5846ba79ed42f0935dbfd9bdbccdff73773734e361e"),
    Artifact("transcriptions/eval/S07.json", 293_931, "7b9faea3b75c64da85e68eb28b8200a007bf8e93b011626e7143ca7afd36a4b1"),
    Artifact("transcriptions/eval/S08.json", 166_689, "4e3b1e48b9a28b117089ceb86364b43f32714265827dc6ffc95af2137e38643a"),
    Artifact("transcriptions/dev/S09.json", 255_179, "8d63eb9655c058660e7e616455f0dfe86b92977a3af060267c1a26cac4697ffb"),
    Artifact("transcriptions/dev/S10.json", 222_548, "a077db402c2129911ad9375e301f1ad81cc11d1f2e37e7afc49873b908d0e9eb"),
)

MODEL_FILES = {
    "okay_nabu": Artifact("models/v2/okay_nabu.tflite", 60_264, "0689abe1912a95a3318a0d8cb2e67bad0cbcfe3e24dd6e050c75debddfb6f891"),
    "hey_jarvis": Artifact("models/v2/hey_jarvis.tflite", 52_272, "21a7976add39ee24ec96c63d96b7aaa18e24d1d9824b963e451da8feb4b78b77"),
    "alexa": Artifact("models/v2/alexa.tflite", 55_856, "9011a8155b04de858c48038529235cbc0e42e9fca05a55bf588cb80a653a723b"),
    "hey_mycroft": Artifact("models/v2/hey_mycroft.tflite", 57_248, "c2a9b6ed51182db72e014781d5a4ece1929dc232a40b5b4be384f0295f0e1571"),
    "vad": Artifact("models/v2/vad.tflite", 34_328, "7aa4db6d5fb7c5358609f6931e7847d303c16a43d178638bc14104f50d7eff5f"),
}

# Quantized uint8 cutoff values from waveshare-va.yaml.
PRESETS = {
    "Least sensitive": {"okay_nabu": 224, "hey_jarvis": 252, "alexa": 245, "hey_mycroft": 254},
    "Slightly sensitive": {"okay_nabu": 217, "hey_jarvis": 247, "alexa": 230, "hey_mycroft": 253},
    "Moderately sensitive": {"okay_nabu": 176, "hey_jarvis": 235, "alexa": 191, "hey_mycroft": 242},
    "Very sensitive": {"okay_nabu": 143, "hey_jarvis": 212, "alexa": 128, "hey_mycroft": 237},
}


def cache_fingerprint() -> str:
    """Identify every input that can change cached probability traces."""
    inputs = {
        "schema": CACHE_SCHEMA,
        "corpus_revision": CORPUS_REVISION,
        "model_revision": MODEL_REVISION,
        "models": {name: artifact.sha256 for name, artifact in MODEL_FILES.items()},
        "sample_rate": SAMPLE_RATE,
        "feature_step_ms": FEATURE_STEP_MS,
    }
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def prediction_dir(cache: Path, max_seconds: float | None) -> Path:
    run = "full" if max_seconds is None else f"smoke-{max_seconds:g}s"
    return cache / "predictions" / cache_fingerprint() / run


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, artifact: Artifact) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == artifact.size
        and sha256_file(path) == artifact.sha256
    )


def download(url: str, destination: Path, artifact: Artifact) -> None:
    if verify(destination, artifact):
        print(f"verified {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    print(f"downloading {destination.name} ({artifact.size / 1_000_000:.1f} MB)")
    request = urllib.request.Request(url, headers={"User-Agent": "waveshare-va-dipco-benchmark/1"})
    with urllib.request.urlopen(request) as response, partial.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    if not verify(partial, artifact):
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded artifact failed size/SHA-256 verification: {url}")
    partial.replace(destination)


def prepare(cache: Path) -> None:
    audio_dir = cache / "audio"
    model_dir = cache / "models"
    for artifact in CORPUS_FILES:
        url = f"https://huggingface.co/datasets/{CORPUS_REPO}/resolve/{CORPUS_REVISION}/{artifact.path}"
        download(url, audio_dir / artifact.filename, artifact)
    for artifact in TRANSCRIPT_FILES:
        url = f"https://huggingface.co/datasets/{CORPUS_REPO}/resolve/{CORPUS_REVISION}/{artifact.path}"
        download(url, cache / "transcriptions" / artifact.filename, artifact)
    for name, artifact in MODEL_FILES.items():
        url = f"https://github.com/{MODEL_REPO}/raw/{MODEL_REVISION}/{artifact.path}"
        download(url, model_dir / f"{name}.tflite", artifact)


class StreamingModel:
    """TFLite streaming inference with the same quantization as upstream."""

    def __init__(self, path: Path):
        self.interpreter = Interpreter(model_path=str(path))
        self.interpreter.allocate_tensors()
        self.inputs = self.interpreter.get_input_details()
        self.output = self.interpreter.get_output_details()[0]
        self.input = self.inputs[0]
        self.stride = int(self.input["shape"][1])
        if tuple(self.input["shape"])[::2] != (1, 40) or self.input["dtype"] != np.int8:
            raise RuntimeError(f"Unexpected model input: {self.input}")
        if self.output["dtype"] != np.uint8:
            raise RuntimeError(f"Unexpected model output: {self.output}")
        for tensor in self.inputs:
            self.interpreter.set_tensor(tensor["index"], np.zeros(tensor["shape"], dtype=tensor["dtype"]))
        self.pending: list[np.ndarray] = []

    def reset(self) -> None:
        """Reset recurrent model state before an independent audio stream."""
        self.interpreter.reset_all_variables()
        for tensor in self.inputs:
            self.interpreter.set_tensor(tensor["index"], np.zeros(tensor["shape"], dtype=tensor["dtype"]))
        self.pending.clear()

    def feed(self, features: Iterable[float]) -> int | None:
        # pymicro-features returns the frontend's integer values divided by
        # 25.6. Reconstruct those integers, then apply ESPHome's exact rounded
        # fixed-point conversion from MicroWakeWord::generate_features_().
        frontend_values = np.rint(np.asarray(features, dtype=np.float32) * 25.6).astype(np.int32)
        quantized_features = ((frontend_values * 256 + 333) // 666) - 128
        self.pending.append(np.clip(quantized_features, -128, 127).astype(np.int8))
        if len(self.pending) < self.stride:
            return None
        chunk = np.asarray(self.pending, dtype=np.int8)
        self.pending.clear()
        self.interpreter.set_tensor(self.input["index"], chunk.reshape(self.input["shape"]))
        self.interpreter.invoke()
        return int(self.interpreter.get_tensor(self.output["index"])[0][0])


def validate_wav(handle: wave.Wave_read, path: Path) -> None:
    actual = (handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getcomptype())
    expected = (1, 2, SAMPLE_RATE, "NONE")
    if actual != expected:
        raise RuntimeError(f"Expected mono 16-bit {SAMPLE_RATE} Hz PCM for {path}, got {actual}")


def generate_session_probabilities(
    audio_path: Path | BinaryIO,
    model_paths: dict[str, Path],
    max_seconds: float | None,
    *,
    display_name: str | None = None,
) -> tuple[dict[str, np.ndarray], float]:
    models = {name: StreamingModel(path) for name, path in model_paths.items()}
    strides = {model.stride for model in models.values()}
    if strides != {3}:
        raise RuntimeError(f"Expected every model to consume three feature slices, got {sorted(strides)}")
    probabilities: dict[str, list[int]] = {name: [] for name in models}
    frontend = MicroFrontend()

    wave_source = str(audio_path) if isinstance(audio_path, Path) else audio_path
    source_name = Path(display_name) if display_name is not None else Path(str(audio_path))
    with wave.open(wave_source, "rb") as wav:
        validate_wav(wav, source_name)
        frame_limit = wav.getnframes()
        if max_seconds is not None:
            frame_limit = min(frame_limit, int(max_seconds * SAMPLE_RATE))
        frames_read = 0
        while frames_read + SAMPLES_PER_FEATURE <= frame_limit:
            pcm = wav.readframes(SAMPLES_PER_FEATURE)
            if len(pcm) != SAMPLES_PER_FEATURE * 2:
                break
            frames_read += SAMPLES_PER_FEATURE
            frontend_result = frontend.process_samples(pcm)
            if not frontend_result.features:
                continue
            outputs = {name: model.feed(frontend_result.features) for name, model in models.items()}
            if all(value is not None for value in outputs.values()):
                for name, value in outputs.items():
                    probabilities[name].append(value)
            elif any(value is not None for value in outputs.values()):
                raise RuntimeError("Model strides are not aligned")

    return ({name: np.asarray(values, dtype=np.uint8) for name, values in probabilities.items()}, frames_read / SAMPLE_RATE)


def inference(cache: Path, max_seconds: float | None) -> dict[str, float]:
    audio_dir = cache / "audio"
    model_paths = {name: cache / "models" / f"{name}.tflite" for name in MODEL_FILES}
    predictions = prediction_dir(cache, max_seconds)
    predictions.mkdir(parents=True, exist_ok=True)
    durations: dict[str, float] = {}

    for index, artifact in enumerate(CORPUS_FILES, start=1):
        audio_path = audio_dir / artifact.filename
        output_path = predictions / f"{audio_path.stem}.npz"
        if output_path.exists():
            with np.load(output_path) as cached:
                if str(cached["fingerprint"]) != cache_fingerprint():
                    raise RuntimeError(f"Stale prediction cache: {output_path}")
                durations[audio_path.stem] = float(cached["duration_s"])
            print(f"[{index}/{len(CORPUS_FILES)}] cached {audio_path.name}")
            continue
        started = time.monotonic()
        probabilities, duration_s = generate_session_probabilities(audio_path, model_paths, max_seconds)
        np.savez_compressed(
            output_path,
            fingerprint=np.asarray(cache_fingerprint()),
            duration_s=np.asarray(duration_s),
            **probabilities,
        )
        durations[audio_path.stem] = duration_s
        print(
            f"[{index}/{len(CORPUS_FILES)}] {audio_path.name}: "
            f"{duration_s / 60:.1f} min in {time.monotonic() - started:.1f}s"
        )
    return durations


def rolling_detected(probabilities: np.ndarray, cutoff: int) -> np.ndarray:
    """Return ESPHome's rolling decision at every prediction, including warm-up zeros."""
    recent = deque([0] * SLIDING_WINDOW, maxlen=SLIDING_WINDOW)
    detected = np.zeros(probabilities.size, dtype=np.bool_)
    for index, probability in enumerate(probabilities):
        recent.append(int(probability))
        detected[index] = sum(recent) > cutoff * SLIDING_WINDOW
    return detected


@njit
def count_firmware_detections(probabilities: np.ndarray, vad: np.ndarray) -> np.ndarray:
    """Replay ESPHome's state for every cutoff in one compiled pass."""
    counts = np.zeros(255, dtype=np.uint32)
    recent = np.zeros((255, SLIDING_WINDOW), dtype=np.uint16)
    ignore_slices = np.full(255, -MIN_FEATURE_SLICES_BEFORE_DETECTION, dtype=np.int16)
    previous = np.zeros(255, dtype=np.uint16)
    use_vad = vad.size != 0

    for index in range(probabilities.size):
        probability = int(probabilities[index])
        ring_index = index % SLIDING_WINDOW
        for cutoff in range(255):
            # One prediction follows three feature slices. The first two see
            # the preceding probability; the third sees the new one.
            if previous[cutoff] < cutoff:
                ignore_slices[cutoff] = min(ignore_slices[cutoff] + 2, 0)
            recent[cutoff, ring_index] = probability
            previous[cutoff] = probability
            if probability < cutoff:
                ignore_slices[cutoff] = min(ignore_slices[cutoff] + 1, 0)

            if ignore_slices[cutoff] < 0:
                continue
            if recent[cutoff].sum() <= cutoff * SLIDING_WINDOW:
                continue
            if use_vad and not vad[index]:
                continue

            counts[cutoff] += 1
            recent[cutoff].fill(0)
            previous[cutoff] = 0
            ignore_slices[cutoff] = -MIN_FEATURE_SLICES_BEFORE_DETECTION
    return counts


def poisson_interval(events: int, hours: float, confidence: float = 0.95) -> tuple[float, float]:
    alpha = 1.0 - confidence
    lower = 0.0 if events == 0 else 0.5 * chi2.ppf(alpha / 2, 2 * events) / hours
    upper = 0.5 * chi2.ppf(1 - alpha / 2, 2 * (events + 1)) / hours
    return float(lower), float(upper)


def transcript_phrase_matches(cache: Path) -> dict[str, list[dict[str, str]]]:
    phrases = {
        "okay_nabu": "okay nabu",
        "hey_jarvis": "hey jarvis",
        "alexa": "alexa",
        "hey_mycroft": "hey mycroft",
    }
    matches: dict[str, list[dict[str, str]]] = {name: [] for name in phrases}
    for artifact in TRANSCRIPT_FILES:
        session = Path(artifact.filename).stem
        utterances = json.loads((cache / "transcriptions" / artifact.filename).read_text(encoding="utf-8"))
        for index, utterance in enumerate(utterances):
            normalized = re.sub(r"[^a-z0-9]+", " ", utterance["words"].lower()).strip()
            for name, phrase in phrases.items():
                if re.search(rf"\b{re.escape(phrase)}\b", normalized):
                    matches[name].append({"session": session, "utterance_index": str(index)})
    return matches


def evaluate(cache: Path, output: Path, max_seconds: float | None) -> dict:
    predictions = prediction_dir(cache, max_seconds)
    counts = {
        name: {"model_only": np.zeros(255, dtype=np.uint32), "vad_gated": np.zeros(255, dtype=np.uint32)}
        for name in MODEL_FILES
        if name != "vad"
    }
    total_seconds = 0.0

    for artifact in CORPUS_FILES:
        path = predictions / f"{Path(artifact.filename).stem}.npz"
        with np.load(path) as session:
            if str(session["fingerprint"]) != cache_fingerprint():
                raise RuntimeError(f"Stale prediction cache: {path}")
            total_seconds += float(session["duration_s"])
            vad = rolling_detected(session["vad"], VAD_CUTOFF)
            for name in counts:
                if session[name].shape != vad.shape:
                    raise RuntimeError(f"Probability length mismatch for {name} in {path}")
                probabilities = session[name]
                counts[name]["model_only"] += count_firmware_detections(
                    probabilities, np.empty(0, dtype=np.bool_)
                )
                counts[name]["vad_gated"] += count_firmware_detections(probabilities, vad)

    hours = total_seconds / 3600.0
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "smoke_test": max_seconds is not None,
        "method": {
            "sample_rate_hz": SAMPLE_RATE,
            "feature_step_ms": FEATURE_STEP_MS,
            "model_stride_features": 3,
            "prediction_step_ms": 30,
            "sliding_window_predictions": SLIDING_WINDOW,
            "strict_greater_than": True,
            "minimum_feature_slices_before_detection": MIN_FEATURE_SLICES_BEFORE_DETECTION,
            "vad_cutoff_uint8": VAD_CUTOFF,
        },
        "corpus": {
            "repo": CORPUS_REPO,
            "revision": CORPUS_REVISION,
            "duration_hours": hours,
            "files": [artifact.__dict__ for artifact in CORPUS_FILES],
            "transcriptions": [artifact.__dict__ for artifact in TRANSCRIPT_FILES],
            "transcript_target_phrase_matches": transcript_phrase_matches(cache),
        },
        "models": {
            "repo": MODEL_REPO,
            "revision": MODEL_REVISION,
            "files": {name: artifact.__dict__ for name, artifact in MODEL_FILES.items()},
        },
        "cutoffs": {},
        "presets": {},
    }

    for name, modes in counts.items():
        result["cutoffs"][name] = {}
        for mode, values in modes.items():
            result["cutoffs"][name][mode] = [
                {
                    "uint8": cutoff,
                    "probability": cutoff / 255.0,
                    "events": int(events),
                    "false_accepts_per_hour": float(events / hours),
                    "poisson_95": poisson_interval(int(events), hours),
                }
                for cutoff, events in enumerate(values)
            ]

    for preset, models in PRESETS.items():
        result["presets"][preset] = {}
        for name, cutoff in models.items():
            result["presets"][preset][name] = {
                mode: result["cutoffs"][name][mode][cutoff] for mode in ("model_only", "vad_gated")
            }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_markdown(result, output.with_suffix(".md"))
    return result


def write_markdown(result: dict, path: Path) -> None:
    lines = [
        "# DiPCo cutoff results",
        "",
        f"Corpus duration: {result['corpus']['duration_hours']:.3f} hours.",
        "Rates in parentheses include the exact Poisson 95% interval.",
        "",
        "| Preset | Model | Cutoff | Model-only FA/h | VAD-gated FA/h |",
        "|---|---|---:|---:|---:|",
    ]
    for preset, models in result["presets"].items():
        for name, modes in models.items():
            raw = modes["model_only"]
            gated = modes["vad_gated"]
            raw_ci = raw["poisson_95"]
            gated_ci = gated["poisson_95"]
            lines.append(
                f"| {preset} | `{name}` | {raw['uint8']}/255 ({raw['probability']:.3f}) "
                f"| {raw['false_accepts_per_hour']:.3f} ({raw_ci[0]:.3f}–{raw_ci[1]:.3f}) "
                f"| {gated['false_accepts_per_hour']:.3f} ({gated_ci[0]:.3f}–{gated_ci[1]:.3f}) |"
            )
    if result["smoke_test"]:
        lines.extend(("", "> **Smoke test only:** truncated audio; do not use these rates to select cutoffs."))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "infer", "evaluate", "all"))
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--max-seconds", type=float, help="Process at most this many seconds from each session")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_seconds is not None and args.max_seconds <= 0:
        raise SystemExit("--max-seconds must be positive")
    output = args.output
    if args.max_seconds is not None and output == DEFAULT_JSON:
        output = args.cache_dir / "reports" / f"smoke-{args.max_seconds:g}s.json"
    if args.command in ("prepare", "all"):
        prepare(args.cache_dir)
    if args.command in ("infer", "all"):
        inference(args.cache_dir, args.max_seconds)
    if args.command in ("evaluate", "all"):
        result = evaluate(args.cache_dir, output, args.max_seconds)
        print(f"wrote {output} ({result['corpus']['duration_hours']:.3f} hours)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
