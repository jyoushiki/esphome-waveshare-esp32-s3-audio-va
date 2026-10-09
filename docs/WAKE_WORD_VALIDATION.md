# Wake-word sensitivity validation

Each wake-word model in this firmware has its own sensitivity cutoffs. Okay
Nabu, Hey Jarvis, Alexa and Hey Mycroft produce different probability
distributions, so one common cutoff would not give them equivalent behaviour.

The **Least sensitive** values were selected in four steps:

1. replay conversational audio without the target phrases to measure false
   accepts across every configurable cutoff;
2. use a speaker-disjoint positive corpus to measure the relative recall cost
   of stricter candidates, fixing each candidate before opening the held-out
   split;
3. compile, flash and exercise the selected preset through the board's real
   microphone, dual-mic AFE and Micro Wake Word path;
4. replay all 35 synchronized DiPCo far-field channels as a follow-up check,
   without retuning against the already opened positive holdout.

The method and its inputs are recorded so the results can be reviewed and
reproduced. A finite benchmark cannot cover every voice, room or television
programme, so the firmware also exposes per-model custom controls.

## Current presets

Micro Wake Word uses quantized unsigned 8-bit probability cutoffs. A larger
value is stricter and therefore less sensitive.

| Preset | Okay Nabu | Hey Jarvis | Alexa | Hey Mycroft |
|---|---:|---:|---:|---:|
| Least sensitive | 224/255 (0.878) | 252/255 (0.988) | 245/255 (0.961) | 254/255 (0.996) |
| Slightly sensitive | 217/255 (0.851) | 247/255 (0.969) | 230/255 (0.902) | 253/255 (0.992) |
| Moderately sensitive | 176/255 (0.690) | 235/255 (0.922) | 191/255 (0.749) | 242/255 (0.949) |
| Very sensitive | 143/255 (0.561) | 212/255 (0.831) | 128/255 (0.502) | 237/255 (0.929) |

This work added **Least sensitive** and aimed to reduce false activations
without making normal use unreasonably difficult. The other three rows are the
existing firmware presets used for comparison.

The corresponding VAD-gated false accepts per detector channel-hour are shown
below. They aggregate all 35 synchronized far-field channels: 5.335 hours of
unique conversation and 186.716 channel-hours of detector exposure. These are
synchronized views of 5.335 hours of conversation, not 186.716 independent
hours. The detailed report therefore gives the median, 90th percentile and
maximum for the 35 physical channels. It does not attach an independent-Poisson
interval to the aggregate.

| Preset | Okay Nabu FA/h | Hey Jarvis FA/h | Alexa FA/h | Hey Mycroft FA/h |
|---|---:|---:|---:|---:|
| Least sensitive | 0.284 | 0.145 | 0.064 | 0.037 |
| Slightly sensitive | 0.353 | 0.252 | 0.327 | 0.086 |
| Moderately sensitive | 1.334 | 0.375 | 1.077 | 0.418 |
| Very sensitive | 2.426 | 0.589 | 2.865 | 0.536 |

## Relationship to the Voice PE values

The original Nabu, Jarvis and Mycroft cutoffs came from the
[Home Assistant Voice PE configuration](https://github.com/esphome/home-assistant-voice-pe/blob/dev/home-assistant-voice.yaml),
which labels them as tested against all DiPCo units and channels. Alexa is not
part of that Voice PE sensitivity table; this project's inherited Alexa
cutoffs had no accompanying FA/h measurements.

For the three presets that existed before Least sensitive, the published Voice
PE comments and this repository's new measurements compare as follows:

| Model | Preset | Voice PE FA/h | This benchmark, VAD-gated FA/h |
|---|---|---:|---:|
| Okay Nabu | Slightly sensitive | 0.000 | 0.353 |
| Okay Nabu | Moderately sensitive | 0.376 | 1.334 |
| Okay Nabu | Very sensitive | 0.751 | 2.426 |
| Hey Jarvis | Slightly sensitive | 0.563 | 0.252 |
| Hey Jarvis | Moderately sensitive | 0.939 | 0.375 |
| Hey Jarvis | Very sensitive | 1.502 | 0.589 |
| Hey Mycroft | Slightly sensitive | 0.567 | 0.086 |
| Hey Mycroft | Moderately sensitive | 1.502 | 0.418 |
| Hey Mycroft | Very sensitive | 1.878 | 0.536 |
| Alexa | Slightly sensitive | Not provided | 0.327 |
| Alexa | Moderately sensitive | Not provided | 1.077 |
| Alexa | Very sensitive | Not provided | 2.865 |

A direct A/B comparison is not possible from these columns. Voice PE names
`okay_nabu@20241226.3`, while this firmware pins the v2 Nabu model from a
specific `micro-wake-word-models` revision. Both evaluations cover every DiPCo
far-field unit and channel, but the Voice PE YAML does not document enough of
the evaluator to confirm that its VAD gating, feature cadence, rearm and event
counting match this replay.

The differences do not establish that either device or frontend is better.
The values in this repository apply to its pinned models and documented test
method. The positive benchmark covers recall, which a negative-only FA/h table
cannot measure.

## Negative test: DiPCo

The negative benchmark uses every raw 16 kHz far-field channel in the Dinner
Party Corpus (DiPCo): five seven-microphone array units in each of ten sessions.
This provides 5.335 hours of unique conversation and 186.716 detector
channel-hours. The accompanying transcripts were checked and contain no literal
instance of any of the four target phrases.

The replay path mirrors the relevant ESPHome streaming behaviour:

- a frontend feature every 10 ms;
- one quantized model prediction per three feature slices;
- the five-prediction rolling window and strict cutoff comparison;
- the 100-feature startup/rearm interval;
- the bundled Micro Wake Word VAD gate.

The machine-readable result includes every cutoff from 0 through 254. Cutoff
zero cannot be used because the detector's strict comparison prevents its
rearm counter from advancing.

At the selected Least sensitive values, the VAD-gated run produced:

| Model | Slightly sensitive | Selected value | False accepts in 186.716 channel-hours |
|---|---:|---:|---:|
| Okay Nabu | 217 | **224** | 66 → 53 (-19.7%) |
| Hey Jarvis | 247 | **252** | 47 → 27 (-42.6%) |
| Alexa | 230 | **245** | 61 → 12 (-80.3%) |
| Hey Mycroft | 253 | **254** | 16 → 7 (-56.3%) |

`Slightly sensitive` is the published baseline for every model. The comparison
excludes provisional development values that were never validated or released.
Candidates were fixed from the original single-channel calibration before the
held-out positive split was opened. The later all-channel pass was a follow-up
validation; it was not used to retune after opening the holdout.

See [`benchmarks/dipco/README.md`](../benchmarks/dipco/README.md) for corpus
selection and limitations, and
[`benchmarks/dipco/all_channels.json`](../benchmarks/dipco/all_channels.json)
for every cutoff and per-channel preset counts.

## Positive test: speaker-disjoint recall

DiPCo alone can reward an unusably strict setting, because it contains no true
wake words. The positive benchmark therefore generates each target phrase with
the pinned `en_GB-vctk-medium` Piper voice model:

- 109 distinct VCTK speakers;
- three deterministic synthesis variants per speaker;
- 327 utterances for each wake-word model;
- 54 speakers (162 utterances) assigned to calibration;
- 55 different speakers (165 utterances) reserved for validation.

Each utterance is tested in five conditions: clean, simulated room response,
and DiPCo conversation mixed at +20, +10 and 0 dB SNR. Confidence intervals
resample speakers as clusters, keeping the three related variants together.

Candidates were written to
[`benchmarks/positive/CANDIDATES.md`](../benchmarks/positive/CANDIDATES.md)
after inspecting calibration and before evaluating the reserved speakers. This
avoids repeatedly tuning against the validation set.

The held-out recall changes relative to `Slightly sensitive` were:

| Model | Clean | Room | DiPCo +20 dB | DiPCo +10 dB | DiPCo 0 dB |
|---|---:|---:|---:|---:|---:|
| Okay Nabu | -1.2 pp | -3.0 pp | -3.6 pp | -3.6 pp | -2.4 pp |
| Hey Jarvis | -4.2 pp | -3.0 pp | -4.2 pp | -4.8 pp | -8.5 pp |
| Alexa | -0.6 pp | -6.1 pp | -4.2 pp | -4.2 pp | -7.9 pp |
| Hey Mycroft | 0.0 pp | 0.0 pp | -1.8 pp | -2.4 pp | -1.8 pp |

In the preregistration run, Nabu 224 was the first point that reduced its DiPCo
event count. The next reduction occurred at 234, with a substantially larger
positive-recall cost. Jarvis 252 was the first point with no event in that run;
it has the largest measured recall cost, particularly in the 0 dB mixture.
Alexa 245 was the first point that reduced its event
count from the real 230 baseline. The later all-channel pass found events at
every selected cutoff but confirmed that each candidate reduced its aggregate
rate relative to `Slightly sensitive`.

The positive corpus manifests record the voice revision, generation settings
and SHA-256 digest of every sample. Per-cutoff results and speaker-cluster
bootstrap intervals are under
[`benchmarks/positive/`](../benchmarks/positive/).

## Hardware check

After corpus selection, the resulting firmware was compiled and flashed to the
Waveshare ESP32-S3-AUDIO-Board. The four models and the Least sensitive preset
were exercised through the actual 48 kHz TDM input, dual microphones,
playback-reference channel, Espressif AFE and 16 kHz Micro Wake Word stream.
This smoke test checked that the selected cutoffs work through the complete
firmware path. Its small number of human speakers is not enough for a
statistical recall estimate.

## Reproducing the benchmarks

The scripts use PEP 723 dependency declarations and can be run with `uv` from
the repository root.

Prepare and run the negative sweep:

```sh
uv run scripts/benchmark_dipco_multichannel.py all
```

Generate all four positive corpora:

```sh
uv run scripts/generate_positive_samples.py all
```

Run calibration for one model:

```sh
uv run scripts/benchmark_positive.py --model okay_nabu --split calibration
```

The other model names are `hey_jarvis`, `alexa` and `hey_mycroft`. Validation
uses `--split validation` and should only be opened after recording a candidate.
Downloaded corpora, models and generated audio are SHA-256 verified and cached
under the ignored `.benchmark-cache/` directory; manifests and result reports
remain tracked in the repository.

## Limits and interpretation

- Synthetic speech supports controlled relative comparisons, but cannot cover
  every accent, cadence or pronunciation.
- All 35 DiPCo far-field channels provide 186.716 detector channel-hours but
  only 5.335 hours of unique conversation. Aggregate FA/h, the distribution
  across channel identities and timestamp-clustered acoustic events are kept
  separate so correlated views are not presented as independent time.
- The positive room response and SNR mixtures are deterministic simulations,
  not recordings through this board's microphones.
- A firmware, model, frontend or VAD revision can invalidate the chosen
  operating points. Pinned model and corpus revisions make it possible to test
  such a change again.
- Users with unusual acoustic conditions can enable the disabled-by-default
  per-model cutoff entities. Editing one switches the shared selector to
  `Custom` so the device-specific setting is explicit.
