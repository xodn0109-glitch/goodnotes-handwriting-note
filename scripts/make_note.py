#!/usr/bin/env python3
"""Render exact Korean text into Goodnotes-ready lined-paper PNG and PDF pages."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RENDER_SCALE = 2
OUTPUT_DPI = 400
BASE_PAGE_WIDTH, BASE_PAGE_HEIGHT = 1358, 1746  # User-supplied Goodnotes paper sample
PAGE_WIDTH, PAGE_HEIGHT = BASE_PAGE_WIDTH * RENDER_SCALE, BASE_PAGE_HEIGHT * RENDER_SCALE
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = (225 * RENDER_SCALE, 40 * RENDER_SCALE, 156 * RENDER_SCALE, 42 * RENDER_SCALE)
MARGIN_LINE_X = 194 * RENDER_SCALE
RULE_GAP = 44 * RENDER_SCALE  # 5.6 mm at 400 DPI; fixed 10-inch tablet preset
PAPER, RULE_COLOR, MARGIN_COLOR = "#F8F7E9", "#DEDFDB", "#C64E58"
BLANK_FILL = "#F1F1F1"
SLIDE_MODE = False
SLIDE_HEADER, SLIDE_ACCENT = "#4B3675", "#F4C95D"
HEADING_HIGHLIGHT = "#FFF1A8"
BLANK_OPEN, BLANK_CLOSE = "[[", "]]"
BUNDLED_GAEGU_REGULAR = Path(__file__).resolve().parents[1] / "assets" / "Gaegu-Regular.ttf"
BUNDLED_GAEGU_BOLD = Path(__file__).resolve().parents[1] / "assets" / "Gaegu-Bold.ttf"
BUNDLED_NOTO_SANS_KR = Path(__file__).resolve().parents[1] / "assets" / "NotoSansKR-Variable.ttf"
BUNDLED_BADASSEUGI_REGULAR = Path(__file__).resolve().parents[1] / "assets" / "HakgyoansimBadasseugiTTF-L.ttf"
BUNDLED_BADASSEUGI_BOLD = Path(__file__).resolve().parents[1] / "assets" / "HakgyoansimBadasseugiTTF-B.ttf"
DEFAULT_FONT_CANDIDATES = (
    str(BUNDLED_BADASSEUGI_REGULAR),
    str(BUNDLED_GAEGU_REGULAR),
    str(BUNDLED_NOTO_SANS_KR),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Text to render. Newlines are preserved.")
    source.add_argument("--input", type=Path, help="UTF-8 text or Markdown file.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--name", default="handwriting-note", help="Output filename stem.")
    parser.add_argument("--title", help="Optional document metadata; the top page area remains blank.")
    parser.add_argument("--first-line-title", action="store_true", help="Use the first nonempty input line as metadata instead of printing it.")
    parser.add_argument("--paper", choices=("sample", "ruled", "grid", "plain"), default="sample")
    parser.add_argument("--ink-color", default="#000000")
    parser.add_argument("--font", type=Path, help="TTF/TTC/OTF font file; defaults to bundled Hakgyoansim Badasseugi.")
    parser.add_argument("--slide", action="store_true", help="Render 16:9 class-display slides instead of Goodnotes paper.")
    parser.add_argument("--single-slide", action="store_true", help="Fit class-display content into one divided 16:9 slide.")
    parser.add_argument("--pdf-only", action="store_true", help="Skip individual PNG exports.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing exports with this exact filename stem.")
    args = parser.parse_args()
    if args.single_slide and not args.slide:
        parser.error("--single-slide requires --slide")
    return args


def find_font(requested: Path | None) -> Path:
    if requested:
        requested = requested.expanduser()
        if not requested.is_file():
            raise FileNotFoundError(f"Font not found: {requested}")
        return requested
    for candidate in DEFAULT_FONT_CANDIDATES:
        if Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("No usable Korean font found. Pass --font /path/to/font.ttf.")


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size, index=0)


def configure_canvas(slide: bool) -> None:
    """Switch between the fixed iPad paper and 16:9 class-display canvases."""
    global PAGE_WIDTH, PAGE_HEIGHT, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM, MARGIN_LINE_X, RULE_GAP, SLIDE_MODE
    SLIDE_MODE = slide
    if slide:
        PAGE_WIDTH, PAGE_HEIGHT = 1920 * RENDER_SCALE, 1080 * RENDER_SCALE
        MARGIN_LEFT, MARGIN_RIGHT = 120 * RENDER_SCALE, 110 * RENDER_SCALE
        MARGIN_TOP, MARGIN_BOTTOM = 132 * RENDER_SCALE, 72 * RENDER_SCALE
        MARGIN_LINE_X, RULE_GAP = 0, 66 * RENDER_SCALE
    else:
        PAGE_WIDTH, PAGE_HEIGHT = BASE_PAGE_WIDTH * RENDER_SCALE, BASE_PAGE_HEIGHT * RENDER_SCALE
        MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = (225 * RENDER_SCALE, 40 * RENDER_SCALE, 156 * RENDER_SCALE, 42 * RENDER_SCALE)
        MARGIN_LINE_X, RULE_GAP = 194 * RENDER_SCALE, 44 * RENDER_SCALE


def heading_font_path(body_font_path: Path) -> Path:
    if body_font_path.resolve() == BUNDLED_BADASSEUGI_REGULAR.resolve() and BUNDLED_BADASSEUGI_BOLD.is_file():
        return BUNDLED_BADASSEUGI_BOLD
    if body_font_path.resolve() == BUNDLED_GAEGU_REGULAR.resolve() and BUNDLED_GAEGU_BOLD.is_file():
        return BUNDLED_GAEGU_BOLD
    return body_font_path


def blank_tokens(text: str) -> list[tuple[str, bool]]:
    """Parse balanced, nonnested review markers without discarding source characters."""
    tokens: list[tuple[str, bool]] = []
    cursor, in_blank = 0, False
    while cursor < len(text):
        if text.startswith(BLANK_OPEN, cursor):
            if in_blank:
                raise ValueError("Nested blank markers '[[' are not supported.")
            in_blank = True
            cursor += len(BLANK_OPEN)
        elif text.startswith(BLANK_CLOSE, cursor):
            if not in_blank:
                raise ValueError("Closing blank marker ']]' has no matching '[['.")
            in_blank = False
            cursor += len(BLANK_CLOSE)
        else:
            tokens.append((text[cursor], in_blank))
            cursor += 1
    if in_blank:
        raise ValueError("Unclosed blank marker '[['.")
    return tokens


def visible_text(text: str) -> str:
    return "".join(char for char, _ in blank_tokens(text))


def encode_blank_tokens(tokens: list[tuple[str, bool]]) -> str:
    output: list[str] = []
    in_blank = False
    for char, is_blank in tokens:
        if is_blank != in_blank:
            output.append(BLANK_OPEN if is_blank else BLANK_CLOSE)
            in_blank = is_blank
        output.append(char)
    if in_blank:
        output.append(BLANK_CLOSE)
    return "".join(output)


def strip_blank_token_edges(tokens: list[tuple[str, bool]], *, left: bool = False, right: bool = False) -> list[tuple[str, bool]]:
    start, end = 0, len(tokens)
    if left:
        while start < end and tokens[start][0].isspace():
            start += 1
    if right:
        while end > start and tokens[end - 1][0].isspace():
            end -= 1
    return tokens[start:end]


def draw_marked_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont, ink: str, stroke_width: int) -> None:
    x, baseline = xy
    tokens = blank_tokens(text)
    prefix = ""
    index = 0
    while index < len(tokens):
        is_blank = tokens[index][1]
        end = index + 1
        while end < len(tokens) and tokens[end][1] == is_blank:
            end += 1
        segment = "".join(char for char, _ in tokens[index:end])
        # Include kerning at the run boundary, e.g. the V in A[[V]].
        cursor = x + round(draw.textlength(prefix + segment, font=font) - draw.textlength(segment, font=font))
        if is_blank:
            box = draw.textbbox((cursor, baseline), segment, font=font, anchor="ls")
            pad_x = max(2, font.size // 18)
            pad_y = max(1, font.size // 28)
            draw.rounded_rectangle(
                (box[0] - pad_x, box[1] - pad_y, box[2] + pad_x, box[3] + pad_y),
                radius=max(2, font.size // 18),
                fill=BLANK_FILL,
            )
        color = BLANK_FILL if is_blank else ink
        draw.text((cursor, baseline), segment, font=font, fill=color, stroke_width=stroke_width, stroke_fill=color, anchor="ls")
        prefix += segment
        index = end


def paper_page(kind: str) -> Image.Image:
    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), PAPER)
    draw = ImageDraw.Draw(page)
    if SLIDE_MODE:
        draw.rectangle((0, 0, PAGE_WIDTH, 82 * RENDER_SCALE), fill=SLIDE_HEADER)
        draw.rectangle((0, 82 * RENDER_SCALE, PAGE_WIDTH, 90 * RENDER_SCALE), fill=SLIDE_ACCENT)
        return page
    if kind == "plain":
        return page
    if kind == "grid":
        for x in range(MARGIN_LEFT, PAGE_WIDTH - MARGIN_RIGHT + 1, RULE_GAP):
            draw.line((x, MARGIN_TOP, x, PAGE_HEIGHT - MARGIN_BOTTOM), fill=RULE_COLOR, width=2 * RENDER_SCALE)
    for y in range(MARGIN_TOP, PAGE_HEIGHT - MARGIN_BOTTOM + 1, RULE_GAP):
        draw.line((0, y, PAGE_WIDTH, y), fill=RULE_COLOR, width=2 * RENDER_SCALE)
    draw.line((MARGIN_LINE_X, 0, MARGIN_LINE_X, PAGE_HEIGHT), fill=MARGIN_COLOR, width=2 * RENDER_SCALE)
    return page


def classify_line(raw: str) -> tuple[str, str]:
    stripped = raw.rstrip()
    if stripped.endswith("\\"):
        stripped = stripped[:-1].rstrip()
    stripped = stripped.replace(r"\.", ".")
    plain = visible_text(stripped)
    if not plain:
        return "blank", ""
    hierarchy_indent = re.match(r"^( +)(?:\d+\)|\(\d+\)|[A-Za-z]\.|[-*•])\s+", plain)
    if hierarchy_indent:
        source_width = len(hierarchy_indent.group(1))
        stripped = " " * (source_width * 2) + stripped[source_width:]
        plain = visible_text(stripped)
    heading = re.match(r"^(#{1,3})\s+", stripped)
    if heading:
        return ("heading1" if len(heading.group(1)) == 1 else "heading2"), stripped[heading.end():]
    if re.match(r"^\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*.+$", plain):
        return "heading1", stripped
    if re.match(r"^\s*<\d+>\s+.+$", plain):
        return "heading1", stripped
    if re.match(r"^\s*\d+\.\s+.+$", plain):
        return "heading2", stripped
    bullet = re.match(r"^(\s*)([-*•])\s+(.+)$", stripped)
    if bullet:
        return "bullet", bullet.group(1) + bullet.group(2) + " " + bullet.group(3)
    return "body", stripped


def split_to_width(draw: ImageDraw.ImageDraw, text: str, used_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if not text:
        return [""]
    chunks: list[list[tuple[str, bool]]] = []
    line: list[tuple[str, bool]] = []
    for token in blank_tokens(text):
        proposed = line + [token]
        proposed_text = "".join(char for char, _ in proposed)
        if line and draw.textbbox((0, 0), proposed_text, font=used_font)[2] > max_width:
            chunks.append(strip_blank_token_edges(line, right=True))
            line = strip_blank_token_edges([token], left=True)
        else:
            line = proposed
    if line or not chunks:
        chunks.append(strip_blank_token_edges(line, right=True))
    return [encode_blank_tokens(chunk) for chunk in chunks]


def definition_prefix_and_detail(kind: str, content: str) -> tuple[str, str] | None:
    """Identify a numbered definition label and its explanatory text."""
    if kind not in ("body", "bullet"):
        return None
    match = re.match(r"^(?P<indent>[\s\u00a0]*)(?P<label>(?:\d+\)|\(\d+\)|[A-Za-z]\.|-)\s+[^:]+:)(?P<separator>[\s\u00a0]*)(?P<detail>.+)$", content)
    if not match:
        return None
    prefix = match.group("indent") + match.group("label") + match.group("separator")
    # A colon inside [[...]] belongs to the hidden concept, not its label.
    # Falling back to the ordinary numbered layout keeps the marker intact.
    if prefix.count(BLANK_OPEN) != prefix.count(BLANK_CLOSE):
        return None
    return prefix, match.group("detail")


def split_hanging_to_width(draw: ImageDraw.ImageDraw, prefix: str, detail: str, used_font: ImageFont.FreeTypeFont, max_width: int) -> list[tuple[str, int]]:
    """Wrap detail text under the horizontal position where its prefix ends."""
    hanging_indent = round(draw.textlength(visible_text(prefix), font=used_font))
    widest_character = max((draw.textbbox((0, 0), char, font=used_font)[2] for char, _ in blank_tokens(detail)), default=0)
    if hanging_indent + widest_character > max_width:
        return [(part, 0) for part in split_to_width(draw, prefix + detail, used_font, max_width)]

    result: list[tuple[str, int]] = []
    line, line_indent, line_width = blank_tokens(prefix), 0, max_width
    for token in blank_tokens(detail):
        proposed = line + [token]
        proposed_text = "".join(char for char, _ in proposed)
        if line and draw.textbbox((0, 0), proposed_text, font=used_font)[2] > line_width:
            result.append((encode_blank_tokens(strip_blank_token_edges(line, right=True)), line_indent))
            line, line_indent, line_width = strip_blank_token_edges([token], left=True), hanging_indent, max_width - hanging_indent
        else:
            line = proposed
    if line or not result:
        result.append((encode_blank_tokens(strip_blank_token_edges(line, right=True)), line_indent))
    return result


def numbered_prefix_and_detail(kind: str, content: str) -> tuple[str, str] | None:
    """Identify an ordinary numbered item for a hanging continuation line."""
    if kind not in ("body", "bullet"):
        return None
    match = re.match(r"^(?P<indent>[\s\u00a0]*)(?P<label>(?:\d+\)|\(\d+\)|[A-Za-z]\.|-)[\s\u00a0]+)(?P<detail>.+)$", content)
    if not match:
        return None
    return match.group("indent") + match.group("label"), match.group("detail")


def layout_lines(text: str, draw: ImageDraw.ImageDraw, body: ImageFont.FreeTypeFont, h1: ImageFont.FreeTypeFont, h2: ImageFont.FreeTypeFont) -> list[tuple[str, str, int]]:
    result: list[tuple[str, str, int]] = []
    for raw in text.splitlines():
        kind, content = classify_line(raw)
        definition = definition_prefix_and_detail(kind, content)
        if definition:
            prefix, detail = definition
            wrapped = split_hanging_to_width(draw, prefix, detail, body, PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT)
            result.extend((kind if index == 0 else "definition-continuation", part, indent) for index, (part, indent) in enumerate(wrapped))
            continue
        numbered = numbered_prefix_and_detail(kind, content)
        if numbered:
            prefix, detail = numbered
            wrapped = split_hanging_to_width(draw, prefix, detail, body, PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT)
            result.extend((kind if index == 0 else "numbered-continuation", part, indent) for index, (part, indent) in enumerate(wrapped))
            continue
        current_font = h1 if kind == "heading1" else h2 if kind == "heading2" else body
        width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT - (35 * RENDER_SCALE if kind == "bullet" else 0)
        result.extend((kind, part, 0) for part in split_to_width(draw, content, current_font, width))
    return result


def layout_lines_for_width(text: str, draw: ImageDraw.ImageDraw, body: ImageFont.FreeTypeFont, h1: ImageFont.FreeTypeFont, h2: ImageFont.FreeTypeFont, width: int) -> list[tuple[str, str, int]]:
    result: list[tuple[str, str, int]] = []
    for raw in text.splitlines():
        kind, content = classify_line(raw)
        definition = definition_prefix_and_detail(kind, content)
        if definition:
            prefix, detail = definition
            wrapped = split_hanging_to_width(draw, prefix, detail, body, width)
            result.extend((kind if index == 0 else "definition-continuation", part, indent) for index, (part, indent) in enumerate(wrapped))
            continue
        numbered = numbered_prefix_and_detail(kind, content)
        if numbered:
            prefix, detail = numbered
            wrapped = split_hanging_to_width(draw, prefix, detail, body, width)
            result.extend((kind if index == 0 else "numbered-continuation", part, indent) for index, (part, indent) in enumerate(wrapped))
            continue
        current_font = h1 if kind == "heading1" else h2 if kind == "heading2" else body
        result.extend((kind, part, 0) for part in split_to_width(draw, content, current_font, width))
    return result


def draw_line(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, kind: str, indent: int, body: ImageFont.FreeTypeFont, h1: ImageFont.FreeTypeFont, h2: ImageFont.FreeTypeFont, ink: str, body_stroke_width: int) -> int:
    x, y = xy
    used_font = h1 if kind == "heading1" else h2 if kind == "heading2" else body
    if kind == "blank":
        return RULE_GAP
    line_x = x + indent
    stroke_width = body_stroke_width if kind in ("body", "bullet", "definition-continuation", "numbered-continuation") else 0
    glyph_box = draw.textbbox((line_x, 0), visible_text(text), font=used_font, anchor="ls", stroke_width=stroke_width)
    glyph_height = glyph_box[3] - glyph_box[1]
    baseline = y + (RULE_GAP - glyph_height) // 2 - glyph_box[1]
    if kind.startswith("heading"):
        box = draw.textbbox((line_x, baseline), visible_text(text), font=used_font, anchor="ls")
        draw_heading_highlight(draw, box, 8 * RENDER_SCALE, 9 * RENDER_SCALE)
    draw_marked_text(draw, (line_x, baseline), text, used_font, ink, stroke_width)
    return RULE_GAP * (2 if kind == "heading1" else 1)


def draw_heading_highlight(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], left_pad: int, right_pad: int) -> None:
    height = box[3] - box[1]
    if height <= 0:
        return
    top = box[1] + min(left_pad, height // 3)
    bottom = box[3] - min(2 * RENDER_SCALE, height // 5)
    draw.rounded_rectangle((box[0] - left_pad, top, box[2] + right_pad, bottom), radius=left_pad, fill=HEADING_HIGHLIGHT)


def fit_header_text(draw: ImageDraw.ImageDraw, title: str, font: ImageFont.FreeTypeFont, width: int) -> tuple[str, ImageFont.FreeTypeFont]:
    title = " ".join(title.splitlines())
    for size in range(font.size, 23, -1):
        fitted_font = font.font_variant(size=size)
        if draw.textbbox((0, 0), title, font=fitted_font)[2] <= width:
            return title, fitted_font
    fitted_font = font.font_variant(size=24)
    suffix = "…"
    low, high = 0, len(title)
    while low < high:
        mid = (low + high + 1) // 2
        if draw.textbbox((0, 0), title[:mid] + suffix, font=fitted_font)[2] <= width:
            low = mid
        else:
            high = mid - 1
    return title[:low] + suffix, fitted_font


def draw_slide_chrome(page: Image.Image, title: str, page_number: int, page_count: int, heading_font: ImageFont.FreeTypeFont) -> None:
    draw = ImageDraw.Draw(page)
    counter = f"{page_number} / {page_count}"
    title_width = PAGE_WIDTH - 230 * RENDER_SCALE - round(draw.textlength(counter, font=heading_font)) - 30 * RENDER_SCALE
    original_title = " ".join(title.splitlines())
    title, title_font = fit_header_text(draw, title, heading_font, title_width)
    if title != original_title and page_number == 1:
        print("warning: Slide title shortened to fit the header. The full title is preserved in PDF metadata.", file=sys.stderr)
    draw.text((120 * RENDER_SCALE, 43 * RENDER_SCALE), title, font=title_font, fill="#FFFFFF", anchor="lm")
    draw.text((PAGE_WIDTH - 110 * RENDER_SCALE, 43 * RENDER_SCALE), counter, font=heading_font, fill="#FFFFFF", anchor="rm")


def line_height(kind: str, rule_gap: int | None = None) -> int:
    return (RULE_GAP if rule_gap is None else rule_gap) * (2 if kind == "heading1" else 1)


def is_major_numbered_item(text: str) -> bool:
    return bool(re.match(r"^\s*\d+\)\s+", visible_text(text)))


def keep_with_next_height(lines: list[tuple[str, str, int]], index: int, rule_gap: int) -> int:
    kind, text, _ = lines[index]
    needed = line_height(kind, rule_gap)
    if not (kind.startswith("heading") or is_major_numbered_item(text)):
        return needed
    # Keep heading chains and intervening blank rows with the first content
    # line. Oversized groups may still flow across pages in the caller.
    for next_index in range(index + 1, len(lines)):
        next_kind, next_text, _ = lines[next_index]
        needed += line_height(next_kind, rule_gap)
        if next_kind != "blank" and not next_kind.startswith("heading"):
            if kind.startswith("heading") and is_major_numbered_item(next_text):
                # The first numbered section must retain its own first child;
                # otherwise the heading could stay behind when that section moves.
                needed += keep_with_next_height(lines, next_index, rule_gap) - line_height(next_kind, rule_gap)
            break
    return needed


def draw_note_panel(draw: ImageDraw.ImageDraw, left: int, top: int, right: int, bottom: int, rule_gap: int) -> tuple[int, int, int]:
    draw.rounded_rectangle((left, top, right, bottom), radius=18 * RENDER_SCALE, fill="#FFFDF6", outline="#D9CEE8", width=2 * RENDER_SCALE)
    content_left, content_right = left + 66 * RENDER_SCALE, right - 34 * RENDER_SCALE
    content_top, content_bottom = top + 22 * RENDER_SCALE, bottom - 22 * RENDER_SCALE
    draw.line((left + 48 * RENDER_SCALE, content_top, left + 48 * RENDER_SCALE, content_bottom), fill=MARGIN_COLOR, width=2 * RENDER_SCALE)
    for y in range(content_top, content_bottom + 1, rule_gap):
        draw.line((left + 16 * RENDER_SCALE, y, right - 16 * RENDER_SCALE, y), fill="#E9E7E2", width=1 * RENDER_SCALE)
    return content_left, content_top, content_bottom


def draw_spread_line(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, kind: str, indent: int, body: ImageFont.FreeTypeFont, h1: ImageFont.FreeTypeFont, h2: ImageFont.FreeTypeFont, ink: str, rule_gap: int) -> int:
    if kind == "blank":
        return rule_gap
    used_font = h1 if kind == "heading1" else h2 if kind == "heading2" else body
    line_x = x + indent
    glyph_box = draw.textbbox((line_x, 0), visible_text(text), font=used_font, anchor="ls")
    baseline = y + (rule_gap - (glyph_box[3] - glyph_box[1])) // 2 - glyph_box[1]
    if kind.startswith("heading"):
        box = draw.textbbox((line_x, baseline), visible_text(text), font=used_font, anchor="ls")
        draw_heading_highlight(draw, box, 6 * RENDER_SCALE, 7 * RENDER_SCALE)
    draw_marked_text(draw, (line_x, baseline), text, used_font, ink, 0)
    return rule_gap * (2 if kind == "heading1" else 1)


def divide_across_panels(lines: list[tuple[str, str, int]], panel_height: int, rule_gap: int) -> list[tuple[int, int]] | None:
    breaks: list[tuple[int, int]] = []
    index = 0
    for _ in range(2):
        start, used = index, 0
        if index == len(lines):
            breaks.append((index, index))
            continue
        while index < len(lines):
            kind, line, _ = lines[index]
            needed = line_height(kind, rule_gap)
            group_height = keep_with_next_height(lines, index, rule_gap)
            if used and group_height <= panel_height and used + group_height > panel_height:
                break
            if used + needed > panel_height:
                break
            used += needed
            index += 1
        if index == start:
            return None
        breaks.append((start, index))
    return breaks if index == len(lines) else None


def render_single_slide(text: str, font_path: Path, ink: str, slide_title: str) -> Image.Image:
    page = paper_page("plain")
    draw = ImageDraw.Draw(page)
    heading_path = heading_font_path(font_path)
    panel_left, panel_gap, panel_right = 78 * RENDER_SCALE, 28 * RENDER_SCALE, 78 * RENDER_SCALE
    panel_top, panel_bottom = 116 * RENDER_SCALE, PAGE_HEIGHT - 58 * RENDER_SCALE
    panel_width = (PAGE_WIDTH - panel_left - panel_right - panel_gap) // 2
    left_panel = (panel_left, panel_top, panel_left + panel_width, panel_bottom)
    right_panel = (left_panel[2] + panel_gap, panel_top, PAGE_WIDTH - panel_right, panel_bottom)
    content_width = left_panel[2] - left_panel[0] - 100 * RENDER_SCALE
    content_height = panel_bottom - panel_top - 44 * RENDER_SCALE
    selected: tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, int, list[tuple[str, str, int]], list[tuple[int, int]]] | None = None
    for body_size in (58, 54, 50, 46, 42, 38):
        body, h1, h2 = load_font(font_path, body_size), load_font(heading_path, body_size + 20), load_font(heading_path, body_size + 14)
        rule_gap = round(body_size * 1.34)
        lines = layout_lines_for_width(text, draw, body, h1, h2, content_width)
        breaks = divide_across_panels(lines, content_height, rule_gap)
        if breaks:
            selected = body, h1, h2, rule_gap, lines, breaks
            break
    if selected is None:
        raise ValueError("The note is too dense for a two-page spread at the supported display size.")
    body, h1, h2, rule_gap, lines, breaks = selected
    draw_slide_chrome(page, slide_title or "수업 자료", 1, 1, load_font(heading_path, 42))
    for panel, (start, end) in zip((left_panel, right_panel), breaks):
        content_x, y, content_bottom = draw_note_panel(draw, *panel, rule_gap)
        for kind, line, indent in lines[start:end]:
            y += draw_spread_line(draw, content_x, y, line, kind, indent, body, h1, h2, ink, rule_gap)
        if y > content_bottom + rule_gap:
            raise ValueError("Two-page spread overflow.")
    return page


def render_pages(text: str, paper: str, font_path: Path, ink: str, slide: bool = False, single_slide: bool = False, slide_title: str = "") -> list[Image.Image]:
    if not text.strip() or not visible_text(text).strip():
        raise ValueError("Input text is empty.")
    if single_slide and not slide:
        raise ValueError("single_slide requires slide=True.")
    configure_canvas(slide)
    if slide and single_slide:
        return [render_single_slide(text, font_path, ink, slide_title)]
    prototype = paper_page(paper)
    prototype_draw = ImageDraw.Draw(prototype)
    heading_font = heading_font_path(font_path)
    body_size, h1_size, h2_size = (88, 110, 100) if slide else (64, 85, 78)
    body, h1, h2 = (load_font(font_path, body_size), load_font(heading_font, h1_size), load_font(heading_font, h2_size))
    body_stroke_width = 1 if font_path.resolve() == BUNDLED_BADASSEUGI_REGULAR.resolve() else 0
    lines = layout_lines(text, prototype_draw, body, h1, h2)
    pages, index, page_number = [], 0, 1
    while index < len(lines) or not pages:
        page = paper_page(paper)
        draw = ImageDraw.Draw(page)
        y = MARGIN_TOP
        max_y = PAGE_HEIGHT - MARGIN_BOTTOM
        while index < len(lines):
            kind, line, indent = lines[index]
            needed = line_height(kind)
            group_height = keep_with_next_height(lines, index, RULE_GAP)
            if y > MARGIN_TOP and group_height <= max_y - MARGIN_TOP and y + group_height > max_y:
                break
            if y + needed > max_y:
                break
            y += draw_line(draw, (MARGIN_LEFT, y), line, kind, indent, body, h1, h2, ink, body_stroke_width)
            index += 1
        pages.append(page)
        page_number += 1
    if slide:
        chrome_font = load_font(heading_font, 42)
        for number, page in enumerate(pages, start=1):
            draw_slide_chrome(page, slide_title or "수업 자료", number, len(pages), chrome_font)
    return pages


def existing_exports(output_dir: Path, stem: str) -> list[Path]:
    if not output_dir.exists():
        return []
    pattern = re.compile(re.escape(stem) + r"-page-\d+\.png$")
    return sorted(path for path in output_dir.iterdir() if path.name == f"{stem}.pdf" or pattern.fullmatch(path.name))


def check_output_conflicts(output_dir: Path, stem: str, overwrite: bool) -> list[Path]:
    existing = existing_exports(output_dir, stem)
    if existing and not overwrite:
        raise FileExistsError(f"Exports already exist for '{stem}'. Choose another --name or pass --overwrite.")
    if any(path.is_dir() for path in existing):
        raise IsADirectoryError("An export filename is occupied by a directory.")
    return existing


def export_pages(pages: list[Image.Image], output_dir: Path, stem: str, title: str, pdf_only: bool, overwrite: bool) -> Path:
    existing = check_output_conflicts(output_dir, stem, overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{stem}.pdf"
    # Finish every encoder before replacing any existing output. Failed renders
    # or encodes must leave the user's previous exports intact.
    with tempfile.TemporaryDirectory(prefix=".make-note-", dir=output_dir) as staging_name:
        staging = Path(staging_name)
        pages[0].save(staging / pdf_path.name, "PDF", resolution=OUTPUT_DPI, save_all=True, append_images=pages[1:], title=title)
        filenames = [pdf_path.name]
        if not pdf_only:
            for number, page in enumerate(pages, start=1):
                filename = f"{stem}-page-{number:02d}.png"
                page.save(staging / filename, "PNG", dpi=(OUTPUT_DPI, OUTPUT_DPI))
                filenames.append(filename)
        # Recheck after encoding in case another process wrote this stem.
        existing = check_output_conflicts(output_dir, stem, overwrite)
        for filename in filenames:
            (staging / filename).replace(output_dir / filename)
        for old_path in existing:
            if old_path.name not in filenames:
                old_path.unlink()
    return pdf_path


def main() -> int:
    args = parse_args()
    text = args.text if args.text is not None else args.input.expanduser().read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("Input text is empty.")
    output_dir = args.output_dir.expanduser().resolve()
    stem = re.sub(r'[\\/:*?"<>|\s]+', "-", args.name).strip(".-") or "handwriting-note"
    font_path = find_font(args.font)
    source_lines = text.splitlines()
    first_content_index = next((index for index, line in enumerate(source_lines) if line.strip()), None)
    metadata_title = args.title
    if args.first_line_title and first_content_index is not None:
        _, first_content = classify_line(source_lines[first_content_index])
        metadata_title = metadata_title or visible_text(first_content)
        text = "\n".join(source_lines[:first_content_index] + source_lines[first_content_index + 1:])
    if args.input and any(path.resolve() == args.input.expanduser().resolve() for path in existing_exports(output_dir, stem)):
        raise ValueError("The input source cannot also be an export destination. Choose another --name or --output-dir.")
    check_output_conflicts(output_dir, stem, args.overwrite)
    pages = render_pages(text, args.paper, font_path, args.ink_color, args.slide, args.single_slide, metadata_title or stem)
    pdf_path = export_pages(pages, output_dir, stem, metadata_title or stem, args.pdf_only, args.overwrite)
    print(f"font={font_path}\npdf={pdf_path}\npages={len(pages)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
