from __future__ import annotations

import hashlib
import io
import math
import re
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageOps
import numpy as np

LAYOUTS = ["editorial", "split", "poster", "frame", "orbit", "stack"]
FEATURE_VERSION = "local-visual-v1"


def rgb(color):
    return tuple(int(color[i:i+2], 16) for i in (1, 3, 5))


def luminance(color):
    channel = [x / 255 for x in rgb(color)]
    linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055)**2.4 for x in channel]
    return sum(a*b for a, b in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    x, y = sorted([luminance(a), luminance(b)])
    return (y + .05) / (x + .05)


def best_ink(bg):
    return max(["#17191F", "#FFFFFF"], key=lambda c: contrast(c, bg))


def extract_image(data: bytes):
    """Decode, bound, strip metadata, then compute deterministic pixel features. No OCR."""
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("이미지는 10MB 이하이어야 합니다.")
    with Image.open(io.BytesIO(data)) as im:
        if im.format not in {"PNG", "JPEG", "WEBP"}:
            raise ValueError("PNG, JPEG, WEBP만 지원합니다.")
        if getattr(im, "n_frames", 1) != 1:
            raise ValueError("정지 이미지 한 장만 지원합니다.")
        if im.width * im.height > 20_000_000:
            raise ValueError("이미지는 2천만 화소 이하이어야 합니다.")
        im.load()
        im = ImageOps.exif_transpose(im).convert("RGBA")
        background = Image.new("RGBA", im.size, "white")
        background.alpha_composite(im)
        im = background.convert("RGB")
        width, height = im.size
        im.thumbnail((2048, 2048))
        out = io.BytesIO()
        im.save(out, "PNG")
        sanitized = out.getvalue()
        thumb = im.copy()
        thumb.thumbnail((128, 128))
        quant = thumb.quantize(colors=5)
        pal = quant.getpalette()
        colors = sorted(quant.getcolors(), reverse=True)
        palette = ["#" + "".join(f"{v:02X}" for v in pal[i*3:i*3+3]) for _, i in colors]
        arr = np.asarray(thumb).astype(float) / 255
        gray = np.mean(arr, axis=2)
        dx = float(np.abs(np.diff(gray, axis=1)).mean()) if gray.shape[1] > 1 else 0
        dy = float(np.abs(np.diff(gray, axis=0)).mean()) if gray.shape[0] > 1 else 0
        saturation = np.max(arr, axis=2) - np.min(arr, axis=2)
        features = {
            "method": FEATURE_VERSION, "width": width, "height": height,
            "stored_width": im.width, "stored_height": im.height,
            "aspect_ratio": round(width / height, 4), "palette": palette,
            "brightness": round(float(gray.mean()), 4),
            "saturation_proxy": round(float(saturation.mean()), 4),
            "edge_density_proxy": round((dx + dy) / 2, 4),
            "semantic_analysis": None,
        }
        return sanitized, hashlib.sha256(sanitized).hexdigest(), features


def redact_comment(text):
    # Basic minimization, not a guarantee of anonymization. Review source exports first.
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[email]", text)
    text = re.sub(r"(?<!\d)(?:\+82[- ]?)?0?1[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)", "[phone]", text)
    return re.sub(r"(?<!\w)@[\w.]+", "[handle]", text)


def event_rates(row):
    denominator = row.get("impressions") or row.get("views")
    basis = "impressions" if row.get("impressions") else "views" if row.get("views") else None
    present = {k: row[k] for k in ("likes", "shares", "comments_count", "saves") if row.get(k) is not None}
    rates = {k: round(v / denominator * 1000, 4) for k, v in present.items()} if denominator else {}
    return {"denominator": denominator, "basis": basis, "events_per_1000": rates,
            "event_sum_per_1000": sum(rates.values()) if rates else None,
            "note": "이벤트 빈도입니다. 사람의 선호 확률이 아니며 중복 참여를 포함합니다."}


def eligible_cohort(records, context, generation=False):
    platform = context.get("cohort_platform")
    if not platform:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=context.get("lookback_days", 90))
    category = context["brief"]["category"]
    # One latest observation per source. Older snapshots remain in DB, never double counted.
    latest = {}
    for row in records:
        if row.get("is_demo") or not row.get("allow_analysis"):
            continue
        if generation and not row.get("allow_generation"):
            continue
        if row["platform"] != platform or row["category"] != category:
            continue
        if row["traffic"] != context.get("traffic", "organic"):
            continue
        if row["window_hours"] != context.get("window_hours", 168):
            continue
        if datetime.fromisoformat(row["published_at"].replace("Z", "+00:00")) < cutoff:
            continue
        if not event_rates(row)["denominator"]:
            continue
        key = row["source_id"]
        if key not in latest or row["observed_at"] > latest[key]["observed_at"]:
            latest[key] = row
    # Do not mix views and impressions or incomplete metric sets.
    groups = {}
    for row in latest.values():
        rates = event_rates(row)
        key = (rates["basis"], tuple(sorted(rates["events_per_1000"])))
        if key[1]:
            groups.setdefault(key, []).append(row)
    return max(groups.values(), key=len) if groups else []


def cohort_scores(cohort):
    if not cohort:
        return []
    baseline = float(np.median([event_rates(r)["event_sum_per_1000"] for r in cohort]))
    out = []
    for row in cohort:
        rates = event_rates(row)
        n = rates["denominator"]
        # 1,000 pseudo-exposures is a declared heuristic, not a fitted prior.
        smoothed = (rates["event_sum_per_1000"] * n + baseline * 1000) / (n + 1000)
        out.append({**row, "rate": rates, "smoothed_event_rate": smoothed})
    return sorted(out, key=lambda r: r["smoothed_event_rate"], reverse=True)


def evidence_for(spec, records, context):
    cohort = cohort_scores(eligible_cohort(records, context))
    out = []
    for row in cohort:
        pal = row.get("palette", [])
        distance = min((math.dist(rgb(spec["accent"]), rgb(c)) / 441.673 for c in pal), default=1)
        similarity = .55 * (1-distance) + .45 * (row.get("layout") == spec["layout"])
        out.append({"observation_id": row["id"], "title": row["title"],
                    "source_url": row.get("source_url"), "platform": row["platform"],
                    "visual_similarity": round(similarity, 3), "rate": row["rate"],
                    "comments": row.get("comments", [])[:4],
                    "observed_at": row["observed_at"], "rights_basis": row["rights_basis"],
                    "warning": "비슷한 사례의 관측치이며 이 시안의 성과 예측이 아닙니다."})
    return sorted(out, key=lambda r: r["visual_similarity"], reverse=True)[:3]


def vector(spec):
    return np.array([float(spec["layout"] == layout) for layout in LAYOUTS] +
                    [x/255 for x in rgb(spec["background"])] +
                    [min(contrast(spec["foreground"], spec["background"]), 10)/10,
                     spec["font_scale"] - 1,
                     float(spec["motif"] == "circle"), float(spec["motif"] == "ribbon"),
                     float(spec["motif"] == "bars")])


def preference_weights(pairs):
    """L2-regularized pairwise logistic fit. Local designer choices, not audience simulation."""
    unique = {}
    for p in pairs:
        key = tuple(sorted([p["winner_id"], p["loser_id"]]))
        unique[key] = p
    pairs = list(unique.values())
    if len(pairs) < 6:
        return None, len(pairs)
    x = np.array([np.array(p["winner_vector"]) - np.array(p["loser_vector"]) for p in pairs])
    w = np.zeros(x.shape[1])
    for _ in range(240):
        probability = 1 / (1 + np.exp(-np.clip(x @ w, -20, 20)))
        w -= .3 * (x.T @ (probability - 1) / len(x) + .1 * w)
    return w, len(pairs)


def score_design(design, pairs):
    spec, brief = design["spec"], design["brief"]
    ratio = contrast(spec["foreground"], spec["background"])
    brand_colors = {c.lower() for c in brief["palette"]}
    brand = sum(spec[k].lower() in brand_colors for k in ("background", "accent")) / 2 * 100
    rules_score = .6 * min(ratio / 7, 1) * 100 + .4 * brand
    w, n = preference_weights(pairs)
    learned = float(100 / (1 + np.exp(-np.clip(vector(spec) @ w, -20, 20)))) if w is not None else None
    ranking = rules_score if learned is None else .75 * rules_score + .25 * learned
    warnings = []
    if ratio < 4.5:
        warnings.append("본문/배경 명도 대비가 내부 기준 4.5:1 미만입니다.")
    if learned is None:
        warnings.append(f"서로 다른 시안 쌍을 {max(0, 6-n)}개 더 선택하면 개인 선택 기록을 반영합니다.")
    return {"rank_score": round(ranking, 1), "contrast_ratio": round(ratio, 2),
            "brand_palette_score": round(brand), "designer_preference_index": round(learned, 1) if learned is not None else None,
            "unique_pairs": n, "method": "rules-v1" if w is None else "rules+local-pairwise-logit-v1",
            "warnings": warnings, "customer_preference_prediction": None,
            "disclaimer": "기술적 점검과 개인 선택 기록 기반 정렬. 미적 품질/소비자 선호 예측이 아닙니다."}
