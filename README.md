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
> **Release status:** `v2.0.0-beta.1` is the first public beta of the 48 kHz TDM
> architecture described below. It is published as a GitHub pre-release with
> precompiled installation and managed beta updates. `v1.1.0` remains the last
> stable tag and uses the earlier 16 kHz layout. Active development continues
> on `dev`; there is no separate beta branch.

```
You  ──▶  Waveshare ESP32-S3  ──▶  Home Assistant Assist
         (wake word + audio)      (STT / LLM / TTS)
```

## Choosing between this project and Michał's

Both projects target the same board and share the same origin, but differ in
audio processing and dependencies. Neither is intended as a drop-in
configuration source for the other.

| | This project | Michał's original project |
|---|---|---|
| Audio ownership | One external full-duplex audio stack owns RX and TX | Stock ESPHome `i2s_audio` components on two logical buses |
| Physical playback | 48 kHz, four 16-bit TDM slots | Simpler 16-bit shared-clock layout, effectively voice-grade playback |
| Microphone path | Both physical microphones plus synchronized analog speaker reference | Stock microphone stream without the reference channel in the Assist path |
| Processing | Espressif AFE with dual-mic BSS/SE, AEC and post-AFE AGC | Standard ESPHome voice pipeline; no local AEC |
| Dependencies | External `esphome-audio-stack`, with the pending sparse-DMA contribution pinned to a tested revision | Pure stock ESPHome; no external audio component |
| Main advantage | Better use of this board's audio hardware, echo handling and 48 kHz output | Simpler build, fewer moving parts and easier alignment with stock ESPHome |
| Main tradeoff | More code, RAM pressure, build time and hardware-specific complexity | Lower playback bandwidth and no use of the board's analog reference for AEC |

Choose Michał's implementation if avoiding external components is the priority.
Choose this one if dual-mic processing, local echo cancellation and 48 kHz
playback justify the additional dependency and complexity. Bugs and setup
questions must be reported against the repository whose firmware is installed;
the two audio architectures require different diagnosis.

## Choosing between this project and `esphome-intercom`

[`esphome-intercom`](https://github.com/n-IA-hane/esphome-intercom) also provides
a maintained full-experience profile for this board. The projects share the
same `esphome-audio-stack` foundation and many audio principles, but serve
different purposes: this firmware is a focused Home Assistant voice satellite,
whereas `esphome-intercom` is a broader voice and SIP/VoIP platform.

| | This project | `esphome-intercom` full experience |
|---|---|---|
| Primary purpose | Dedicated Assist satellite and media player | Voice assistant plus a complete SIP/VoIP endpoint |
| Physical buttons | Volume up, play/pause and volume down | Calling, contact selection, answering and declining |
| Wake words | Four bundled alternatives with selectable sensitivity | A simpler default wake-word setup intended for its shared runtime |
| LED experience | Selectable per-phase effects and a physical volume-level display | Call, assistant and media state coordinated by a generic runtime controller |
| Voice tuning | Board-specific speech-recognition AFE, post-AFE AGC and calibrated mic/reference gain | Full-duplex profile tuned for simultaneous Voice Assistant, media and calls |
| Extra infrastructure | No PBX, SIP account or custom VoIP integration required | Optional HA phone system, softphones, routing, phonebook, groups and trunks |
| Configuration scope | One board and one focused interaction model | Reusable packages and profiles spanning several devices and use cases |

Choose `esphome-intercom` when room-to-room calls, SIP equipment, a door station
or Home Assistant phone routing are part of the goal; duplicating those features
here is explicitly out of scope. Choose this project when the board should
behave primarily as a compact Assist appliance with volume and
media controls, multiple wake-word choices and configurable LED animations.

Both designs can use the board at 48 kHz with its two microphones, synchronized
playback reference and local AEC.

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
  announcement pipelines, so a doorbell announcement plays while the music is
  ducked. Both are exposed to Music Assistant.
- **LED ring**: one state machine drives it. Boot, no-Wi-Fi, no-HA, listening,
  thinking, replying, timer counting, ringing, volume changed - each a distinct
  colour/effect. Brightness and the animation for the listening / thinking /
  replying phases are pickable from HA: solid plus 14 animations - pulses,
  breathe, wipe, scan, spinner, comet, twinkle, fireworks, fire, rainbows.
- **Timers**: set by voice, with an on-ring countdown and a "Next timer" sensor
  in HA. Home Assistant automations can invoke the same local ringing behaviour.
- **Buttons**: Key 1 raises volume, Key 2 stops an active timer/ring request or
  otherwise toggles play/pause, Key 3 lowers volume, and Boot toggles the
  persistent microphone privacy mute.
- **Boot chime**: a short "ready" sound once the device connects to HA
  (toggleable, and it also settles the amp so the ring boots silent).
- **Tunable live from HA**: microphone mute, post-AFE mic gain, LED brightness
  and wake-word sensitivity are all entities, so there's no reflashing to tune it.

## Audio rates and resource tradeoff

The shared physical codec bus and speaker output run at **48 kHz** with four
**16-bit TDM slots and 16-bit samples**. The stack
converts the selected microphone/reference inputs to **16 kHz** before
Espressif's AFE, Micro Wake Word and Home Assistant. Music and TTS therefore
retain 48 kHz playback while the speech pipeline stays at its native rate.

This is possible because the forked audio stack preserves all four physical
TDM slots for clock timing but transfers only the slots each DMA direction
uses: RX carries the two microphones plus analog playback reference, and TX
carries the single speaker slot. With the 16-bit framing, the stack can retain
its normal processor margin and select the DMA geometry automatically. The
validated build uses eight 512-frame descriptors without exhausting the
ESP32-S3's internal DMA-capable RAM.
Large buffers and media-decoder stacks use the board's PSRAM so Voice Assistant
does not compete with I2S DMA, while latency-sensitive task stacks retain their
default internal-RAM placement.

The tradeoff is additional rate-conversion work and reliance on the fork's
sparse-DMA revision until the change is available in an upstream release. See
[Hardware: Shared I2S clocks](docs/HARDWARE.md#shared-i2s-clocks) for the
measured DMA geometry and validation results.

> [!TIP]
> ⭐ **Enjoying this project?** Every star is real motivation to keep it going.
>
> [![Star this repo](https://img.shields.io/github/stars/jyoushiki/esphome-waveshare-esp32-s3-audio-va?style=social)](https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va)


## Installation

The **precompiled release is the default and recommended route**. It can be
installed through ESPHome Web, receives Wi-Fi credentials afterwards and
supports managed stable or beta updates without ESPHome Device Builder.

See **[Installation and updates](docs/INSTALLATION.md)** for the illustrated
first-flash procedure, Wi-Fi provisioning, update channels and recovery. The
same guide documents the optional YAML route for developers and users who need
compile-time substitutions, diagnostic packages or firmware modifications.

## Documentation

Documentation for this firmware lives with this repository so that it can be
versioned together with the implementation:

- **This README**: project choice, features and user-facing
  configuration overview.
- **[Installation and updates](docs/INSTALLATION.md)**: precompiled first-flash,
  stable/beta OTA channels, advanced source builds, network, validation and
  rollback.
- **[Using the voice assistant](docs/USAGE.md)**: physical buttons, wake words,
  Home Assistant controls, diagnostic entities and LED-ring meanings.
- **[Public beta testing](docs/BETA_TESTING.md)**: basic and extended test
  matrices plus a consistent results template.
- **[Troubleshooting](docs/TROUBLESHOOTING.md)**: symptom-led checks for builds,
  connectivity, wake words, capture, playback and runtime audio faults.
- **[Diagnostic tools](docs/DIAGNOSTICS.md)**: optional raw-TDM and AFE-runtime
  packages for investigating the audio path.
- **[Hardware reference](docs/HARDWARE.md)**: sourced pinout, codecs, TDM slot
  map, measured DMA geometry, AEC reference and hardware bring-up findings.
- **[Changelog](CHANGELOG.md)**: release history and hardware validation notes.
- **[`base/core.yaml`](base/core.yaml)**: the annotated source of truth for the
  current firmware behavior.

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
16-bit physical bus. It transfers TDM slots 0 and 2 as the two microphones and
slot 1 as the analog playback reference through RX DMA, while TX DMA carries
only speaker slot 0. Espressif's dual-mic AFE receives a synchronized 16 kHz
conversion, performs AEC and dual-microphone Speech Enhancement/BSS, then
applies post-AFE AGC and publishes processed mono audio to Micro Wake Word and
Home Assistant. ESP-SR omits its separate NS stage from this dual-mic graph;
playback remains at 48 kHz. The annotated configuration is in `base/core.yaml`.


## Repository layout

```
prebuilt/
  waveshare-va.factory.yaml # credential-free universal release wrapper
waveshare-va.yaml           # optional advanced source-build configuration
secrets.example.yaml        # source builds: copy to secrets.yaml
base/
  core.yaml                 # shared firmware implementation
docs/
  INSTALLATION.md          # install, update, rollback and WAV capture
  USAGE.md                 # controls, entities and LED states
  BETA_TESTING.md          # public beta test matrix and report format
  TROUBLESHOOTING.md       # symptom-led diagnosis
  DIAGNOSTICS.md           # opt-in raw-TDM and AFE runtime instrumentation
  HARDWARE.md              # pinout, I2C map and audio architecture
scripts/
  validate.py              # offline YAML check (syntax, substitutions, duplicate ids)
  esplog.py                # stream device logs over the native API
```

## Configuration

Day-to-day settings are available as Home Assistant entities: mic gain,
LED brightness, the ring animation per assistant phase
(Listening / Thinking / Replying effect), wake-word sensitivity, wake sound,
boot sound, microphone mute.

The precompiled firmware uses the documented defaults. The following
compile-time substitutions are available only when using the optional source
build through `waveshare-va.yaml`:

| Substitution | Default | What it does |
|---|---|---|
| `name` / `friendly_name` | `waveshare-voice` / `Waveshare Voice` | Device name. Changing `name` re-creates every entity in HA. |
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
- **[ESPHome](https://esphome.io)**: everything the firmware is built out of.
- **[Home Assistant Voice PE](https://github.com/esphome/home-assistant-voice-pe)**:
  the sounds, and the phase/ducking model the LED state machine follows.


## License and attribution

This project is licensed under the MIT License.

It was originally forked from
[Michał Zaniewicz's ESPHome Waveshare ESP32-S3 Audio VA project](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va),
Copyright (c) 2026 Michał Zaniewicz.

Subsequent development and the current project architecture are
Copyright (c) 2026 Juan Marcos Torero.

See [LICENSE](LICENSE) for the full license terms.
