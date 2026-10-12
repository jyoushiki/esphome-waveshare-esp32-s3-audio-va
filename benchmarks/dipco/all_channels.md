# Multichannel DiPCo cutoff results

Unique conversation duration: 5.335 hours.
Detector exposure across 35 synchronized channels: 186.716 channel-hours.

## Individual models

| Preset | Model | Cutoff | Aggregate FA/channel-hour | Channel median | Channel p90 | Channel maximum | Synchronized events | Synchronized FA/h |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Least sensitive | `okay_nabu` | 224/255 | 0.284 | 0.187 | 0.562 | 0.562 | 10 | 1.874 |
| Least sensitive | `hey_jarvis` | 252/255 | 0.145 | 0.187 | 0.187 | 0.375 | 3 | 0.562 |
| Least sensitive | `alexa` | 245/255 | 0.064 | 0.000 | 0.187 | 0.375 | 6 | 1.125 |
| Least sensitive | `hey_mycroft` | 254/255 | 0.037 | 0.000 | 0.187 | 0.187 | 3 | 0.562 |
| Slightly sensitive | `okay_nabu` | 217/255 | 0.353 | 0.375 | 0.562 | 0.750 | 12 | 2.249 |
| Slightly sensitive | `hey_jarvis` | 247/255 | 0.252 | 0.187 | 0.375 | 0.562 | 3 | 0.562 |
| Slightly sensitive | `alexa` | 230/255 | 0.327 | 0.375 | 0.562 | 0.750 | 20 | 3.749 |
| Slightly sensitive | `hey_mycroft` | 253/255 | 0.086 | 0.000 | 0.187 | 0.562 | 5 | 0.937 |
| Moderately sensitive | `okay_nabu` | 176/255 | 1.334 | 1.312 | 1.874 | 2.437 | 46 | 8.622 |
| Moderately sensitive | `hey_jarvis` | 235/255 | 0.375 | 0.375 | 0.562 | 0.750 | 6 | 1.125 |
| Moderately sensitive | `alexa` | 191/255 | 1.077 | 0.937 | 1.499 | 1.874 | 49 | 9.184 |
| Moderately sensitive | `hey_mycroft` | 242/255 | 0.418 | 0.375 | 0.750 | 0.937 | 15 | 2.811 |
| Very sensitive | `okay_nabu` | 143/255 | 2.426 | 2.437 | 3.111 | 4.498 | 87 | 16.307 |
| Very sensitive | `hey_jarvis` | 212/255 | 0.589 | 0.562 | 0.750 | 0.937 | 13 | 2.437 |
| Very sensitive | `alexa` | 128/255 | 2.865 | 2.999 | 3.561 | 3.749 | 96 | 17.993 |
| Very sensitive | `hey_mycroft` | 237/255 | 0.536 | 0.562 | 0.937 | 1.312 | 19 | 3.561 |

## All four wake-word models enabled

VAD-gated detections from all four models are merged within each recording before calculating FA/channel-hour. Successive detections within one second form one cluster (990 ms at the 30 ms prediction cadence); a chain can span longer than one second. Synchronized counts also merge across microphones within each session.

These are clustered offline detections, not measured Assist sessions. Nearby independent triggers can be merged, and detections from the same utterance more than one second apart can remain separate.

| Preset | Raw model detections | Combined events | Combined FA/channel-hour | Channel median | Channel p90 | Channel maximum | Synchronized events | Synchronized FA/h |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Least sensitive | 99 | 99 | 0.530 | 0.375 | 0.937 | 0.937 | 22 | 4.123 |
| Slightly sensitive | 190 | 190 | 1.018 | 0.937 | 1.499 | 1.687 | 40 | 7.497 |
| Moderately sensitive | 598 | 598 | 3.203 | 3.186 | 4.236 | 4.686 | 116 | 21.742 |
| Very sensitive | 1198 | 1198 | 6.416 | 6.373 | 7.422 | 8.997 | 215 | 40.298 |
