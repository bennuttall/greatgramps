#!/usr/bin/env python3
"""Generate a printable A4 PDF ancestor pedigree chart."""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from reportlab.lib import colors
from reportlab.lib import pagesizes
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas

from gramps.gen.db import DBMODE_R
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite

from greatgramps.gramps_data import get_event, get_parents, get_year
from greatgramps.settings import get_config

FEMALE, MALE = 0, 1

PAPER_SIZES = {
    'A0': pagesizes.A0, 'A1': pagesizes.A1, 'A2': pagesizes.A2,
    'A3': pagesizes.A3, 'A4': pagesizes.A4, 'A5': pagesizes.A5,
    'letter': pagesizes.LETTER, 'legal': pagesizes.LEGAL,
    'ledger': pagesizes.LEDGER,
}

PALETTE_BW = dict(
    male    = colors.white,
    female  = colors.HexColor('#dddddd'),
    unknown = colors.HexColor('#eeeeee'),
    border  = colors.HexColor('#666666'),
    line    = colors.HexColor('#666666'),
    name    = colors.black,
    dates   = colors.HexColor('#444444'),
    title   = colors.black,
)

PALETTE_COLOR = dict(
    male    = colors.HexColor('#ddeeff'),
    female  = colors.HexColor('#fde8dc'),
    unknown = colors.HexColor('#f2f2f2'),
    border  = colors.HexColor('#aaaaaa'),
    line    = colors.HexColor('#888888'),
    name    = colors.HexColor('#111111'),
    dates   = colors.HexColor('#555555'),
    title   = colors.HexColor('#333333'),
)

# Active palette — set in main() based on --color/--no-color
C_MALE = C_FEMALE = C_UNKNOWN = C_BORDER = C_LINE = C_NAME = C_DATES = C_TITLE = None


def _apply_palette(palette):
    global C_MALE, C_FEMALE, C_UNKNOWN, C_BORDER, C_LINE, C_NAME, C_DATES, C_TITLE
    C_MALE, C_FEMALE, C_UNKNOWN = palette['male'], palette['female'], palette['unknown']
    C_BORDER, C_LINE            = palette['border'], palette['line']
    C_NAME, C_DATES, C_TITLE   = palette['name'], palette['dates'], palette['title']


_apply_palette(PALETTE_BW)


def _get_ancestors(db, root, max_gen):
    """Return {ahnentafel: person} for all ancestors up to max_gen levels (root = 1)."""
    result = {}
    queue = [(root, 1)]
    while queue:
        person, ahn = queue.pop(0)
        if ahn.bit_length() - 1 >= max_gen:
            continue
        result[ahn] = person
        father, mother = get_parents(db, person)
        if father:
            queue.append((father, ahn * 2))
        if mother:
            queue.append((mother, ahn * 2 + 1))
    return result


def _person_text(db, person):
    """Return (name, dates) for display. Surname in uppercase."""
    pn = person.get_primary_name()
    given = pn.get_first_name()
    surname = pn.get_surname().upper()
    name = f"{given} {surname}".strip() or "Unknown"
    birth_year = get_year(get_event(db, person, EventType.BIRTH))
    death_year = get_year(get_event(db, person, EventType.DEATH))
    parts = []
    if birth_year:
        parts.append(f"b. {birth_year}")
    if death_year:
        parts.append(f"d. {death_year}")
    return name, "   ".join(parts)


def _fit_size(text, font, max_size, max_width, min_size=4.0):
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def _truncate(text, font, size, max_width):
    if stringWidth(text, font, size) <= max_width:
        return text
    while text and stringWidth(text + "…", font, size) > max_width:
        text = text[:-1]
    return text + "…"


def _draw_box(c, x, y, w, h, gender, name, dates, vertical=False):
    fill = C_MALE if gender == MALE else (C_FEMALE if gender == FEMALE else C_UNKNOWN)
    c.setFillColor(fill)
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.4)
    c.roundRect(x, y, w, h, radius=2, fill=1, stroke=1)

    pad = 3.0

    if vertical:
        # Rotate 90° CCW around box centre; available text width = h, size capped by w
        text_w = h - pad * 2
        max_name_pt = min(w * 0.38, 10.0)
        max_date_pt = min(w * 0.28,  8.0)
        c.saveState()
        c.translate(x + w / 2, y + h / 2)
        c.rotate(90)
        if dates:
            name_size = _fit_size(name,  "Helvetica-Bold", max_name_pt, text_w)
            date_size = _fit_size(dates, "Helvetica",      min(max_date_pt, name_size - 1), text_w)
            name  = _truncate(name,  "Helvetica-Bold", name_size, text_w)
            block = name_size + 2 + date_size
            name_y = block / 2 - name_size * 0.8
            date_y = name_y - date_size - 2
            c.setFont("Helvetica-Bold", name_size)
            c.setFillColor(C_NAME)
            c.drawCentredString(0, name_y, name)
            c.setFont("Helvetica", date_size)
            c.setFillColor(C_DATES)
            c.drawCentredString(0, date_y, dates)
        else:
            name_size = _fit_size(name, "Helvetica-Bold", max_name_pt, text_w)
            name = _truncate(name, "Helvetica-Bold", name_size, text_w)
            c.setFont("Helvetica-Bold", name_size)
            c.setFillColor(C_NAME)
            c.drawCentredString(0, -name_size * 0.35, name)
        c.restoreState()
    else:
        text_w = w - pad * 2
        max_name_pt = min(h * 0.38, 8.5)
        max_date_pt = min(h * 0.28, 7.0)
        if dates:
            name_size = _fit_size(name,  "Helvetica-Bold", max_name_pt, text_w)
            date_size = _fit_size(dates, "Helvetica",      min(max_date_pt, name_size - 1), text_w)
            name  = _truncate(name,  "Helvetica-Bold", name_size, text_w)
            block = name_size + 2 + date_size
            name_y = y + (h + block) / 2 - name_size * 0.8
            date_y = name_y - date_size - 2
            c.setFont("Helvetica-Bold", name_size)
            c.setFillColor(C_NAME)
            c.drawString(x + pad, name_y, name)
            c.setFont("Helvetica", date_size)
            c.setFillColor(C_DATES)
            c.drawString(x + pad, date_y, dates)
        else:
            name_size = _fit_size(name, "Helvetica-Bold", max_name_pt, text_w)
            name = _truncate(name, "Helvetica-Bold", name_size, text_w)
            name_y = y + h / 2 - name_size * 0.35
            c.setFont("Helvetica-Bold", name_size)
            c.setFillColor(C_NAME)
            c.drawString(x + pad, name_y, name)


def generate_pdf(db, root_gid, max_gen, output_path, page_size=None):
    pw, ph = landscape(page_size or pagesizes.A4)
    margin  = 10 * mm
    title_h = 7  * mm

    usable_w = pw - 2 * margin
    usable_h = ph - 2 * margin - title_h
    col_w    = usable_w / max_gen
    gap_x    = col_w * 0.08   # padding on each side of a box within its column
    box_w    = col_w - gap_x * 2

    root = db.get_person_from_gramps_id(root_gid)
    ancestors = _get_ancestors(db, root, max_gen)

    def slot_geometry(ahn):
        """(box_x, box_y, box_w, box_h, mid_y) for an ahnentafel number."""
        gen   = ahn.bit_length() - 1
        pos   = ahn - (1 << gen)             # 0 = topmost slot
        n     = 1 << gen                     # slots in this generation
        slot_h = usable_h / n
        gap_y  = slot_h * 0.07
        bh = slot_h - gap_y * 2
        bx = margin + gen * col_w + gap_x
        by = (ph - margin - title_h) - (pos + 1) * slot_h + gap_y
        return bx, by, box_w, bh, by + bh / 2

    c = rl_canvas.Canvas(str(output_path), pagesize=(pw, ph))

    # Title
    root_name, _ = _person_text(db, root)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_TITLE)
    c.drawString(margin, ph - margin - 4 * mm,
                 f"Ancestor Tree — {root_name}   ({max_gen} generations)")

    # Generation labels along the top
    gen_labels = {0: "Self", 1: "Parents", 2: "Grandparents", 3: "Great-grandparents"}
    for g in range(max_gen):
        label = gen_labels.get(g, f"{'Great-' * (g - 2)}Great-grandparents" if g > 2 else "")
        if g >= 4:
            label = f"Gen +{g}"
        lx = margin + g * col_w + gap_x
        ly = ph - margin - title_h + 1
        c.setFont("Helvetica", 5.5)
        c.setFillColor(C_DATES)
        c.drawString(lx, ly, label)

    # Draw connector lines first (boxes render on top)
    # All non-leaf slots get lines regardless of whether the person is known
    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.5)
    for ahn in range(1, 1 << (max_gen - 1)):
        bx, by, bw, bh, mid_y = slot_geometry(ahn)
        junction_x = bx + bw + gap_x
        father_ahn, mother_ahn = ahn * 2, ahn * 2 + 1
        _, _, _, _, f_mid = slot_geometry(father_ahn)
        _, _, _, _, m_mid = slot_geometry(mother_ahn)
        fbx, _, _, _, _ = slot_geometry(father_ahn)
        mbx, _, _, _, _ = slot_geometry(mother_ahn)
        c.line(bx + bw, mid_y, junction_x, mid_y)
        c.line(junction_x, f_mid, junction_x, m_mid)
        c.line(junction_x, f_mid, fbx, f_mid)
        c.line(junction_x, m_mid, mbx, m_mid)

    # Draw all slots — filled for known people, empty outline for missing
    for ahn in range(1, 1 << max_gen):
        bx, by, bw, bh, _ = slot_geometry(ahn)
        gen = ahn.bit_length() - 1
        if ahn in ancestors:
            person = ancestors[ahn]
            name, dates = _person_text(db, person)
            if gen >= 6 and dates:
                name = f"{name}  {dates}"
                dates = ""
            _draw_box(c, bx, by, bw, bh, person.get_gender(), name, dates)
        else:
            c.setFillColor(colors.white)
            c.setStrokeColor(C_BORDER)
            c.setLineWidth(0.4)
            c.roundRect(bx, by, bw, bh, radius=2, fill=1, stroke=1)

    c.save()

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = Path(tmp.name)
    output_path.rename(tmp_path)
    subprocess.run(
        [
            'ghostscript', '-dBATCH', '-dNOPAUSE', '-dQUIET',
            '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
            f'-sOutputFile={output_path}', str(tmp_path),
        ],
        check=True,
    )
    tmp_path.unlink()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate a printable A4 PDF ancestor pedigree chart.")
    parser.add_argument("generations", type=int, help="Number of generations to show (minimum 2)")
    parser.add_argument("output", nargs="?", type=Path, help="Output PDF filename (default: ancestor_tree_Ngen.pdf)")
    parser.add_argument("--color", action=argparse.BooleanOptionalAction, default=False,
                        help="Use colour boxes (default: black & white)")
    parser.add_argument("--paper", default="A4", choices=PAPER_SIZES,
                        metavar="|".join(PAPER_SIZES),
                        help="Paper size (default: A4)")
    args = parser.parse_intermixed_args()

    if args.generations < 2:
        parser.error("Minimum 2 generations.")
    _, ph_pts = landscape(PAPER_SIZES[args.paper])
    usable_h_mm = ph_pts / mm - 27  # 2×margin(10mm) + title(7mm)
    warn_threshold = int(math.log2(usable_h_mm / 2.0)) + 1
    if args.generations > warn_threshold:
        print(f"Warning: {args.generations} generations will produce very small text on {args.paper}.")

    _apply_palette(PALETTE_COLOR if args.color else PALETTE_BW)

    output = args.output or Path(f"ancestor_tree_{args.generations}gen.pdf")

    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_R)
    try:
        generate_pdf(db, config.me, args.generations, output, page_size=PAPER_SIZES[args.paper])
    finally:
        db.close()


if __name__ == '__main__':
    main()
