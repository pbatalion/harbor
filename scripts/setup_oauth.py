from __future__ import annotations

import argparse
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from src.settings import load_settings


GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = {
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
    "calendar": "https://www.googleapis.com/auth/calendar.readonly",
}


class OAuthResult:
    def __init__(self) -> None:
        self.code: str = ""
        self.state: str = ""
        self.error: str = ""


def build_auth_url(*, client_id: str, redirect_uri: str, scopes: list[str], state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_OAUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def make_handler(result: OAuthResult):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            result.code = params.get("code", [""])[0]
            result.state = params.get("state", [""])[0]
            result.error = params.get("error", [""])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization received.</h1><p>You can return to the terminal.</p></body></html>"
            )

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Google refresh token for Harbor.")
    parser.add_argument("--account", choices=["work", "personal"], required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--include-calendar",
        action="store_true",
        help="Request calendar.readonly in addition to gmail.readonly.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not try to open the browser automatically.",
    )
    args = parser.parse_args()

    settings = load_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        print("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first.")
        return

    redirect_uri = f"http://127.0.0.1:{args.port}"
    scopes = [SCOPES["gmail"]]
    if args.include_calendar:
        scopes.append(SCOPES["calendar"])

    state = secrets.token_urlsafe(24)
    auth_url = build_auth_url(
        client_id=settings.google_client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state=state,
    )

    result = OAuthResult()
    server = HTTPServer(("127.0.0.1", args.port), make_handler(result))
    server.timeout = 300
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    print(f"Generating token for GOOGLE_REFRESH_TOKEN_{args.account.upper()}")
    print(f"Redirect URI: {redirect_uri}")
    print("Requested scopes:")
    for scope in scopes:
        print(f"- {scope}")
    print("\nOpen this URL and complete the consent flow:\n")
    print(auth_url)
    print("")

    if not args.no_browser:
        webbrowser.open(auth_url)

    server_thread.join(timeout=305)
    server.server_close()

    if result.error:
        print(f"OAuth error returned: {result.error}")
        return
    if not result.code:
        print("No authorization code received. If the browser flow did not complete, try again.")
        return
    if result.state != state:
        print("State mismatch. Abort and retry.")
        return

    try:
        payload = exchange_code_for_tokens(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            code=result.code,
            redirect_uri=redirect_uri,
        )
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        print(f"Token exchange failed: {body}")
        return

    refresh_token = str(payload.get("refresh_token", "")).strip()
    access_token = str(payload.get("access_token", "")).strip()

    if not refresh_token:
        print("No refresh_token returned. Re-run with prompt=consent by using a fresh authorization.")
        print(f"Access token (temporary): {access_token}")
        return

    print("\nSuccess. Put this in your .env:\n")
    print(f"GOOGLE_REFRESH_TOKEN_{args.account.upper()}={refresh_token}")


if __name__ == "__main__":
    main()
