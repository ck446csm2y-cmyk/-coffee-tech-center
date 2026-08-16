#!/usr/bin/env python3
"""Static quality gate for Avito production manifest.

Audit mode checks structural/business invariants and may pass while assets are still blocked.
Release mode additionally requires every ad selected for release to have verified copy/images and ready_to_publish=true.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "avito" / "production_manifest.json"

FORBIDDEN_CLAIMS = (
    "24/7",
    "без выходных",
    "запчасти в наличии",
    "гарантия от 3",
    "официальный партн",
    "официальный сервис",
)

EXPECTED_PRICE_KEYS = {
    "HOME_REPAIR": "home_repair_from",
    "B2B_SERVICE": "professional_repair_from",
}


def fail(errors: list[str]) -> int:
    for e in errors:
        print(f"ERROR: {e}")
    print(f"QUALITY_GATE=FAIL errors={len(errors)}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true", help="require release-ready assets and status")
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    prices = data["price_rules"]
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_intents: dict[str, str] = {}

    for ad in data.get("ads", []):
        aid = ad.get("id", "<missing-id>")
        if aid in seen_ids:
            errors.append(f"{aid}: duplicate id")
        seen_ids.add(aid)

        title = str(ad.get("title", "")).strip()
        desc = str(ad.get("description", "")).strip()
        intent = str(ad.get("intent", "")).strip().lower()
        portfolio = ad.get("portfolio")
        price = ad.get("price_from")
        field_scope = ad.get("field_service_scope")

        if not title:
            errors.append(f"{aid}: missing title")
        if len(desc) < 180:
            errors.append(f"{aid}: description too short or missing")
        if not intent:
            errors.append(f"{aid}: missing search intent")
        elif intent in seen_intents and "wave_2" not in str(ad.get("activation_policy", "")):
            errors.append(f"{aid}: duplicate intent with {seen_intents[intent]}")
        else:
            seen_intents[intent] = aid

        lower = (title + " " + desc).lower()
        for claim in FORBIDDEN_CLAIMS:
            if claim in lower:
                errors.append(f"{aid}: forbidden/unverified claim '{claim}'")

        if field_scope not in ("none", "vending_only"):
            errors.append(f"{aid}: invalid field_service_scope={field_scope!r}")
        if field_scope == "none":
            desc_has_positive_visit = "выезд" in desc.lower() and "не выполняем" not in desc.lower() and "не заявляем" not in desc.lower()
            if "выезд" in title.lower() or desc_has_positive_visit:
                errors.append(f"{aid}: field-service language conflicts with field_service_scope=none")
        if field_scope == "vending_only" and portfolio not in ("VENDING_SERVICE", "INTEGRATION"):
            errors.append(f"{aid}: vending-only field service outside vending/integration portfolio")

        if portfolio in EXPECTED_PRICE_KEYS:
            expected = prices[EXPECTED_PRICE_KEYS[portfolio]]
            if price != expected:
                errors.append(f"{aid}: price {price} != source-of-truth {expected}")
        elif portfolio == "VENDING_SERVICE":
            expected = prices["vending_maintenance_from"] if aid == "ktc-vending-maintenance" else prices["vending_repair_from"]
            if price != expected:
                errors.append(f"{aid}: price {price} != source-of-truth {expected}")
        elif portfolio == "INTEGRATION" and price != prices["acquiring_telemetry_from"]:
            errors.append(f"{aid}: integration price {price} != source-of-truth {prices['acquiring_telemetry_from']}")

        published_model_fields = [title, desc] + [str(x) for x in (ad.get("models") or [])]
        if any("JL25" in value for value in published_model_fields):
            errors.append(f"{aid}: JL25 is blocked pending primary-source/model verification")

        image_policy = ad.get("image_policy", "")
        if not image_policy:
            errors.append(f"{aid}: missing image policy")
        if image_policy.startswith("exact_model") and not ad.get("models"):
            errors.append(f"{aid}: exact-model image policy without models list")

        if args.release:
            if ad.get("copy_verified") is not True:
                errors.append(f"{aid}: copy_verified is not true")
            if ad.get("image_verified") is not True:
                errors.append(f"{aid}: image_verified is not true")
            if ad.get("ready_to_publish") is not True:
                errors.append(f"{aid}: ready_to_publish is not true")
            if str(ad.get("status", "")).startswith(("BLOCKED_", "DRAFT_")):
                errors.append(f"{aid}: blocked/draft status cannot release")

    if errors:
        return fail(errors)

    mode = "RELEASE" if args.release else "AUDIT"
    print(f"QUALITY_GATE=PASS mode={mode} ads={len(data.get('ads', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
