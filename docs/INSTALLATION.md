# Installation and updates

This guide applies to **this repository's firmware**. It does not apply to
Michał Zaniewicz's stock-ESPHome implementation, whose audio architecture and
package source are different.

## Before you start

You need:

- A Waveshare ESP32-S3-AUDIO-Board with its onboard 8 MB octal PSRAM.
- Home Assistant with an Assist pipeline.
- ESPHome 2026.8.0 or newer, using the ESP-IDF framework.
- A USB data cable for the first installation.
- A build host with enough memory for ESP-IDF, ESP-SR and the wake-word models.
- `waveshare-va.yaml` and `secrets.yaml` in the same ESPHome configuration
  directory.

The build host needs internet access to fetch this repository, the external
audio component, sound assets and wake-word models. The ESP32 does not download
source code or models itself.

## Choose a firmware channel

| Reference | Intended use | Changes automatically? |
|---|---|---|
| A release tag such as `v1.1.0` | Stable installation | No |
| `beta` | Public testing of a selected and dependency-pinned snapshot | Only when the next beta round is published |
| A full commit SHA | Reproducing one exact build | No |
| `dev` | Active firmware development | Yes; not recommended for testers |

`v1.1.0` uses the previous 16 kHz audio layout. The 48 kHz TDM firmware remains
pre-release until a newer stable tag is published. Do not use `beta` until a
beta round has been announced: the branch may otherwise still refer to an older
snapshot.

Before a beta is announced, its external audio-stack reference is also pinned
to a commit or release. Freezing only this repository while tracking a mutable
dependency branch would not create a reproducible firmware build.

## 1. Create `secrets.yaml`

Copy `secrets.example.yaml` to `secrets.yaml` and enter the Wi-Fi credentials:

```yaml
wifi_ssid: "YOUR_WIFI_SSID"
wifi_password: "YOUR_WIFI_PASSWORD"
```

Do not commit this file. If the credentials change, update this local copy
before rebuilding or flashing.

## 2. Prepare the thin device file

Copy `waveshare-va.yaml` and edit only its `substitutions:` values:

```yaml
substitutions:
  name: waveshare-voice
  friendly_name: "Waveshare Voice"
  volume_min: '0.4'
  volume_max: '0.8'
  hidden_ssid: 'false'
```

`name` must be a valid ESPHome hostname. Changing it after Home Assistant has
discovered the device may create new entity identifiers.

Anyone may join a beta round. Its package source must be:

```yaml
packages:
  core:
    url: https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va
    ref: beta
    files:
      - base/core.yaml
    refresh: always
```

Keep personal names and credentials only in the thin local file. The downloaded
`base/core.yaml` should not be edited inside ESPHome's package cache.

## 3. Check network access

For a normal Home Assistant installation, allow at least:

- Home Assistant/ESPHome to reach the device's native API on TCP 6053.
- The ESPHome build host to reach GitHub over HTTPS.
- The board to reach the HTTP or HTTPS URLs supplied for TTS, announcements and
  Music Assistant media.
- The ESPHome host to reach the device's OTA service when installing wirelessly.

Media ports are installation-dependent. Ports such as 8095 or 8097 may appear
in Music Assistant URLs, but they are not universal defaults: allow the actual
destination and port shown in the failed URL or logs.

If the IoT network can reach Home Assistant's API but not its media URLs, wake
word and speech recognition may work while replies or music fail with messages
such as:

```text
Failed to open URL
ESP_ERR_HTTP_CONNECT
Media reader encountered an error
```

That is normally a routing, DNS, TLS or firewall problem rather than an audio
codec failure.

## 4. Build and install

From a workstation with ESPHome installed:

```bash
esphome run waveshare-va.yaml
```

In Home Assistant's ESPHome Device Builder, place `waveshare-va.yaml` and
`secrets.yaml` in its configuration directory, open the device and select
**Install**. Use USB for the first flash; later installations can use OTA.

A clean first build is large and can take several minutes. If the compiler ends
with this message:

```text
xtensa-esp-elf-g++: fatal error: Killed signal terminated program cc1plus
```

the operating system killed the compiler because the build host ran out of
memory. It is not a board failure. Build on a machine with more available RAM or
swap and connect Device Builder to that build host if necessary.

## 5. Add it to Home Assistant

After the board joins Wi-Fi:

1. Add or accept the discovered ESPHome integration.
2. Assign the desired Assist pipeline when Home Assistant prompts for it.
3. Wait for the one-shot startup sound.
4. Say **OK Nabu**. It is the first configured model and therefore the only one
   enabled on a new flash by default.
5. Enable `Hey Jarvis`, `Alexa` or `Hey Mycroft` from Home Assistant if desired.
   Their enabled states are saved in flash.

## Temporarily record the audio received by Assist

Home Assistant can save the audio received by its Assist pipeline as WAV files.
This is useful for checking input level, clipping, residual echo, metallic audio
or a command whose beginning or end was lost. For this firmware, it lets you
hear the signal after the board's AFE processing rather than the unprocessed TDM
channels.

> **Enable this only while diagnosing a problem.** Recordings accumulate without
> automatic retention, contain speech and background audio, and may consume a
> significant amount of storage. A 16 kHz, 16-bit mono WAV requires about 1.9 MB
> per minute of audio; repeated Assist runs and multiple recording stages add up.

Add this block to Home Assistant's `configuration.yaml`, not to the ESPHome
device YAML:

```yaml
assist_pipeline:
  debug_recording_dir: /config/assist_pipeline_debug
```

If an `assist_pipeline:` section already exists, add only
`debug_recording_dir:` beneath it instead of creating a second section. Check
the Home Assistant configuration and restart Home Assistant to apply the
change. The destination directory and its subdirectories are created
automatically.

Run the voice-assistant tests you want to capture, then inspect:

```text
/config/assist_pipeline_debug/<device_id>/<pipeline_name>/<run_id>/
```

Depending on where the pipeline starts, a run may contain:

- `00_wake-<wake_word_entity>.wav`: audio used for server-side wake-word
  detection.
- `01_stt-<speech_to_text_engine>.wav`: audio sent through the speech-to-text
  stage. With the wake word detected locally on this board, this is normally
  the relevant file.

The files are 16 kHz, 16-bit mono WAVs. They can be downloaded using a Home
Assistant file-management add-on, Samba or SSH and opened in an audio editor.
Before sharing one, listen for private speech and background audio and redact or
trim it as appropriate.

When testing is complete, remove `debug_recording_dir` (or the complete
`assist_pipeline` block if it contains nothing else), restart Home Assistant,
and delete the accumulated directory after verifying that it contains only the
diagnostic recordings you no longer need.

## Validation checklist

Before declaring an installation healthy, verify:

- The startup sound has the correct speed and pitch.
- The wake word is detected at a normal speaking distance.
- Capture ends naturally after the command rather than timing out.
- Assist plays a complete response and returns to idle.
- Music plays at the expected speed and can be paused with the center button.
- A wake word during music ducks playback and the Assist response completes.
- Key 1 raises volume, Key 3 lowers it, and the LED ring shows the level.
- A voice timer counts down, rings and can be stopped.
- Rebooting preserves microphone mute and wake-word selections.

## Updating a beta installation

The `beta` branch and its external component revision are held stable during a
test round and advanced deliberately for the next one. When an update is
announced:

```bash
esphome clean waveshare-va.yaml
esphome run waveshare-va.yaml
```

Cleaning is important after changing a branch, tag or commit because both the
Git package and generated ESP-IDF state may otherwise remain cached.

For an exact long-term build, replace `ref: beta` with the full tested commit
SHA. A branch name is convenient, but only a commit SHA or immutable release tag
identifies one permanent source tree.

## Rolling back

1. Replace `ref:` with the previous known-good commit SHA or release tag.
2. Run `esphome clean waveshare-va.yaml`.
3. Build and install again over OTA or USB.

Changing firmware does not normally erase saved ESPHome preferences. A factory
reset is a separate destructive action and is not required for an ordinary
rollback.

## Reporting a beta issue

Include:

- ESPHome version and firmware commit SHA.
- Board revision, if known.
- Whether it followed a cold power-on, reboot, OTA update or runtime setting
  change.
- The exact sequence that reproduces it.
- Relevant logs from boot through the failure.
- Whether music was playing and whether AEC/AFE processing was enabled.
- A short recording when the problem concerns gain, echo or audio artifacts.

Remove Wi-Fi credentials, API keys, private URLs and tokens before sharing logs
or configuration files.
