"""Downloader contract tests with temporary files and fake HTTP responses only."""
from pathlib import Path
import hashlib
import io
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import download_models as dm


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status, self.headers = status, headers or {}


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(dm, "ROOT", self.root)
        self.root_patch.start()
        self.data = b"model-content-for-verification"
        self.spec = {"bytes": len(self.data), "sha256": hashlib.sha256(self.data).hexdigest()}
        self.model = {"directory": "models/test", "repo": "example/public", "revision": "pinned"}
        self.dest = self.root / "models/test/weights.bin"

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_valid_existing_file_is_reused_without_network(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(self.data)
        with patch.object(dm.urllib.request, "urlopen") as network:
            dm.fetch_file(self.model, "weights.bin", self.spec)
            network.assert_not_called()

    def test_corrupt_existing_file_is_not_overwritten(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(b"bad")
        with self.assertRaisesRegex(RuntimeError, "wrong hash"):
            dm.fetch_file(self.model, "weights.bin", self.spec)
        self.assertEqual(self.dest.read_bytes(), b"bad")

    def test_success_is_published_only_after_hash_verification(self):
        with patch.object(dm.urllib.request, "urlopen", return_value=Response(self.data)):
            dm.fetch_file(self.model, "weights.bin", self.spec)
        self.assertTrue(dm.verified(self.dest, self.spec))
        self.assertFalse(self.dest.with_name("weights.bin.part").exists())

    def test_invalid_download_never_becomes_model_file(self):
        with patch.object(dm.urllib.request, "urlopen", return_value=Response(b"wrong")):
            with self.assertRaisesRegex(RuntimeError, "mismatch"):
                dm.fetch_file(self.model, "weights.bin", self.spec)
        self.assertFalse(self.dest.exists())

    def test_partial_is_resumed_only_with_correct_content_range(self):
        self.dest.parent.mkdir(parents=True)
        partial = self.dest.with_name("weights.bin.part")
        partial.write_bytes(self.data[:5])
        with patch.object(dm.urllib.request, "urlopen", return_value=Response(self.data[5:], 206, {"Content-Range": f"bytes 5-{len(self.data)-1}/{len(self.data)}"})) as network:
            dm.fetch_file(self.model, "weights.bin", self.spec)
            self.assertEqual(network.call_args.args[0].get_header("Range"), "bytes=5-")
        self.assertEqual(self.dest.read_bytes(), self.data)

    def test_server_ignoring_range_restarts_instead_of_appending(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.with_name("weights.bin.part").write_bytes(self.data[:5])
        with patch.object(dm.urllib.request, "urlopen", return_value=Response(self.data, 200)):
            dm.fetch_file(self.model, "weights.bin", self.spec)
        self.assertEqual(self.dest.read_bytes(), self.data)

    def test_completed_bad_partial_fails_without_network(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.with_name("weights.bin.part").write_bytes(b"x" * len(self.data))
        with patch.object(dm.urllib.request, "urlopen") as network:
            with self.assertRaisesRegex(RuntimeError, "wrong hash"):
                dm.fetch_file(self.model, "weights.bin", self.spec)
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
