"""Tests de cohérence entre la documentation et le code :
- la table des codes de sortie du README (et de tasker/README.md)
  doit correspondre exactement aux constantes EXIT_* du script ;
- la contrainte requests doit être identique dans pyproject.toml
  (référence) et requirements.txt.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import load_script

mod = load_script()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXIT_CONSTANTS = {
    "EXIT_OK": 0,
    "EXIT_ALREADY": 2,
    "EXIT_UNREACHABLE": 3,
    "EXIT_AUTH": 4,
    "EXIT_WRITE": 5,
    "EXIT_UNCONFIRMED": 6,
    "EXIT_RUNNING": 7,
    "EXIT_USAGE": 8,
    "EXIT_ROUTER_ERROR": 9,
}


def table_codes(path, marker):
    """Codes de la table des codes de sortie d'un README.

    `marker` est le texte qui précède la table (titre de section
    pour le README principal, phrase d'introduction pour
    tasker/README.md, qui n'a pas de titre dédié).
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    section = text.split(marker, 1)[1]
    # La table s'arrête à la première ligne non-table après son début.
    codes = set()
    for line in section.splitlines():
        match = re.match(r"\|\s*(\d+)\s*\|", line)
        if match:
            codes.add(int(match.group(1)))
        elif codes and not line.startswith("|"):
            break
    return codes


class TestExitCodeTableMatchesScript(unittest.TestCase):
    def test_script_constants_are_as_expected(self):
        for name, value in EXIT_CONSTANTS.items():
            self.assertEqual(getattr(mod, name), value, name)

    def test_readme_table_matches_script_constants(self):
        expected = set(EXIT_CONSTANTS.values())
        self.assertEqual(table_codes(os.path.join(ROOT, "README.md"),
                                     "Codes de sortie"),
                         expected)

    def test_tasker_readme_table_matches_script_constants(self):
        expected = set(EXIT_CONSTANTS.values())
        self.assertEqual(
            table_codes(os.path.join(ROOT, "tasker", "README.md"),
                        "Le code de sortie"),
            expected)


def requests_constraint_from_pyproject(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r'"requests([^"]*)"', text)
    if match is None:
        raise ValueError("requests introuvable dans pyproject.toml")
    return "requests" + match.group(1)


class TestRequestsConstraintParity(unittest.TestCase):
    def test_pyproject_and_requirements_agree(self):
        pyproject = requests_constraint_from_pyproject(
            os.path.join(ROOT, "pyproject.toml"))
        with open(os.path.join(ROOT, "requirements.txt"),
                  encoding="utf-8") as handle:
            requirements = handle.read().strip()
        self.assertEqual(requirements, pyproject)


if __name__ == "__main__":
    unittest.main()
