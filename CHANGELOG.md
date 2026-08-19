# Changelog

## [1.1.0] - 2026-08-19

Hardware-validated dual-microphone AFE/AEC release for this fork. Tagged
`v1.1.0`; the thin Device Builder configuration pins this immutable tag.

### Added

- **Local echo cancellation using the board's real analog playback reference.**
  The ES7210 exposes the two physical microphones on TDM slots 0 and 2 and the
  attenuated ES8311 playback loopback on slot 1. The pinned `esp_audio_stack`
  feeds them to Espressif's full-duplex AFE as `MMR` for AEC, noise suppression,
  and dual-mic Speech Enhancement/BSS before Micro Wake Word or Home Assistant
  receives the processed mono stream.
- **Hardware AEC controls and diagnostics.** Home Assistant gains an Echo
  cancellation switch, post-AFE microphone gain, and disabled-by-default level
  sensors for all four TDM slots. These make A/B testing and future board
  bring-up possible without changing codec gain or reflashing diagnostics.
- **`Hey Jarvis` wake-word model**, integrated with all three sensitivity
  profiles. Saved sensitivity is reapplied after setup.
- Documentation of the verified TDM map, DMA geometry, 48 kHz experiments, and
  the distinction between the board's hardware analog reference and the
  software AEC performed by Espressif's AFE.

### Changed

- **Audio ownership moved from two native `i2s_audio` buses to one full-duplex
  TDM owner.** `esp_audio_stack` now owns RX and TX together and configures the
  ES7210 and ES8311 through `esp_codec_dev`, keeping microphones, playback, and
  the echo reference sample-aligned.
- **Speaker output is intentionally reduced from 48 kHz to a 16 kHz physical
  bus.** Incoming 48 kHz announcements and media are resampled to 16 kHz. This
  limits music to voice-grade bandwidth, but provides the DMA headroom required
  for the four-slot, 32-bit dual-mic/reference stream and lets the AFE operate at
  its native 16 kHz rate. On hardware, the verified geometry is 10 DMA
  descriptors of 128 frames.
- The ES7210 hardware gain is fixed at 24 dB so runtime changes cannot disturb
  the microphone/reference balance used by AEC. User gain is applied after the
  AFE instead.
- Amplifier power now follows actual speaker ownership through audio-stack
  lifecycle hooks, avoiding boot hiss without relying on media-player state.

### Hardware validation

- A 48 kHz four-slot/32-bit bus was rejected before startup because its
  1024-sample AFE quantum computed as 20 descriptors of 192 frames, beyond the
  component safety ceiling and measured DMA-capable memory budget.
- A 48 kHz bus with 16-bit words and 16-bit slots started but broke startup
  playback and wake-word recognition. Combining 16-bit words with 32-bit slots
  restored wake detection but left playback silent and Assist capture unable to
  complete normally.
- The final 16 kHz/32-bit configuration played the startup chime, detected
  `Hey Jarvis`, ended capture through VAD, recognized the spoken command,
  completed the intent, played the response, and returned to wake-word mode.
- During playback, reference slot 1 rose from roughly -87 dBFS to -38 dBFS while
  unused slot 3 remained near the noise floor, confirming the electrical
  playback-reference path.

## [1.0.0] - 2026-07-18

First stable release. The full voice assistant is confirmed on hardware, the
regressions found during bring-up testing are fixed, and the project ships with
complete documentation and a wiki. Tagged `v1.0.0`; the example config pins this
tag so a build is reproducible instead of tracking a moving `main`.

### Fixed
- **Boot loop into safe mode after selecting a ring effect.** The three
  effect selects restore their saved option during `setup()` (at HARDWARE
  priority), which fired `on_value` and ran the LED state machine before the
  light/RMT and voice_assistant were initialised, painting an effect on an
  uninitialised strip and crashing the boot. The `on_value` is now gated on
  `init_in_progress` (cleared by `on_boot` at priority -100), so it only runs
  once setup is complete; a live effect change from HA still repaints the ring.

### Changed
- **Boot chime is now a bundled sound, not the wake-word beep.**
  `base/sounds/startup.mp3` (16 kHz mono, ~11 KB) plays on connect to HA and is
  swappable through the `boot_sound_file` substitution (any URL or local
  MP3/FLAC/WAV; the media player decodes all three).

### Removed
- **The Flicker ring effect** (weak visually); 15 effects remain.

## [0.2.0] - 2026-07-18

First on-hardware bring-up. The full voice assistant works: on-device wake word,
STT/intent/TTS, clean playback, no boot hiss - all on stock ESPHome components.

### Changed
- **Audio reworked to two I2S buses with the mic as master; the patched es8311
  and `force_master` are gone.** The board shares BCLK/LRCLK between the DAC and
  ADC, and ESPHome can't run one bus full-duplex (the speaker hits "Parent bus
  is busy"). Two buses over the shared pins, with the always-capturing mic
  mastering the clock and the speaker slaving to it, gives simultaneous capture
  and playback on stock components. The mic is pinned to 16-bit so its master
  frame matches the DAC (a 32-bit frame played back as noise).
- **The amplifier is gated on playback** (`ALWAYS_OFF` at boot, turned on by the
  media_player `on_state`) to remove the idle hiss the always-on amp produced
  before the first playback.
- **API encryption dropped** (LAN-only device); `secrets.yaml` is now just Wi-Fi.
  Re-enable it via the commented block in `base/core.yaml` if you want it.
- **Timers are visible in HA** (the "Next timer" / "Next timer name" sensors are
  no longer `disabled_by_default`).
- **Boot chime**: a short "ready" sound plays once the device connects to HA,
  played after the mic (I2S master) is clocking so the slave speaker can output
  it. New `boot_sound` switch toggles it. The sound ships with the repo
  (`base/sounds/startup.mp3`, 16 kHz mono) and is swappable via the
  `boot_sound_file` substitution (any URL or local MP3/FLAC/WAV).

### Added
- **Per-phase ring animation, pickable from HA.** New "Listening effect",
  "Thinking effect" and "Replying effect" selects choose the animation for those
  voice-assistant phases (the phase colour stays fixed). 15 effects to choose
  from: solid, three pulses, Breathe, Wipe, Scan, Spinner, Comet, Twinkle,
  Random Twinkle, Fireworks, Fire, and two rainbows. Breathe / Spinner /
  Comet / Fire are custom `addressable_lambda` effects.

### Fixed
- **The Pulse LED effects showed a solid colour instead of pulsing.** Their
  `update_interval` (16 ms) was shorter than the transition (300-1000 ms);
  `update_interval` is how often the pulse flips its brightness target, so it
  flipped faster than the brightness could move. Now ~2x the transition, with
  30-100% min/max brightness.
- Compile-time issues found during bring-up: a quoted `mclk_multiple`
  substitution (string vs the int a `cv.one_of` wants), a `template select`
  missing its `options:`, `select` `.state` -> `current_option()`, the dead
  microWakeWord model URLs (404), and a `/` in a switch name.

### Removed
- **The `stop` wake word.** This board has no usable hardware AEC, so the mic
  hears the device's own TTS far louder than the user; "stop" is detected only
  weakly and too late to be useful.
- **The daily-alarm entities** (Alarm time / Alarm on / Alarm action), the
  device-clock text sensor, and the diagnostic mic-disable switch are now
  `internal:` (hidden from HA). The logic stays; the clutter is gone.
- The dead "Mute and unmute sound" switch and its unused sound files.
- `components/es8311/` and the `external_components:` block - no longer needed.

## [0.1.0] - 2026-07-17

First cut. A working single-file config for the Waveshare ESP32-S3-AUDIO-Board,
restructured into a core package + a thin user config, with the patched
`es8311` component brought in-tree so nothing depends on an upstream repo that
has gone quiet.

### Added
- `base/core.yaml`: the always-on core with ES8311 speaker, ES7210 dual mic,
  on-device wake word (`alexa` + `okay_nabu`), the HA Assist pipeline,
  music/announcement mixing with ducking, the 7x WS2812 status ring state
  machine, the three onboard buttons, voice timers and an alarm clock.
- `waveshare-va.yaml`: thin user config. Pulls the core from GitHub at compile
  time, so it is the only file you keep.
- `components/es8311/`: vendored fork of ESPHome's `es8311` adding
  `force_master` + `mclk_multiple`. Origin, credits and the licensing situation
  are in the README.
- `docs/HARDWARE.md`: board pinout and the I2C device map.
- `skill/waveshare-esp32-s3-audio/`: Claude Code skill with pinout + gotchas.
- `scripts/validate.py`: offline YAML check (syntax, substitutions, duplicate
  ids) so a typo does not cost a dashboard round trip.
- `scripts/esplog.py`: stream device logs over the native API.

### Fixed
Bugs carried over from the config this started as:

- **The mic was stopped on every boot.** The `diag_disable_mic` check was
  inverted: with the switch in its default OFF position `on_boot` ran
  `micro_wake_word.stop` + `microphone.stop_capture`. It only ever recovered
  because `on_client_connected` restarted the wake word, so the switch also did
  not actually work, in either direction.
- **"Microphone Mute" did not mute.** It dropped the ES7210 gain to `0.0f`,
  but 0 dB is *unity* gain, not silence. The mic kept hearing the room and only
  the wake-word handler ignored it. It now uses ESPHome's own `microphone.mute`,
  which hands every consumer a zero-filled buffer, so the wake word hears actual
  silence with no I2S restart.
- **A test sound fired on every LED repaint during boot.** A leftover
  `id(play_sound).execute(1, id(wake_word_triggered_sound)); //TEST` sat in the
  `init_in_progress` branch of `control_leds`.
- **Wake word sensitivity did nothing.** The select only set cutoffs on
  `okay_nabu`, while the primary wake word is `alexa`. It now sets both.
- **Mic gain slider promised 42 dB.** The ES7210 caps at 37.5 dB and the driver
  silently clamps, so the top third of the slider was a lie. Range is now
  0 to 37.5 dB in 1.5 dB steps (the chip's real granularity), and the boot value
  in `audio_adc` matches the number entity instead of contradicting it (24 dB vs
  a 32 dB global).
- **The API encryption key was hard-coded in the config.** It now comes from
  `!secret api_encryption_key`.
- **The `time:` block was half-commented-out**, leaving `id: rtc` dangling under
  `platform: homeassistant`. Cleaned up. PCF85063 support is not in this build.
- **Two `on_boot: priority: -100` blocks** ran in an order nobody had chosen.
  Merged into one.

### Changed
- All pins, audio format and the HA-facing values are `substitutions:` with
  documented defaults, instead of literals scattered through the file.
- `${mic_channel_${which_mic}}` nested-substitution trickery replaced with two
  plainly named knobs: `mic_channel` (the I2S slot) and `mic_va_channel` (the
  index handed to Assist). These are genuinely different things and the old
  names implied they were the same one.
- Dropped dead substitutions (`i2s_bits_per_sample`, `i2s_mode_speaker`,
  `rtc_int`, `mic_channel_2`) and the now-unused `mic_gain_saved` global.
- Timezone is a `posix_timezone` substitution rather than a hard-coded `UTC0`.
