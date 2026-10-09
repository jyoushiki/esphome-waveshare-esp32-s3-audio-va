# DiPCo wake-word cutoff validation

This benchmark measures false wake-word activations on the
[Dinner Party Corpus (DiPCo)](https://www.amazon.science/publications/dipco-dinner-party-corpus).
It evaluates the exact quantized models pinned by `waveshare-va.yaml` and sweeps
all configurable ESPHome probability cutoffs (`0..254`). Cutoff zero is a
firmware edge case: because the initial rearm counter advances only while the
latest probability is below the cutoff, zero never arms detection. It is kept
in the machine-readable output for completeness, but preset comparisons start
above zero.

The benchmark starts from the original 16 kHz PCM recordings. The
precomputed `dinner_party_eval` feature archive commonly used by microWakeWord
was extracted at a 20 ms step, while ESPHome produces a feature every 10 ms.
Merely correcting its duration denominator does not restore the missing feature
windows. Re-extracting at 10 ms makes the inference cadence match the device:
three feature slices and one model prediction every 30 ms.

## Corpus selection

The main benchmark evaluates all 35 far-field channels in every session:
five microphone-array units with seven channels each. They contain 5.3 hours of
unique conversation but approximately 187 detector channel-hours. The channels
are synchronized views of the same events. The report keeps their 5.3 hours of
unique conversation separate from the 187 channel-hours of detector exposure.

The complete archive comes from the official
[DiPCo Zenodo record](https://zenodo.org/records/8122551). Its size, published
MD5 digest and a locally established SHA-256 digest are pinned and checked
before inference. Human transcripts come from the `huckiyang/DiPCo` Hugging
Face mirror at commit
`e2b29d3d0d88692c744feb15e290f7316b68014e`, with a pinned SHA-256 digest for
each file. The transcript audit is included in the JSON report; it contains no
literal occurrence of any of the four target phrases. The corpus is licensed
under CDLA-Permissive-1.0; no corpus audio or transcripts are committed here.

The earlier single-channel run remains in `results.json` and `results.md` as a
small reproducibility check. It deterministically selects one far-field channel
from each session, totalling approximately 615 MB and the same 5.3 hours of
unique conversation. Published preset rates come from the full 35-channel run.

## Running

[`scripts/benchmark_dipco_multichannel.py`](../../scripts/benchmark_dipco_multichannel.py)
is a self-contained `uv` script:

```sh
uv run scripts/benchmark_dipco_multichannel.py all
```

The command downloads and verifies the 13.4 GB compressed archive and the
models, generates and caches compact probability traces, then writes:

- `benchmarks/dipco/all_channels.json`: complete aggregate counts and rates for
  every quantized cutoff;
- `benchmarks/dipco/all_channels.md`: a concise table for the firmware presets.

Downloads and intermediate probability traces are stored under
`.benchmark-cache/` and ignored by Git. Inference defaults to eight workers and
accepts `--workers`; only a bounded set of temporary WAVs is extracted at once.
Use `--max-seconds 60` for a short pipeline smoke test; results from a truncated
run must not be used to select production cutoffs.

The smaller historical run can still be reproduced separately:

```sh
uv run scripts/benchmark_dipco.py all
```

## Metrics and limitations

Two false-accept rates are reported:

- **model-only** applies the exact five-prediction moving average and strict
  integer cutoff comparison used by ESPHome;
- **VAD-gated** additionally requires the bundled microWakeWord VAD model to be
  active, matching the firmware's acceptance gate.

Detection counting replays ESPHome's probability ring, its 100-feature-slice
start/rearm interval and the probability reset after an accepted detection. A
detection blocked by VAD does not reset the wake-word ring, matching the
firmware.

The multichannel report contains three views:

- aggregate false accepts per detector channel-hour;
- the minimum, median, 90th percentile and maximum FA/h across the 35 physical
  unit/channel identities;
- detections clustered by session and timestamp, so one utterance activating
  several synchronized microphones is counted as one acoustic event.

The first metric describes total detector exposure. The 35 channels are
synchronized views, so they do not provide 187 independent hours of
conversation. The distribution shows position-dependent failures, while the
synchronized count uses the 5.3 hours of unique conversation. DiPCo contains
only negative/background audio and cannot measure wake-word recall. Final
cutoff selection also uses the speaker-disjoint positive benchmark and hardware
testing.
