"""Generate the two-channel ESP Web Tools page from prepared release manifests."""

import argparse
import json
import re
from pathlib import Path
from string import Template


REPOSITORY = "https://github.com/jyoushiki/esphome-waveshare-esp32-s3-audio-va"
RELEASES = f"{REPOSITORY}/releases"
FACTORY = "waveshare-voice-esp32s3.factory.bin"


def generate(site: Path) -> None:
    values = {}
    for channel in ("stable", "beta"):
        directory = site / "firmware" / channel
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        version = manifest["version"]
        if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
            raise ValueError(f"Invalid {channel} release version: {version!r}")
        builds = manifest["builds"]
        if len(builds) != 1 or builds[0]["chipFamily"] != "ESP32-S3":
            raise ValueError(f"Unexpected {channel} chip family")
        parts = builds[0]["parts"]
        if len(parts) != 1 or parts[0]["path"] != FACTORY or parts[0]["offset"] != 0:
            raise ValueError(f"Unexpected {channel} factory image layout")
        if not (directory / FACTORY).is_file():
            raise FileNotFoundError(directory / FACTORY)
        tag = "v" + version.removeprefix("v")
        values[f"{channel}_version"] = tag
        values[f"{channel}_release"] = f"{RELEASES}/tag/{tag}"
        values[f"{channel}_source"] = f"{RELEASES}/download/{tag}/waveshare-va.yaml"
        values[f"{channel}_docs"] = f"{REPOSITORY}/blob/{tag}/README.md#documentation-and-support"
    template = Path(__file__).with_name("installer.html").read_text(encoding="utf-8")
    (site / "index.html").write_text(Template(template).substitute(values), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    generate(parser.parse_args().site)
