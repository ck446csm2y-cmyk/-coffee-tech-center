#!/usr/bin/env python3
"""Asset/source and spend-safety gate for Coffee Tech Center Avito.

Audit mode validates that every production ad has an explicit real-asset state and
that the safe-launch policy covers the portfolio. Release mode is deliberately
stricter: every ad present in a release package must have a release-approved first
frame with a verified source, acceptable reuse status and no unresolved blocker.

This script never contacts Avito and never spends money.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "avito" / "production_manifest_v3.json"
ASSETS = ROOT / "avito" / "asset_manifest.json"
LAUNCH = ROOT / "avito" / "launch_control.json"

BLOCKING_ASSET_STATUSES = {
    "BLOCKED_FIRST_FRAME",
    "SOURCE_PARTIALLY_VERIFIED",
    "SOURCE_VERIFIED_VISUAL_NOT_SCORED",
    "REFERENCE_ONLY",
}

UNACCEPTABLE_REUSE_MARKERS = (
    "UNCLEAR",
    "REFERENCE_ONLY",
    "NOT_EXPLICITLY_VERIFIED",
)


def fail(errors: list[str]) -> int:
    for error in errors:
        print(f"ERROR: {error}")
    print(f"ASSET_GATE=FAIL errors={len(errors)}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()

    production = json.loads(PRODUCTION.read_text(encoding="utf-8"))
    assets = json.loads(ASSETS.read_text(encoding="utf-8"))
    launch = json.loads(LAUNCH.read_text(encoding="utf-8"))

    ads = production.get("ads") or []
    production_ids = {str(ad.get("id", "")).strip() for ad in ads}
    asset_rows = assets.get("assets") or []
    asset_by_id = {str(row.get("ad_id", "")).strip(): row for row in asset_rows}
    errors: list[str] = []

    if "" in production_ids:
        errors.append("production manifest contains ad without id")
    if set(asset_by_id) != production_ids:
        missing = sorted(production_ids - set(asset_by_id))
        extra = sorted(set(asset_by_id) - production_ids)
        if missing:
            errors.append(f"asset manifest missing production ads: {missing}")
        if extra:
            errors.append(f"asset manifest contains unknown ads: {extra}")

    rejected = " ".join(str(x).lower() for x in assets.get("explicitly_rejected_assets") or [])
    if "ai" not in rejected:
        errors.append("asset manifest must explicitly reject prior AI-generated equipment visuals")

    protection = launch.get("money_protection") or {}
    required_money_guards = {
        "autoload_purchase_does_not_authorize_paid_promotion": True,
        "paid_promotion_requires_explicit_owner_confirmation": True,
        "automatic_budget_increase": False,
        "automatic_category_expansion": False,
        "automatic_price_reduction": False,
        "publish_all_ads_at_once": False,
    }
    for key, expected in required_money_guards.items():
        if protection.get(key) is not expected:
            errors.append(f"launch money guard {key} must be {expected}")

    wave = launch.get("initial_release") or {}
    max_ads = wave.get("wave_1_max_ads")
    if not isinstance(max_ads, int) or max_ads < 1 or max_ads > 2:
        errors.append("initial wave must be capped at 1-2 ads")

    for aid in production_ids:
        row = asset_by_id.get(aid) or {}
        status = str(row.get("status", "")).strip()
        if not status:
            errors.append(f"{aid}: asset status missing")
        required_object = str(row.get("required_object", "")).strip()
        if not required_object:
            errors.append(f"{aid}: required visual object missing")

        sources = row.get("sources") or row.get("supporting_assets") or []
        for source in sources:
            if source.get("source_type") == "third_party_retailer" and "REFERENCE_ONLY" not in str(source.get("reuse_status", "")):
                errors.append(f"{aid}: third-party retailer image must remain reference-only unless rights are verified")
            if source.get("service_proof_for_kofe_teh_centr") is True and source.get("source_type") != "user_owned":
                errors.append(f"{aid}: external image cannot be marked as proof of Kofe Teh Centr service")

        if args.release:
            if status in BLOCKING_ASSET_STATUSES or status != "RELEASE_APPROVED":
                errors.append(f"{aid}: asset status {status!r} is not RELEASE_APPROVED")
            if row.get("blocker"):
                errors.append(f"{aid}: unresolved asset blocker remains")
            selected = row.get("selected_first_frame") or {}
            if not selected:
                errors.append(f"{aid}: selected_first_frame missing")
                continue
            if selected.get("real_image") is not True:
                errors.append(f"{aid}: selected first frame is not confirmed real")
            if not selected.get("source_page") and not selected.get("user_owned_file"):
                errors.append(f"{aid}: selected first frame lacks provenance")
            reuse = str(selected.get("reuse_status", "")).upper()
            if any(marker in reuse for marker in UNACCEPTABLE_REUSE_MARKERS):
                errors.append(f"{aid}: selected first-frame reuse status is unresolved: {reuse}")
            if selected.get("source_type") == "ai_generated":
                errors.append(f"{aid}: AI-generated equipment can never release")

            models = next((ad.get("models") or [] for ad in ads if ad.get("id") == aid), [])
            if models:
                confidence = selected.get("model_confidence_percent")
                if not isinstance(confidence, (int, float)) or confidence < 95:
                    errors.append(f"{aid}: selected model visual confidence must be >=95%")
                if selected.get("exact_model_match") is not True:
                    errors.append(f"{aid}: exact model match not confirmed for selected frame")

    if errors:
        return fail(errors)

    mode = "RELEASE" if args.release else "AUDIT"
    print(f"ASSET_GATE=PASS mode={mode} ads={len(production_ids)} wave1_max={max_ads}")
    if not args.release:
        blocked = sum(1 for row in asset_rows if row.get("status") != "RELEASE_APPROVED")
        print(f"ASSETS_NOT_RELEASE_APPROVED={blocked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
