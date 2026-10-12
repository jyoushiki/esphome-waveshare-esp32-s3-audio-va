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
  tdm_diagnostics: !include diagnostics/tdm-levels.yaml
```

If the diagnostic file is not stored beside your editable configuration, it
can instead be included as a remote Git package pinned to the same release tag.

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
  afe_runtime_diagnostics: !include diagnostics/afe-runtime.yaml
```

If the diagnostic file is not stored beside your editable configuration, it
can instead be included as a remote Git package pinned to the same release tag.

A small non-zero startup value is not necessarily a fault. Record whether a
counter **increases during the failing interaction**. Healthy operation should
leave the error counters unchanged after initialization.

Remove the package after diagnosis because its DEBUG logging and telemetry add
work to the real-time audio path.

## Playback resource comparisons

Before changing the playback architecture, include these packages in the local
wrapper that already contains your device name and Wi-Fi secrets:

```yaml
packages:
  firmware: !include waveshare-va.yaml
  resource_diagnostics: !include diagnostics/resources.yaml
  cpu_diagnostics: !include diagnostics/cpu.yaml
```

`resources.yaml` reports internal 8-bit RAM and PSRAM separately: current free
bytes, allocator minimum free bytes since boot, and largest contiguous free
block. It also reports the maximum ESPHome loop interval observed in each
five-second reporting window. Loop interval is a responsiveness measurement,
not CPU utilization. The allocator minima are sums of each matching heap
region's low-water mark; they need not represent one simultaneous allocation.
Five-second sampling can miss brief changes in the largest block.

`cpu.yaml` additionally enables FreeRTOS runtime accounting. It reports each
core's busy percentage over the preceding sample interval using idle-task
runtime, and logs task stack minimum-free bytes once a minute or when the
**Resource task stack snapshot** button is pressed. The first CPU measurement
needs two samples. Busy percentage is an idle-time estimate, not attribution of
CPU time to individual tasks or interrupts. Do not interpret loop time or CPU
frequency as utilization. Stack minima are lifetime high-water marks, not the
current stack use.

CPU profiling snapshots briefly suspend scheduling and scan task stacks. The
profiler allocates space for up to 64 task records in PSRAM; failure produces a
warning rather than a fabricated measurement. Runtime accounting also has
overhead. Use identical packages, ESPHome/ESP-IDF versions, logger level,
network settings, wake-word models, volume, and audio files for both builds.
Keep the more intrusive AFE/TDM packages off for the initial resource comparison.
After the comparison, remove these packages and repeat listening tests without
profiling to check for instrumentation effects.

Capture separate logs for these workloads, allowing startup to settle first:

| Workload | Suggested capture |
|---|---|
| Connected idle with wake word enabled | 2 minutes |
| Continuous HTTP music | 3 minutes |
| Music plus local chimes or ringing | 2 minutes |
| Music plus repeated Assist requests and TTS replies | 3 minutes |
| Stopped playback, then repeated start/stop transitions | 2 minutes |

Reboot before independent runs if comparing lifetime heap/stack minima. Use
the same sequence for a transition run and check whether memory recovers after
playback stops. Record glitches, resets, Wi-Fi/API reconnects, and task snapshot
warnings alongside the metrics. A successful compile alone does not validate
audio behavior or runtime headroom.

For serial logging, use your actual device port (Linux example):

```sh
esphome logs waveshare-va.local.yaml --device /dev/serial/by-id/YOUR_DEVICE > capture.log 2>&1
python3 scripts/analyze_resources.py capture.log > capture-summary.json
```

Stop logging with Ctrl-C. The analyzer accepts complete `[resources:...]` log
rows and reports sample count, minimum, median, nearest-rank p95, and maximum,
plus observed task stack minima. Keep raw logs locally: other firmware log
lines can contain recognized speech, media URLs, or network information.

Preserve the baseline YAML and firmware binary before migrating. For the first
migration, set HTTP buffers explicitly to the old player's values; compare
architecture with equivalent buffers before attempting memory tuning.

## Reporting results

Record the installed firmware version, whether the build is precompiled or
source-built, the exact interaction and the counter values immediately before
and after it. When relevant, include a privacy-reviewed Assist WAV and logs
from before the first symptom through recovery.

Never publish Wi-Fi credentials, API keys, tokens or private media URLs.
