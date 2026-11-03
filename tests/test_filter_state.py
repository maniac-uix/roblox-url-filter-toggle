"""Tests de lecture d'état : parsing XML, erreurs, mapping blocked/allowed,
détection de la liste blanche (abandon sans écriture)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import (FakeResponse, FakeSession, default_state,
                         load_script, run_action)

mod = load_script()


class TestStateParsing(unittest.TestCase):
    def _session(self, **kwargs):
        return FakeSession(**kwargs)

    def test_parse_state(self):
        session = self._session(states=[default_state(
            UrlFilterEnable="1", UrlFilterTarget="0",
            MacFilterEnable="1", MacFilterTarget="0")])
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            etat = mod.lire_etat_filtre(session, "http://192.168.11.1")
        self.assertEqual(etat["UrlFilterEnable"], "1")
        self.assertEqual(etat["UrlFilterTarget"], "0")
        self.assertEqual(etat["MacFilterEnable"], "1")
        self.assertEqual(etat["MacFilterTarget"], "0")

    def test_parse_bad_if_errorstr(self):
        session = self._session()
        session.get = lambda url, **kw: FakeResponse(
            text="<root><IF_ERRORSTR>FAIL</IF_ERRORSTR></root>")
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.StateReadError):
                mod.lire_etat_filtre(session, "http://192.168.11.1")

    def test_parse_malformed_xml(self):
        session = self._session()
        session.get = lambda url, **kw: FakeResponse(text="ceci n'est pas du XML")
        with mock.patch.object(mod.requests, "Session",
                               lambda *a, **k: session):
            with self.assertRaises(mod.StateReadError):
                mod.lire_etat_filtre(session, "http://192.168.11.1")


class TestStatusMapping(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(mod.status_label("1"), "blocked")
        self.assertEqual(mod.status_label("0"), "allowed")

    def test_status_command_reads_only(self):
        session = FakeSession(states=[default_state(UrlFilterEnable="1")])
        code, result = run_action(mod, "status", session)
        self.assertEqual(code, 0)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["requested_action"], "status")
        self.assertTrue(result["verified"])
        self.assertEqual(session.write_count(), 0)


class TestWhitelistDetection(unittest.TestCase):
    def test_whitelist_aborts_without_write(self):
        # UrlFilterTarget "1" = liste blanche : abandon de sécurité.
        session = FakeSession(states=[default_state(UrlFilterTarget="1")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 8)
        self.assertEqual(result["error"], "WHITELIST_DETECTED")
        self.assertFalse(result["success"])
        self.assertEqual(session.write_count(), 0)

    def test_blacklist_passes_guard(self):
        session = FakeSession(states=[default_state(UrlFilterTarget="0")])
        code, result = run_action(mod, "status", session)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "allowed")


class TestStrictParamValidation(unittest.TestCase):
    """Validation stricte des 4 paramètres avant toute écriture :
    chaque valeur doit valoir "0" ou "1", sinon abandon (code 6)
    sans aucun appel d'écriture."""

    def _assert_aborts_without_write(self, session):
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 6)
        self.assertEqual(result["error"], "STATE_READ_FAILED")
        self.assertFalse(result["success"])
        self.assertEqual(session.write_count(), 0)

    def test_mac_filter_enable_invalid_value(self):
        session = FakeSession(states=[default_state(MacFilterEnable="2")])
        self._assert_aborts_without_write(session)

    def test_mac_filter_target_invalid_value(self):
        session = FakeSession(states=[default_state(MacFilterTarget="yes")])
        self._assert_aborts_without_write(session)

    def test_mac_filter_enable_empty_value(self):
        # <ParaValue></ParaValue> donne None au parsing : traité comme absent.
        session = FakeSession(states=[default_state(MacFilterEnable="")])
        self._assert_aborts_without_write(session)

    def test_mac_filter_enable_absent(self):
        state = default_state()
        del state["MacFilterEnable"]
        session = FakeSession(states=[state])
        self._assert_aborts_without_write(session)

    def test_url_filter_target_out_of_range(self):
        # "2" n'est ni 0 ni 1 : erreur de lecture, pas liste blanche.
        session = FakeSession(states=[default_state(UrlFilterTarget="2")])
        self._assert_aborts_without_write(session)

    def test_mac_params_at_one_still_toggle(self):
        # Valeurs "1" légitimes : la bascule a lieu normalement.
        session = FakeSession(states=[
            default_state(UrlFilterEnable="0", MacFilterEnable="1",
                          MacFilterTarget="1"),
            default_state(UrlFilterEnable="1", MacFilterEnable="1",
                          MacFilterTarget="1")])
        code, result = run_action(mod, "toggle", session)
        self.assertEqual(code, 0)
        self.assertTrue(result["success"])
        self.assertEqual(session.write_count(), 1)
        self.assertIn("MacFilterEnable=1", session.writes[0])
        self.assertIn("MacFilterTarget=1", session.writes[0])


if __name__ == "__main__":
    unittest.main()
