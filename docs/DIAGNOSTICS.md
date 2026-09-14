# Diagnostic tools

The normal firmware deliberately omits continuous audio-path instrumentation.
Diagnostic sampling and DEBUG telemetry consume CPU time and can affect the
real-time workload being measured, so enable these packages only while
investigating a specific problem and remove them afterwards.

Start with the symptom-led checks in [Troubleshooting](TROUBLESHOOTING.md).
Home Assistant's temporary
[Assist WAV recording](INSTALLATION.md#temporarily-record-the-audio-received-by-assist)
is usually the least intrusive way to inspect the processed speech delivered by
the board.

## Raw TDM levels

Use [`diagnostics/tdm-levels.yaml`](../diagnostics/tdm-levels.yaml) when you need
to verify the physical input slots before AFE processing. It reports:

| TDM slot | Signal |
|---|---|
| 0 | First physical microphone |
| 1 | Analog playback reference used by AEC |
| 2 | Second physical microphone |
| 3 | Unused channel / noise floor |

For a local checkout, add it as a second package:

```yaml
packages:
  core: !include base/core.yaml
  tdm_diagnostics: !include diagnostics/tdm-levels.yaml
```

For a remotely fetched Git package, add `diagnostics/tdm-levels.yaml` to the
same `files:` list as `base/core.yaml` and use the same repository revision.

The entities expose RMS levels for checking that both microphones respond,
that playback reaches the reference slot and that the unused slot remains near
the noise floor. `disabled_by_default` only hides an entity in Home Assistant;
it does not stop the device from sampling it. Remove the package when the test
is complete to eliminate its periodic RMS work.

## AFE runtime diagnostics

Use [`diagnostics/afe-runtime.yaml`](../diagnostics/afe-runtime.yaml) for
intermittently low, metallic or discontinuous processed audio, or when a voice
interaction appears to starve the processing pipeline. It publishes:

- AFE input and output levels;
- output misses;
- input and output ring drops;
- feed rejections;
- fetch timeouts;
- short-interval performance telemetry in the logs.

For a local checkout:

```yaml
packages:
  core: !include base/core.yaml
  afe_runtime_diagnostics: !include diagnostics/afe-runtime.yaml
```

For a remotely fetched Git package, add `diagnostics/afe-runtime.yaml` to the
same `files:` list as `base/core.yaml` and select both files under `packages:`.

A small non-zero startup value is not necessarily a fault. Record whether a
counter **increases during the failing interaction**. Healthy operation should
leave the error counters unchanged after initialization.

Remove the package after diagnosis because its DEBUG logging and telemetry add
work to the real-time audio path.

## Reporting results

Record the installed firmware version, whether the build is precompiled or
source-built, the exact interaction and the counter values immediately before
and after it. When relevant, include a privacy-reviewed Assist WAV and logs
from before the first symptom through recovery.

Never publish Wi-Fi credentials, API keys, tokens or private media URLs.
