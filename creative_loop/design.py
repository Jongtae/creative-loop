from __future__ import annotations

import base64
import html
import random
import unicodedata
from .models import Brief, DesignSpec
from .features import LAYOUTS, best_ink, contrast, eligible_cohort, cohort_scores

SIZES = {"square": (1080, 1080), "portrait": (1080, 1350), "landscape": (1200, 628)}


def generate_specs(request, records):
    rng = random.Random(request.seed)
    palette = request.brief.palette
    layouts = LAYOUTS[:]
    evidence_ids = []
    if request.use_evidence:
        cohort = cohort_scores(eligible_cohort(records, request.model_dump(mode="json"), generation=True))
        if len(cohort) >= 3:
            favored = [r["layout"] for r in cohort[:3] if r.get("layout")]
            layouts = list(dict.fromkeys(favored + layouts))
            evidence_ids = [r["id"] for r in cohort[:3] if r.get("layout")]
    candidates = []
    for layout in layouts:
        for idx, bg in enumerate(palette):
            accent = palette[(idx+1) % len(palette)]
            fg = max(palette + ["#17191F", "#FFFFFF"], key=lambda c: contrast(c, bg))
            for motif in ["circle", "ribbon", "bars"]:
                for scale in [.9, 1., 1.1]:
                    candidates.append(DesignSpec(layout=layout, background=bg, foreground=fg,
                                                 accent=accent, motif=motif, font_scale=scale))
    # Cover every layout first, then mix palette/motif combinations without duplicates.
    first = [next(c for c in candidates if c.layout == layout and c.background == palette[i % len(palette)]) for i, layout in enumerate(layouts)]
    rest = [c for c in candidates if c not in first]
    rng.shuffle(rest)
    ordered = first + rest
    while len(ordered) < request.count:
        # Minimum two palette colors provide >=36 combinations. Extra scale creates unique variants.
        c = ordered[len(ordered) % len(first)].model_copy(update={"font_scale": 1.2})
        if c not in ordered:
            ordered.append(c)
        else:
            break
    return ordered[:request.count], evidence_ids


def units(text):
    return sum(1.0 if unicodedata.east_asian_width(c) in "WF" else .58 for c in text)


def wrap(text, max_units):
    lines, current = [], ""
    for char in text:
        if char == "\n" or (current and units(current + char) > max_units):
            lines.append(current.strip())
            current = "" if char == "\n" else char
        else:
            current += char
    if current:
        lines.append(current.strip())
    return lines or [""]


def fitted_lines(text, width, height, ideal_size, max_lines):
    size = ideal_size
    while size >= 10:
        lines = wrap(text, width / size)
        if len(lines) <= max_lines and len(lines)*size*1.24 <= height:
            return lines, size
        size -= 1
    return wrap(text, width/10), 10


def text_block(text, x, y, width, height, ideal_size, color, max_lines=4, bold=True, align="start"):
    lines, size = fitted_lines(text, width, height, ideal_size, max_lines)
    tx = x + width/2 if align == "middle" else x
    return "".join(f'<text x="{tx:.1f}" y="{y+size+i*size*1.24:.1f}" fill="{color}" '
                   f'font-size="{size:.1f}" font-weight="{750 if bold else 400}" text-anchor="{align}">{html.escape(line)}</text>'
                   for i, line in enumerate(lines))


def render_svg(brief: Brief, spec: DesignSpec, asset_bytes: bytes | None = None) -> str:
    w, h = SIZES[brief.format]
    short = min(w, h)
    margin = short*.075
    bg, fg, ac = spec.background, spec.foreground, spec.accent
    layout = spec.layout
    # Text and imagery occupy distinct regions, including in landscape format.
    if layout == "split":
        box = (margin, h*.24, w*.47, h*.40)
        art = (w*.62, h*.14, w*.31, h*.67)
    elif layout == "poster":
        box = (margin, h*.21, w-margin*2, h*.38)
        art = (w*.62, h*.65, w*.28, h*.23)
    elif layout == "frame":
        box = (margin*1.8, h*.25, w-margin*3.6, h*.34)
        art = (w*.7, h*.68, w*.17, h*.15)
    elif layout == "orbit":
        box = (margin, h*.28, w*.58, h*.35)
        art = (w*.70, h*.16, w*.23, h*.57)
    elif layout == "stack":
        box = (margin, h*.19, w-margin*2, h*.32)
        art = (margin, h*.69, w-margin*2, h*.17)
    else:
        box = (margin, h*.24, w*.63, h*.39)
        art = (w*.73, h*.35, w*.2, h*.39)
    x, y, tw, th = box
    ax, ay, aw, ah = art
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
           f'<title>{html.escape(brief.brand + " — " + brief.headline)}</title>',
           '<g font-family="Arial, Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, sans-serif">',
           f'<rect width="{w}" height="{h}" fill="{bg}"/>']
    if layout == "frame":
        out.append(f'<rect x="{margin}" y="{margin}" width="{w-2*margin}" height="{h-2*margin}" fill="none" stroke="{ac}" stroke-width="{short*.016}"/>')
    if layout == "poster":
        out.append(f'<rect x="{margin}" y="{h*.13}" width="{w-2*margin}" height="{short*.012}" fill="{fg}"/>')
    if asset_bytes:
        encoded = base64.b64encode(asset_bytes).decode()
        out.extend([f'<defs><clipPath id="hero-clip"><rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" rx="{short*.025}"/></clipPath></defs>',
                    f'<image x="{ax}" y="{ay}" width="{aw}" height="{ah}" preserveAspectRatio="xMidYMid slice" clip-path="url(#hero-clip)" href="data:image/png;base64,{encoded}"/>'])
    elif spec.motif == "circle":
        radius = min(aw, ah)*.47
        out.append(f'<circle cx="{ax+aw*.5}" cy="{ay+ah*.5}" r="{radius}" fill="{ac}"/>')
        out.append(f'<circle cx="{ax+aw*.5}" cy="{ay+ah*.5}" r="{radius*.48}" fill="{bg}"/>')
    elif spec.motif == "bars":
        for n in range(5):
            bw = aw/7
            bh = ah*(.4+n*.12)
            out.append(f'<rect x="{ax+n*aw/5}" y="{ay+ah-bh}" width="{bw}" height="{bh}" rx="{bw*.4}" fill="{ac}"/>')
    else:
        for n in range(3):
            out.append(f'<rect x="{ax}" y="{ay+ah*n/3}" width="{aw}" height="{ah*.22}" rx="{ah*.11}" fill="{ac}"/>')
    out.append(text_block(brief.brand, margin if layout != "frame" else margin*1.8,
                          h*.075, w*.7, h*.06, short*.027, fg, max_lines=1))
    out.append(text_block(brief.headline, x, y, tw, th, short*.084*spec.font_scale, fg, max_lines=4))
    sub_y = y+th+.015*h
    out.append(text_block(brief.subline, x, sub_y, tw, h*.10, short*.023, fg, max_lines=3, bold=False))
    if brief.cta:
        button_width = min(w*.56, max(short*.24, units(brief.cta)*short*.021+margin*.85))
        button_height = max(38, short*.059)
        bx, by = (margin*1.8 if layout == "frame" else margin), h*.90-button_height*.6
        if layout == "stack":
            by = h*.90
        out.append(f'<rect x="{bx}" y="{by}" width="{button_width}" height="{button_height}" rx="{button_height/2}" fill="{ac}"/>')
        out.append(f'<text x="{bx+button_width/2}" y="{by+button_height*.66}" fill="{best_ink(ac)}" font-size="{short*.02}" font-weight="650" text-anchor="middle">{html.escape(brief.cta)}</text>')
    out.extend(["</g>", "</svg>"])
    return "".join(out)
