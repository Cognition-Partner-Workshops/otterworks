from __future__ import annotations

import unittest

from collection_slack.config import ConfigError, load_config

BASE = {"COLLECTION_ACCESS_TOKEN": "x" * 24}
LIVE = {
    **BASE,
    "COLLECTION_MODE": "live",
    "DEVIN_API_KEY": "cog_example",
    "COLLECTION_DEVIN_ORG_ID": "org-example",
    "COLLECTION_CREATE_AS_USER_ID": "user-example",
}


class ConfigTests(unittest.TestCase):
    def test_defaults_are_local_stub(self) -> None:
        c = load_config(BASE)
        self.assertEqual(c.bind_host, "127.0.0.1")
        self.assertEqual(c.mode, "stub")
        self.assertFalse(c.live)
        self.assertEqual(c.devin_mode, "fusion")

    def test_short_access_token_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            load_config({"COLLECTION_ACCESS_TOKEN": "short"})

    def test_live_requires_server_side_ids(self) -> None:
        for missing in ("DEVIN_API_KEY", "COLLECTION_DEVIN_ORG_ID", "COLLECTION_CREATE_AS_USER_ID"):
            env = {k: v for k, v in LIVE.items() if k != missing}
            with self.assertRaises(ConfigError):
                load_config(env)
        self.assertTrue(load_config(LIVE).live)

    def test_non_loopback_http_api_base_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            load_config({**LIVE, "COLLECTION_DEVIN_API_BASE": "http://api.example.com"})

    def test_automation_url_must_match_allowlist(self) -> None:
        env = {
            **BASE,
            "COLLECTION_AUTOMATION_URL": "https://hooks.example.com/x",
            "COLLECTION_AUTOMATION_SECRET": "s",
            "COLLECTION_AUTOMATION_RULES": "mention:",
        }
        with self.assertRaises(ConfigError):
            load_config(env)
        with self.assertRaises(ConfigError):
            load_config({**env, "COLLECTION_AUTOMATION_ALLOWED_HOST": "other.example.com"})
        with self.assertRaises(ConfigError):
            load_config(
                {
                    **env,
                    "COLLECTION_AUTOMATION_URL": "https://hooks.example.com/x?token=1",
                    "COLLECTION_AUTOMATION_ALLOWED_HOST": "hooks.example.com",
                }
            )
        c = load_config({**env, "COLLECTION_AUTOMATION_ALLOWED_HOST": "hooks.example.com"})
        self.assertTrue(c.automation_enabled)

    def test_secrets_not_in_repr(self) -> None:
        c = load_config({**LIVE, "COLLECTION_AUTOMATION_SECRET": "automation-secret-value"})
        self.assertNotIn("cog_example", repr(c))
        self.assertNotIn("automation-secret-value", repr(c))
        self.assertNotIn("x" * 24, repr(c))
