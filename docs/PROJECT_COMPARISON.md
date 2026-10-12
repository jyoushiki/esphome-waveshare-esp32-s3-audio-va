# Firmware projects for this board

This guide compares the projects linked from the [README](../README.md).
Use the documentation and issue tracker for the firmware installed on your
board.

## Michał Zaniewicz's firmware

Both projects target the same board and share the same origin. The original
[firmware configuration](https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va/blob/main/base/core.yaml)
uses stock ESPHome components. Their audio
processing and dependencies differ, so their configurations cannot be used
interchangeably.

| | This project | Michał's original project |
|---|---|---|
| Audio ownership | One external full-duplex audio stack owns RX and TX | Stock ESPHome `i2s_audio` components on two logical buses |
| Physical playback | 48 kHz, four 16-bit TDM slots | 16-bit shared-clock layout using stock I2S buses |
| Microphone path | Both physical microphones plus synchronized analog speaker reference | Stock microphone stream without the reference channel in the Assist path |
| Processing | Espressif AFE with dual-mic BSS/SE, AEC and post-AFE AGC | Standard ESPHome voice pipeline; no local AEC |
| Dependencies | External `esphome-audio-stack`, pinned to a hardware-tested upstream release | Pure stock ESPHome; no external audio component |
| Main advantage | Dual-mic processing, local echo cancellation and 48 kHz output | Simpler build, fewer moving parts and easier alignment with stock ESPHome |
| Main tradeoff | More code, RAM pressure, build time and hardware-specific complexity | No local AEC or analog playback reference in the Assist path |

Choose Michał's implementation if avoiding external components is the priority.
Choose this one if dual-mic processing, local echo cancellation and 48 kHz
playback justify the additional dependency and complexity. Bugs and setup
questions must be reported against the repository whose firmware is installed;
the two audio architectures require different diagnosis.

## `esphome-intercom`

[`esphome-intercom`](https://github.com/n-IA-hane/esphome-intercom) also provides
a full-experience profile for this board. Both projects use
`esphome-audio-stack`. This firmware is a Home Assistant voice satellite;
`esphome-intercom` also provides SIP/VoIP calling. Its
[Waveshare profile](https://github.com/n-IA-hane/esphome-intercom/blob/main/yamls/full-experience/single-bus/waveshare-s3-full-afe.yaml)
shows how the shared audio stack is used for voice, media and calls.

| | This project | `esphome-intercom` full experience |
|---|---|---|
| Primary purpose | Dedicated Assist satellite and media player | Voice assistant plus a complete SIP/VoIP endpoint |
| Physical buttons | Volume up, contextual Assist/media action and volume down | Calling, contact selection, answering and declining |
| Wake words | Four bundled alternatives with selectable sensitivity | Wake-word configuration from shared runtime packages |
| LED experience | Selectable per-phase effects and a physical volume-level display | Call, assistant and media state coordinated by a generic runtime controller |
| Voice tuning | Board-specific speech-recognition AFE, post-AFE AGC and calibrated mic/reference gain | Full-duplex profile tuned for simultaneous Voice Assistant, media and calls |
| Extra infrastructure | No PBX, SIP account or custom VoIP integration required | Optional HA phone system, softphones, routing, phonebook, groups and trunks |
| Configuration scope | One board and one focused interaction model | Reusable packages and profiles spanning several devices and use cases |

For room-to-room calls, SIP equipment, a door station or Home Assistant phone
routing, see `esphome-intercom`. Calling is outside this firmware's scope.
This project provides Assist and media playback, with physical volume controls,
four wake-word choices and configurable LED animations.

Both designs can use the board at 48 kHz with its two microphones, synchronized
playback reference and local AEC.
