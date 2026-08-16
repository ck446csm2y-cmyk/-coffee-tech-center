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
TARGET_SLUGS = ("remont_i_obsluzhivanie_tekhniki", "predlozhenija_uslug")


def fail(message: str, exit_code: int = 1) -> None:
    print(f"::error::{message}")
    raise SystemExit(exit_code)


def request_json(url: str, token: str):
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "coffee-tech-center-avito-readonly-check/2.1",
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


def iter_nodes(obj, path=""):
    if isinstance(obj, dict):
        label = next((obj[k] for k in ("name", "title", "label", "display_name") if isinstance(obj.get(k), str)), None)
        slug = next((str(obj[k]) for k in ("slug", "node_slug", "id", "value") if isinstance(obj.get(k), (str, int))), None)
        if label and any(k in label.lower() for k in KEYWORDS):
            yield {"label": label, "slug": slug, "path": path}
        for key, value in obj.items():
            yield from iter_nodes(value, f"{path}/{key}" if path else key)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from iter_nodes(value, f"{path}[{i}]")


def compact_fields(obj):
    if not isinstance(obj, (dict, list)):
        return obj
    text = json.dumps(obj, ensure_ascii=False)
    return text[:12000]


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
        "User-Agent": "coffee-tech-center-avito-readonly-check/2.1",
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

    profile_status, profile = request_json(f"{API_BASE}/autoload/v2/profile", token)
    print(f"AUTOLOAD_PROFILE_HTTP={profile_status}")
    if isinstance(profile, dict):
        print("AUTOLOAD_PROFILE_SAFE=" + json.dumps({
            "autoload_enabled": profile.get("autoload_enabled"),
            "has_feeds_data": bool(profile.get("feeds_data")),
            "schedule_present": bool(profile.get("schedule")),
        }, ensure_ascii=False, sort_keys=True))

    tree_status, tree = request_json(f"{API_BASE}/autoload/v1/user-docs/tree", token)
    print(f"AUTOLOAD_TREE_HTTP={tree_status}")
    if tree_status == 200:
        candidates, seen = [], set()
        for node in iter_nodes(tree):
            key = (node.get("label"), node.get("slug"))
            if key not in seen:
                seen.add(key); candidates.append(node)
            if len(candidates) >= 80:
                break
        print("AUTOLOAD_CATEGORY_CANDIDATES=" + json.dumps(candidates, ensure_ascii=False))

    for slug in TARGET_SLUGS:
        status, fields = request_json(f"{API_BASE}/autoload/v1/user-docs/node/{slug}/fields", token)
        print(f"FIELDS_{slug}_HTTP={status}")
        print(f"FIELDS_{slug}=" + compact_fields(fields))

    print("READ_ONLY_CHECK_COMPLETE=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
