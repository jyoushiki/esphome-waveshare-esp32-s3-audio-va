#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "numpy==2.3.4",
#   "piper-tts==1.3.0",
# ]
# ///
"""Generate a reproducible synthetic positive wake-word corpus with Piper."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from piper import PiperVoice, SynthesisConfig


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPO_ROOT / ".benchmark-cache" / "positive"
VOICE_REPO = "rhasspy/piper-voices"
VOICE_REVISION = "b145f2ac26522d6a2ccde0164b7b0e48b1e3199c"
VOICE_PATH = "en/en_GB/vctk/medium/en_GB-vctk-medium.onnx"
VOICE_SIZE = 76_952_753
VOICE_SHA256 = "4e9fc85ab9009385319fc6bae7f55577f8a2d7ee77fd9159a5500eb6531f41e6"
CONFIG_SIZE = 6_637
CONFIG_SHA256 = "7f85e6391ed0f7f46e4abd19345929a16be931a0c9945086f96692dce2087fa8"
PHRASES = {
    "okay_nabu": "Okay Nabu.",
    "hey_jarvis": "Hey Jarvis.",
    "alexa": "Alexa.",
    "hey_mycroft": "Hey Mycroft.",
}
DEFAULT_SPEAKERS = 109
DEFAULT_VARIANTS = 3
GENERATION_SEED = 20_261_009

LENGTH_SCALES = (0.8, 1.0, 1.2)
NOISE_SCALES = (0.5, 0.667, 0.8)
NOISE_W_SCALES = (0.6, 0.8, 1.0)


@dataclass(frozen=True)
class Sample:
    file: str
    speaker_id: int
    variant: int
    split: str
    length_scale: float
    noise_scale: float
    noise_w_scale: float
    sample_rate_hz: int
    duration_s: float
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, size: int, digest: str) -> None:
    if destination.is_file() and destination.stat().st_size == size and sha256_file(destination) == digest:
        print(f"verified {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    print(f"downloading {destination.name} ({size / 1_000_000:.1f} MB)")
    request = urllib.request.Request(url, headers={"User-Agent": "waveshare-va-positive-benchmark/1"})
    with urllib.request.urlopen(request) as response, partial.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    if partial.stat().st_size != size or sha256_file(partial) != digest:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded artifact failed size/SHA-256 verification: {url}")
    partial.replace(destination)


def prepare(cache: Path) -> tuple[Path, Path]:
    voice_dir = cache / "voices"
    model = voice_dir / Path(VOICE_PATH).name
    config = voice_dir / f"{Path(VOICE_PATH).name}.json"
    base = f"https://huggingface.co/{VOICE_REPO}/resolve/{VOICE_REVISION}/{VOICE_PATH}"
    download(base, model, VOICE_SIZE, VOICE_SHA256)
    download(f"{base}.json", config, CONFIG_SIZE, CONFIG_SHA256)
    return model, config


def corpus_dir(cache: Path, model: str, speakers: int, variants: int) -> Path:
    return cache / "dry" / f"{model}-vctk-{speakers}x{variants}"


def generate(cache: Path, model: str, speakers: int, variants: int) -> Path:
    if not 1 <= speakers <= DEFAULT_SPEAKERS:
        raise ValueError(f"--speakers must be in 1..{DEFAULT_SPEAKERS}")
    if variants < 1:
        raise ValueError("--variants must be positive")

    model_path, config_path = prepare(cache)
    phrase = PHRASES[model]
    output_dir = corpus_dir(cache, model, speakers, variants)
    output_dir.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(model_path, config_path=config_path)
    samples: list[Sample] = []

    for speaker_id in range(speakers):
        split = "calibration" if speaker_id < speakers // 2 else "validation"
        for variant in range(variants):
            settings_index = (speaker_id + variant) % len(LENGTH_SCALES)
            length_scale = LENGTH_SCALES[settings_index]
            noise_scale = NOISE_SCALES[(speaker_id * 2 + variant) % len(NOISE_SCALES)]
            noise_w_scale = NOISE_W_SCALES[(speaker_id + variant * 2) % len(NOISE_W_SCALES)]
            filename = f"{model}-spk{speaker_id:03d}-v{variant}.wav"
            path = output_dir / filename

            if not path.exists():
                np.random.seed(GENERATION_SEED + speaker_id * 100 + variant)
                with wave.open(str(path), "wb") as wav:
                    voice.synthesize_wav(
                        phrase,
                        wav,
                        SynthesisConfig(
                            speaker_id=speaker_id,
                            length_scale=length_scale,
                            noise_scale=noise_scale,
                            noise_w_scale=noise_w_scale,
                        ),
                    )

            with wave.open(str(path), "rb") as wav:
                if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
                    1,
                    2,
                    22_050,
                    "NONE",
                ):
                    raise RuntimeError(f"Unexpected Piper WAV format: {path}")
                duration_s = wav.getnframes() / wav.getframerate()

            samples.append(
                Sample(
                    file=filename,
                    speaker_id=speaker_id,
                    variant=variant,
                    split=split,
                    length_scale=length_scale,
                    noise_scale=noise_scale,
                    noise_w_scale=noise_w_scale,
                    sample_rate_hz=22_050,
                    duration_s=duration_s,
                    sha256=sha256_file(path),
                )
            )
        print(f"speaker {speaker_id + 1}/{speakers}")

    manifest = {
        "schema": 1,
        "model": model,
        "phrase": phrase,
        "seed": GENERATION_SEED,
        "voice": {
            "repo": VOICE_REPO,
            "revision": VOICE_REVISION,
            "path": VOICE_PATH,
            "size": VOICE_SIZE,
            "sha256": VOICE_SHA256,
            "config_size": CONFIG_SIZE,
            "config_sha256": CONFIG_SHA256,
        },
        "speakers": speakers,
        "variants_per_speaker": variants,
        "samples": [asdict(sample) for sample in samples],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_text = json.dumps(manifest, indent=2) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    if speakers == DEFAULT_SPEAKERS and variants == DEFAULT_VARIANTS:
        public_manifest = REPO_ROOT / "benchmarks" / "positive" / f"corpus-manifest-{model}.json"
        public_manifest.parent.mkdir(parents=True, exist_ok=True)
        public_manifest.write_text(manifest_text, encoding="utf-8")
    print(f"wrote {manifest_path} ({len(samples)} samples)")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "generate", "all"))
    parser.add_argument("--model", choices=(*PHRASES, "all"), default="alexa")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--speakers", type=int, default=DEFAULT_SPEAKERS)
    parser.add_argument("--variants", type=int, default=DEFAULT_VARIANTS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.cache_dir)
    elif args.command == "all":
        for model in PHRASES:
            generate(args.cache_dir, model, args.speakers, args.variants)
    elif args.command == "generate":
        models = PHRASES if args.model == "all" else (args.model,)
        for model in models:
            generate(args.cache_dir, model, args.speakers, args.variants)
    return 0


if __name__ == "__main__":
    sys.exit(main())
