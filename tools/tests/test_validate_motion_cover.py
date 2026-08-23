import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_motion_cover import validate_catalog


class ValidateMotionCoverTest(unittest.TestCase):
    def make_repo(self, *, probe=None, manifest_overrides=None, asset_bytes=b"fake-video"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        asset_dir = root / "covers" / "artist" / "album"
        asset_dir.mkdir(parents=True)
        sha = hashlib.sha256(asset_bytes).hexdigest()
        asset_path = asset_dir / f"demo-{sha[:8]}.mp4"
        asset_path.write_bytes(asset_bytes)

        asset = {
            "type": "mp4",
            "path": asset_path.relative_to(root).as_posix(),
            "sha256": sha,
            "sizeBytes": len(asset_bytes),
            "width": 720,
            "height": 720,
            "fps": 24,
            "durationMs": 15000,
        }
        manifest = {
            "schema": 1,
            "catalogId": "mispotify-official",
            "revision": 1,
            "generatedAt": "2026-08-23T00:00:00Z",
            "cdnBaseUrl": "https://example.invalid/",
            "assets": {"demo": asset},
            "entries": [{
                "id": "demo-track",
                "scope": "track",
                "identity": {"artist": "Artist", "title": "Song"},
                "assetId": "demo",
            }],
        }
        if manifest_overrides:
            manifest_overrides(manifest, asset, asset_path)
        manifest_path = root / "catalog" / "v1" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        default_probe = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": 720,
                "height": 720,
                "avg_frame_rate": "24/1",
                "r_frame_rate": "24/1",
                "duration": "15.000000",
            }],
            "format": {"duration": "15.000000", "size": str(len(asset_bytes))},
        }
        return root, manifest_path, (probe or default_probe)

    def test_valid_official_mp4_passes(self):
        root, manifest, probe = self.make_repo()
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        self.assertEqual([], errors)

    def test_audio_stream_is_rejected_with_clear_reason(self):
        fixture = Path(__file__).with_name("fixtures") / "invalid_audio_ffprobe.json"
        probe = json.loads(fixture.read_text(encoding="utf-8"))
        root, manifest, probe = self.make_repo(probe=probe)
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        self.assertTrue(any("audio" in error.lower() for error in errors), errors)

    def test_dimensions_above_720_are_rejected(self):
        probe = {
            "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 1080, "height": 1080, "avg_frame_rate": "24/1", "duration": "15"}],
            "format": {"duration": "15", "size": "10"},
        }
        root, manifest, probe = self.make_repo(probe=probe)
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        self.assertTrue(any("720" in error and "dimension" in error.lower() for error in errors), errors)

    def test_mp4_codec_and_pixel_format_are_enforced(self):
        probe = {
            "streams": [{"codec_type": "video", "codec_name": "hevc", "pix_fmt": "yuv444p", "width": 720, "height": 720, "avg_frame_rate": "24/1", "duration": "15"}],
            "format": {"duration": "15", "size": "10"},
        }
        root, manifest, probe = self.make_repo(probe=probe)
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        joined = "\n".join(errors).lower()
        self.assertIn("h264", joined)
        self.assertIn("yuv420p", joined)

    def test_fps_above_24_and_duration_above_20_seconds_are_rejected(self):
        probe = {
            "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 720, "height": 720, "avg_frame_rate": "30/1", "duration": "21"}],
            "format": {"duration": "21", "size": "10"},
        }
        root, manifest, probe = self.make_repo(probe=probe)
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        joined = "\n".join(errors).lower()
        self.assertIn("24 fps", joined)
        self.assertIn("20 seconds", joined)

    def test_manifest_hash_size_and_hash_suffix_must_match_file(self):
        def break_manifest(manifest, asset, asset_path):
            asset["sha256"] = "0" * 64
            asset["sizeBytes"] = 999

        root, manifest, probe = self.make_repo(manifest_overrides=break_manifest)
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        joined = "\n".join(errors).lower()
        self.assertIn("sha-256", joined)
        self.assertIn("sizebytes", joined)
        self.assertIn("filename", joined)

    def test_traversal_and_missing_asset_reference_are_rejected(self):
        def break_manifest(manifest, asset, asset_path):
            asset["path"] = "../escape.mp4"
            manifest["entries"][0]["assetId"] = "missing"

        root, manifest, probe = self.make_repo(manifest_overrides=break_manifest)
        errors = validate_catalog(root, manifest, probe_runner=lambda _: probe)
        joined = "\n".join(errors).lower()
        self.assertIn("unsafe path", joined)
        self.assertIn("missing asset", joined)


if __name__ == "__main__":
    unittest.main()
