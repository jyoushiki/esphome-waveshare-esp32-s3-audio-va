# Waveshare ESP32-S3-AUDIO-Board hardware reference

This is the practical hardware reference for the parts of the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm)
used by this firmware. The values below match the current implementation and
have been validated on the target board.

## Board and ESPHome target

| Item | Value |
|---|---|
| MCU | ESP32-S3R8, dual-core LX7 at 240 MHz |
| Flash | 16 MB |
| PSRAM | 8 MB octal, operated at 80 MHz |
| Radio | 2.4 GHz Wi-Fi and Bluetooth LE |
| Input codec | ES7210 four-channel ADC |
| Output codec | ES8311 DAC |
| Amplifier | NS4150B mono Class-D |
| I/O expander | TCA9555 |
| RTC | PCF85063 |
| Status ring | Seven WS2812-compatible RGB LEDs |

The ESPHome target is:

```yaml
esp32:
  board: esp32-s3-devkitc-1
  variant: esp32s3
  flash_size: 16MB
  framework:
    type: esp-idf

psram:
  mode: octal
  speed: 80MHz
```

## Pins used by this firmware

| Function | Pin or expander channel | Direction |
|---|---|---|
| I2C SDA | GPIO11 | Bidirectional |
| I2C SCL | GPIO10 | Bidirectional/open drain |
| I2S MCLK | GPIO12 | ESP32 to codecs |
| I2S BCLK/SCLK | GPIO13 | ESP32 to codecs |
| I2S LRCLK/WS | GPIO14 | ESP32 to codecs |
| I2S DIN | GPIO15 | ES7210 to ESP32 |
| I2S DOUT | GPIO16 | ESP32 to ES8311 |
| RGB ring | GPIO38 | Output |
| Amplifier enable | TCA9555 EXIO8 | Output, active high |
| Key 1 | TCA9555 EXIO9 | Input, active low |
| Key 2 | TCA9555 EXIO10 | Input, active low |
| Key 3 | TCA9555 EXIO11 | Input, active low |
| Boot button | GPIO0 | Input, active low |
| Reset button | CHIP_PU/EN | Hardware reset |

Key 1 raises volume, Key 2 toggles play/pause and Key 3 lowers volume. The key
inputs have 10 kΩ hardware pull-ups and do not require internal pull resistors.
See the labelled board image in the [usage guide](USAGE.md#physical-controls).

## I2C bus

The board uses one I2C bus at 100 kHz:

| Device | Address | Role |
|---|---|---|
| TCA9555 | `0x20` | Buttons and amplifier enable |
| ES8311 | `0x18` | Speaker DAC |
| ES7210 | `0x40` | Microphones and playback reference |
| PCF85063 | `0x51` | Real-time clock |

GPIO11 is SDA and GPIO10 is SCL.

## Audio hardware

### Shared full-duplex bus

The ES7210 and ES8311 share MCLK, BCLK and LRCLK. They must therefore be driven
by one coordinated full-duplex I2S owner. This firmware uses
`esp_audio_stack` for both RX and TX; stock independent ESPHome microphone and
speaker buses must not be added alongside it.

The validated physical bus format is:

| Parameter | Value |
|---|---|
| Bus mode | TDM, ESP32 master, full duplex |
| Sample rate | 48 kHz |
| Frame | Four physical slots |
| Slot width | 16 bits |
| Sample word width | 16 bits |
| RX data pin | GPIO15 |
| TX data pin | GPIO16 |

RX and TX are independent directions even when they use the same numbered
physical slot. RX slot 0 is microphone data arriving from the ES7210; TX slot 0
is speaker data leaving for the ES8311. They share clock position, not sample
storage or signal content.

### ES7210 input and TDM slots

The board has two physical microphones and an analog sample of its own playback.
The latter is a synchronized AEC reference, not a hardware echo-cancellation
processor.

| TDM slot | Captured signal | Firmware use |
|---|---|---|
| 0 | Right microphone | AFE microphone 1 |
| 1 | Attenuated ES8311 playback | AFE reference |
| 2 | Left microphone | AFE microphone 2 |
| 3 | Unused/noise floor | Not transferred |

The AFE input is assembled as `MMR`: two microphone channels followed by the
reference channel. Both microphone inputs and the ES7210 reference input use
30 dB analog gain so the echo/reference relationship remains calibrated.

### Processing and sample rates

The physical codecs remain at 48 kHz. The audio stack converts the selected RX
channels to 16 kHz before Espressif's speech-recognition AFE. The effective
processing path is:

```text
ES7210: mic R + mic L + playback reference, 48 kHz
                         │
                         ▼
             Espressif AFE, 16 kHz MMR
                  AEC → dual-mic SE/BSS
                         │
                         ▼
              Post-AFE WebRTC AGC adapter
                         │
                         ▼
        Micro Wake Word + Home Assistant Assist, 16 kHz mono
```

The dual-microphone speech-enhancement graph takes the place of the separate
noise-suppression stage, so `ns_enabled: false` reflects the effective ESP-SR
pipeline. Because that ESP-SR profile does not expose its own AGC control, the
audio-stack integration applies its optional WebRTC AGC adapter after AFE
output. AFE VAD is disabled; Home Assistant handles the end of spoken-command
capture. Playback and the mixer remain at 48 kHz.

## Sparse TDM DMA

The physical frame still contains four slots, but the ESP32-S3 does not need to
store all of them in both DMA directions:

| Direction | Transferred physical slots |
|---|---|
| RX | 0, 1 and 2 |
| TX | 0 |

ESP-IDF packs the enabled slots for each direction, and the audio stack maps RX
data back to its configured microphone/reference identities. This reduces
internal DMA-capable memory without changing BCLK, LRCLK or the codecs' physical
frame.

The validated DMA operating point is:

| Parameter | Value |
|---|---|
| Descriptor count | 8, selected automatically |
| Frames per descriptor | 512, selected automatically |
| Queued bus frames | 4096 |
| Queue duration at 48 kHz | 85.3 ms |
| Automatic processor margin | Enabled |

The audio stack initially calculates six descriptors and raises the count to
eight to retain its normal processor-frame margin. The 16-bit sparse RX/TX
geometry leaves approximately 50 KiB of DMA-capable memory free after I2S is
enabled on the validated build. Earlier 32-bit framing consumed twice as much
DMA memory and made that margin impractical; it was not a codec requirement.

## Memory layout

The ESP32-S3's internal RAM is needed for I2S DMA, ESP-SR and code that cannot
run safely from external memory. The firmware therefore:

- reserves 32 KiB of internal RAM;
- prefers PSRAM for ordinary allocations larger than 1 KiB;
- places supported audio, mixer, decoder and wake-word task stacks in PSRAM;
- places large audio buffers and supported AFE rings in PSRAM.

These settings are part of the working audio architecture. Removing them may
allow the firmware to boot but fail later when Assist starts or while media and
announcements run together.

## Speaker and amplifier

The ES8311 provides one mono output to the NS4150B amplifier. A second playback
channel would be discarded by the hardware.

The amplifier is disabled at boot and follows speaker ownership:

- it is enabled when the audio stack requires the physical speaker path;
- it is disabled after the speaker becomes idle.

This avoids leaving the amplifier connected to an undriven DAC line during
startup and reduces idle hiss and turn-on artifacts. The amplifier control is
internal because it is not an independent user setting.

## Status ring

| Parameter | Value |
|---|---|
| Data pin | GPIO38 |
| LED count | 7 |
| Component order | RGB |
| Driver | ESP32 RMT |

The ring is connected directly to the ESP32, not through the TCA9555 expander.
Firmware state and configurable effects are described in the
[usage guide](USAGE.md#led-ring-states).

## USB, boot and unavailable GPIOs

USB D- and D+ use GPIO19 and GPIO20. Hold Boot while resetting the board only
when manual download mode is required; ordinary operation and OTA updates do
not use the Boot button.

The ESP32-S3R8's octal flash/PSRAM interface occupies GPIO26 through GPIO37.
GPIO33 through GPIO37 must not be assigned to application components.

The LCD, camera, SD-card and battery-sensing interfaces are not configured or
supported by this voice-assistant firmware. Adding them requires a separate
pin/resource review, particularly because camera pins include ESP32-S3
strapping pins and may affect boot.

## Validation measurements

The optional TDM level diagnostics measured:

- slots 0 and 2 at approximately -61 dBFS in a quiet room;
- unused slot 3 near -91 dBFS;
- slot 1 rising from approximately -87 dBFS to -38 dBFS during startup-sound
  playback while slot 3 remained at its noise floor.

These measurements confirm the two microphone slots and the electrical playback
reference. The complete 48 kHz path has been tested with on-device wake-word
detection, AEC, command capture and VAD completion, Assist recognition,
correctly pitched responses, music, announcements and simultaneous
music/Assist operation.

For temporary per-slot or AFE runtime telemetry, use the diagnostic packages
described in the [README](../README.md#optional-raw-tdm-diagnostics).

## Sources

- [Waveshare ESP32-S3-AUDIO-Board product wiki](https://www.waveshare.com/wiki/ESP32-S3-AUDIO-Board)
- [Waveshare schematic v1.1](https://files.waveshare.com/wiki/ESP32-S3-AUDIO-Board/ESP32-S3-AUDIO-Board_1.1.pdf)
- [Waveshare Arduino and ESP-IDF examples](https://files.waveshare.com/wiki/ESP32-S3-AUDIO-Board/ESP32-S3-AUDIO-Board-Demo.zip)
- [Espressif ESP32-S3 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf)
- [ESPHome Audio Stack](https://github.com/n-IA-hane/esphome-audio-stack)
