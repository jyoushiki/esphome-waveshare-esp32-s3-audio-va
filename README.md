![ESPHome and Home Assistant voice assistant on the Waveshare ESP32-S3-AUDIO-Board](docs/hero.jpg)

# ESPHome Voice Assistant for the Waveshare ESP32-S3-AUDIO-Board

A hardware-specific **Home Assistant voice satellite** running on the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm),
the little AI smart-speaker devkit with a dual-mic array, an ES8311 codec, three
buttons and a 7-LED RGB ring. It combines ESPHome with an external audio stack
to use the board as one coordinated full-duplex audio device: 48 kHz playback,
both microphones, the analog playback reference, local AEC and Espressif's
speech front end.

> [!NOTE]
> This project started as a fork of
> [Michał Zaniewicz's firmware](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va),
> but now follows an independent architecture and release path. Michał's work
> remains the foundation and is credited under the original license; this
> repository's documentation describes this firmware only.

> [!IMPORTANT]
> **Release status:** `v1.1.0` is the last stable tag, using the earlier 16 kHz
> audio layout. Development of the next release happens on the moving `dev`
> branch and contains the 48 kHz TDM architecture described below. Each beta
> round will use a deliberately selected `beta` snapshot of `dev`; pin its
> commit SHA if an installation must remain exactly reproducible afterwards.

```
You  ──▶  Waveshare ESP32-S3  ──▶  Home Assistant Assist
         (wake word + audio)      (STT / LLM / TTS)
```

> [!TIP]
> ⭐ **Enjoying this project?** Every star is real motivation to keep it going.
>
> [![Star this repo](https://img.shields.io/github/stars/jyoushiki/esphome-waveshare-esp32-s3-audio-va?style=social)](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va)

## Choosing between this project and Michał's

Both projects target the same board and share the same origin, but optimize for
different things. Neither is intended as a drop-in configuration source for the
other.

| | This project | Michał's original project |
|---|---|---|
| Audio ownership | One external full-duplex audio stack owns RX and TX | Stock ESPHome `i2s_audio` components on two logical buses |
| Physical playback | 48 kHz, four 32-bit TDM slots | Simpler 16-bit shared-clock layout, effectively voice-grade playback |
| Microphone path | Both physical microphones plus synchronized analog speaker reference | Stock microphone stream without the reference channel in the Assist path |
| Processing | Espressif AFE with dual-mic BSS/SE, AEC and post-AFE AGC | Standard ESPHome voice pipeline; no local AEC |
| Dependencies | External `esphome-audio-stack`, currently including a pending sparse-DMA contribution | Pure stock ESPHome; no external audio component |
| Main advantage | Better use of this board's audio hardware, echo handling and 48 kHz output | Simpler build, fewer moving parts and easier alignment with stock ESPHome |
| Main tradeoff | More code, RAM pressure, build time and hardware-specific complexity | Lower playback bandwidth and no use of the board's analog reference for AEC |

Choose Michał's implementation if avoiding external components is the priority.
Choose this one if dual-mic processing, local echo cancellation and 48 kHz
playback justify the additional dependency and complexity. Bugs and setup
questions must be reported against the repository whose firmware is installed;
the two audio architectures require different diagnosis.

## What it does

| Voice and audio | Experience and control |
|---|---|
| 🎙️ **Local voice satellite**<br>On-device wake words and the complete Home Assistant Assist pipeline | 💡 **Visible feedback**<br>Seven-LED status ring with configurable phase animations and volume display |
| 🔊 **Full-duplex audio**<br>48 kHz playback with dual microphones, synchronized reference and local AEC | 🎛️ **Live Home Assistant controls**<br>Wake words, sensitivity, microphone gain, mute, sounds and brightness without reflashing |
| 🎵 **Music and announcements**<br>Music Assistant playback, mixed announcements and automatic ducking | ⏱️ **Voice timers**<br>Countdown state, ring indication and spoken cancellation |

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
- **Buttons**: Key 1 raises volume, Key 2 toggles play/pause and Key 3 lowers
  volume, matching their physical placement and the LED volume direction.
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

## Optional AFE runtime diagnostics

For intermittent low, metallic or discontinuous processed audio, include
[`diagnostics/afe-runtime.yaml`](diagnostics/afe-runtime.yaml) instead. It
publishes the AFE input/output levels and accumulated output-miss, ring-drop,
feed-rejection and fetch-timeout counters to Home Assistant, while also logging
short-interval performance telemetry:

```yaml
packages:
  core: !include base/core.yaml
  afe_runtime_diagnostics: !include diagnostics/afe-runtime.yaml
```

Healthy operation should leave the error counters unchanged after startup.
Remove this package after diagnosis because its DEBUG logging and telemetry add
work to the real-time audio path.

For a remotely fetched Git package, add `diagnostics/afe-runtime.yaml` to the
same `files:` list as `base/core.yaml` and select both files under `packages:`.

## Quick start

> Requires **ESPHome 2026.8.0+**, ESP-IDF, and the board's octal PSRAM.

1. In Home Assistant's ESPHome Device Builder directory, provide a
   `secrets.yaml` containing `wifi_ssid` and `wifi_password`. You can copy
   `secrets.example.yaml` as a starting point. Never commit the populated file.
2. Copy only **`waveshare-va.yaml`** next to it and edit the `substitutions:` at
   the top (device name, timezone and volume limits).
3. Choose the firmware channel in its `packages:` block:

   - Keep `ref: v1.1.0` for the immutable stable release. It uses the previous
     16 kHz architecture and does not contain the current beta improvements.
   - Once a beta round is announced, anyone who wants to test pre-release
     firmware can use the public `beta` branch. It is advanced deliberately
     from `dev` and then held stable for that test round; before an announcement
     it may still lag behind `dev`:

     ```yaml
     packages:
       core:
         url: https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va
         ref: beta
         files:
           - base/core.yaml
         refresh: always
     ```

     Do not point a tester at the rolling `dev` branch. Once a test setup is
     known-good, replace `beta` with its commit SHA if you need to preserve that
     exact build after the next beta round begins.
4. **First flash over USB**, then updates go wireless:
   ```
   esphome run waveshare-va.yaml
   ```
   Or drop both files into the ESPHome dashboard's `/config/esphome/` and hit
   Install.
5. In Home Assistant: the new ESPHome device appears, open **Configure** and
   assign an Assist pipeline.
6. Say "OK Nabu"; the ring should go violet after it is detected. Because it
   is the first configured model, ESPHome enables only this model on the first
   boot. `Hey Jarvis`, `Alexa` and `Hey Mycroft` are also installed and can be
   enabled from Home Assistant. ESPHome saves and restores each model's enabled
   state in flash.

After changing between a tag, branch or commit, clean the ESPHome build files
once so both the package and generated build state are refreshed:

```
esphome clean waveshare-va.yaml
esphome run waveshare-va.yaml
```

## Documentation

Documentation for this firmware lives with this repository so that it can be
versioned together with the implementation:

- **This README**: project choice, quick start, features and user-facing
  configuration overview.
- **[Installation and updates](docs/INSTALLATION.md)**: complete first-flash,
  beta-channel, network, validation, update and rollback guide.
- **[Using the voice assistant](docs/USAGE.md)**: physical buttons, wake words,
  Home Assistant controls, diagnostic entities and LED-ring meanings.
- **[Public beta testing](docs/BETA_TESTING.md)**: basic and extended test
  matrices plus a consistent results template.
- **[Troubleshooting](docs/TROUBLESHOOTING.md)**: symptom-led checks for builds,
  connectivity, wake words, capture, playback and runtime audio faults.
- **[Hardware reference](docs/HARDWARE.md)**: sourced pinout, codecs, TDM slot
  map, measured DMA geometry, AEC reference and hardware bring-up findings.
- **[Changelog](CHANGELOG.md)**: release history and hardware validation notes.
- **[`base/core.yaml`](base/core.yaml)**: the annotated source of truth for the
  current firmware behavior.
- **[Optional TDM diagnostics](#optional-raw-tdm-diagnostics)** and
  **[AFE runtime diagnostics](#optional-afe-runtime-diagnostics)**: temporary
  packages for investigating the audio path.

Michał's wiki documents his stock-ESPHome implementation. It remains useful for
that project and for historical context, but it is not authoritative for this
firmware: in particular, its two-bus audio architecture, 16 kHz playback advice
and lack of local AEC do not apply here. Installation, configuration, LED-ring,
troubleshooting and FAQ guides specific to this project will therefore be kept
locally rather than linked across repositories.

## How the shared I2S bus is handled

The board wires the **ES8311 (DAC) and the ES7210 (ADC) to the same BCLK/LRCLK
pins**, and only one device can drive those clocks. Native ESPHome's independent
microphone and speaker components cannot coordinate that peripheral while also
exposing the ES7210 TDM channels needed for echo cancellation.

The forked `esp_audio_stack` owns RX and TX together on a 48 kHz, four-slot,
32-bit physical bus. It transfers TDM slots 0 and 2 as the two microphones and
slot 1 as the analog playback reference through RX DMA, while TX DMA carries
only speaker slot 0. Espressif's dual-mic AFE receives a synchronized 16 kHz
conversion, performs AEC and dual-microphone Speech Enhancement/BSS, then
applies post-AFE AGC and publishes processed mono audio to Micro Wake Word and
Home Assistant. ESP-SR omits its separate NS stage from this dual-mic graph;
playback remains at 48 kHz. The annotated configuration is in `base/core.yaml`.

## Repository layout

```
waveshare-va.yaml          # YOUR config: copy + edit this (pulls base/core.yaml from the fork)
secrets.example.yaml       # copy to secrets.yaml
base/
  core.yaml                # the always-on core package fetched by waveshare-va.yaml
docs/
  INSTALLATION.md          # install, update, rollback and WAV capture
  USAGE.md                 # controls, entities and LED states
  BETA_TESTING.md          # public beta test matrix and report format
  TROUBLESHOOTING.md       # symptom-led diagnosis
  HARDWARE.md              # pinout, I2C map and audio architecture
scripts/
  validate.py              # offline YAML check (syntax, substitutions, duplicate ids)
  esplog.py                # stream device logs over the native API
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
| `wake_chime_capture_delay` | `600ms` | Delay before Assist starts capturing after the wake chime begins; tune for custom sounds. |

Pins and the audio format are substitutions too (in `base/core.yaml`), but you
should not need them unless you are porting to another board.

## Credits

- **[Michał Zaniewicz](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va)**:
  the original firmware and repository this project grew from. Its copyright
  and license remain preserved.
- **[esphome-audio-stack](https://github.com/n-IA-hane/esphome-audio-stack)**:
  the external full-duplex audio and Espressif AFE integration used by this
  firmware.
- **[jensenbox](https://github.com/jensenbox/waveshare-esp32-s3-audio)**: the
  early ESP-master I2S layout that informed this board's bring-up.
- **ESPHome**: everything the firmware is built out of.
- **[Home Assistant Voice PE](https://github.com/esphome/home-assistant-voice-pe)**:
  the sounds, and the phase/ducking model the LED state machine follows.
