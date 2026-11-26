"""Secret encryption used before any BookOrbit key or Discord URL reaches SQLite."""

from cryptography.fernet import Fernet, InvalidToken


class SecretCipher:
    """Authenticated symmetric encryption backed by a separately supplied Fernet key."""

    def __init__(self, key: str | bytes) -> None:
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid application encryption key") from error

    def encrypt(self, plaintext: str) -> str:
        """Encrypt one secret for database storage; empty secrets are never valid config."""

        if not plaintext:
            raise ValueError("Cannot encrypt an empty secret")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a stored secret without logging ciphertext or error material."""

        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise ValueError("Stored secret cannot be decrypted with this application key") from error
