from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AuthError(RuntimeError):
    pass


def _load_encryption_key(path: str) -> bytes:
    key_path = Path(path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        raw = key_path.read_text(encoding="utf-8").strip()
        return base64.urlsafe_b64decode(raw.encode("utf-8"))

    key = os.urandom(32)
    key_path.write_text(base64.urlsafe_b64encode(key).decode("utf-8"), encoding="utf-8")
    return key


def encrypt_token(plaintext: str, key_path: str) -> str:
    key = _load_encryption_key(key_path)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = {
        "nonce": base64.urlsafe_b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("utf-8"),
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str, key_path: str) -> str:
    key = _load_encryption_key(key_path)
    decoded = base64.urlsafe_b64decode(ciphertext.encode("utf-8"))
    payload = json.loads(decoded.decode("utf-8"))
    nonce = base64.urlsafe_b64decode(payload["nonce"].encode("utf-8"))
    encrypted = base64.urlsafe_b64decode(payload["ciphertext"].encode("utf-8"))
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, encrypted, None)
    return plaintext.decode("utf-8")


def get_google_access_token(
    *, client_id: str, client_secret: str, refresh_token: str, timeout_seconds: int = 20
) -> str:
    if not client_id or not client_secret or not refresh_token:
        raise AuthError("Missing Google OAuth credentials")

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=timeout_seconds,
    )
    if response.status_code != 200:
        raise AuthError(f"Failed to refresh Google token: {response.status_code} {response.text}")

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise AuthError(f"Missing access_token in OAuth response: {json.dumps(payload)}")
    return token
