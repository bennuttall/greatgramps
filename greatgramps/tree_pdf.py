"""Generate printable PDF pedigree charts: ancestors, descendants, or both (hourglass)."""

from __future__ import annotations

import tempfile
import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib import pagesizes
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas

from gramps.gen.lib.eventtype import EventType

from .gramps_data import get_children, get_event, get_parents, get_year
from .paper_sizes import PAPER_SIZE_NAMES

FEMALE, MALE = 0, 1

_PAGESIZE_ATTR = {'letter': 'LETTER', 'legal': 'LEGAL', 'ledger': 'LEDGER'}
PAPER_SIZES = {
    name: getattr(pagesizes, _PAGESIZE_ATTR.get(name, name))
    for name in PAPER_SIZE_NAMES
}

ANCESTOR_LABELS = ("Self", "Parents", "Grandparents", "Great-grandparents")
DESCENDANT_LABELS = ("Self", "Children", "Grandchildren", "Great-grandchildren")

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

# Active palette — set by generate_*_pdf() based on the color argument
C_MALE = C_FEMALE = C_UNKNOWN = C_BORDER = C_LINE = C_NAME = C_DATES = C_TITLE = None


def _apply_palette(palette):
    global C_MALE, C_FEMALE, C_UNKNOWN, C_BORDER, C_LINE, C_NAME, C_DATES, C_TITLE
    C_MALE, C_FEMALE, C_UNKNOWN = palette['male'], palette['female'], palette['unknown']
    C_BORDER, C_LINE            = palette['border'], palette['line']
    C_NAME, C_DATES, C_TITLE   = palette['name'], palette['dates'], palette['title']


_apply_palette(PALETTE_BW)


# --- Tree building ----------------------------------------------------------
#
# Both ancestor and descendant trees are represented the same way: a node is
# {'person': Person|None, 'children': [node, ...]}. For ancestors, 'children'
# always holds exactly 2 entries (father, mother slots — possibly None) down
# to max_gen, mirroring a fixed Ahnentafel layout. For descendants, 'children'
# holds however many real children the person has, so branching is uneven.

def _build_ancestor_tree(db, person, max_gen):
    def node(p, gen):
        children = []
        if gen + 1 < max_gen:
            father, mother = get_parents(db, p) if p else (None, None)
            children = [node(father, gen + 1), node(mother, gen + 1)]
        return {'person': p, 'children': children}
    return node(person, 0)


def _build_descendant_tree(db, person, max_gen):
    def node(p, gen):
        children = []
        if gen + 1 < max_gen:
            children = [node(child, gen + 1) for child in get_children(db, p)]
        return {'person': p, 'children': children}
    return node(person, 0)


def _weight(node):
    if not node['children']:
        return 1
    return sum(_weight(c) for c in node['children'])


def _layout(node, gen=0, lo=0.0, span=1.0, out=None):
    """Flatten a tree into [(node, gen, lo, span), ...], lo/span normalised to [0, 1]."""
    if out is None:
        out = []
    out.append((node, gen, lo, span))
    children = node['children']
    if children:
        weights = [_weight(c) for c in children]
        total = sum(weights)
        cursor = lo
        for child, w in zip(children, weights):
            child_span = span * w / total
            _layout(child, gen + 1, cursor, child_span, out)
            cursor += child_span
    return out


# --- Text rendering -----------------------------------------------------

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


def _fit_size(text, font, max_size, max_width, min_size=1.0):
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def _fits_better_vertical(w, h, name):
    """Only rotate when the name doesn't fit horizontally at its natural size, and
    rotating would let it render larger."""
    pad = 3.0
    max_name_pt_h = min(h * 0.38, 8.5)
    text_w_h = w - pad * 2
    if stringWidth(name, "Helvetica-Bold", max_name_pt_h) <= text_w_h:
        return False  # fits horizontally at full size already

    h_size = _fit_size(name, "Helvetica-Bold", max_name_pt_h, text_w_h)
    v_size = _fit_size(name, "Helvetica-Bold", min(w * 0.38, 10.0), h - pad * 2)
    return v_size > h_size


def _draw_box(c, x, y, w, h, gender, name, dates, center=False, vertical=False):
    fill = C_MALE if gender == MALE else (C_FEMALE if gender == FEMALE else C_UNKNOWN)
    c.setFillColor(fill)
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.4)
    c.roundRect(x, y, w, h, radius=2, fill=1, stroke=1)

    pad = 3.0

    if vertical:
        # Rotate 90° CCW around the box centre: text runs along the box height,
        # font size is capped by the box width — suited to short/narrow boxes.
        text_w = h - pad * 2
        max_name_pt = min(w * 0.38, 10.0)
        max_date_pt = min(w * 0.28,  8.0)
        c.saveState()
        c.translate(x + w / 2, y + h / 2)
        c.rotate(90)
        if dates:
            name_size = _fit_size(name,  "Helvetica-Bold", max_name_pt, text_w)
            date_size = _fit_size(dates, "Helvetica",      min(max_date_pt, name_size - 1), text_w)
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
            c.setFont("Helvetica-Bold", name_size)
            c.setFillColor(C_NAME)
            c.drawCentredString(0, -name_size * 0.35, name)
        c.restoreState()
        return

    text_w = w - pad * 2
    max_name_pt = min(h * 0.38, 8.5)
    max_date_pt = min(h * 0.28, 7.0)
    draw_text = (lambda ty, t: c.drawCentredString(x + w / 2, ty, t)) if center else \
                (lambda ty, t: c.drawString(x + pad, ty, t))
    if dates:
        name_size = _fit_size(name,  "Helvetica-Bold", max_name_pt, text_w)
        date_size = _fit_size(dates, "Helvetica",      min(max_date_pt, name_size - 1), text_w)
        block = name_size + 2 + date_size
        name_y = y + (h + block) / 2 - name_size * 0.8
        date_y = name_y - date_size - 2
        c.setFont("Helvetica-Bold", name_size)
        c.setFillColor(C_NAME)
        draw_text(name_y, name)
        c.setFont("Helvetica", date_size)
        c.setFillColor(C_DATES)
        draw_text(date_y, dates)
    else:
        name_size = _fit_size(name, "Helvetica-Bold", max_name_pt, text_w)
        name_y = y + h / 2 - name_size * 0.35
        c.setFont("Helvetica-Bold", name_size)
        c.setFillColor(C_NAME)
        draw_text(name_y, name)


def _draw_node_box(c, db, node, rect, allow_empty, center=False):
    bx, by, bw, bh = rect
    person = node['person']
    if person is not None:
        name, dates = _person_text(db, person)
        vertical = _fits_better_vertical(bw, bh, name)
        _draw_box(c, bx, by, bw, bh, person.get_gender(), name, dates, center=center, vertical=vertical)
    elif allow_empty:
        c.setFillColor(colors.white)
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.4)
        c.roundRect(bx, by, bw, bh, radius=2, fill=1, stroke=1)


def _connect(c, parent_rect, child_rects, orientation, gap):
    """Draw connector lines from a parent box to its child boxes.

    orientation: 'right' (children to the right, landscape charts) or
    'up'/'down' (children above/below, hourglass chart).
    """
    bx, by, bw, bh = parent_rect
    if orientation == 'right':
        px, py = bx + bw, by + bh / 2
        junction = px + gap
        pts = [(cx, cy + ch / 2) for cx, cy, cw, ch in child_rects]
        c.line(px, py, junction, py)
        ys = [p[1] for p in pts]
        c.line(junction, min(ys), junction, max(ys))
        for cx, cy in pts:
            c.line(junction, cy, cx, cy)
    elif orientation == 'up':
        px, py = bx + bw / 2, by + bh
        junction = py + gap
        pts = [(cx + cw / 2, cy) for cx, cy, cw, ch in child_rects]
        c.line(px, py, px, junction)
        xs = [p[0] for p in pts]
        c.line(min(xs), junction, max(xs), junction)
        for cx, cy in pts:
            c.line(cx, junction, cx, cy)
    elif orientation == 'down':
        px, py = bx + bw / 2, by
        junction = py - gap
        pts = [(cx + cw / 2, cy + ch) for cx, cy, cw, ch in child_rects]
        c.line(px, py, px, junction)
        xs = [p[0] for p in pts]
        c.line(min(xs), junction, max(xs), junction)
        for cx, cy in pts:
            c.line(cx, junction, cx, cy)


def _gen_label(g, labels):
    return labels[g] if g < len(labels) else f"Gen +{g}"


def _draw_gen_label(c, x, y, label, max_width):
    size = _fit_size(label, "Helvetica", 5.5, max_width, min_size=3.0)
    c.setFont("Helvetica", size)
    c.setFillColor(C_DATES)
    c.drawString(x, y, label)


def _min_box_height_mm(rects):
    return min(bh for (_, _, _, bh) in rects) / mm


def _compress_pdf(output_path):
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, dir=output_path.parent) as tmp:
        tmp_path = Path(tmp.name)
    output_path.rename(tmp_path)
    subprocess.run(
        [
            'ghostscript', '-dBATCH', '-dNOPAUSE', '-dQUIET',
            '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4', '-dAutoRotatePages=/None',
            f'-sOutputFile={output_path}', str(tmp_path),
        ],
        check=True,
    )
    tmp_path.unlink()


_SMALL_TEXT_WARNING = (
    "Warning: this chart will produce very small text at this size — "
    "consider fewer generations or larger paper."
)


# --- Landscape charts (ancestors-only / descendants-only) -------------------

def _generate_landscape_pdf(db, root, tree, max_gen, output_path, color, page_size, title, labels, allow_empty, center=False):
    _apply_palette(PALETTE_COLOR if color else PALETTE_BW)

    pw, ph = landscape(page_size or pagesizes.A4)
    margin  = 10 * mm
    title_h = 7  * mm

    usable_w = pw - 2 * margin
    usable_h = ph - 2 * margin - title_h
    col_w    = usable_w / max_gen
    gap_x    = col_w * 0.08
    box_w    = col_w - gap_x * 2
    top_y    = ph - margin - title_h

    def rect(gen, lo, span):
        slot_h = span * usable_h
        gap_y  = slot_h * 0.07
        bh = slot_h - gap_y * 2
        bx = margin + gen * col_w + gap_x
        by = top_y - (lo + span) * usable_h + gap_y
        return bx, by, box_w, bh

    c = rl_canvas.Canvas(str(output_path), pagesize=(pw, ph))

    root_name, _ = _person_text(db, root)
    c.setTitle(f"{title} — {root_name}")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_TITLE)
    c.drawString(margin, ph - margin - 4 * mm, f"{title} — {root_name}   ({max_gen} generations)")

    for g in range(max_gen):
        lx = margin + g * col_w + gap_x
        ly = ph - margin - title_h + 1
        _draw_gen_label(c, lx, ly, _gen_label(g, labels), box_w)

    layout = _layout(tree)
    rects = {id(node): rect(gen, lo, span) for node, gen, lo, span in layout}

    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.5)
    for node, gen, lo, span in layout:
        if node['children']:
            child_rects = [rects[id(child)] for child in node['children']]
            _connect(c, rects[id(node)], child_rects, 'right', gap_x)

    for node, gen, lo, span in layout:
        _draw_node_box(c, db, node, rects[id(node)], allow_empty, center=center)

    c.save()
    warning = _SMALL_TEXT_WARNING if _min_box_height_mm(rects.values()) < 3.0 else None
    _compress_pdf(output_path)
    return warning


def generate_ancestor_pdf(db, root_gid, max_gen, output_path, color=False, page_size=None):
    """Generate a printable PDF ancestor pedigree chart for root_gid, max_gen generations deep."""
    root = db.get_person_from_gramps_id(root_gid)
    tree = _build_ancestor_tree(db, root, max_gen)
    return _generate_landscape_pdf(
        db, root, tree, max_gen, output_path, color, page_size,
        title="Ancestor Tree", labels=ANCESTOR_LABELS, allow_empty=True,
    )


def generate_descendant_pdf(db, root_gid, max_gen, output_path, color=False, page_size=None):
    """Generate a printable PDF descendant tree chart for root_gid, max_gen generations deep."""
    root = db.get_person_from_gramps_id(root_gid)
    tree = _build_descendant_tree(db, root, max_gen)
    return _generate_landscape_pdf(
        db, root, tree, max_gen, output_path, color, page_size,
        title="Descendant Tree", labels=DESCENDANT_LABELS, allow_empty=False, center=True,
    )


# --- Hourglass chart (ancestors above, descendants below) -------------------

def generate_hourglass_pdf(db, root_gid, ancestor_gen, descendant_gen, output_path, color=False, page_size=None):
    """Generate a printable PDF hourglass chart: ancestors above, descendants below root_gid."""
    _apply_palette(PALETTE_COLOR if color else PALETTE_BW)

    pw, ph = page_size or pagesizes.A4
    margin  = 10 * mm
    title_h = 7  * mm
    label_w = 16 * mm

    usable_w  = pw - 2 * margin - label_w
    usable_h  = ph - 2 * margin - title_h
    total_rows = ancestor_gen + descendant_gen - 1
    row_h     = usable_h / total_rows
    gap_row   = row_h * 0.08
    top_y     = ph - margin - title_h
    left_x    = margin + label_w
    root_row  = ancestor_gen - 1

    root = db.get_person_from_gramps_id(root_gid)
    ancestor_tree   = _build_ancestor_tree(db, root, ancestor_gen)
    descendant_tree = _build_descendant_tree(db, root, descendant_gen)

    def rect(row_index, lo, span):
        slot_w = span * usable_w
        gap_x  = slot_w * 0.07
        bw = slot_w - gap_x * 2
        bx = left_x + lo * usable_w + gap_x
        row_top = top_y - row_index * row_h
        bh = row_h - gap_row * 2
        by = row_top - row_h + gap_row
        return bx, by, bw, bh

    c = rl_canvas.Canvas(str(output_path), pagesize=(pw, ph))

    root_name, _ = _person_text(db, root)
    c.setTitle(f"Ancestors & Descendants — {root_name}")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_TITLE)
    c.drawCentredString(
        pw / 2, ph - margin - 4 * mm,
        f"Ancestors & Descendants — {root_name}   ({ancestor_gen} up / {descendant_gen} down)",
    )

    label_max_w = label_w - 3
    for g in range(ancestor_gen):
        row_index = root_row - g
        _draw_gen_label(c, margin, top_y - row_index * row_h - row_h / 2 + 2, _gen_label(g, ANCESTOR_LABELS), label_max_w)
    for g in range(1, descendant_gen):
        row_index = root_row + g
        _draw_gen_label(c, margin, top_y - row_index * row_h - row_h / 2 + 2, _gen_label(g, DESCENDANT_LABELS), label_max_w)

    ancestor_layout   = _layout(ancestor_tree)
    descendant_layout = _layout(descendant_tree)
    ancestor_rects   = {id(n): rect(root_row - g, lo, span) for n, g, lo, span in ancestor_layout}
    descendant_rects = {id(n): rect(root_row + g, lo, span) for n, g, lo, span in descendant_layout}

    c.setStrokeColor(C_LINE)
    c.setLineWidth(0.5)
    for node, gen, lo, span in ancestor_layout:
        if node['children']:
            child_rects = [ancestor_rects[id(child)] for child in node['children']]
            _connect(c, ancestor_rects[id(node)], child_rects, 'up', gap_row)
    for node, gen, lo, span in descendant_layout:
        if node['children']:
            child_rects = [descendant_rects[id(child)] for child in node['children']]
            _connect(c, descendant_rects[id(node)], child_rects, 'down', gap_row)

    for node, gen, lo, span in ancestor_layout:
        _draw_node_box(c, db, node, ancestor_rects[id(node)], allow_empty=True, center=True)
    for node, gen, lo, span in descendant_layout:
        if gen == 0:
            continue  # root already drawn by the ancestor pass
        _draw_node_box(c, db, node, descendant_rects[id(node)], allow_empty=False, center=True)

    c.save()
    warning = _SMALL_TEXT_WARNING if min(
        _min_box_height_mm(ancestor_rects.values()), _min_box_height_mm(descendant_rects.values()),
    ) < 3.0 else None
    _compress_pdf(output_path)
    return warning
