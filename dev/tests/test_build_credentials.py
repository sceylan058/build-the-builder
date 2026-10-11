"""build.py credential handling: a credit/auth error is a credential failure, never a config error.   python3 -m unittest dev/tests/test_build_credentials.py"""
import pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder"))
import build  # noqa: E402


class Credentials(unittest.TestCase):
    def test_detects_credit_and_auth_errors(self):
        for t in ("Credit balance is too low", "API Error: 401 {\"type\":\"authentication_error\"}", "invalid x-api-key", "Your credit balance is too low to access the API"):
            self.assertTrue(build.credential_error(t), t)

    def test_config_errors_are_not_credential_errors(self):
        for t in ("config error: missing 'hardship_triggers'", "R1 openapi: unknown field", "config ready", ""):
            self.assertFalse(build.credential_error(t), t)

    def test_fallback_path_is_wired(self):
        src = (ROOT / "builder" / "build.py").read_text()
        self.assertIn('credentials: api_key -> claude_login (', src)
        self.assertIn('os.environ.pop("ANTHROPIC_API_KEY", None)', src)
        self.assertIn("no repair rounds on a credential failure", src)


if __name__ == "__main__":
    unittest.main()
