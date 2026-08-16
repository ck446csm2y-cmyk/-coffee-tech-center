#!/usr/bin/env python3
"""Static red-team quality gate for Avito Production v2.

Audit mode validates business rules, copy structure, price transparency, tiering and
visual briefs. Release mode additionally requires final image verification and
ready_to_publish=true. No Avito API call is made here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "avito" / "production_manifest_v2.json"

FORBIDDEN_CLAIMS = (
    "24/7",
    "без выходных",
    "запчасти в наличии",
    "все запчасти",
    "официальный партн",
    "официальный сервис",
    "ремонт в день обращения",
    "ремонт за 1 день",
    "№1",
    "лучший сервис",
)

EXPECTED_PRICES = {
    "ktc-home-repair-orenburg-v2": "home_repair_from",
    "ktc-professional-repair-orenburg-v2": "professional_repair_from",
    "ktc-jetinno-jl22-jl24-v2": "professional_repair_from",
    "ktc-vendista-25-v2": "acquiring_telemetry_from",
    "ktc-kitpos-master-lite-v2": "acquiring_telemetry_from",
    "ktc-mdb-acquiring-telemetry-v2": "acquiring_telemetry_from",
    "ktc-vending-repair-orenburg-v2": "vending_repair_from",
    "ktc-vending-maintenance-v2": "vending_maintenance_from",
    "ktc-european-vending-repair-v2": "vending_repair_from",
    "ktc-snack-vending-repair-v2": "vending_repair_from",
}

VALID_TIERS = {"core", "secondary", "test_only"}
VALID_FIELD_SCOPES = {"none", "vending_only"}


def fail(errors: list[str]) -> int:
    for error in errors:
        print(f"ERROR: {error}")
    print(f"QUALITY_GATE=FAIL errors={len(errors)}")
    return 1


def positive_visit_language(text: str) -> bool:
    lower = text.lower()
    if "выезд" not in lower:
        return False
    negatives = (
        "выезд на домашние кофемашины не выполняем",
        "выезд для этого направления в объявлении не заявляем",
        "без выезда",
    )
    return not any(neg in lower for neg in negatives)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    prices = data["prices"]
    strategy = data["launch_strategy"]
    ads = data.get("ads", [])

    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_primary_titles: set[str] = set()
    tier_by_id: dict[str, str] = {}

    for ad in ads:
        aid = str(ad.get("id", "")).strip()
        title = str(ad.get("title_primary", "")).strip()
        alt_title = str(ad.get("title_test_sequential", "")).strip()
        desc = str(ad.get("description", "")).strip()
        intent = str(ad.get("intent", "")).strip()
        tier = str(ad.get("tier", "")).strip()
        field_scope = str(ad.get("field_service_scope", "")).strip()
        price = ad.get("price_card_rub")
        price_explanation = str(ad.get("price_explanation", "")).strip()
        proofs = ad.get("proofs") or []
        visual = ad.get("visual_brief") or {}

        if not aid:
            errors.append("ad missing id")
            continue
        if aid in seen_ids:
            errors.append(f"{aid}: duplicate id")
        seen_ids.add(aid)
        tier_by_id[aid] = tier

        if not title:
            errors.append(f"{aid}: missing title_primary")
        elif title.lower() in seen_primary_titles:
            errors.append(f"{aid}: duplicate primary title")
        else:
            seen_primary_titles.add(title.lower())

        if not alt_title:
            errors.append(f"{aid}: missing sequential title test")
        if not intent:
            errors.append(f"{aid}: missing intent")
        if len(desc) < 350:
            errors.append(f"{aid}: description too short for production standard")
        if tier not in VALID_TIERS:
            errors.append(f"{aid}: invalid tier={tier!r}")
        if field_scope not in VALID_FIELD_SCOPES:
            errors.append(f"{aid}: invalid field_service_scope={field_scope!r}")

        combined = f"{title} {alt_title} {desc} {price_explanation}".lower()
        for claim in FORBIDDEN_CLAIMS:
            if claim in combined:
                errors.append(f"{aid}: forbidden/unverified claim '{claim}'")

        if field_scope == "none" and positive_visit_language(f"{title} {desc}"):
            errors.append(f"{aid}: positive visit language conflicts with field_service_scope=none")
        if field_scope == "vending_only" and "выезд" not in desc.lower():
            errors.append(f"{aid}: vending-only scope should state visit conditions explicitly")

        price_key = EXPECTED_PRICES.get(aid)
        if not price_key:
            errors.append(f"{aid}: no source-of-truth price mapping")
        elif price != prices[price_key]:
            errors.append(f"{aid}: card price {price} != source-of-truth {prices[price_key]}")

        if len(price_explanation) < 80:
            errors.append(f"{aid}: price explanation is too weak")
        if "точн" not in price_explanation.lower() and "дополнитель" not in price_explanation.lower():
            errors.append(f"{aid}: price explanation does not clarify variability/additional work")
        if aid not in {"ktc-vending-maintenance-v2", "ktc-vendista-25-v2", "ktc-kitpos-master-lite-v2", "ktc-mdb-acquiring-telemetry-v2"}:
            if "запчаст" not in price_explanation.lower() and "детал" not in price_explanation.lower():
                errors.append(f"{aid}: repair price explanation must clarify parts/details")

        if len(proofs) < 3:
            errors.append(f"{aid}: fewer than 3 proof points")
        if not visual.get("first_frame"):
            errors.append(f"{aid}: missing first-frame visual brief")
        if len(visual.get("overlay") or []) < 1:
            errors.append(f"{aid}: missing visual overlay")
        if len(visual.get("gallery") or []) < 3:
            errors.append(f"{aid}: gallery brief is incomplete")

        published_models = [title, alt_title, desc] + [str(x) for x in (ad.get("models") or [])]
        if any("JL25" in value for value in published_models):
            errors.append(f"{aid}: JL25 remains blocked pending explicit production verification")

        if ad.get("copy_verified") is not True:
            errors.append(f"{aid}: copy_verified must be true after red-team copy pass")

        if args.release:
            if ad.get("image_verified") is not True:
                errors.append(f"{aid}: image_verified is not true")
            if ad.get("ready_to_publish") is not True:
                errors.append(f"{aid}: ready_to_publish is not true")
            if str(ad.get("status", "")).startswith(("BLOCKED_", "DRAFT_")):
                errors.append(f"{aid}: blocked/draft status cannot release")

    all_strategy_ids: list[str] = []
    for bucket in ("core", "secondary", "test_only"):
        ids = strategy.get(bucket) or []
        all_strategy_ids.extend(ids)
        for aid in ids:
            if aid not in seen_ids:
                errors.append(f"launch_strategy.{bucket}: unknown ad id {aid}")
            elif tier_by_id.get(aid) != bucket:
                errors.append(f"{aid}: tier={tier_by_id.get(aid)} but listed under launch_strategy.{bucket}")

    if len(all_strategy_ids) != len(set(all_strategy_ids)):
        errors.append("launch_strategy: ad appears in more than one tier")
    if set(all_strategy_ids) != seen_ids:
        missing = sorted(seen_ids - set(all_strategy_ids))
        extra = sorted(set(all_strategy_ids) - seen_ids)
        if missing:
            errors.append(f"launch_strategy missing ads: {missing}")
        if extra:
            errors.append(f"launch_strategy unknown ads: {extra}")

    if errors:
        return fail(errors)

    mode = "RELEASE" if args.release else "AUDIT"
    print(f"QUALITY_GATE=PASS mode={mode} ads={len(ads)}")
    print(f"CORE={len(strategy.get('core') or [])} SECONDARY={len(strategy.get('secondary') or [])} TEST_ONLY={len(strategy.get('test_only') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
