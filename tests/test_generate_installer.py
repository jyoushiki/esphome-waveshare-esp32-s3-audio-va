import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from scripts.generate_installer import FACTORY, RELEASES, REPOSITORY, generate


class PageLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.channel = None
        self.links = {}
        self.manifests = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.channel = attrs["aria-labelledby"].removesuffix("-heading")
            self.links[self.channel] = []
        elif self.channel and tag == "a":
            self.links[self.channel].append(attrs["href"])
        elif self.channel and tag == "esp-web-install-button":
            self.manifests[self.channel] = attrs["manifest"]

    def handle_endtag(self, tag):
        if tag == "section":
            self.channel = None


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)
        self.write_channel("stable", "v2.0.0")
        self.write_channel("beta", "2.1.0-beta.1")

    def write_channel(self, channel, version, factory=FACTORY):
        directory = self.site / "firmware" / channel
        directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": version,
            "builds": [{"chipFamily": "ESP32-S3", "parts": [{"path": factory, "offset": 0}]}],
        }
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / FACTORY).write_bytes(b"synthetic factory image")

    def test_each_install_and_download_uses_its_own_release(self):
        generate(self.site)
        html = (self.site / "index.html").read_text()
        page = PageLinks(html)
        for channel, tag in (("stable", "v2.0.0"), ("beta", "v2.1.0-beta.1")):
            self.assertEqual(page.manifests[channel], f"firmware/{channel}/manifest.json")
            expected = [
                f"firmware/{channel}/{FACTORY}",
                f"{RELEASES}/tag/{tag}",
                f"{RELEASES}/download/{tag}/waveshare-va.yaml",
                f"{REPOSITORY}/blob/{tag}/README.md#documentation-and-support",
            ]
            self.assertEqual(page.links[channel], expected)
            self.assertIn(f'<p class="version">{tag}</p>', html)

    def test_channels_can_offer_the_same_stable_release(self):
        self.write_channel("beta", "v2.0.0")
        generate(self.site)
        page = PageLinks((self.site / "index.html").read_text())
        self.assertEqual(page.links["stable"][1:], page.links["beta"][1:])
        self.assertNotEqual(page.manifests["stable"], page.manifests["beta"])

    def test_missing_image_does_not_publish_a_broken_page(self):
        (self.site / "firmware" / "stable" / FACTORY).unlink()
        with self.assertRaises(FileNotFoundError):
            generate(self.site)
        self.assertFalse((self.site / "index.html").exists())

    def test_unsafe_version_and_wrong_image_layout_are_rejected(self):
        for version, factory in (("<script>oops</script>", FACTORY),
                                 ("v2.1.0-beta.1", "../wrong.bin")):
            with self.subTest(version=version, factory=factory):
                self.write_channel("beta", version, factory)
                with self.assertRaises(ValueError):
                    generate(self.site)
                self.assertFalse((self.site / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
