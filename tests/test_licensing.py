import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import services.licensing as licensing


class LicensingSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / "private_key.pem"
        self.public = self.root / "public_key.pem"
        self.private_patch = patch.object(licensing, "LICENSE_PRIVATE_KEY_PATH", self.private)
        self.public_patch = patch.object(licensing, "LICENSE_PUBLIC_KEY_PATH", self.public)
        self.private_patch.start()
        self.public_patch.start()

    def tearDown(self):
        self.private_patch.stop()
        self.public_patch.stop()
        self.temp.cleanup()

    def test_verification_fails_closed_without_public_key_and_creates_no_keys(self):
        self.assertFalse(licensing.verify_license_payload({"edition": "starter"}, "invalid"))
        self.assertFalse(self.private.exists())
        self.assertFalse(self.public.exists())

    def test_signing_does_not_generate_keys_implicitly(self):
        with self.assertRaises(FileNotFoundError):
            licensing.load_private_key()
        self.assertFalse(self.private.exists())
        self.assertFalse(self.public.exists())

    def test_explicit_issuer_key_generation_signs_and_verifies(self):
        licensing.ensure_keys()
        payload = {"customer_name": "Test", "edition": "starter"}
        signature = licensing.sign_license_payload(payload)
        self.assertTrue(licensing.verify_license_payload(payload, signature))
        self.assertTrue(self.private.exists())
        self.assertTrue(self.public.exists())

    def test_invalid_existing_keypair_is_rejected(self):
        self.private.write_text("not a private key", encoding="utf-8")
        self.public.write_text("not a public key", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "invalid or mismatched"):
            licensing.ensure_keys()

    def test_partial_keypair_is_not_overwritten(self):
        self.public.write_text("existing public key", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Restore the matching keypair"):
            licensing.ensure_keys()
        self.assertEqual(self.public.read_text(encoding="utf-8"), "existing public key")
        self.assertFalse(self.private.exists())


if __name__ == "__main__":
    unittest.main()
