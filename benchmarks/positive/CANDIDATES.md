# Least-sensitive wake-word candidates

These candidates were fixed after inspecting the speaker-disjoint calibration
split and before evaluating the reserved validation speakers. The results
measure synthetic relative recall. End-to-end hardware validation is recorded
separately.

| Model | Baseline | Candidate | DiPCo false accepts |
|---|---:|---:|---:|
| Okay Nabu | 217/255 | **224/255** | 2 → 1 |
| Hey Jarvis | 247/255 | **252/255** | 1 → 0 |
| Alexa | 230/255 | **245/255** | 2 → 1 |
| Hey Mycroft | 253/255 | **254/255** | 0 → 0 |

The baseline is the existing **Slightly sensitive** preset for every model.
Development values tried before this benchmark were never published as a
least-sensitive preset, so they are excluded from the presets and baselines.
The first table records the original one-channel calibration used to
preregister the candidates. Those counts remain unchanged after opening the
held-out positive results.

## Candidate selection

For Okay Nabu, 224 is the first cutoff that reduces the DiPCo event count. No
further reduction occurs until 234, while positive recall falls substantially
over that interval.

For Hey Jarvis, 252 is the first cutoff with no DiPCo false accepts.

Alexa 245 is the first cutoff that removes one of the two DiPCo events seen at
the 230 baseline; higher values degrade adverse-condition recall progressively
without another event reduction until 251.

Hey Mycroft already records no DiPCo false accepts at its 253 baseline. The
254 candidate is retained because the calibration loss is small in clean and
reverberant conditions, it remains useful as a distinct stricter preset, and
254 is the highest functional cutoff. A cutoff of zero cannot re-arm under the
microWakeWord comparison semantics and is not a usable maximum.

These choices were fixed before opening the validation split. A later candidate
change requires a new independent holdout or must be labelled exploratory.

## Reserved validation result

All four candidates were subsequently evaluated against the 55 held-out
speakers (165 utterances per condition). Recall changes relative to each
baseline were:

| Model | Clean | Room | DiPCo +20 dB | DiPCo +10 dB | DiPCo 0 dB |
|---|---:|---:|---:|---:|---:|
| Okay Nabu | -1.2 pp | -3.0 pp | -3.6 pp | -3.6 pp | -2.4 pp |
| Hey Jarvis | -4.2 pp | -3.0 pp | -4.2 pp | -4.8 pp | -8.5 pp |
| Alexa | -0.6 pp | -6.1 pp | -4.2 pp | -4.2 pp | -7.9 pp |
| Hey Mycroft | 0.0 pp | 0.0 pp | -1.8 pp | -2.4 pp | -1.8 pp |

The validation results support the pre-registered choices. Jarvis has the
largest cost under the hardest mixture, but 252 is also the first tested cutoff
that removes its remaining DiPCo false accept. Exact counts and
speaker-cluster bootstrap intervals are retained in the per-model result files.

## All-channel follow-up

After the held-out positive result had been opened, the negative replay was
expanded to all five DiPCo units and all seven channels per unit. That pass
represents 186.716 detector channel-hours over the same 5.335 hours of
synchronized conversation:

| Model | Baseline events | Candidate events | Aggregate FA/h reduction |
|---|---:|---:|---:|
| Okay Nabu | 66 | 53 | 0.353 → 0.284 (-19.7%) |
| Hey Jarvis | 47 | 27 | 0.252 → 0.145 (-42.6%) |
| Alexa | 61 | 12 | 0.327 → 0.064 (-80.3%) |
| Hey Mycroft | 16 | 7 | 0.086 → 0.037 (-56.3%) |

Every preregistered candidate reduces false accepts across the full set of
acoustic views. This was a follow-up validation of fixed values. Choosing a
different cutoff after seeing the reserved positive split would require a new
independent holdout or an explicitly exploratory analysis.
