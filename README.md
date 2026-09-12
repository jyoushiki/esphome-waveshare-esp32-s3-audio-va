![ESPHome and Home Assistant voice assistant on the Waveshare ESP32-S3-AUDIO-Board](docs/hero.jpg)

# ESPHome Voice Assistant for the Waveshare ESP32-S3-AUDIO-Board

A **Home Assistant voice satellite** running on the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm),
the little AI smart-speaker devkit with a dual-mic array, an ES8311 codec, three
buttons and a 7-LED RGB ring. It uses ESPHome plus a pinned external audio
component: an always-on core you pull as a package, plus one thin config file
you actually edit.

> [!NOTE]
> This fork is based on
> [Michał Zaniewicz's original project](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va).
> Release `v1.1.0` adds a hardware playback-reference path,
> dual-microphone Espressif AFE processing, local AEC, and the accompanying
> board validation notes. The original copyright and license are preserved.

<div align="center">
  <video src="https://github.com/user-attachments/assets/0eae0230-de47-4f20-a6ea-47f65af35f86" controls width="400"></video>
</div>

> **Status: stable for this fork (`v1.1.0`).** Wake word, VAD-ended
> capture, STT/TTS, playback, the dual microphones, and the analog AEC reference
> are confirmed on-device. The upstream project's broader documentation remains
> available in its
> [Wiki](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki).

```
You  ──▶  Waveshare ESP32-S3  ──▶  Home Assistant Assist
         (wake word + audio)      (STT / LLM / TTS)
```

> [!TIP]
> ⭐ **Enjoying this project?** Every star is real motivation to keep it going.
>
> [![Star this repo](https://img.shields.io/github/stars/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va?style=social)](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va)

## What it does

![Home Assistant entities, the LED ring animation picker, the media player and the wake-word controls](docs/features.jpg)

- **Voice assistant**: on-device wake words via `micro_wake_word`, with
  `okay_nabu` enabled by default and `hey_jarvis`, `alexa` and `hey_mycroft`
  available as alternatives, plus the full Home Assistant Assist pipeline (STT / LLM / TTS),
  a wake beep and music ducking while it listens.
- **Dual-mic local AEC**: both physical microphones and the board's analog
  playback-reference channel feed Espressif's AFE, allowing wake-word detection
  to continue while the device is speaking or playing audio.
- **Simultaneous music and announcements**: a mixer speaker blends the media and
  announcement pipelines, so a doorbell announcement ducks the music instead of
  fighting it. Both are exposed to Music Assistant.
- **LED ring**: one state machine drives it. Boot, no-Wi-Fi, no-HA, listening,
  thinking, replying, timer counting, ringing, volume changed - each a distinct
  colour/effect. Brightness and the animation for the listening / thinking /
  replying phases are pickable from HA: solid plus 14 animations - pulses,
  breathe, wipe, scan, spinner, comet, twinkle, fireworks, fire, rainbows.
- **Timers**: set by voice, with an on-ring countdown and a "Next timer" sensor
  in HA. (A daily-alarm engine is present but its entities are hidden by default.)
- **Buttons**: the three onboard keys do volume down, play-pause, volume up.
- **Boot chime**: a short "ready" sound once the device connects to HA
  (toggleable, and it also settles the amp so the ring boots silent).
- **Tunable live from HA**: microphone mute, post-AFE mic gain, LED brightness
  and wake-word sensitivity are all entities, so there's no reflashing to tune it.

## Audio rates and resource tradeoff

The shared physical codec bus and speaker output run at **48 kHz** with the
32-bit four-slot framing required by the ES7210/ES8311 hardware. The stack
converts the selected microphone/reference inputs to **16 kHz** before
Espressif's AFE, Micro Wake Word and Home Assistant. Music and TTS therefore
retain 48 kHz playback while the speech pipeline stays at its native rate.

This is possible because the forked audio stack preserves all four physical
TDM slots for clock timing but transfers only the slots each DMA direction
uses: RX carries the two microphones plus analog playback reference, and TX
carries the single speaker slot. This profile explicitly disables the optional
processor DMA margin; twelve 256-frame descriptors then hold exactly one 64 ms
AFE quantum without exhausting the ESP32-S3's internal DMA-capable RAM.
Large ordinary allocations prefer the board's PSRAM so Voice Assistant does
not compete with I2S DMA.

The tradeoff is additional rate-conversion work and reliance on the fork's
`feature/tdm-sparse-dma` branch until the change is available in an upstream
release. See [Hardware: Shared I2S clocks](docs/HARDWARE.md#shared-i2s-clocks)
for the measured DMA geometry and validation results.

## Optional raw TDM diagnostics

The normal firmware omits continuous raw-bus level monitoring. Marking an
ESPHome entity `disabled_by_default` hides it in Home Assistant, but does not
stop the device from sampling it inside the audio task. When investigating the
microphones or AEC reference, add
[`diagnostics/tdm-levels.yaml`](diagnostics/tdm-levels.yaml) as a second package:

```yaml
packages:
  core: !include base/core.yaml
  tdm_diagnostics: !include diagnostics/tdm-levels.yaml
```

For a remotely fetched Git package, add `diagnostics/tdm-levels.yaml` to the
same `files:` list as `base/core.yaml` and use the same repository revision.
The optional entities report slots 0 and 2 for the physical microphones, slot
1 for the analog playback reference and slot 3 for the unused/noise-floor
channel. Remove the package again after diagnosis to eliminate the periodic RMS
work.

## Quick start

> Requires **ESPHome 2026.8.0+**, ESP-IDF, and the board's octal PSRAM.

1. In Home Assistant's ESPHome Device Builder directory, provide a
   `secrets.yaml` containing `wifi_ssid` and `wifi_password`. You can copy
   `secrets.example.yaml` as a starting point. Never commit the populated file.
2. Copy only **`waveshare-va.yaml`** next to it and edit the `substitutions:` at
   the top (device name, timezone, volume limits). Its `packages:` block pulls
   `base/core.yaml` from this fork's immutable `v1.1.0` tag at compile time.
3. **First flash over USB**, then updates go wireless:
   ```
   esphome run waveshare-va.yaml
   ```
   Or drop both files into the ESPHome dashboard's `/config/esphome/` and hit
   Install.
4. In Home Assistant: the new ESPHome device appears, open **Configure** and
   assign an Assist pipeline.
5. Say "OK Nabu"; the ring should go violet after it is detected. Because it
   is the first configured model, ESPHome enables only this model on the first
   boot. `Hey Jarvis`, `Alexa` and `Hey Mycroft` are also installed and can be
   enabled from Home Assistant. ESPHome saves and restores each model's enabled
   state in flash.

The example config pins the immutable `v1.1.0` tag so Device Builder rebuilds
are reproducible. After changing `ref:` for a future upgrade, clean the ESPHome
build files once so the package cache is refreshed.

## Documentation

The [Wiki](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki)
has the full guide:

- **[Installation](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/Installation)**: first flash, Home Assistant setup, updating.
- **[Configuration](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/Configuration)**: every substitution and every Home Assistant entity.
- **[Audio architecture](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/Audio-architecture)**: shared-bus TDM, dual microphones and local AEC.
- **[LED ring](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/LED-ring)**: the state machine and every ring effect.
- **[Hardware](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/Hardware)**: pinout, I2C map, and sourced gotchas.
- **[Troubleshooting](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/Troubleshooting)** and **[FAQ](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/wiki/FAQ)**.

## How the shared I2S bus is handled

The board wires the **ES8311 (DAC) and the ES7210 (ADC) to the same BCLK/LRCLK
pins**, and only one device can drive those clocks. Native ESPHome's independent
microphone and speaker components cannot coordinate that peripheral while also
exposing the ES7210 TDM channels needed for echo cancellation.

The forked `esp_audio_stack` owns RX and TX together on a 48 kHz, four-slot,
32-bit physical bus. It transfers TDM slots 0 and 2 as the two microphones and
slot 1 as the analog playback reference through RX DMA, while TX DMA carries
only speaker slot 0. Espressif's dual-mic AFE receives a synchronized 16 kHz
conversion, performs AEC, noise suppression and Speech Enhancement/BSS, then
publishes processed mono audio to Micro Wake Word and Home Assistant. Playback
remains at 48 kHz. The annotated configuration is in `base/core.yaml`.

## Repository layout

```
waveshare-va.yaml          # YOUR config: copy + edit this (pulls base/core.yaml from the fork)
secrets.example.yaml       # copy to secrets.yaml
base/
  core.yaml                # the always-on core package fetched by waveshare-va.yaml
docs/
  HARDWARE.md              # pinout, I2C map, gotchas
scripts/
  validate.py              # offline YAML check (syntax, substitutions, duplicate ids)
  esplog.py                # stream device logs over the native API
skill/
  waveshare-esp32-s3-audio/  # Claude Code skill: pinout + hard-won gotchas
```

## Configuration

Everything worth changing day to day is a Home Assistant entity, not a config
edit: mic gain, LED brightness, the ring animation per assistant phase
(Listening / Thinking / Replying effect), wake-word sensitivity, wake sound,
boot sound, microphone mute.

What lives in `waveshare-va.yaml`:

| Substitution | Default | What it does |
|---|---|---|
| `name` / `friendly_name` | `waveshare-va` / `Waveshare Voice` | Device name. Changing `name` re-creates every entity in HA. |
| `posix_timezone` | `CET-1CEST,...` | Clock zone in POSIX form (the device has no IANA database). DST automatic. |
| `volume_min` / `volume_max` | `0.4` / `0.8` | Media player clamps, because the onboard amp distorts near the top. |
| `hidden_ssid` | `false` | `true` enables `fast_connect` for a hidden SSID. |
| `boot_sound_file` | repo `startup.mp3` | The connect-to-HA chime. Any URL or local MP3/FLAC/WAV. |

Pins and the audio format are substitutions too (in `base/core.yaml`), but you
should not need them unless you are porting to another board.

## Claude Code skill

This repo ships a [Claude Code](https://claude.com/claude-code) skill at
[`skill/waveshare-esp32-s3-audio/`](skill/waveshare-esp32-s3-audio/SKILL.md):
the pinout, the shared-I2S constraint, and the gotchas that cost real debugging
time. Install it user-wide so any session picks it up:

```bash
cp -r skill/waveshare-esp32-s3-audio ~/.claude/skills/
```

## Credits

- **[jensenbox](https://github.com/jensenbox/waveshare-esp32-s3-audio)**: the
  ESP-master I2S layout for this board that the audio setup is based on.
- **ESPHome**: everything the firmware is built out of.
- **[Home Assistant Voice PE](https://github.com/esphome/home-assistant-voice-pe)**:
  the sounds, and the phase/ducking model the LED state machine follows.
