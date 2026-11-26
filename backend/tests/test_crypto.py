from cryptography.fernet import Fernet

from app.core.crypto import SecretCipher


def test_secret_cipher_round_trip_does_not_store_plaintext() -> None:
    """Persisted values are authenticated ciphertext, not merely encoded credentials."""

    cipher = SecretCipher(Fernet.generate_key())
    encrypted = cipher.encrypt("bok_production_key")

    assert encrypted != "bok_production_key"
    assert cipher.decrypt(encrypted) == "bok_production_key"
