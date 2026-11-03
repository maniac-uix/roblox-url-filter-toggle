"""Tests cryptographiques : padding PKCS#1 v1.5, en-tête Check
(RSA + SHA-256 + Base64), longueurs de ciphertext, rejet des messages
trop longs.

Aucun routeur requis, aucune clé réelle : la paire RSA de test ci-dessous
est synthétique (générée pour ces tests, elle ne protège rien) et sert
uniquement à déchiffrer pour vérifier la structure du bloc.
"""
import base64
import hashlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from fake_router import load_script

mod = load_script()

# Paire RSA de test (N de 511 bits, k = 64 octets), E = 65537.
TEST_N_HEX = (
    "591414b1a429becc7082a57eed9d07bfbffb9ec45e4812635b5071109a15c808"
    "34e0f7b37baf42ac3c6a14b03c57cd66f9e5217b9eef11131cdbfc7d1c3da237"
)
TEST_E = 65537
TEST_D = int(
    "5913bb9de88bd6409a420b3ce260255f9a9c04285a1fb843a30cce03cc11fbf5"
    "0a00f6a211fe14e5244ca4c3aa0089fda60813b2b3c203dc979a0c5b722801",
    16)
TEST_K = 64  # (511 + 7) // 8

# Seconde paire de test (N de 768 bits, k = 96 octets) : le digest SHA-256
# hexadécimal (64 octets) y entre, ce qui permet le round-trip complet de
# make_check_header avec une clé dont on possède l'exposant privé.
TEST_N768_HEX = (
    "b179fb9682c2bc89ae4859e016a595c11f460aad7e2613d6528b7167c4b89d5d"
    "79ab4f42959cc90b7841360fd4e21f24bcf7dea2d9b1a43e10113b516522968c0"
    "8235e4ff6ba39d555d38e4dc5cdfc3942c5d782d4a3525c6d028de1905e80f5"
)
TEST_D768 = int(
    "3ecb3e2d1ecef00e76cfba9d02e64b7a2d2a8714a391ad6b23819afa702c31e1"
    "a4eeebf84f1f4e32f4b57dff53ff3dad1719ae83dee2d359971e2b9d1fde8e23"
    "c2ac7d442277387569329739d40e4d17d44b0a6d0ee34e0f79e143bb50aff9f1",
    16)
TEST_K768 = 96


def decrypt_test_key(ciphertext, n_hex=TEST_N_HEX, d=TEST_D, k=TEST_K):
    """Déchiffre avec un exposant privé de test (vérification seulement)."""
    n = int(n_hex, 16)
    m = pow(int.from_bytes(ciphertext, "big"), d, n)
    return m.to_bytes(k, "big")


def parse_pkcs1_block(em):
    """Découpe un bloc 00 02 || PS || 00 || message. Retourne (PS, message)."""
    assert em[0] == 0x00, "premier octet non nul"
    assert em[1] == 0x02, "deuxième octet différent de 02"
    sep = em.index(b"\x00", 2)
    return em[2:sep], em[sep + 1:]


class TestCiphertextLength(unittest.TestCase):
    def test_real_key_ciphertext_is_512_bytes(self):
        # Clé du routeur (4096 bits) : le ciphertext fait toujours 512 octets.
        self.assertEqual(len(mod.rsa_pkcs1v15_encrypt(b"test")), 512)

    def test_small_key_ciphertext_is_key_size(self):
        with mock.patch.object(mod, "RSA_N_HEX", TEST_N_HEX), \
                mock.patch.object(mod, "RSA_E", TEST_E):
            self.assertEqual(len(mod.rsa_pkcs1v15_encrypt(b"test")), TEST_K)


class TestPkcs1v15Structure(unittest.TestCase):
    def _encrypt_small(self, message):
        with mock.patch.object(mod, "RSA_N_HEX", TEST_N_HEX), \
                mock.patch.object(mod, "RSA_E", TEST_E):
            return mod.rsa_pkcs1v15_encrypt(message)

    def test_block_structure_and_roundtrip(self):
        message = b"hello"
        ps, recovered = parse_pkcs1_block(
            decrypt_test_key(self._encrypt_small(message)))
        self.assertEqual(recovered, message)
        self.assertEqual(len(ps), TEST_K - len(message) - 3)
        self.assertTrue(all(b != 0 for b in ps),
                        "chaque octet de PS doit être non nul")

    def test_padding_length_for_various_messages(self):
        for message in (b"a", b"test-message", b"x" * 53):
            # 53 = longueur maximale pour k = 64 (64 - 11).
            ps, recovered = parse_pkcs1_block(
                decrypt_test_key(self._encrypt_small(message)))
            self.assertEqual(recovered, message)
            self.assertEqual(len(ps), TEST_K - len(message) - 3)
            self.assertGreaterEqual(len(ps), 8,
                                    "PS doit faire au moins 8 octets")
            self.assertTrue(all(b != 0 for b in ps))

    def test_message_too_long_rejected(self):
        # 54 octets > 64 - 11 : rejet, même chose pour un message plus long.
        with mock.patch.object(mod, "RSA_N_HEX", TEST_N_HEX), \
                mock.patch.object(mod, "RSA_E", TEST_E):
            with self.assertRaises(ValueError):
                mod.rsa_pkcs1v15_encrypt(b"x" * 54)
            with self.assertRaises(ValueError):
                mod.rsa_pkcs1v15_encrypt(b"x" * 100)

    def test_real_key_message_too_long_rejected(self):
        # Clé du routeur : 512 - 11 = 501 octets maximum.
        with self.assertRaises(ValueError):
            mod.rsa_pkcs1v15_encrypt(b"x" * 502)


class TestCheckHeader(unittest.TestCase):
    BODY = "IF_ACTION=Apply&MacFilterEnable=0&UrlFilterTarget=0"

    def test_header_decodes_to_512_bytes_with_real_key(self):
        raw = base64.b64decode(mod.make_check_header(self.BODY))
        self.assertEqual(len(raw), 512)

    def test_header_uses_sha256_of_body_then_base64(self):
        captured = {}

        def fake_encrypt(message):
            captured["message"] = message
            return b"\xAB" * 512

        with mock.patch.object(mod, "rsa_pkcs1v15_encrypt", fake_encrypt):
            header = mod.make_check_header(self.BODY)
        # L'entrée du chiffrement est le SHA-256 hex du body...
        self.assertEqual(captured["message"],
                         hashlib.sha256(self.BODY.encode("utf-8"))
                         .hexdigest().encode("utf-8"))
        # ... et la sortie est le Base64 du ciphertext.
        self.assertEqual(header, base64.b64encode(b"\xAB" * 512).decode())

    def test_header_roundtrip_with_test_key(self):
        # Le digest SHA-256 (64 octets) ne rentre pas dans la clé de 64
        # octets : on utilise la clé de test de 96 octets pour le
        # round-trip complet de make_check_header.
        with mock.patch.object(mod, "RSA_N_HEX", TEST_N768_HEX), \
                mock.patch.object(mod, "RSA_E", TEST_E):
            header = mod.make_check_header(self.BODY)
        raw = base64.b64decode(header)
        self.assertEqual(len(raw), TEST_K768)
        ps, recovered = parse_pkcs1_block(
            decrypt_test_key(raw, TEST_N768_HEX, TEST_D768, TEST_K768))
        self.assertEqual(recovered,
                         hashlib.sha256(self.BODY.encode("utf-8"))
                         .hexdigest().encode("utf-8"))
        self.assertTrue(all(b != 0 for b in ps))


if __name__ == "__main__":
    unittest.main()
