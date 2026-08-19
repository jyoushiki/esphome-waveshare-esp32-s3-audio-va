---
name: waveshare-esp32-s3-audio
description: >
  Reference for building/editing ESPHome configs on the Waveshare
  ESP32-S3-AUDIO-Board (ESP32-S3R8 smart-speaker devkit: ES8311 codec + NS4150B amp,
  ES7210 dual-mic ADC, TCA9555 I/O expander, 7x WS2812 ring, PCF85063 RTC, DVP camera
  and SPI LCD connectors). Use whenever working on this board (or the base/core.yaml in
  this repo): correct pinout, why the DAC must be forced I2S master, the mute/gain
  traps, the EXIO map, strapping pins, and which "official" sources are wrong.
---

# Waveshare ESP32-S3-AUDIO-Board: ESPHome working notes

Facts below are from Waveshare's **schematic v1.1** and their **own demo source**
(Arduino + ESP-IDF), cross-checked with a working ESPHome config. Where sources
conflict, that is stated. Don't paper over it.

Full detail and citations: `docs/HARDWARE.md` in this repo.

## Board

- **ESP32-S3R8** (bare chip), 240 MHz, **8 MB octal PSRAM**, **16 MB flash**.
- **ES8311** mono codec (DAC) into **NS4150B** Class-D amp into speaker (JST header).
- **ES7210** 4-ch ADC with **2 physical mics** (CH1/CH2). CH3 = AEC loopback.
- **TCA9555** I/O expander @ 0x20: amp enable + 3 buttons (+ LCD/cam/SD lines).
- **7x WS2812B** ring on GPIO38, driven directly over RMT, **not** via expander.
- **PCF85063** RTC @ 0x51. DVP camera + SPI/QSPI LCD connectors. USB-C. Li-ion header.
- Wi-Fi 2.4 GHz + BT 5 LE. ESP32-S3 has **no Bluetooth Classic**, so no A2DP.

ESPHome target: `board: esp32-s3-devkitc-1`, `variant: esp32s3`, `flash_size: 16MB`,
`framework: esp-idf`, `psram: {mode: octal, speed: 80MHz}`.

## Pinout (authoritative)

```
I2S (ONE shared bus):  MCLK=12  BCLK/SCLK=13  LRCK/WS=14   DIN=15 (mic)  DOUT=16 (spk)
I2C (one bus):         SDA=11   SCL=10        100 kHz confirmed working
LED ring WS2812:       DATA=38  (7 LEDs, RGB order, but verify: see gotchas)
BOOT button:           GPIO0 (active low).  RESET = hardware CHIP_PU, not readable.
SD (1-bit SDMMC):      CLK=40 CMD=42 D0=41   CS=EXIO3   (D1/D2 = NC)
LCD (use WIKI table):  CS=3 SCK=4 BL=5 SDA3=6 DC=7 MISO=8 MOSI=9  RST=EXIO0
Camera DVP:            D0=2 D1=17 D2=18 D3=39 D4=45 D5=46 D6=47 D7=48
                       VSYNC=21 HREF=1  PCLK/XCLK muxed 44/43 or 19/20  PWDN=EXIO5
USB:                   D-=19  D+=20        UART0: TX=43 RX=44
GPIO33-37:             UNUSABLE, taken by octal PSRAM (flash uses 26-32)
```

I2C addresses: **ES8311 0x18**, **ES7210 0x40**, **TCA9555 0x20**, **PCF85063 0x51**.

### TCA9555 EXIO map

```
0: LCD_RST     4: unknown          8:  PA_EN  (amp enable, ACTIVE HIGH)
1: TP_RST      5: CAM_PWDN (AL)    9:  Key1   (active low, 10k HW pull-up)
2: TP_INT      6: Camera_SEL  *    10: Key2   (active low)
3: SD_CS       7: USB/cam mux *    11: Key3   (active low)
                                   12-15: expansion header
* EXIO6/EXIO7: schematic and wiki/demo disagree on which does the mux.
  NEVER drive either. The wrong one kills USB and forces manual download mode.
```

The TCA9555 has **no reset pin** (schematic pin 1 is `INT#`).

## The one thing that defines this board: shared I2S clocks and TDM

ES8311 and ES7210 sit on the **same BCLK (13) / LRCK (14)**. Only one device may
drive them. Native ESPHome's independent `i2s_audio` microphone and speaker
cannot coordinate a full-duplex peripheral here. Use the pinned
`esp_audio_stack` component as the single owner; do not also declare native
`i2s_audio`, `audio_adc`, or `audio_dac` components.

Verified TDM slots are **0 = right mic, 1 = analog playback reference,
2 = left mic, 3 = unused**. Capture slots `[0, 2]` and reference slot `1`.

```yaml
external_components:
  - source: github://n-IA-hane/esphome-audio-stack@v2026.7.0
    components: [esp_audio_stack, esp_afe]

esp_audio_stack:
  id: audio_stack
  processor_id: afe_processor
  sample_rate: 16000
  output_sample_rate: 16000
  bits_per_sample: 32
  slot_bit_width: 32
  i2s_mclk_pin: GPIO12
  i2s_bclk_pin: GPIO13
  i2s_lrclk_pin: GPIO14
  i2s_din_pin: GPIO15
  i2s_dout_pin: GPIO16
  use_tdm_reference: true
  tdm_total_slots: 4
  tdm_mic_slots: [0, 2]
  tdm_ref_slot: 1
  codec:
    input: { type: es7210, address: 0x40, mic_selected: 0x0F, gain_db: 24 }
    output: { type: es8311, address: 0x18, use_mclk: true, no_dac_ref: true }

esp_afe:
  id: afe_processor
  type: fd
  mode: high_perf
  mic_num: 2
  input_format: mmr
  aec_enabled: true
  se_enabled: true
```

Keep the shared bus at 16 kHz with `esp_audio_stack` v2026.7.0. The required
48 kHz, four-slot, 32-bit geometry computes as 20 x 192-frame descriptors,
exceeding the component's 16-descriptor safety ceiling and the measured
DMA-capable memory budget. Both 48 kHz/16-bit experiments were also rejected
on hardware: 16-bit slots broke playback and wake detection; 32-bit slots with
16-bit words restored wake detection but left playback and the Assist session
broken. The verified 16 kHz geometry uses 10 x 128-frame descriptors. This
trades music bandwidth for a stable native-rate voice path.

## Gotchas that cost real time

- **`microphone.mute` is the correct mute.** It makes the Microphone hand every
  consumer a zero-filled buffer (`set_mute_state` in `microphone.h`), so the wake
  word hears real silence and the stream never restarts. **Do not "mute" by
  setting ES7210 gain to 0**, because 0 dB is *unity* gain, not silence. There
  are also `microphone.unmute` and the `microphone.is_muted` condition.
- Keep the **ES7210 hardware gain fixed** (24 dB in this firmware) so runtime
  changes do not alter the mic/reference relationship seen by AEC. Expose the
  audio stack's post-AFE `mic_gain` number for user adjustment instead.
- **Template switch triggers fire during `setup()`**, at `setup_priority
  HARDWARE - 2`, i.e. **before** the mic/mWW components exist, whenever
  `restore_mode` isn't `DISABLED` (`TemplateSwitch::setup()` calls
  `turn_on()`/`turn_off()`, which fires the trigger). If a switch's
  `on_turn_on`/`turn_on_action` touches audio components, guard it with an
  `init_in_progress`-style flag and apply the real state from `on_boot`
  (priority -100). **The same applies to a template `select` with
  `restore_value: true`**: it replays the saved option during `setup()` and
  fires `on_value` before the light/RMT and voice_assistant exist. An
  `on_value` that repaints the ring (`control_leds`) then paints an effect on
  an uninitialised strip and crash-loops the board into safe mode. Guard the
  `on_value` with the same `init_in_progress` check.
- **`channels:` on `voice_assistant`/`micro_wake_word` is NOT a channel count.**
  If you wrap the mic (`microphone: { microphone: id, channels: N }`) it is a
  `MicrophoneSource` and `channels` is a **list of channel indices**
  (`cv.ensure_list(cv.int_range(0, 7))`, default `0`), not a count. This firmware
  just passes the mic directly (`microphone: i2s_mics`) and lets it default, so
  the wrapper isn't used - simplest, and Assist won't take a stereo source anyway.
- The board has a **hardware analog echo-reference path**, not a hardware AEC
  DSP. Stock ESPHome cannot reach it, but this firmware's external audio stack
  unpacks the TDM reference and runs software AEC in Espressif AFE. HA's
  `noise_suppression_level` and `auto_gain` are not substitutes for local AEC.
- **Cold-boot: mic + LEDs sometimes don't come up until a reset.** Reported on
  the HA forum in **a single post with zero replies, with no published root cause
  or fix.** The TCA9555 direction registers defaulting to `0xFF` (all inputs)
  would leave PA_EN undriven, which ESPHome's `tca9555` setup addresses before
  the audio stack enables the `ALWAYS_OFF` GPIO switch. This does **not** explain
  the LED symptom
  (the ring is on GPIO38/RMT, not the expander), and the reporter says replaying
  registers didn't help. Don't claim this is solved.
- **Strapping: GPIO45 (CAM_D4) and GPIO46 (CAM_D5) must be LOW at boot.** A
  camera left plugged into J3 sits on both and can stop the board booting, even
  on a voice-only build. GPIO3 (LCD_CS) is also a strap, so don't add strong
  pulls.
- **Waveshare's demo source contains stale copy-paste from other boards.** Proven:
  its `bsp_board.h` LCD pins contradict the wiki's LCD table, and its
  `BAT_ADC_PIN 8` contradicts the schematic's GPIO1 (GPIO8 is LCD_MISO here).
  **Prefer the wiki + schematic over the demo for pin tables**; prefer the demo
  for *behaviour* (which EXIO gets driven, init order).
- **The HA forum thread swaps I2C**: it says SDA=10/SCL=11. It's SDA=11, SCL=10.
- **RGB vs GRB**: the demo says RGB and its own trailing comment says GRB, while
  WS2812B is conventionally GRB. Two sources favour `rgb_order: RGB`, but
  confirm with a pure-red test before trusting either.
- **Idle-amp hiss at boot.** Keep PA_EN on EXIO8 at `ALWAYS_OFF`; use
  `esp_audio_stack`'s `on_amplifier_required` and `on_amplifier_idle` hooks to
  gate it with actual speaker ownership. **Do not** try to fix this by
  playing a boot sound through the media player - a standalone boot announcement
  leaves `media_player.is_announcing` stuck true, and `on_wake_word_detected`
  then only ever stops that phantom announcement instead of starting Assist
  (wake word detected, nothing happens).
- **Battery monitoring is effectively unavailable**: the divider needs a 0 Ω
  resistor soldered (depopulated by default) and **enabling it kills the camera**.
  Ratio 3.0. Pin is GPIO1 per schematic, not GPIO8, which is stale demo code.

## Validating without flashing

ESPHome is the real validator, but `scripts/validate.py` in this repo catches
YAML syntax, unresolved `${substitutions}` and duplicate component ids offline.
Note when writing such tooling: an `id:` under a **dotted key** (`script.execute`,
`light.turn_on`, `mixer_speaker.apply_ducking`) is a *reference*, not a
declaration. Component declarations never sit under a dotted key.

`scripts/esplog.py` streams device logs over the native API (reads the API key
out of `secrets.yaml`), which beats the dashboard's log view for boot-time races.
