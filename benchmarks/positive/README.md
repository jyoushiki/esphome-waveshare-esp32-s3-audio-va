# Synthetic positive wake-word validation

This benchmark adds a reproducible positive set to the DiPCo false-accept test.
It compares the relative recall of candidate cutoffs when board recordings are
unavailable. Human speech and end-to-end hardware tests are still required.

The evaluation covers Okay Nabu, Hey Jarvis, Alexa and Hey Mycroft. Dry
utterances are generated with the 109-speaker `en_GB-vctk-medium` Piper model,
pinned to revision
`b145f2ac26522d6a2ccde0164b7b0e48b1e3199c` of `rhasspy/piper-voices`. VCTK is
used instead of the LibriTTS generator commonly used by microWakeWord training,
reducing direct speaker-corpus overlap. Each speaker produces three variants
with deterministic synthesis settings. Speakers, rather than individual
variants, are divided between calibration and validation.

Generate the dry corpus with:

```sh
uv run scripts/generate_positive_samples.py all
```

The voice model, generated WAV files and working manifests are stored under
`.benchmark-cache/positive/` and are ignored by Git. Every downloaded artifact
and generated WAV is recorded with a SHA-256 digest in the corresponding
tracked `corpus-manifest-<model>.json`.

The evaluation stage adds 1.5 seconds of pre-roll and one second of post-roll,
then tests clean, reverberant and DiPCo conversation mixtures. Results must be
described as synthetic relative recall. A cutoff should not be presented as
hardware-validated until it has also been tried with real speakers through the
board's microphone and AFE path.

Run the two speaker-disjoint splits separately:

```sh
uv run scripts/benchmark_positive.py --model okay_nabu --split calibration
uv run scripts/benchmark_positive.py --model hey_jarvis --split calibration
uv run scripts/benchmark_positive.py --model alexa --split calibration
uv run scripts/benchmark_positive.py --model hey_mycroft --split calibration
```

The validation split must remain unopened until candidates have been recorded
in `CANDIDATES.md`. After that, replace `calibration` with `validation` in the
commands above. The current candidate set is 224/255 for Okay Nabu, 252/255 for
Hey Jarvis, 245/255 for Alexa and 254/255 for Hey Mycroft. Confidence intervals
resample speakers as clusters, keeping the three correlated variants of each
voice together.

The generated voices allow nearby cutoffs to be compared under identical
conditions, but they cover only a limited range of accents, microphones, rooms
and AFE artefacts. Selected presets still need practical board testing. Users
who need a different trade-off can set a custom value.
