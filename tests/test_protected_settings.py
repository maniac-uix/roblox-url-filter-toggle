"""Tests des paramètres protégés : inchangés -> succès, modifiés -> échec,
filtre MAC activé préservé (corps de la requête repris tel quel)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import FakeSession, default_state, load_script, run_action

mod = load_script()


class TestProtectedSettings(unittest.TestCase):
    def test_protected_unchanged_is_success(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="0"),
                                      default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 0)
        self.assertTrue(result["verified"])

    def test_protected_changed_is_exit_6(self):
        before = default_state(UrlFilterEnable="0", MacFilterEnable="0")
        after = default_state(UrlFilterEnable="1", MacFilterEnable="1")
        session = FakeSession(states=[before, after])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "PROTECTED_PARAMS_CHANGED")
        self.assertFalse(result["success"])

    def test_mode_changed_is_exit_6(self):
        before = default_state(UrlFilterEnable="0", UrlFilterTarget="0")
        after = default_state(UrlFilterEnable="1", UrlFilterTarget="1")
        session = FakeSession(states=[before, after])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "PROTECTED_PARAMS_CHANGED")

    def test_mac_enabled_is_preserved_in_write_body(self):
        before = default_state(UrlFilterEnable="0", MacFilterEnable="1",
                               MacFilterTarget="0")
        after = default_state(UrlFilterEnable="1", MacFilterEnable="1",
                              MacFilterTarget="0")
        session = FakeSession(states=[before, after])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 0)
        self.assertIn("MacFilterEnable=1", session.writes[0])
        self.assertIn("MacFilterTarget=0", session.writes[0])


if __name__ == "__main__":
    unittest.main()
