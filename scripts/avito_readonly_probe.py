#!/usr/bin/env python3
"""Read-only Avito API probe: verify auth and inspect the coffee-machine service feed schema safely."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://api.avito.ru/token/"
API_BASE = "https://api.avito.ru"
REQUIRED_ENV = ("AVITO_CLIENT_ID", "AVITO_CLIENT_SECRET", "AVITO_USER_ID")
TARGET_SLUG = "kofemashiny_2169978"


def fail(message: str, exit_code: int = 1) -> None:
    print(f"::error::{message}")
    raise SystemExit(exit_code)


def request_json(url: str, token: str):
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "coffee-tech-center-avito-readonly-check/2.2",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = {"raw": body[:500]}
        return exc.code, payload


def summarize_fields(payload):
    out = []
    if not isinstance(payload, dict):
        return out
    for field in payload.get("fields") or []:
        if not isinstance(field, dict):
            continue
        contents = field.get("content") or []
        variants = []
        for c in contents:
            if not isinstance(c, dict):
                continue
            vals = []
            for v in c.get("values") or []:
                if isinstance(v, dict) and "value" in v:
                    vals.append(v.get("value"))
            variants.append({
                "required": c.get("required"),
                "required_by_dependency": c.get("required_by_dependency"),
                "field_type": c.get("field_type"),
                "default": (c.get("default") or {}).get("value") if isinstance(c.get("default"), dict) else c.get("default"),
                "values": vals[:80],
            })
        out.append({
            "tag": field.get("tag"),
            "label": field.get("label"),
            "variants": variants,
        })
    return out


def main() -> int:
    missing = [n for n in REQUIRED_ENV if not os.environ.get(n, "").strip()]
    if missing:
        fail("Missing GitHub repository secrets: " + ", ".join(missing))

    client_id = os.environ["AVITO_CLIENT_ID"].strip()
    client_secret = os.environ["AVITO_CLIENT_SECRET"].strip()
    user_id = "".join(os.environ["AVITO_USER_ID"].strip().split())
    if not user_id.isdigit():
        fail("AVITO_USER_ID must contain digits only")

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "coffee-tech-center-avito-readonly-check/2.2",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"Avito token endpoint returned HTTP {exc.code}")
    except urllib.error.URLError as exc:
        fail(f"Could not reach Avito token endpoint: {exc.reason}")

    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        fail("Avito response did not contain an access token")
    print("AVITO_AUTH_OK=true")

    profile_status, _ = request_json(f"{API_BASE}/autoload/v2/profile", token)
    print(f"AUTOLOAD_PROFILE_HTTP={profile_status}")

    status, fields = request_json(f"{API_BASE}/autoload/v1/user-docs/node/{TARGET_SLUG}/fields", token)
    print(f"COFFEE_SERVICE_FIELDS_HTTP={status}")
    print("COFFEE_SERVICE_FIELDS_SUMMARY=" + json.dumps(summarize_fields(fields), ensure_ascii=False, separators=(",", ":")))

    print("READ_ONLY_CHECK_COMPLETE=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
