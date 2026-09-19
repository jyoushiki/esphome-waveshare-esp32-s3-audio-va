import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_firmware_channel import prepare


FACTORY_NAME = "waveshare-voice-esp32s3.factory.bin"
OTA_NAME = "waveshare-voice-esp32s3.ota.bin"


def checksum(data: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, data).hexdigest()


class PrepareFirmwareChannelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "artifact"
        self.output = self.root / "site" / "firmware" / "beta"
        self.version_dir = self.source / "waveshare-voice" / "v2.0.0-beta.3"
        self.version_dir.mkdir(parents=True)

        self.factory_data = b"synthetic factory image"
        self.ota_data = b"synthetic ota image"
        (self.version_dir / FACTORY_NAME).write_bytes(self.factory_data)
        (self.version_dir / OTA_NAME).write_bytes(self.ota_data)

        self.manifest = {
            "name": "jyoushiki.waveshare-voice",
            "version": "v2.0.0-beta.3",
            "builds": [
                {
                    "chipFamily": "ESP32-S3",
                    "ota": {
                        "path": OTA_NAME,
                        "md5": checksum(self.ota_data, "md5"),
                        "sha256": checksum(self.ota_data, "sha256"),
                    },
                    "parts": [
                        {
                            "path": FACTORY_NAME,
                            "offset": 0,
                            "md5": checksum(self.factory_data, "md5"),
                            "sha256": checksum(self.factory_data, "sha256"),
                        }
                    ],
                }
            ],
        }
        (self.version_dir / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_nested_build_artifact_is_normalized_for_pages(self) -> None:
        prepare(self.source, self.output)

        self.assertEqual(
            (self.output / FACTORY_NAME).read_bytes(), self.factory_data
        )
        self.assertEqual((self.output / OTA_NAME).read_bytes(), self.ota_data)

        manifest = json.loads((self.output / "manifest.json").read_text())
        build = manifest["builds"][0]
        self.assertEqual(build["parts"][0]["path"], FACTORY_NAME)
        self.assertEqual(build["ota"]["path"], OTA_NAME)
        self.assertEqual(build["ota"]["sha256"], checksum(self.ota_data, "sha256"))

    def test_duplicate_firmware_file_is_rejected(self) -> None:
        duplicate = self.source / "duplicate"
        duplicate.mkdir()
        (duplicate / FACTORY_NAME).write_bytes(self.factory_data)

        with self.assertRaisesRegex(ValueError, "found 2"):
            prepare(self.source, self.output)

    def test_hash_mismatch_is_rejected(self) -> None:
        (self.version_dir / OTA_NAME).write_bytes(b"corrupted")

        with self.assertRaisesRegex(ValueError, "mismatch"):
            prepare(self.source, self.output)

    def test_multiple_manifests_are_rejected(self) -> None:
        (self.source / "second.manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "found 2"):
            prepare(self.source, self.output)


if __name__ == "__main__":
    unittest.main()
