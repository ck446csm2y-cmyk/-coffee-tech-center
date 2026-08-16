#!/usr/bin/env python3
"""Read-only Avito API probe: verify auth and inspect autoload configuration/category metadata safely."""

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
KEYWORDS = ("коф", "ремонт", "техник", "услуг", "оборуд")


def fail(message: str, exit_code: int = 1) -> None:
    print(f"::error::{message}")
    raise SystemExit(exit_code)


def request_json(url: str, token: str):
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "coffee-tech-center-avito-readonly-check/2.0",
        },
    )
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


def iter_nodes(obj, path=""):
    if isinstance(obj, dict):
        label = None
        for key in ("name", "title", "label", "display_name"):
            if isinstance(obj.get(key), str):
                label = obj[key]
                break
        slug = None
        for key in ("slug", "node_slug", "id", "value"):
            val = obj.get(key)
            if isinstance(val, (str, int)):
                slug = str(val)
                break
        if label:
            text = label.lower()
            if any(k in text for k in KEYWORDS):
                yield {"label": label, "slug": slug, "path": path}
        for key, value in obj.items():
            child_path = f"{path}/{key}" if path else key
            yield from iter_nodes(value, child_path)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            child_path = f"{path}[{i}]"
            yield from iter_nodes(value, child_path)


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        fail("Missing GitHub repository secrets: " + ", ".join(missing))

    client_id = os.environ["AVITO_CLIENT_ID"].strip()
    client_secret = os.environ["AVITO_CLIENT_SECRET"].strip()
    raw_user_id = os.environ["AVITO_USER_ID"].strip()
    user_id = "".join(raw_user_id.split())
    if not user_id.isdigit():
        fail("AVITO_USER_ID must contain digits only")

    print("AVITO_SECRETS_PRESENT=true")
    print("AVITO_USER_ID_FORMAT_OK=true")

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "coffee-tech-center-avito-readonly-check/2.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401):
            fail("Avito authentication was rejected. Check current API keys.")
        if exc.code == 403:
            fail("Avito authentication is forbidden. Check API access granted to the application.")
        fail(f"Avito token endpoint returned HTTP {exc.code}")
    except urllib.error.URLError as exc:
        fail(f"Could not reach Avito token endpoint: {exc.reason}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("Avito token endpoint returned an unreadable response")

    token = payload.get("access_token") if isinstance(payload, dict) else None
    if status != 200 or not token:
        fail("Avito response did not contain an access token")
    print("AVITO_AUTH_OK=true")

    profile_status, profile = request_json(f"{API_BASE}/autoload/v2/profile", token)
    print(f"AUTOLOAD_PROFILE_HTTP={profile_status}")
    if isinstance(profile, dict):
        safe_profile = {
            "autoload_enabled": profile.get("autoload_enabled"),
            "feeds_count": len(profile.get("feeds_data") or []) if isinstance(profile.get("feeds_data"), list) else None,
            "has_feeds_data": bool(profile.get("feeds_data")),
            "schedule_present": bool(profile.get("schedule")),
        }
        print("AUTOLOAD_PROFILE_SAFE=" + json.dumps(safe_profile, ensure_ascii=False, sort_keys=True))

    tree_status, tree = request_json(f"{API_BASE}/autoload/v1/user-docs/tree", token)
    print(f"AUTOLOAD_TREE_HTTP={tree_status}")
    if tree_status == 200:
        candidates = []
        seen = set()
        for node in iter_nodes(tree):
            key = (node.get("label"), node.get("slug"))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(node)
            if len(candidates) >= 40:
                break
        print("AUTOLOAD_CATEGORY_CANDIDATES=" + json.dumps(candidates, ensure_ascii=False))
    else:
        print("AUTOLOAD_TREE_ERROR=" + json.dumps(tree, ensure_ascii=False)[:1200])

    print("READ_ONLY_CHECK_COMPLETE=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
