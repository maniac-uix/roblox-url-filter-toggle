"""Tests de cohérence entre la documentation et le code :
- la table des codes de sortie du README (et de tasker/README.md)
  doit correspondre exactement aux constantes EXIT_* du script ;
- la contrainte requests doit être identique dans pyproject.toml
  (référence) et requirements.txt ;
- la ligne du code 8 des deux tables doit mentionner
  CONFIG_PERMISSIONS ;
- REF dans install.sh doit être un SHA complet de 40 caractères
  hexadécimaux.
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


def table_row_for_code(path, marker, code):
    """Ligne de la table des codes de sortie pour un code donné."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    section = text.split(marker, 1)[1]
    for line in section.splitlines():
        match = re.match(r"\|\s*(\d+)\s*\|", line)
        if match and int(match.group(1)) == code:
            return line
    raise ValueError("code %s introuvable dans %s" % (code, path))


class TestErrorIdentifiersInTables(unittest.TestCase):
    def test_config_permissions_in_code_8_rows(self):
        # CONFIG_PERMISSIONS doit figurer dans la ligne du code 8 des
        # deux tables, sinon elle dérive comme ROUTER_ERROR l'a fait.
        for path, marker in ((os.path.join(ROOT, "README.md"),
                              "Codes de sortie"),
                             (os.path.join(ROOT, "tasker", "README.md"),
                              "Le code de sortie")):
            row = table_row_for_code(path, marker, 8)
            self.assertIn("CONFIG_PERMISSIONS", row, path)


class TestInstallRefPinned(unittest.TestCase):
    def test_ref_is_a_full_40_hex_sha(self):
        # REF doit être un SHA complet (40 hex), jamais une forme
        # courte ni une branche : c'est ce qui garantit que
        # l'installation tire exactement l'arbre taggé.
        # Si REF passe un jour sur un nom de tag, ce test doit
        # être mis à jour en conséquence.
        with open(os.path.join(ROOT, "install.sh"),
                  encoding="utf-8") as handle:
            text = handle.read()
        match = re.search(r'REF="\$\{REF:-([^}]+)\}"', text)
        self.assertIsNotNone(match, "REF par défaut introuvable")
        self.assertRegex(match.group(1), r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
