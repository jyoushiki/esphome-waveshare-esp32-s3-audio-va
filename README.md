![ESPHome and Home Assistant voice assistant on the Waveshare ESP32-S3-AUDIO-Board](docs/hero.jpg)

# ESPHome voice assistant for the Waveshare ESP32-S3-AUDIO-Board

ESPHome firmware that runs the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm)
as a Home Assistant voice satellite. It uses both microphones and the board's
playback reference for local echo cancellation, with 48 kHz speaker output.
The onboard buttons control volume, Assist and microphone mute, and the
seven-LED ring shows the device's state.

You need Home Assistant with an Assist pipeline. Wake-word detection runs on
the board; Home Assistant handles speech recognition, intent processing and
spoken replies through the providers configured in your pipeline.

> [!NOTE]
> This project started as a fork of
> [Michał Zaniewicz's firmware](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va).
> It now uses a different audio architecture and has its own release path.
> Follow this repository's guides when installing or configuring this firmware.
> See the [project comparison](docs/PROJECT_COMPARISON.md) for the differences.

The current stable release is `v2.0.0`, the first stable release of the
48 kHz firmware. See the [changelog](CHANGELOG.md) for features, upgrade
guidance and release history.

The documentation on `main` covers stable firmware. The `dev` branch may
include features that are still in development. Choose the guides for your
installed version:

| Firmware | Release | Documentation |
|---|---|---|
| Stable | [v2.0.0](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va/releases/tag/v2.0.0) | [All guides](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va/blob/v2.0.0/README.md#documentation-and-support) |
| Public beta | [v2.1.0-beta.1](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va/releases/tag/v2.1.0-beta.1) | [All guides](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va/blob/v2.1.0-beta.1/README.md#documentation-and-support) |

Betas use fixed release tags from `dev`. There is no separate beta branch.
We merge tested changes into `main` for stable releases.

## Installation

Use the [browser installer](https://jyoushiki.github.io/esphome-waveshare-esp32-s3-audio-va/)
for a precompiled installation:

1. Connect the board over USB with a data cable and open the installer in
   Chrome or Edge.
2. Choose **Stable** (recommended) or **Beta** (for testing), check its version
   and select its **Connect** button.
3. Reconnect when prompted and enter your Wi-Fi credentials.
4. Add the discovered ESPHome device to Home Assistant and assign an Assist
   pipeline.
5. Say **OK Nabu**.

The installer uses the same factory image attached to the GitHub release.
Precompiled installations support managed Stable and Beta updates without
ESPHome Device Builder or a local build host. Keep only one update channel
enabled in Home Assistant.

The [installation guide](docs/INSTALLATION.md) covers first-flash setup,
Wi-Fi provisioning, channel selection and recovery. It also explains how to
build from the complete `waveshare-va.yaml` if you want to modify the firmware
or add diagnostic packages. Source builds require ESPHome 2026.9.0 or newer,
ESP-IDF and a host with enough memory for the audio stack and wake-word models.

## Features

- Four on-device wake words: OK Nabu, Hey Jarvis, Alexa and Hey Mycroft. All are
  available, with OK Nabu enabled by default. Enable models and adjust
  sensitivity from Home Assistant without reflashing.
- Local echo cancellation through Espressif's speech front end, using both
  microphones and the synchronized analog playback reference. Wake-word
  detection continues while music or spoken replies play.
- Music Assistant playback and announcements mixed over music. Assist and
  announcements duck music, which returns to its previous level afterwards.
- Voice timers, with a seven-LED countdown for the nearest active timer and a
  Next timer sensor in Home Assistant. Stop ringing with a wake word or Key 2.
  Home Assistant automations can start and stop the same local ringing behavior.
- Ring feedback for startup, connectivity, Assist phases, timers, mute and
  volume changes. Choose solid light or one of 14 animations for listening,
  thinking and replying, and adjust brightness from Home Assistant.
- A switchable ready chime after connecting to Home Assistant and a wake chime
  before Assist capture. The amplifier stays off until playback needs it.

Each wake-word model has its own sensitivity thresholds. Least sensitive is
available for rooms where television or conversation causes unwanted
activations; custom cutoffs allow further tuning. The
[wake-word validation guide](docs/WAKE_WORD_VALIDATION.md) records the
reproducible 5.3-hour DiPCo false-accept sweep, speaker-disjoint synthetic
positive corpus and hardware check used to select that preset. It also explains
the recall tradeoff and the limits of those measurements.

## Controls and settings

| Button | Action |
|---|---|
| Key 1 | Raise volume by 5% |
| Key 2 | Stop ringing, Assist or an announcement; otherwise control music or start Assist |
| Key 3 | Lower volume by 5% |
| Boot | Toggle microphone privacy mute |

Microphone mute survives reboot and supplies silence to every microphone
consumer, including wake-word detection. A dim red ring indicates mute. Volume
changes briefly show a blue level bar.

Home Assistant also exposes post-AFE microphone gain, LED brightness, phase
animations, wake-word sensitivity, and wake and boot sound switches. The
[usage guide](docs/USAGE.md) lists the controls, saved settings and ring states.

For source builds, these substitutions set the device name and playback
preferences. The precompiled firmware uses the defaults below.

| Substitution | Default | What it does |
|---|---|---|
| `name` / `friendly_name` | `waveshare-voice` / `Waveshare Voice` | Device name. Changing `name` may create new entity identifiers in Home Assistant. |
| `volume_min` / `volume_max` | `0.4` / `0.8` | Media player clamps, because the onboard amp distorts near the top. |
| `hidden_ssid` | `false` | `true` enables `fast_connect` for a hidden SSID. |
| `boot_sound_file` | repo `startup.mp3` | Ready chime after connecting to Home Assistant. Any URL or local MP3/FLAC/WAV. |
| `wake_chime_capture_delay` | `600ms` | Delay before Assist starts capturing after the wake chime begins; tune for custom sounds. |

Pin assignments are also substitutions in `waveshare-va.yaml`. The audio
format is configured in the same file; see the hardware guide before changing
either when porting to another board.

## Audio architecture

The ES7210 microphone ADC and ES8311 speaker DAC share their clock pins.
The external `esp_audio_stack` component owns input and output together on a
48 kHz bus with four 16-bit TDM slots. RX transfers the two microphone slots
and analog playback reference; TX transfers the speaker slot. Transferring
only the required slots reduces DMA memory without changing the physical frame.

The microphone and reference inputs are converted together to 16 kHz for
Espressif's AFE. It applies echo cancellation and dual-microphone Speech
Enhancement/BSS, followed by post-AFE AGC, then sends mono audio to
`micro_wake_word` and Home Assistant. ESP-SR omits its separate noise-suppression
stage in this dual-microphone graph. Music and TTS playback remain at 48 kHz.

```
You  ──▶  Waveshare ESP32-S3  ──▶  Home Assistant Assist
         (wake word + audio)      (STT / LLM / TTS)
```

This firmware pins Audio Stack v2026.10.2 and ESP-SR 2.5.5. Rate conversion and
speech processing add build time and memory requirements. Audio buffers and
media-decoder task stacks use PSRAM; DMA and latency-sensitive task stacks use
internal RAM. See the
[hardware reference](docs/HARDWARE.md#shared-full-duplex-bus) for the slot map,
automatic DMA geometry, measured memory use and pin assignments.

## Documentation and support

The links below open guides and images from the same branch or release tag
as this README. This keeps all documentation on the version you selected.

- [Installation and updates](docs/INSTALLATION.md): browser installation, source
  builds, network setup and recovery.
- [Using the voice assistant](docs/USAGE.md): buttons, wake words, Home Assistant
  entities and ring states.
- [Troubleshooting](docs/TROUBLESHOOTING.md): build, connection and audio problems.
- [Diagnostic tools](docs/DIAGNOSTICS.md): optional raw TDM and AFE runtime packages.
- [Wake-word sensitivity validation](docs/WAKE_WORD_VALIDATION.md): benchmarks,
  preset results and limitations.
- [Hardware reference](docs/HARDWARE.md): codecs, pinout and audio processing.
- [Public beta testing](docs/BETA_TESTING.md): test checklist and report format.
- [Changelog](CHANGELOG.md): release history.
- [`waveshare-va.yaml`](waveshare-va.yaml): complete editable firmware configuration.

Use the [issue forms](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va/issues/new/choose)
to report a bug, submit a beta result or propose a feature. Include the installed
version and whether you used precompiled firmware or a source build.

## Related projects and credits

[esphome-intercom](https://github.com/n-IA-hane/esphome-intercom) uses the same
audio-stack foundation and also supports SIP/VoIP calling. This firmware
focuses on Assist and media playback. See the
[project comparison](docs/PROJECT_COMPARISON.md) for differences in audio
processing, controls and configuration.

The firmware uses
[esphome-audio-stack](https://github.com/n-IA-hane/esphome-audio-stack) for
full-duplex audio and Espressif AFE integration, and
[ESPHome](https://esphome.io) for the device components and Home Assistant
connection. [jensenbox](https://github.com/jensenbox/waveshare-esp32-s3-audio)
provided the early ESP-master I2S layout that informed bring-up.
The sounds and Assist phase/ducking behavior follow
[Home Assistant Voice PE](https://github.com/esphome/home-assistant-voice-pe).

> [!TIP]
> If you find this firmware useful, a star on
> [GitHub](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va)
> is a welcome way to support the project.
>
> [![Star this repo](https://img.shields.io/github/stars/jyoushiki/esphome-waveshare-esp32-s3-audio-va?style=social)](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va)

## License and attribution

This project is licensed under the MIT License.

It was originally forked from
[Michał Zaniewicz's ESPHome Waveshare ESP32-S3 Audio VA project](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va),
Copyright (c) 2026 Michał Zaniewicz.

Subsequent development and the current project architecture are
Copyright (c) 2026 Juan Marcos Torero.

See [LICENSE](LICENSE) for the full license terms.

## Repository layout

The complete configuration is [`waveshare-va.yaml`](waveshare-va.yaml).
See [Installation and updates](docs/INSTALLATION.md#advanced-build-from-the-yaml-source)
for source-build requirements and setup.

```text
waveshare-va.yaml           # complete editable firmware configuration
secrets.example.yaml        # optional source-build credentials template
prebuilt/
  waveshare-va.factory.yaml # universal release wrapper
base/
  sounds/                   # project-owned audio assets
docs/
  INSTALLATION.md           # install, update, rollback and WAV capture
  USAGE.md                  # controls, entities and LED states
  BETA_TESTING.md           # beta test checklist and report format
  TROUBLESHOOTING.md        # build, connection and audio troubleshooting
  DIAGNOSTICS.md            # optional TDM and AFE runtime instrumentation
  WAKE_WORD_VALIDATION.md   # sensitivity benchmarks and preset selection
  HARDWARE.md               # pinout, codecs and audio architecture
  PROJECT_COMPARISON.md     # differences between firmware projects
benchmarks/
  dipco/                    # negative-corpus results and cutoff data
  positive/                 # manifests, recall results and preset rationale
scripts/
  validate.py               # offline YAML checks
  esplog.py                 # device logs over the native API
  prepare_firmware_channel.py # installer and OTA channel packaging
  benchmark_dipco.py        # single-channel negative sweep
  benchmark_dipco_multichannel.py # all-channel negative sweep
  generate_positive_samples.py # generate the pinned synthetic corpus
  benchmark_positive.py     # positive recall evaluation
tests/
  test_prepare_firmware_channel.py # release packaging tests
.github/
  workflows/                # repository checks and firmware releases
  ISSUE_TEMPLATE/           # bug, beta and feature report forms
```

Active development is on `dev`. Public betas are frozen GitHub pre-release
tags; there is no separate beta branch. Source builds should use the YAML
attached to the release they intend to build.
