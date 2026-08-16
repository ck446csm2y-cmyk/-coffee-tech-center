#!/usr/bin/env python3
"""Verify Avito API credentials without exposing secrets or changing Avito data."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


TOKEN_URL = "https://api.avito.ru/token/"
REQUIRED_ENV = ("AVITO_CLIENT_ID", "AVITO_CLIENT_SECRET", "AVITO_USER_ID")


def fail(message: str, exit_code: int = 1) -> None:
    print(f"::error::{message}")
    raise SystemExit(exit_code)


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        fail("Missing GitHub repository secrets: " + ", ".join(missing))

    client_id = os.environ["AVITO_CLIENT_ID"].strip()
    client_secret = os.environ["AVITO_CLIENT_SECRET"].strip()
    raw_user_id = os.environ["AVITO_USER_ID"].strip()
    # Avito shows profile numbers grouped with spaces (for example, 165 818 622).
    # Accept that copied display format while keeping strict numeric validation.
    user_id = "".join(raw_user_id.split())

    if not user_id.isdigit():
        fail("AVITO_USER_ID must contain digits only")

    print("AVITO_SECRETS_PRESENT=true")
    print("AVITO_USER_ID_FORMAT_OK=true")

    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "coffee-tech-center-avito-readonly-check/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401):
            fail("Avito authentication was rejected. Check that the rotated API keys are current.")
        if exc.code == 403:
            fail("Avito authentication is forbidden. Check the API access granted to the application.")
        fail(f"Avito token endpoint returned HTTP {exc.code}")
    except urllib.error.URLError as exc:
        fail(f"Could not reach the Avito token endpoint: {exc.reason}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("Avito token endpoint returned an unreadable response")

    if status != 200 or not isinstance(payload, dict) or not payload.get("access_token"):
        fail("Avito response did not contain an access token")

    print("AVITO_AUTH_OK=true")
    if isinstance(payload.get("expires_in"), int):
        print(f"AVITO_TOKEN_EXPIRES_IN={payload['expires_in']}")
    print("READ_ONLY_CHECK_COMPLETE=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
