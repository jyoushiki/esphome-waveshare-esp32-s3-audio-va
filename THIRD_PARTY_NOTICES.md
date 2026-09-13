# Third-Party Notices

This project references and uses third-party software, models, and media assets. These components remain subject to their respective licenses and copyright notices.

## Home Assistant Voice Preview Edition sounds

This project references sound assets from the Home Assistant Voice Preview Edition repository at build time.

Source:  
https://github.com/esphome/home-assistant-voice-pe/tree/dev/sounds

The sound assets are:

Copyright © 2024 Clayton Charles Tapp

Licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0).

License:  
https://creativecommons.org/licenses/by/4.0/

Upstream license notice:  
https://github.com/esphome/home-assistant-voice-pe/blob/dev/sounds/LICENSE.md

The referenced assets currently include sounds such as the wake-word indication, timer-finished sound, and error notification sounds.

These files are not stored in this repository; they are fetched from the upstream repository during the ESPHome build process. They may, however, be incorporated into generated firmware images.

## ESPHome Micro Wake Word models

This project references wake-word and voice-activity-detection models from the ESPHome Micro Wake Word Models repository.

Source:  
https://github.com/esphome/micro-wake-word-models

The upstream project is licensed under the Apache License 2.0.

License:  
https://github.com/esphome/micro-wake-word-models/blob/main/LICENSE

The model manifests and associated model files are fetched from the upstream repository during the ESPHome build process and are not stored directly in this repository.

Individual model manifests may also contain author and model-specific attribution information supplied by the upstream project.

## esphome-audio-stack

This project uses `esphome-audio-stack` as an ESPHome external component.

Source:  
https://github.com/jyoushiki/esphome-audio-stack

The component is distributed separately under the MIT License.

Upstream copyright notice:

Copyright (c) 2025 n-IA-hane (meconiotech@gmail.com)

License:  
https://github.com/jyoushiki/esphome-audio-stack/blob/main/LICENSE

The component source is not vendored into this repository. ESPHome retrieves it as an external component when building the firmware.

## ESPHome

This project is built using ESPHome and uses ESPHome components and generated runtime code.

Source:  
https://github.com/esphome/esphome

ESPHome uses a combination of licenses depending on the part of the project. In particular, its C/C++ runtime code is licensed under the GNU General Public License version 3, while Python code and other portions are generally licensed under the MIT License.

See the upstream ESPHome license for the authoritative terms:

https://github.com/esphome/esphome/blob/dev/LICENSE

## Original project

This repository originated as a fork of Michał Zaniewicz's ESPHome firmware for the Waveshare ESP32-S3-AUDIO-Board:

https://github.com/MichalZaniewicz/esphome-waveshare-esp32-s3-audio-va

The original project is licensed under the MIT License. Its copyright notice is retained in this repository's main `LICENSE` file as required by that license.

Subsequent modifications and independently authored portions of this repository are covered by the same repository-level license unless otherwise stated.

---

This notice is provided for attribution and convenience. The license files and notices distributed by each upstream project remain authoritative.