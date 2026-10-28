"""AES-256-GCM decryption for AA's 96-bit nonce, without associated data."""
from __future__ import annotations

import hmac


def _gf_byte(a: int, b: int) -> int:
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = ((a << 1) ^ (0x11b if a & 0x80 else 0)) & 0xff
        b >>= 1
    return result


def _sbox_value(value: int) -> int:
    # The AES S-box is the affine transform of the inverse in GF(2^8).
    inv = 1
    base, exponent = value, 254
    while exponent:
        if exponent & 1:
            inv = _gf_byte(inv, base)
        base = _gf_byte(base, base)
        exponent >>= 1
    return (inv ^ ((inv << 1) | (inv >> 7)) ^ ((inv << 2) | (inv >> 6))
            ^ ((inv << 3) | (inv >> 5)) ^ ((inv << 4) | (inv >> 4)) ^ 0x63) & 0xff


SBOX = tuple(_sbox_value(i) for i in range(256))


def _ror(word: int, shift: int) -> int:
    return ((word >> shift) | (word << (32 - shift))) & 0xffffffff


T0 = tuple((_gf_byte(s, 2) << 24) | (s << 16) | (s << 8) | _gf_byte(s, 3)
           for s in SBOX)
T1 = tuple(_ror(value, 8) for value in T0)
T2 = tuple(_ror(value, 16) for value in T0)
T3 = tuple(_ror(value, 24) for value in T0)


def _subword(word: int) -> int:
    return (SBOX[word >> 24] << 24 | SBOX[(word >> 16) & 255] << 16
            | SBOX[(word >> 8) & 255] << 8 | SBOX[word & 255])


class AES256:
    """Expand a 256-bit key once and encrypt 128-bit blocks."""

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("AES-256 requires a 32-byte key")
        words = [int.from_bytes(key[i:i + 4], "big") for i in range(0, 32, 4)]
        rcon = 1
        for index in range(8, 60):
            word = words[-1]
            if index % 8 == 0:
                word = _subword(_ror(word, 24)) ^ (rcon << 24)
                rcon = _gf_byte(rcon, 2)
            elif index % 8 == 4:
                word = _subword(word)
            words.append(words[index - 8] ^ word)
        self.words = words

    def encrypt(self, block: bytes) -> bytes:
        if len(block) != 16:
            raise ValueError("AES requires a 16-byte block")
        words = self.words
        state = [int.from_bytes(block[i:i + 4], "big") ^ words[i // 4]
                 for i in range(0, 16, 4)]
        for round_index in range(1, 14):
            a, b, c, d = state
            state = [
                T0[a >> 24] ^ T1[(b >> 16) & 255] ^ T2[(c >> 8) & 255] ^ T3[d & 255] ^ words[round_index * 4],
                T0[b >> 24] ^ T1[(c >> 16) & 255] ^ T2[(d >> 8) & 255] ^ T3[a & 255] ^ words[round_index * 4 + 1],
                T0[c >> 24] ^ T1[(d >> 16) & 255] ^ T2[(a >> 8) & 255] ^ T3[b & 255] ^ words[round_index * 4 + 2],
                T0[d >> 24] ^ T1[(a >> 16) & 255] ^ T2[(b >> 8) & 255] ^ T3[c & 255] ^ words[round_index * 4 + 3],
            ]
        out = []
        for i in range(4):
            word = (SBOX[state[i] >> 24] << 24
                    | SBOX[(state[(i + 1) % 4] >> 16) & 255] << 16
                    | SBOX[(state[(i + 2) % 4] >> 8) & 255] << 8
                    | SBOX[state[(i + 3) % 4] & 255])
            out.append((word ^ words[56 + i]).to_bytes(4, "big"))
        return b"".join(out)


def _ghash(ciphertext: bytes, subkey: bytes) -> bytes:
    value = int.from_bytes(subkey, "big")
    basis = []
    for _ in range(128):
        basis.append(value)
        value = (value >> 1) ^ (0xe1000000000000000000000000000000 if value & 1 else 0)
    tables = []
    for position in range(16):
        table = [0] * 256
        for byte in range(1, 256):
            bit = byte & -byte
            table[byte] = table[byte ^ bit] ^ basis[position * 8 + 8 - bit.bit_length()]
        tables.append(table)

    def multiply(block: bytes, accumulator: int) -> int:
        mixed = (accumulator ^ int.from_bytes(block, "big")).to_bytes(16, "big")
        product = 0
        for table, byte in zip(tables, mixed):
            product ^= table[byte]
        return product

    result = 0
    for offset in range(0, len(ciphertext), 16):
        result = multiply(ciphertext[offset:offset + 16].ljust(16, b"\0"), result)
    result = multiply((len(ciphertext) * 8).to_bytes(16, "big"), result)
    return result.to_bytes(16, "big")


def decrypt(key: bytes, nonce: bytes, body: bytes) -> bytes:
    """Verify the tag before decrypting a ciphertext followed by its tag."""
    if len(nonce) != 12 or len(body) < 16:
        raise ValueError("invalid GCM nonce or tag length")
    cipher = AES256(key)
    ciphertext, tag = body[:-16], body[-16:]
    initial_counter = nonce + bytes(3) + b"\1"
    mask = cipher.encrypt(initial_counter)
    auth = _ghash(ciphertext, cipher.encrypt(bytes(16)))
    expected = bytes(a ^ b for a, b in zip(mask, auth))
    if not hmac.compare_digest(expected, tag):
        raise ValueError("GCM tag mismatch")
    result = bytearray()
    for offset in range(0, len(ciphertext), 16):
        counter = nonce + (2 + offset // 16).to_bytes(4, "big")
        stream = cipher.encrypt(counter)
        result.extend(a ^ b for a, b in zip(ciphertext[offset:offset + 16], stream))
    return bytes(result)
