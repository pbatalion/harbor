from __future__ import annotations

import urllib.parse

from src.settings import load_settings


GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def build_auth_url(client_id: str, scope: str, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob") -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_OAUTH_URL}?{urllib.parse.urlencode(params)}"


def main() -> None:
    settings = load_settings()
    if not settings.google_client_id:
        print("Set GOOGLE_CLIENT_ID in .env first.")
        return

    scope = " ".join(
        [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
        ]
    )

    print("Open this URL to generate an auth code:")
    print(build_auth_url(settings.google_client_id, scope=scope))
    print("\nThen exchange the code manually for refresh tokens using Google's token endpoint.")


if __name__ == "__main__":
    main()
