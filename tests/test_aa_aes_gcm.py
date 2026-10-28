"""Known-answer tests for the authenticated GDPval payload decoder."""
import importlib

import pytest


def test_aes256_zero_key_known_block():
    aes = importlib.import_module("scripts.aa_aes_gcm")
    cipher = aes.AES256(bytes(32))
    assert cipher.encrypt(bytes(16)).hex() == "dc95c078a2408989ad48a21492842087"


def test_aes256_fips_incrementing_key_known_block():
    aes = importlib.import_module("scripts.aa_aes_gcm")
    cipher = aes.AES256(bytes(range(32)))
    block = bytes.fromhex("00112233445566778899aabbccddeeff")
    assert cipher.encrypt(block).hex() == "8ea2b7ca516745bfeafc49904b496089"


@pytest.mark.parametrize("ciphertext,tag,plaintext", [
    ("", "530f8afbc74536b9a963b4f1c4cb738b", b""),
    ("cea7403d4d606b6e074ec5d3baf39d18",
     "d0d1c8a799996bf0265b98b5d48ab919", bytes(16)),
])
def test_nist_aes256_gcm_vectors(ciphertext, tag, plaintext):
    aes = importlib.import_module("scripts.aa_aes_gcm")
    assert aes.decrypt(bytes(32), bytes(12), bytes.fromhex(ciphertext + tag)) == plaintext


def test_gcm_refuses_a_tampered_tag():
    aes = importlib.import_module("scripts.aa_aes_gcm")
    body = bytearray.fromhex("cea7403d4d606b6e074ec5d3baf39d18"
                             "d0d1c8a799996bf0265b98b5d48ab919")
    body[-1] ^= 1
    with pytest.raises(ValueError, match="tag"):
        aes.decrypt(bytes(32), bytes(12), body)
