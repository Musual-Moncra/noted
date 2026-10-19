import pytest
from noted.crypto import (
    CryptoError,
    InvalidPasswordOrCorruptedError,
    derive_key,
    encrypt_body,
    decrypt_body,
)

def test_round_trip_encryption():
    plaintext = "Bí mật cần bảo vệ: Mật khẩu ngân hàng 123456!"
    password = "SuperSecretPassword123"

    ciphertext_b64, salt_hex, nonce_hex = encrypt_body(plaintext, password)
    assert ciphertext_b64 != plaintext
    assert len(salt_hex) == 32  # 16 bytes hex
    assert len(nonce_hex) == 24  # 12 bytes hex

    decrypted = decrypt_body(ciphertext_b64, password, salt_hex, nonce_hex)
    assert decrypted == plaintext

def test_invalid_password_raises_error():
    plaintext = "Top secret data"
    password = "CorrectPassword"
    wrong_password = "WrongPassword"

    ciphertext_b64, salt_hex, nonce_hex = encrypt_body(plaintext, password)

    with pytest.raises(InvalidPasswordOrCorruptedError):
        decrypt_body(ciphertext_b64, wrong_password, salt_hex, nonce_hex)

def test_corrupted_ciphertext_raises_error():
    plaintext = "Data integrity test"
    password = "ValidPassword"

    ciphertext_b64, salt_hex, nonce_hex = encrypt_body(plaintext, password)
    # Tamper with ciphertext
    tampered_b64 = ("A" if ciphertext_b64[0] != "A" else "B") + ciphertext_b64[1:]

    with pytest.raises(InvalidPasswordOrCorruptedError):
        decrypt_body(tampered_b64, password, salt_hex, nonce_hex)

def test_empty_string_encryption():
    plaintext = ""
    password = "MyPassword"

    ciphertext_b64, salt_hex, nonce_hex = encrypt_body(plaintext, password)
    decrypted = decrypt_body(ciphertext_b64, password, salt_hex, nonce_hex)
    assert decrypted == ""

def test_vietnamese_unicode_normalization_preserved():
    # Test all Vietnamese tones and combining marks
    plaintext = "Tiếng Việt có dấu: Ắ, Ộ, Ễ, Ỷ, Đ, ừ, ợ... emoji: 🔒🔑"
    password = "Mật khẩu tiếng Việt"

    ciphertext_b64, salt_hex, nonce_hex = encrypt_body(plaintext, password)
    decrypted = decrypt_body(ciphertext_b64, password, salt_hex, nonce_hex)
    assert decrypted == plaintext
