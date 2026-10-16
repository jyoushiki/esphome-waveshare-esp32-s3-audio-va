# Public beta testing

Anyone with a Waveshare ESP32-S3-AUDIO-Board may test an announced beta. The
purpose of the beta channel is to validate one frozen firmware and dependency
snapshot on more boards and Home Assistant installations before it becomes a
stable release.

Betas are published as GitHub pre-releases, not through a `beta` branch. The
recommended path is to install the precompiled image or select the managed Beta
firmware update channel. Follow the
[installation guide](INSTALLATION.md#recommended-install-a-precompiled-release).
Do not substitute `dev`: it moves during development and makes results
difficult to reproduce. Source-build testers should pin the announced
pre-release tag.

## Before testing

Record:

- the beta name or announcement;
- the installed version or pre-release tag;
- installation method: precompiled or source build;
- Home Assistant version, plus ESPHome version for a source build;
- board revision, if printed on the PCB;
- Assist pipeline, STT and TTS providers;
- enabled wake-word model or models;
- whether the board is on the same network as Home Assistant or in an isolated
  IoT VLAN.

Start with the normal beta configuration. Do not enable raw TDM or AFE runtime
diagnostics unless a test fails or the beta announcement asks for them.

On a precompiled installation, disable the **Stable firmware** entity and
enable **Beta firmware**. Leave only the beta entity enabled: the updater tests
version equality rather than semantic ordering, so enabling both channels can
make an older stable release appear as an available update.

## v2.1.0 beta focus

The v2.1.0 betas test the HTTP/embedded audio-source migration, experimental
Sendspin playback, night mode and the option to hide timer-countdown lighting.
Run these checks along with the basic test below:

| Test | Expected result |
|---|---|
| HTTP music and announcements | Music, local chimes and HTTP replies play normally; ducking and recovery work across repeated transitions |
| Confirmed Sendspin playback | Select Sendspin as the preferred output protocol, restart playback and verify Sendspin in Music Assistant's Audio Pipeline view |
| Assist during Sendspin music | Wake detection, replies, local chimes, ducking and timer cancellation continue working |
| HTTP/Sendspin switching | Starting one music source replaces the other without a stuck player or lost announcements |
| Night pulse brightness | Toggle Night mode while a timer rings; pulses respect night brightness and return to normal after leaving night mode |
| Effect changes after night pulses | Cancel ringing, then use volume and privacy controls; brightness is appropriate for the current mode |
| Quiet chimes | Night mode suppresses wake and ready chimes; replies and ringing remain audible; turning night mode off restores normal chime behavior |
| Countdown visibility | Disable Timer countdown on ring; sensors continue counting, the countdown hides, and ringing still sounds and lights the ring |

Music Assistant may expose Home Assistant and Sendspin as two protocols of one
player. Protocol badges alone do not confirm which transport is playing. See
[Sendspin setup](USAGE.md#sendspin-beta), including the legacy-client setting
required by this ESPHome version. Once playback works on one board, test
grouped Sendspin playback and synchronization too.

## Basic test

This short sequence is the minimum useful beta report:

| Test | Expected result |
|---|---|
| Browser installation | The installer shows separate Stable and Beta choices. Choosing Beta installs the displayed version; after reconnecting, Wi-Fi provisioning is available and Home Assistant discovers the device |
| Cold power-on | Board joins Wi-Fi and Home Assistant; the startup sound has normal speed and pitch when enabled and night mode is off |
| Managed update | Beta firmware detects an announced pre-release, installs it and returns online with Wi-Fi and saved settings intact |
| Wake word | An enabled wake word is detected at normal speaking distance |
| Short command | Capture starts, ends naturally and produces the correct response |
| Long command | The complete sentence reaches STT without losing its beginning or ending early |
| Spoken reply | The full reply plays without crackle, acceleration or a stuck LED phase |
| Volume controls | Key 1 raises and Key 3 lowers volume in 5% steps; the blue ring follows the level |
| Contextual action button | Key 2 stops ringing, an active Assist run or an announcement before falling back to music play/pause or manual Assist start |
| Physical ring stop | Key 2 stops a voice timer or external ring request, including while the microphone is muted |
| Physical mute | Boot toggles microphone mute; the ring briefly lights red, then stays dim red and wake words are ignored while muted |
| Voice timer | The violet bar drains with the closest timer; it then rings and can be stopped |
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
- the wake chime is audible when enabled and outside night mode;
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
- night mode and night LED brightness;
- timer-countdown visibility;
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
- Optionally use Device Builder's **Take control** flow and confirm that it
  creates the complete editable YAML rather than a remote package wrapper.
  Taking control alone must not alter the running precompiled firmware; an
  actual source build still requires a host with sufficient memory.
  For the v2.1.0 beta, replace the imported stable configuration with the
  pre-release's attached YAML before compiling, as described in
  [source preparation](INSTALLATION.md#2-prepare-the-editable-device-file).

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

Add the [AFE runtime diagnostics](DIAGNOSTICS.md#afe-runtime-diagnostics)
only when investigating intermittent processing. Report whether counters
increase during the failure, not merely their startup values. Remove diagnostic
packages and Home Assistant WAV recording after testing.

## Reporting results

A successful report is valuable too. Use this compact format:

```text
Pre-release tag / installed version:
Installation method:
ESPHome version (source build only):
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

Submit the result using the repository's
[beta test report form](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va/issues/new?template=beta-report.yml).
