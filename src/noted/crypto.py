import base64
import os
import unicodedata
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class CryptoError(Exception):
    """Base exception for crypto operations."""
    pass

class InvalidPasswordOrCorruptedError(CryptoError):
    """Raised when password is wrong or ciphertext has been altered."""
    pass

def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 256-bit AES key from a password and salt using PBKDF2-HMAC-SHA256."""
    norm_password = unicodedata.normalize("NFC", password).encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(norm_password)

def encrypt_body(plaintext: str, password: str) -> tuple[str, str, str]:
    """Encrypts plaintext using AES-256-GCM.
    
    Returns (ciphertext_b64, salt_hex, nonce_hex).
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    data = unicodedata.normalize("NFC", plaintext).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)
    ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")

    return ciphertext_b64, salt.hex(), nonce.hex()

def decrypt_body(ciphertext_b64: str, password: str, salt_hex: str, nonce_hex: str) -> str:
    """Decrypts ciphertext using AES-256-GCM.
    
    Raises InvalidPasswordOrCorruptedError on mismatch or tampering.
    """
    try:
        salt = bytes.fromhex(salt_hex)
        nonce = bytes.fromhex(nonce_hex)
        ciphertext = base64.b64decode(ciphertext_b64)
        key = derive_key(password, salt)
        aesgcm = AESGCM(key)

        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return unicodedata.normalize("NFC", plaintext_bytes.decode("utf-8"))
    except Exception as e:
        raise InvalidPasswordOrCorruptedError("Invalid password or corrupted data.") from e
