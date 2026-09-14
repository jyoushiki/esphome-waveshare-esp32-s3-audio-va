# Public beta testing

Anyone with a Waveshare ESP32-S3-AUDIO-Board may test an announced beta. The
purpose of the beta channel is to validate one frozen firmware and dependency
snapshot on more boards and Home Assistant installations before it becomes a
stable release.

Use the `beta` branch only after a beta round is announced. Follow the
[installation guide](INSTALLATION.md#choose-a-firmware-channel) to install it.
Do not substitute `dev`: it moves during development and makes results difficult
to reproduce.

## Before testing

Record:

- the beta name or announcement;
- the firmware commit SHA stated in that announcement;
- ESPHome and Home Assistant versions;
- board revision, if printed on the PCB;
- Assist pipeline, STT and TTS providers;
- enabled wake-word model or models;
- whether the board is on the same network as Home Assistant or in an isolated
  IoT VLAN.

Start with the normal beta configuration. Do not enable raw TDM or AFE runtime
diagnostics unless a test fails or the beta announcement asks for them.

## Basic test

This short sequence is the minimum useful beta report:

| Test | Expected result |
|---|---|
| Cold power-on | Board joins Wi-Fi and Home Assistant; startup sound has normal speed and pitch |
| Wake word | An enabled wake word is detected at normal speaking distance |
| Short command | Capture starts, ends naturally and produces the correct response |
| Long command | The complete sentence reaches STT without losing its beginning or ending early |
| Spoken reply | The full reply plays without crackle, acceleration or a stuck LED phase |
| Volume controls | Key 1 raises and Key 3 lowers volume in 5% steps; the cyan ring follows the level |
| Media control | Key 2 toggles current music between play and pause |
| Physical mute | Boot toggles microphone mute; after a bright pulse the ring stays dim red and wake words are ignored while muted |
| Voice timer | A timer counts down, rings and can be stopped |
| External ringing | The Home Assistant `start_ringing` action rings locally and `stop_ringing` restores normal playback and LEDs |
| Reset | The board returns to ready state and responds again |

Run each failed item at least twice. A one-off network timeout and a repeatable
firmware failure need different reports.

## Extended audio and concurrency tests

These tests exercise the features most likely to expose full-duplex, memory or
network problems:

### Wake word during music

1. Start a Music Assistant stream and let it play for at least one minute.
2. Say the enabled wake word while music is playing.
3. Give a normal command.
4. Wait for the spoken reply and for music to return to its previous level.

Expected behavior:

- wake-word detection continues during playback;
- the wake chime is audible;
- music is strongly ducked while listening;
- the complete reply plays;
- music resumes without requiring a manual stop/start;
- the ring returns to its correct idle or playback-independent state.

### Announcement over music

While music is playing, send an announcement to the device. It should duck the
music, play once at the correct speed and restore music afterwards. A failed URL
is usually a network-path problem; use the
[media troubleshooting steps](TROUBLESHOOTING.md#media-or-announcements-do-not-play)
before reporting it as an audio failure.

### Repeated Assist workload

Run at least ten voice interactions containing a mix of short and long
commands. Include one request while music is playing. Watch for:

- a reboot or native-API disconnect;
- a response that remains stuck in listening, thinking or replying;
- progressively lower, metallic or discontinuous microphone audio;
- crackle limited to the first announcement;
- a wake word that stops responding until reset.

### Multiple timers

1. Create two timers with different durations and names.
2. Confirm that `Next timer` shows the nearest active timer.
3. Cancel or let the first timer finish.
4. Confirm that the second timer becomes the displayed timer.
5. Stop a ringing timer using an enabled wake word.

## Persistence test

Change each of the following, reboot once, and verify the saved state:

- microphone mute;
- enabled wake-word models;
- wake-word sensitivity;
- wake and boot sound switches;
- LED brightness;
- listening, thinking and replying effects;
- post-AFE microphone gain.

The temporary volume-level display and active timer state are runtime state, not
configuration that should be restored after an arbitrary reboot.

## Optional resilience tests

These tests are useful but not required for every tester:

- Restart Home Assistant while leaving the board powered. The board should not
  reboot merely because the API is unavailable and should recover when Home
  Assistant returns.
- Briefly interrupt Wi-Fi and verify reconnection.
- Play music for 30 minutes, then run Assist without rebooting first.
- Run repeated music/announcement/Assist transitions while observing free
  memory and logs.

Do not factory-reset the device merely for a beta test. A factory reset erases
saved preferences and is not part of an ordinary update or rollback.

## When an audio test fails

First save the normal logs. If the problem concerns capture level, echo,
clipping, metallic speech or early VAD termination, temporarily enable Home
Assistant's [Assist WAV recording](INSTALLATION.md#temporarily-record-the-audio-received-by-assist).

Use the disabled-by-default `Echo cancellation` and `AFE processing` controls
only for an intentional comparison:

1. normal path, both on;
2. AEC off, AFE processing still on;
3. complete AFE bypass only if the first comparison is insufficient;
4. return both switches to on.

Add the [AFE runtime diagnostics](../README.md#optional-afe-runtime-diagnostics)
only when investigating intermittent processing. Report whether counters
increase during the failure, not merely their startup values. Remove diagnostic
packages and Home Assistant WAV recording after testing.

## Reporting results

A successful report is valuable too. Use this compact format:

```text
Beta / firmware SHA:
ESPHome version:
Home Assistant version:
Board revision:
Assist pipeline (STT/TTS):
Wake-word model(s):
Network layout:

Basic test: PASS / FAIL
Extended tests performed:
Observed result:
Expected result:
Reproduction steps:
Reproduction rate:
Recovery required:
Relevant log excerpt:
Diagnostic counters changed:
```

For a failure, attach logs from before the first symptom through recovery or
reboot. Include a short WAV only when it helps explain an audio-path problem.
Remove Wi-Fi credentials, API keys, access tokens, private URLs and unrelated
speech before publishing any file.

Follow the symptom-specific checks in the
[troubleshooting guide](TROUBLESHOOTING.md) before opening an issue. State
clearly when an item was not tested instead of treating it as a pass.
