from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

import struct


def derive_routing_key(psk: bytes, hours_since_epoch: int) -> bytes:
    data = b"r" + struct.pack("<I", hours_since_epoch) + psk
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize()[:16]


def derive_crypto_key(psk: bytes, hours_since_epoch: int) -> bytes:
    data = b"c" + struct.pack("<I", hours_since_epoch) + psk
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize()[:16]


def aes_gcm_encrypt(key: bytes, payload: bytes, iv: bytes, tagLength: int) -> bytes:
    encryptor = Cipher(
        algorithms.AES(key), modes.GCM(iv), backend=default_backend()
    ).encryptor()

    ciphertext = encryptor.update(payload) + encryptor.finalize()
    full_tag = encryptor.tag  # 16 bytes

    short_tag = full_tag[:tagLength]  # truncate

    return ciphertext + short_tag


def aes_gcm_decrypt(key: bytes, ciphertext: bytes, iv: bytes, tagLength: int) -> bytes:
    short_tag = ciphertext[-tagLength:]
    ciphertext = ciphertext[:-tagLength]

    # # Pad back to 16 bytes
    # full_tag = short_tag + b'\x00' * (16 - len(short_tag))

    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, short_tag, min_tag_length=tagLength),
        backend=default_backend(),
    ).decryptor()

    return decryptor.update(ciphertext) + decryptor.finalize()
