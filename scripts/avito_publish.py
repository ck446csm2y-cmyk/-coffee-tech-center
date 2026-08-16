#!/usr/bin/env python3
"""Publish the controlled Coffee Tech Center feed through Avito Autoload.

Safety: upload is launched only after the profile is successfully pointed at our known GitHub feed.
Secrets are never printed.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://api.avito.ru/token/"
API_BASE = "https://api.avito.ru"
FEED_URL = "https://raw.githubusercontent.com/ck446csm2y-cmyk/-coffee-tech-center/main/avito/feed.xml"


def http_json(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "coffee-tech-center-avito-publisher/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = {"raw": raw[:1000]}
            return resp.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = {"raw": raw[:1000]}
        return exc.code, body


def safe_error(body):
    if not isinstance(body, dict):
        return str(body)[:1000]
    allowed = {}
    for key in ("error", "message", "code", "result", "status"):
        if key in body:
            allowed[key] = body[key]
    return json.dumps(allowed or body, ensure_ascii=False)[:1500]


def main():
    cid = os.environ.get("AVITO_CLIENT_ID", "").strip()
    sec = os.environ.get("AVITO_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        print("::error::Missing Avito GitHub secrets")
        return 2

    token_data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": sec,
    }).encode("utf-8")
    token_req = urllib.request.Request(
        TOKEN_URL,
        data=token_data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(token_req, timeout=20) as resp:
            token = json.loads(resp.read().decode("utf-8"))["access_token"]
    except Exception as exc:
        print(f"::error::Token request failed: {type(exc).__name__}")
        return 3
    print("AVITO_AUTH_OK=true")

    self_status, self_body = http_json("GET", API_BASE + "/core/v1/accounts/self", token)
    if self_status != 200 or not isinstance(self_body, dict) or not self_body.get("email"):
        print(f"::error::Could not read Avito account email; HTTP {self_status}")
        return 4
    report_email = self_body["email"]

    profile_v2 = {
        "autoload_enabled": True,
        "report_email": report_email,
        "schedule": [
            {"rate": 100, "weekdays": [0, 1, 2, 3, 4, 5, 6], "time_slots": [4]}
        ],
        "feeds_data": [
            {"feed_name": "coffee-tech-center", "feed_url": FEED_URL}
        ],
        "agreement": True,
    }

    status, body = http_json("POST", API_BASE + "/autoload/v2/profile", token, profile_v2)
    print(f"AUTOLOAD_PROFILE_V2_POST_HTTP={status}")
    if status != 200:
        print("AUTOLOAD_PROFILE_V2_ERROR=" + safe_error(body))
        # Controlled fallback to deprecated v1 profile. Same known feed only.
        profile_v1 = {
            "autoload_enabled": True,
            "report_email": report_email,
            "schedule": [
                {"rate": 100, "weekdays": [0, 1, 2, 3, 4, 5, 6], "time_slots": [4]}
            ],
            "upload_url": FEED_URL,
            "agreement": True,
        }
        status, body = http_json("POST", API_BASE + "/autoload/v1/profile", token, profile_v1)
        print(f"AUTOLOAD_PROFILE_V1_POST_HTTP={status}")
        if status != 200:
            print("AUTOLOAD_PROFILE_V1_ERROR=" + safe_error(body))
            print("::error::Avito refused Autoload profile creation/update; upload was NOT launched")
            return 10

    print("AUTOLOAD_PROFILE_CONTROLLED=true")
    # Launch only after the profile points to the controlled feed above.
    upload_status, upload_body = http_json("POST", API_BASE + "/autoload/v1/upload", token, {})
    print(f"AUTOLOAD_UPLOAD_HTTP={upload_status}")
    if upload_status not in (200, 201, 202, 204):
        print("AUTOLOAD_UPLOAD_ERROR=" + safe_error(upload_body))
        print("::error::Avito did not accept the upload launch")
        return 11

    print("AUTOLOAD_UPLOAD_LAUNCHED=true")
    print("FEED_ID=ktc-coffee-repair-orenburg-001")
    return 0


if __name__ == "__main__":
    sys.exit(main())
