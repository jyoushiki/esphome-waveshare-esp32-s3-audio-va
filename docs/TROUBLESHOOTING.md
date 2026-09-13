# Troubleshooting

Start with the symptom, change one variable at a time, and keep the firmware
revision in every test note. Problems that look like audio failures may instead
come from the build host, the network path to a media URL, or Home Assistant's
Assist pipeline.

## First checks

Before changing audio settings:

1. Record the ESPHome version and the firmware reference or commit SHA.
2. Confirm that `waveshare-va.yaml` fetches this repository, not the original
   stock-ESPHome project.
3. After changing a branch, tag, commit or external-component revision, run a
   clean build so cached sources cannot mix revisions.
4. Capture logs from boot through the failure.
5. Reproduce the problem twice before and twice after a change when possible.

```bash
esphome clean waveshare-va.yaml
esphome run waveshare-va.yaml
```

## Quick symptom map

| Symptom | Check first |
|---|---|
| Build ends with `Killed signal terminated program cc1plus` | Build-host RAM or swap |
| Ring keeps pulsing red | Wi-Fi or Home Assistant API connectivity |
| Wake word does nothing | Microphone mute and enabled wake-word model |
| Chime plays but Assist does not answer | Assist pipeline, STT capture and network logs |
| Music or a reply fails with `Failed to open URL` | Routing, DNS, TLS and firewall access to the exact media URL |
| Playback is fast and high-pitched | Mixed component revisions or an unsupported sample-rate/TDM change |
| Captured speech is low, metallic or intermittent | WAV comparison and AFE runtime counters |
| Device reboots during or after wake detection | Runtime memory, power stability and complete serial logs |

## The device does not become ready

During startup the ring shows a rainbow. Once initialization is complete, a
pulsing red ring means that Wi-Fi or the Home Assistant native API is not
connected.

- Recheck the current `wifi_ssid` and `wifi_password` in the local
  `secrets.yaml` used by this build.
- Verify that the IoT network can reach Home Assistant and that TCP 6053 is not
  blocked between Home Assistant/ESPHome and the board.
- Check whether Home Assistant discovered the ESPHome device and assigned an
  Assist pipeline.
- If a cold power-on fails but pressing Reset works, collect logs from both
  starts so codec, I/O-expander and audio-stack initialization can be compared.

The boot sound is played only once per boot, after the Home Assistant client
connects. Its absence does not by itself prove that the speaker is broken.

## The wake word is not detected

Check in Home Assistant that:

- `Microphone Mute` is off.
- At least one wake-word model is enabled.
- You are saying the phrase for an enabled model. Only OK Nabu is enabled on a
  first boot by default.
- `AFE processing`, if manually exposed for diagnosis, has been returned to on.

Try the conservative default with one model first, then raise `Wake word
sensitivity` one step if needed. Enabling several models or selecting `Very
sensitive` also increases opportunities for false activation.

If detection changes suddenly without a firmware update, reboot once and test
again before tuning thresholds. Then make a temporary Assist WAV recording and
check whether ordinary speech reaches Home Assistant at a usable level. See
[recording the audio received by Assist](INSTALLATION.md#temporarily-record-the-audio-received-by-assist).

## The chime plays, but capture or the reply fails

Separate the interaction into stages:

1. Wake word detected and chime played.
2. Speech captured and ended by Home Assistant's VAD.
3. STT produced text.
4. The Assist pipeline handled the intent.
5. A reply URL reached the device and played.

The LED phase and logs show how far the run progressed. A saved
`01_stt-*.wav` reveals whether the command started late, ended early or reached
Home Assistant at a low level.

`wake_chime_capture_delay` controls when capture opens after the wake sound
begins. Increasing it can exclude more chime, but may remove the first syllable
from a fast speaker. It does not control when server-side VAD ends the command.
Do not tune this delay to compensate for an STT, pipeline or network failure.

## Media or announcements do not play

Errors such as these normally mean that the device could not reach the supplied
URL:

```text
Failed to open URL
ESP_ERR_HTTP_CONNECT
Media reader encountered an error
```

The native Home Assistant API and media downloads are separate connections. A
wake word can work even while a firewall blocks the reply or Music Assistant
stream. Inspect the failed URL and allow the board's VLAN to reach its actual
host and port. Music Assistant installations may use ports such as 8095 or
8097, but the URL in your own logs is authoritative.

If a reply works after music is stopped, repeat the test after confirming that
both media and announcement URLs are reachable. Include logs spanning music
startup, wake detection and the delayed reply in a bug report.

## Playback is fast, slow or has the wrong pitch

Speed and pitch changing together indicate a sample-rate or physical bus-format
mismatch, not an ordinary volume or codec-quality setting. The current firmware
uses a 48 kHz, four-slot, 16-bit TDM bus and resamples speech sources as needed.
The hardware speaker must also declare 48 kHz; leaving it at 16 kHz makes
playback run three times too fast and sound correspondingly high-pitched.

With an unmodified published build, first clean the build directory and verify
that the core and external audio components came from the intended revisions.
Each external component must be provided by one source entry only. If the issue
persists, report the source revisions and the audio-stack configuration printed
at boot; do not compensate by changing a file's declared sample rate.

## Microphone audio is low, metallic or discontinuous

Use comparable phrases, distance and room conditions. Peak and RMS values are
useful only when the selected region and speaking level are comparable; avoid
reporting excessive decimal precision for a human-spoken sample.

1. Save a normal Assist WAV.
2. Repeat with `Echo cancellation` off to isolate AEC while retaining the rest
   of the AFE path.
3. If necessary, repeat with `AFE processing` off for a raw-path comparison.
4. Return both switches to on after the test.

The bundled [AFE runtime diagnostics](../README.md#optional-afe-runtime-diagnostics) expose
input/output level plus processing misses, input/output ring drops, feed
rejections and fetch timeouts. Compare counter **changes during the failing
interaction**, rather than treating a small startup value as proof of a runtime
failure. Healthy operation should not continuously increase these counters.

For channel-level diagnosis, the optional
[TDM diagnostics](../README.md#optional-raw-tdm-diagnostics) expose the two microphone
slots, the analog playback reference and the unused slot. These packages add
work to the real-time audio path; remove them from the device YAML after the
test.

`Mic gain (post-AFE)` is suitable for adjusting the delivered level without
disturbing the microphone/reference relationship used by AEC. Increase it in
small steps and check peaks as well as RMS so that louder speech does not clip.

## Pops, crackle or background hum

Distinguish isolated transition noises from continuous artifacts:

- Compare the boot sound, the first Assist reply, a later reply and continuous
  music. A problem limited to one source or the first playback is useful timing
  evidence.
- Test with a stable USB power supply and cable.
- Keep the configured upper volume clamp below the range where the onboard
  speaker and amplifier visibly distort.
- Record whether the noise exists only at the speaker or also in the Assist WAV.
  The latter records the microphone path, not the electrical DAC output.

A faint analog noise floor and repeated digital discontinuities are different
problems. For crackle accompanied by microphone corruption, use the AFE runtime
counters. For speaker-only noise, collect media-player and audio-stack logs.

## Build failure versus runtime reboot

`cc1plus` being killed during compilation means the computer or Home Assistant
host ran out of memory; the firmware was never installed. Build on a machine
with more RAM or swap. See [Build and install](INSTALLATION.md#4-build-and-install).

A board reboot is different. Capture the reset reason and logs before the boot
banner, and note whether it happens at idle, on wake detection, while starting
Assist, or during playback. Use serial logging when the native API disconnects
too quickly. Repeated allocation failures or watchdog messages should be
reported with the exact commit rather than worked around by reducing arbitrary
audio buffers.

## What to include in an issue

- Firmware commit SHA, ESPHome version and board revision if known.
- Package and external-component references.
- Cold boot, Reset, OTA update or runtime sequence that preceded the failure.
- Exact reproduction steps and whether music was playing.
- Logs from before the first symptom through recovery or reboot.
- Whether microphone mute, AEC and AFE processing were on.
- A short, privacy-reviewed WAV for gain, echo, VAD or audio-quality problems.
- Whether the relevant diagnostic counters increased during the failure.

Remove credentials, API keys, access tokens and private media URLs before
publishing the report.
