#!/usr/bin/env python3
"""Static red-team + visual quality gate for Avito Production v3.

Audit mode validates copy/business rules and integrity of the DOMINATOR visual QA
protocol. Release mode additionally requires verified final images, a completed
visual scorecard, five critical PASS checks, the 10-question Visual Red Team and
minimum 88/100 first-frame score. No Avito API call is made here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "avito" / "production_manifest_v3.json"
VISUAL_PROTOCOL = ROOT / "avito" / "visual_qa_protocol.json"

FORBIDDEN_CLAIMS = (
    "24/7", "без выходных", "запчасти в наличии", "все запчасти",
    "официальный партн", "официальный сервис", "ремонт в день обращения",
    "ремонт за 1 день", "№1", "лучший сервис",
)
WEAK_PHRASES = (
    "не работает домашняя кофемашина?", "не работает кофемашина?",
    "около 4 лет", "работает заметно не так, как раньше",
    "работает не так, как раньше", "чтобы не тратить время на лишние звонки",
    "чтобы не тратить время на звонки",
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
REPAIR_IDS = {
    "ktc-home-repair-orenburg-v2", "ktc-professional-repair-orenburg-v2",
    "ktc-jetinno-jl22-jl24-v2", "ktc-vending-repair-orenburg-v2",
    "ktc-european-vending-repair-v2", "ktc-snack-vending-repair-v2",
}


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
        "выезд для этого направления не заявляем",
        "без выезда",
    )
    return not any(neg in lower for neg in negatives)


def explains_price_variability(text: str) -> bool:
    lower = text.lower()
    markers = (
        "точн", "дополнитель", "рассчитыва", "согласовыва", "после диагност",
        "оплачиваются отдельно", "оплачивается отдельно", "запчасти отдельно",
        "детали отдельно", "расходные материалы", "заменяемые компоненты",
    )
    return any(marker in lower for marker in markers)


def validate_visual_protocol(protocol: dict, ad_ids: set[str], errors: list[str]) -> None:
    if protocol.get("thresholds", {}).get("publication_minimum") != 88:
        errors.append("visual protocol: publication minimum must be 88")
    scorecard = protocol.get("scorecard") or {}
    if sum(scorecard.values()) != 100:
        errors.append("visual protocol: scorecard weights must total 100")
    if set(protocol.get("five_checks") or []) != {"PRODUCT", "RECOGNITION", "CTR", "TRUST", "SALES"}:
        errors.append("visual protocol: five critical checks are incomplete")
    questions = protocol.get("visual_red_team_questions") or []
    if len(questions) != 10 or len(set(questions)) != 10:
        errors.append("visual protocol: Visual Red Team must contain exactly 10 unique questions")
    anchors = protocol.get("portfolio_visual_anchors") or {}
    if set(anchors) != ad_ids:
        errors.append("visual protocol: every production ad must have exactly one visual anchor")
    priority = protocol.get("visual_priority") or []
    if set(priority) != ad_ids or len(priority) != len(ad_ids):
        errors.append("visual protocol: visual_priority must contain every ad exactly once")


def validate_release_visual(ad: dict, protocol: dict, errors: list[str]) -> None:
    aid = ad["id"]
    qa = ad.get("visual_qa") or {}
    score_limits = protocol["scorecard"]
    min_score = protocol["thresholds"]["publication_minimum"]

    if ad.get("image_verified") is not True:
        errors.append(f"{aid}: image_verified is not true")
    if not qa:
        errors.append(f"{aid}: missing visual_qa release evidence")
        return

    checks = qa.get("five_checks") or {}
    for name in protocol["five_checks"]:
        if checks.get(name) != "PASS":
            errors.append(f"{aid}: visual critical check {name} != PASS")

    scores = qa.get("scores") or {}
    total = 0
    for key, maximum in score_limits.items():
        value = scores.get(key)
        if not isinstance(value, int) or not 0 <= value <= maximum:
            errors.append(f"{aid}: visual score {key} must be integer 0..{maximum}")
            continue
        total += value
    if scores.get("total") != total:
        errors.append(f"{aid}: visual score total must equal component sum ({total})")
    if total < min_score:
        errors.append(f"{aid}: first-frame visual score {total} < publication minimum {min_score}")

    red_team = qa.get("red_team") or {}
    for question in protocol["visual_red_team_questions"]:
        if red_team.get(question) is not True:
            errors.append(f"{aid}: Visual Red Team failed/unanswered: {question}")

    if qa.get("mobile_test_pass") is not True:
        errors.append(f"{aid}: mobile 1-2 second recognition test not passed")
    if qa.get("real_image") is not True:
        errors.append(f"{aid}: first frame is not confirmed real")
    if qa.get("equipment_recognizable") is not True:
        errors.append(f"{aid}: equipment is not confirmed recognizable")
    if qa.get("visual_anchor_distinct") is not True:
        errors.append(f"{aid}: portfolio visual distinction not confirmed")
    if qa.get("gallery_story_pass") is not True:
        errors.append(f"{aid}: gallery story/evidence QA not passed")
    if qa.get("final_next_step_pass") is not True:
        errors.append(f"{aid}: final gallery frame lacks verified next step")

    frame_share = qa.get("equipment_frame_share_percent")
    if not isinstance(frame_share, (int, float)) or frame_share < 40:
        errors.append(f"{aid}: equipment meaningful frame share must be >=40%")
    text_share = qa.get("text_composition_share_percent")
    if not isinstance(text_share, (int, float)) or text_share > 25:
        errors.append(f"{aid}: first-frame text composition share must be <=25%")

    models = ad.get("models") or []
    if models:
        confidence = qa.get("model_confidence_percent")
        if not isinstance(confidence, (int, float)) or confidence < 95:
            errors.append(f"{aid}: model-specific visual confidence must be >=95%")
        if qa.get("exact_model_match") is not True:
            errors.append(f"{aid}: exact model match not confirmed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    protocol = json.loads(VISUAL_PROTOCOL.read_text(encoding="utf-8"))
    prices = data["prices"]
    strategy = data["launch_strategy"]
    ads = data.get("ads", [])

    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_primary_titles: set[str] = set()
    tier_by_id: dict[str, str] = {}

    if data.get("source_of_truth", {}).get("profile_experience") != "4 года работы с кофейным оборудованием":
        errors.append("source_of_truth: experience wording must be exact confirmed 4 years")

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
        for phrase in WEAK_PHRASES:
            if phrase in combined:
                errors.append(f"{aid}: weak/red-team-blocked phrase '{phrase}'")
        if "4 года" not in desc and tier != "test_only":
            errors.append(f"{aid}: core/secondary copy must surface confirmed 4-year experience")

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
        if not explains_price_variability(f"{price_explanation} {desc}"):
            errors.append(f"{aid}: listing copy does not clarify price variability/additional work")
        if aid in REPAIR_IDS:
            p = price_explanation.lower()
            if not ("работ" in p and ("запчаст" in p or "детал" in p)):
                errors.append(f"{aid}: repair pricing must explicitly separate work from parts/details")

        if aid == "ktc-home-repair-orenburg-v2":
            lower_desc = desc.lower()
            if "приём оборудования: оренбург, ул. 9 января, д. 58" not in lower_desc:
                errors.append(f"{aid}: physical service address must be surfaced near the top")
            if "до приёмки уточним стоимость диагностики для вашей модели" not in lower_desc:
                errors.append(f"{aid}: diagnostic 'from 700' must be de-risked before intake")
            if "подскажем, нужно ли привозить кофемашину" not in lower_desc:
                errors.append(f"{aid}: CTA must reward user with a concrete next-step answer")

        if len(proofs) < 3:
            errors.append(f"{aid}: fewer than 3 proof points")
        if not visual.get("first_frame"):
            errors.append(f"{aid}: missing first-frame visual brief")
        if len(visual.get("overlay_primary") or []) < 1:
            errors.append(f"{aid}: missing primary visual overlay")
        if len(visual.get("overlay_test_sequential") or []) < 1:
            errors.append(f"{aid}: missing sequential visual-overlay test")
        if len(visual.get("gallery") or []) < 3:
            errors.append(f"{aid}: gallery brief is incomplete")
        if "узнаваем" not in str(visual.get("first_frame", "")).lower() and aid in REPAIR_IDS:
            errors.append(f"{aid}: first frame should keep equipment recognizable")

        published_models = [title, alt_title, desc] + [str(x) for x in (ad.get("models") or [])]
        if any("JL25" in value for value in published_models):
            errors.append(f"{aid}: JL25 remains blocked pending explicit production verification")
        if ad.get("copy_verified") is not True:
            errors.append(f"{aid}: copy_verified must be true after red-team copy pass")

        if args.release:
            if ad.get("ready_to_publish") is not True:
                errors.append(f"{aid}: ready_to_publish is not true")
            if str(ad.get("status", "")).startswith(("BLOCKED_", "DRAFT_")):
                errors.append(f"{aid}: blocked/draft status cannot release")
            validate_release_visual(ad, protocol, errors)

    validate_visual_protocol(protocol, seen_ids, errors)

    all_strategy_ids: list[str] = []
    for bucket in ("core", "secondary", "test_only"):
        ids = strategy.get(bucket) or []
        all_strategy_ids.extend(ids)
        for aid in ids:
            if aid not in seen_ids:
                errors.append(f"launch_strategy.{bucket}: unknown ad id {aid}")
            elif tier_by_id.get(aid) != bucket:
                errors.append(f"{aid}: tier mismatch with launch_strategy.{bucket}")
    if len(all_strategy_ids) != len(set(all_strategy_ids)):
        errors.append("launch_strategy: ad appears in more than one tier")
    if set(all_strategy_ids) != seen_ids:
        errors.append("launch_strategy: every production ad must appear exactly once")

    if errors:
        return fail(errors)

    mode = "RELEASE" if args.release else "AUDIT"
    print(f"QUALITY_GATE=PASS mode={mode} ads={len(ads)} visual_protocol=DOMINATOR")
    print(f"CORE={len(strategy.get('core') or [])} SECONDARY={len(strategy.get('secondary') or [])} TEST_ONLY={len(strategy.get('test_only') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
