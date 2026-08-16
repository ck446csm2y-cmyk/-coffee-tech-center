#!/usr/bin/env python3
"""Read-only Avito API probe: verify auth, inspect coffee service schema, and safely inspect existing ads."""

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
        "User-Agent": "coffee-tech-center-avito-readonly-check/2.3",
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
        variants = []
        for c in field.get("content") or []:
            if not isinstance(c, dict):
                continue
            vals = [v.get("value") for v in (c.get("values") or []) if isinstance(v, dict) and "value" in v]
            variants.append({
                "required": c.get("required"),
                "field_type": c.get("field_type"),
                "default": (c.get("default") or {}).get("value") if isinstance(c.get("default"), dict) else c.get("default"),
                "values": vals[:80],
            })
        out.append({"tag": field.get("tag"), "label": field.get("label"), "variants": variants})
    return out


def summarize_items(payload):
    if not isinstance(payload, dict):
        return payload
    resources = payload.get("resources") or []
    out = []
    for item in resources[:20]:
        if not isinstance(item, dict):
            continue
        image_urls = []
        for key in ("images", "image_urls"):
            val = item.get(key)
            if isinstance(val, list):
                for x in val[:3]:
                    if isinstance(x, str): image_urls.append(x)
                    elif isinstance(x, dict):
                        u = x.get("url") or x.get("1280x960") or x.get("640x480")
                        if u: image_urls.append(u)
        out.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "category": item.get("category"),
            "price": item.get("price"),
            "address": item.get("address") or item.get("location"),
            "url": item.get("url"),
            "images": image_urls,
        })
    return {"count": len(resources), "items": out}


def main() -> int:
    missing = [n for n in REQUIRED_ENV if not os.environ.get(n, "").strip()]
    if missing:
        fail("Missing GitHub repository secrets: " + ", ".join(missing))
    client_id = os.environ["AVITO_CLIENT_ID"].strip()
    client_secret = os.environ["AVITO_CLIENT_SECRET"].strip()
    user_id = "".join(os.environ["AVITO_USER_ID"].strip().split())
    if not user_id.isdigit():
        fail("AVITO_USER_ID must contain digits only")

    body = urllib.parse.urlencode({"grant_type":"client_credentials","client_id":client_id,"client_secret":client_secret}).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Accept":"application/json","Content-Type":"application/x-www-form-urlencoded","User-Agent":"coffee-tech-center-avito-readonly-check/2.3"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"Avito token endpoint returned HTTP {exc.code}")
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        fail("Avito response did not contain an access token")
    print("AVITO_AUTH_OK=true")

    profile_status, _ = request_json(f"{API_BASE}/autoload/v2/profile", token)
    print(f"AUTOLOAD_PROFILE_HTTP={profile_status}")

    status, fields = request_json(f"{API_BASE}/autoload/v1/user-docs/node/{TARGET_SLUG}/fields", token)
    print(f"COFFEE_SERVICE_FIELDS_HTTP={status}")
    print("COFFEE_SERVICE_FIELDS_SUMMARY=" + json.dumps(summarize_fields(fields), ensure_ascii=False, separators=(",", ":")))

    items_url = f"{API_BASE}/core/v1/accounts/{user_id}/items?status=active&page=1&per_page=100"
    items_status, items = request_json(items_url, token)
    print(f"ACTIVE_ITEMS_HTTP={items_status}")
    print("ACTIVE_ITEMS_SAFE=" + json.dumps(summarize_items(items), ensure_ascii=False, separators=(",", ":"))[:12000])

    print("READ_ONLY_CHECK_COMPLETE=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
