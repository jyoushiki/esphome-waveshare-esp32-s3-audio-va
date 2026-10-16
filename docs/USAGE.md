# Using the voice assistant

This guide describes the controls and Home Assistant entities exposed by this
firmware. Names below are shown without the device-friendly-name prefix that
Home Assistant may add.

## Sendspin beta

The development firmware includes a Sendspin music source alongside HTTP
playback. Use a Sendspin-capable server, such as Music Assistant, whose
Sendspin player provider is built in. Discovery needs mDNS on the local
network, and TCP port
8928 must be reachable between the board and server. See the
[ESPHome Sendspin documentation](https://esphome.io/components/sendspin/).

Music Assistant can merge the board's Home Assistant and Sendspin protocols
into one player. In that player's settings, select **Output Protocols →
Preferred Output Protocol → Sendspin**, save, then stop and restart playback.
The protocol badges indicate available methods; the **Audio Pipeline** view
shows which one is active. See
[Music Assistant player settings](https://www.music-assistant.io/settings/individual-player/).

The ESPHome 2026.9.1 Sendspin client uses legacy, unencrypted transport and
does not support encrypted pairing. A Music Assistant message saying pairing
is unavailable is expected for this build. Playback depends on its
**Allow legacy clients** provider setting, which is currently enabled by
default. Music Assistant describes that compatibility option as temporary;
future server versions may require updated client support. See
[Music Assistant Sendspin settings](https://www.music-assistant.io/player-support/sendspin/).

The existing Home Assistant media player continues to handle HTTP music,
Assist replies and local sounds. Sendspin music uses that same player and
speaker pipeline; only one music source plays at a time. Starting HTTP music
replaces Sendspin music on this board, and a Sendspin stream can replace HTTP
music. Announcements use their separate pipeline and duck the local music.

Key 1 and Key 3 change this board's volume. While Sendspin is active, Key 2's
music pause/resume command is forwarded to the Sendspin group, so other group
members can pause or resume too. Stopping media on the board releases its
Sendspin playback rather than sending a group-wide stop. Use the server for
group controls. No additional Sendspin group media-player entity is exposed.

Sendspin is experimental in ESPHome 2026.9.1. This firmware uses its default
48 kHz FLAC/Opus/PCM preferences and 1 MB audio buffer, with playback and hub
server task stacks in PSRAM. The mono HTTP preference does not constrain
Sendspin's codec/channel negotiation; stereo Sendspin streams are downmixed
by the existing mono speaker pipeline.

Sendspin selects ESPHome's high-performance lwIP and Wi-Fi settings
automatically. Source builds no longer override `network.enable_high_performance`
to `false`. These settings trade additional memory for streaming throughput;
measure with Sendspin connected and playing when assessing available memory.

For beta testing, check discovery, individual and grouped playback, pause and
resume from Key 2, volume and mute from both the board and server, and recovery
after restarting the server or reconnecting Wi-Fi. Repeat Assist, local chime,
timer cancellation and ducking checks while Sendspin plays. Switching between
HTTP and Sendspin should release the previous music source. Multiroom timing
needs a listening check with another player; successful solo playback does
not establish synchronization accuracy.

## Physical controls

<img src="buttons.png"
     alt="Button positions on the Waveshare ESP32-S3-AUDIO-Board: Reset, Boot, volume down, multifunction action and volume up"
     width="560">

| Board button | Action |
|---|---|
| Key 1 | Raise media-player volume by 5% |
| Key 2 | Contextual action: stop ringing, Assist or an announcement; control music; or start Assist |
| Key 3 | Lower media-player volume by 5% |
| Boot | Toggle microphone privacy mute |

Changing volume briefly turns the seven LEDs into a blue level bar. The bar
starts beside one edge of the USB-C connector and fills around the ring towards
the other edge.

Muting through Boot and changing the `Microphone Mute` entity in Home Assistant
control the same persisted state. A solid red ring indicates that every
microphone consumer, including wake-word detection, is receiving silence. The
ring acknowledges the change with a brief bright-red pulse, then remains dim
red while mute is active so it is not distracting at night.

`Reset` restarts the board. Holding Boot while resetting still enters the
ESP32-S3 download bootloader; an ordinary press after startup toggles mute.

## Wake words

Four on-device models are installed:

- OK Nabu
- Hey Jarvis
- Alexa
- Hey Mycroft

All four models are available. **OK Nabu** is enabled by default on a fresh
installation. Home Assistant exposes a switch for each model so that the
alternatives can be enabled or disabled without rebuilding. Their enabled
states are stored in flash and restored after reboot.

Enabling more models makes more phrases available, but also gives the detector
more opportunities for a false activation. Start with one model while checking
the installation.

`Wake word sensitivity` changes the detection thresholds of all four models:

- **Least sensitive** is the strictest preset. Use it in rooms where television
  or background conversation causes false activations.
- **Slightly sensitive** is the conservative default and should produce fewer
  false activations.
- **Moderately sensitive** is a middle ground for a quiet room or a more distant
  speaker.
- **Very sensitive** is most permissive and may respond at greater distance, at
  the cost of more false activations.
- **Custom** is selected automatically when one of the disabled-by-default
  per-model probability-cutoff entities is changed. It is intended for expert
  per-device tuning rather than normal setup.

The presets use different cutoffs for each model because the same numerical
threshold does not give them equivalent behaviour. The Least sensitive values
were selected using negative and positive corpus tests, a held-out speaker
split and a hardware check. The other presets retain their existing cutoffs;
the benchmark measures their false-accept rates and recall for comparison.
The full method and machine-readable results are in
[Wake-word sensitivity validation](WAKE_WORD_VALIDATION.md).

## Everyday Home Assistant controls

| Entity | Purpose | Remembered after reboot? |
|---|---|---|
| Microphone Mute | Supplies silence to every microphone consumer, including the local wake-word detector | Yes |
| Mic gain (post-AFE) | Applies gain after AEC and dual-mic processing; defaults to 0 dB on first boot | Yes |
| Wake word sensitivity | Selects the probability thresholds used by all wake-word models | Yes |
| Wake sound | Enables the short acknowledgement chime before Assist capture | Yes |
| Boot sound | Enables the one-shot ready sound after connecting to Home Assistant | Yes |
| LED Ring Brightness | Sets the brightness used by firmware-controlled ring states | Yes |
| Timer countdown on ring | Shows the timer countdown on the ring; on by default | Yes |
| Listening effect | Selects the animation used while speech is being captured | Yes |
| Thinking effect | Selects the animation used while Home Assistant processes a request | Yes |
| Replying effect | Selects the animation used while the reply is played | Yes |
| Next timer | Reports the remaining duration of the closest active voice timer | Runtime only |
| Next timer name | Reports the name of the closest active voice timer | Runtime only |

`Mic gain (post-AFE)` does not change the ES7210 analog gains or the balance
between the two microphones and playback-reference channel seen by AEC. It is
therefore the appropriate live control for correcting the level delivered to
wake-word detection and Home Assistant. Increase it cautiously: clipping cannot
be repaired later in the pipeline. For objective comparison, use the temporary
WAV-recording procedure in the
[installation guide](INSTALLATION.md#temporarily-record-the-audio-received-by-assist).

## Firmware update entities

The recommended precompiled installation adds two diagnostic entities:

| Entity | Default availability | Purpose |
|---|---|---|
| Stable firmware | Enabled | Follows normal GitHub releases |
| Beta firmware | Disabled | Follows public GitHub pre-releases |

Use only one channel at a time. Normal users leave Stable firmware enabled;
beta testers disable it and enable Beta firmware from Home Assistant's entity
settings. See [Managed precompiled updates](INSTALLATION.md#managed-precompiled-updates)
for the update behavior and channel limitation. Source/YAML builds use
ESPHome's normal rebuild-and-upload workflow and do not expose these entities.

## Advanced and diagnostic entities

Some entities are disabled by default in Home Assistant. Enable them from the
device's entity list only for troubleshooting or expert tuning:

| Entity | Normal state | What changing it does |
|---|---|---|
| Echo cancellation | On | Disables only AEC; dual-mic speech enhancement and post-AFE AGC remain active |
| AFE processing | On | Bypasses the complete processed path for an A/B comparison with converted raw microphone audio |
| Per-model probability cutoff (four entities) | Model-specific | Sets an exact threshold and changes Wake word sensitivity to Custom |
| Logger Level | Build default | Changes runtime logging verbosity |
| Restart | — | Reboots the ESPHome device |

`AFE processing` is a diagnostic switch, not a listening-quality preference.
Turning it off removes AEC, dual-mic processing and AGC from the published
microphone path. Return it to **on** after a comparison.

The amplifier-enable switch and factory-reset button are intentionally internal
and are not exposed for normal control. The amplifier follows audio ownership
automatically; manually controlling it would make the hardware state disagree
with the playback pipeline.

Custom probability cutoffs are limited to `1/255` through `254/255`
(approximately 0.00392–0.99608). Zero prevents the detector from rearming;
`255/255` prevents detection. A saved zero from earlier firmware is corrected
to `1/255` when Custom settings are applied.

## LED ring states

| Ring state | Meaning |
|---|---|
| Rainbow during startup | Firmware is initializing; red-dominant before Wi-Fi and violet-dominant after Wi-Fi |
| Pulsing red | Wi-Fi or the Home Assistant API is unavailable |
| Solid violet | Wake word accepted; waiting for the command |
| Configurable violet animation | Listening, thinking or replying, according to the active phase |
| Violet countdown bar | Remaining fraction of the closest active voice timer |
| Quickly pulsing violet | A timer is ringing |
| Quickly pulsing red | Assist pipeline error |
| Dim solid red | Microphone privacy mute is active |
| Blue level bar | Volume was changed |
| Off | Connected and idle |

The listening, thinking and replying effects may be different even though the
phase colour remains violet. This makes the activity recognizable without
giving arbitrary control of the status light to Home Assistant.

## Music, announcements, timers and external ringing

The media player accepts ordinary media as well as announcements. An
announcement ducks ongoing music, and starting Assist ducks music more strongly
while the microphone is being captured. Music resumes its previous level when
the interaction finishes.

Voice timers are managed by the Assist pipeline. When a timer finishes, its
sound repeats until stopped or until the 15-minute safety timeout expires.
Saying an enabled wake word while the timer is ringing stops it instead of
starting a new Assist request.

While timers are active and the device is otherwise idle, the violet ring
shows the remaining fraction of the timer that will finish first. It starts
full and drains from one side of the USB-C connector towards the other. With
multiple timers, the display automatically moves to the next one when the
closest timer finishes or is cancelled.

Turn off **Timer countdown on ring** to hide this countdown, for example for a
nap timer in a dark room. The switch is on by default, remembers its setting
after reboot, and updates the display immediately when changed. It does not
cancel or pause timers: their Home Assistant sensors, ringing sound and ringing
LEDs still work. Assist, connectivity, privacy-mute and volume feedback remain
visible when applicable.

Home Assistant owns calendar and alarm scheduling. Two device actions expose
the same local ringing behaviour to automations:

- `start_ringing` starts the repeating timer sound, ducks music and shows the
  ringing LED state.
- `stop_ringing` stops the sound and restores the normal audio and LED states.

In Home Assistant their generated action names include the ESPHome node name,
for example `esphome.waveshare_voice_start_ringing` and
`esphome.waveshare_voice_stop_ringing`. The ringing safety timeout remains 15
minutes, and saying an enabled wake word also stops it.

Key 2 is a contextual action button. Each press performs the first applicable
action in this order:

1. Stop a voice timer or external ring request.
2. Cancel the active Assist interaction.
3. Stop the current announcement or TTS response.
4. Pause or resume music.
5. Start Assist manually when the device is otherwise idle.

Stopping a ring or controlling playback remains available while the microphone
is muted. Manual Assist start is ignored until microphone privacy mute is
disabled.
