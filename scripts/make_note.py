#!/usr/bin/env python3
"""Render exact Korean text into Goodnotes-ready lined-paper PNG and PDF pages."""

from __future__ import annotations

import argparse
import re
import sys
from math import ceil
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
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/1fb44cf128344a11e654a43ccd7a45a68026bf5d.asset/AssetData/NanumScript.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Text to render. Newlines are preserved.")
    source.add_argument("--input", type=Path, help="UTF-8 text or Markdown file.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--name", default="handwriting-note", help="Output filename stem.")
    parser.add_argument("--title", help="Optional document metadata; the top page area remains blank.")
    parser.add_argument("--paper", choices=("sample", "ruled", "grid", "plain"), default="sample")
    parser.add_argument("--ink-color", default="#000000")
    parser.add_argument("--font", type=Path, help="TTF/TTC/OTF font file; defaults to bundled Hakgyoansim Badasseugi.")
    parser.add_argument("--slide", action="store_true", help="Render 16:9 class-display slides instead of Goodnotes paper.")
    parser.add_argument("--single-slide", action="store_true", help="Fit class-display content into one divided 16:9 slide.")
    parser.add_argument("--pdf-only", action="store_true", help="Skip individual PNG exports.")
    return parser.parse_args()


def find_font(requested: Path | None) -> Path:
    if requested:
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
    """Return text characters paired with whether they should match the paper color."""
    tokens: list[tuple[str, bool]] = []
    cursor = 0
    while cursor < len(text):
        if text.startswith(BLANK_OPEN, cursor):
            end = text.find(BLANK_CLOSE, cursor + len(BLANK_OPEN))
            if end == -1:
                raise ValueError("Unclosed blank marker '[['.")
            tokens.extend((char, True) for char in text[cursor + len(BLANK_OPEN):end])
            cursor = end + len(BLANK_CLOSE)
        elif text.startswith(BLANK_CLOSE, cursor):
            raise ValueError("Closing blank marker ']]' has no matching '[['.")
        else:
            tokens.append((text[cursor], False))
            cursor += 1
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
        cursor = x + round(draw.textlength(prefix, font=font))
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
    return match.group("indent") + match.group("label") + match.group("separator"), match.group("detail")


def split_hanging_to_width(draw: ImageDraw.ImageDraw, prefix: str, detail: str, used_font: ImageFont.FreeTypeFont, max_width: int) -> list[tuple[str, int]]:
    """Wrap detail text under the horizontal position where its prefix ends."""
    hanging_indent = round(draw.textlength(visible_text(prefix), font=used_font))
    if hanging_indent >= max_width:
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
    baseline = y + (RULE_GAP + glyph_height) // 2
    if kind.startswith("heading"):
        box = draw.textbbox((line_x, baseline), visible_text(text), font=used_font, anchor="ls")
        draw.rounded_rectangle((line_x - 8 * RENDER_SCALE, box[1] + 8 * RENDER_SCALE, box[2] + 9 * RENDER_SCALE, box[3] - 2 * RENDER_SCALE), radius=8 * RENDER_SCALE, fill=HEADING_HIGHLIGHT)
    draw_marked_text(draw, (line_x, baseline), text, used_font, ink, stroke_width)
    return RULE_GAP * (2 if kind == "heading1" else 1)


def draw_slide_chrome(page: Image.Image, title: str, page_number: int, page_count: int, heading_font: ImageFont.FreeTypeFont) -> None:
    draw = ImageDraw.Draw(page)
    draw.text((120 * RENDER_SCALE, 43 * RENDER_SCALE), title, font=heading_font, fill="#FFFFFF", anchor="lm")
    draw.text((PAGE_WIDTH - 110 * RENDER_SCALE, 43 * RENDER_SCALE), f"{page_number} / {page_count}", font=heading_font, fill="#FFFFFF", anchor="rm")


def line_height(kind: str) -> int:
    return RULE_GAP * (2 if kind == "heading1" else 1)


def is_major_numbered_item(text: str) -> bool:
    return bool(re.match(r"^\s*\d+\)\s+", visible_text(text)))


def collect_slide_sections(text: str) -> tuple[str, str, list[list[str]]]:
    chapter, topic, current, sections = "", "", None, []
    for raw in text.splitlines():
        kind, content = classify_line(raw)
        if kind == "blank":
            continue
        if kind == "heading1":
            chapter = content
            continue
        if kind == "heading2":
            topic = content
            continue
        if is_major_numbered_item(content):
            if current:
                sections.append(current)
            current = [content]
        elif current is not None:
            current.append(content)
    if current:
        sections.append(current)
    return chapter, topic, sections


def card_text_lines(draw: ImageDraw.ImageDraw, section: list[str], body: ImageFont.FreeTypeFont, heading: ImageFont.FreeTypeFont, width: int) -> tuple[list[str], list[str]]:
    title = split_to_width(draw, section[0].lstrip(), heading, width)
    body_lines: list[str] = []
    for source in section[1:]:
        body_lines.extend(split_to_width(draw, source, body, width))
    return title, body_lines


def render_card_slide(text: str, font_path: Path, ink: str, slide_title: str) -> Image.Image:
    page = paper_page("plain")
    draw = ImageDraw.Draw(page)
    heading_path = heading_font_path(font_path)
    chapter, topic, sections = collect_slide_sections(text)
    if not sections:
        sections = [[slide_title or "수업 자료"]]
    columns = 1 if len(sections) == 1 else 2
    rows = ceil(len(sections) / columns)
    outer_left, outer_right = 96 * RENDER_SCALE, 96 * RENDER_SCALE
    grid_top, grid_bottom, gap = 118 * RENDER_SCALE, 62 * RENDER_SCALE, 28 * RENDER_SCALE
    grid_width = PAGE_WIDTH - outer_left - outer_right
    card_width = (grid_width - gap * (columns - 1)) // columns
    card_height = (PAGE_HEIGHT - grid_top - grid_bottom - gap * (rows - 1)) // rows
    padding = 30 * RENDER_SCALE
    inner_width = card_width - padding * 2
    selected: tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, int, int] | None = None
    for body_size in (48, 44, 40, 36, 32, 28):
        body, heading = load_font(font_path, body_size), load_font(heading_path, body_size + 14)
        body_step, heading_step = round(body_size * 1.28), round((body_size + 14) * 1.18)
        fits = True
        for section in sections:
            title_lines, body_lines = card_text_lines(draw, section, body, heading, inner_width)
            required = padding * 2 + len(title_lines) * heading_step + 14 * RENDER_SCALE + len(body_lines) * body_step
            if required > card_height:
                fits = False
                break
        if fits:
            selected = body, heading, body_step, heading_step
            break
    if selected is None:
        selected = load_font(font_path, 28), load_font(heading_path, 42), 36, 50
    body, heading, body_step, heading_step = selected
    header_text = " · ".join(part for part in (visible_text(chapter), visible_text(topic)) if part) or slide_title or "수업 자료"
    draw_slide_chrome(page, header_text, 1, 1, load_font(heading_path, 42))
    for index, section in enumerate(sections):
        row, column = divmod(index, columns)
        left = outer_left + column * (card_width + gap)
        top = grid_top + row * (card_height + gap)
        right, bottom = left + card_width, top + card_height
        draw.rounded_rectangle((left, top, right, bottom), radius=18 * RENDER_SCALE, fill="#FFFDF6", outline="#D9CEE8", width=2 * RENDER_SCALE)
        title_lines, body_lines = card_text_lines(draw, section, body, heading, inner_width)
        cursor_y = top + padding
        for line in title_lines:
            draw.text((left + padding, cursor_y), visible_text(line), font=heading, fill=SLIDE_HEADER)
            cursor_y += heading_step
        cursor_y += 14 * RENDER_SCALE
        for line in body_lines:
            draw_marked_text(draw, (left + padding, cursor_y + body.size), line, body, ink, 0)
            cursor_y += body_step
    return page


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
    baseline = y + (rule_gap + glyph_box[3] - glyph_box[1]) // 2
    if kind.startswith("heading"):
        box = draw.textbbox((line_x, baseline), visible_text(text), font=used_font, anchor="ls")
        draw.rounded_rectangle((line_x - 6 * RENDER_SCALE, box[1] + 6 * RENDER_SCALE, box[2] + 7 * RENDER_SCALE, box[3] - 2 * RENDER_SCALE), radius=6 * RENDER_SCALE, fill=HEADING_HIGHLIGHT)
    draw_marked_text(draw, (line_x, baseline), text, used_font, ink, 0)
    return rule_gap * (2 if kind == "heading1" else 1)


def divide_across_panels(lines: list[tuple[str, str, int]], panel_height: int, rule_gap: int) -> list[tuple[int, int]] | None:
    breaks: list[tuple[int, int]] = []
    index = 0
    for _ in range(2):
        start, used = index, 0
        while index < len(lines):
            kind, line, _ = lines[index]
            needed = rule_gap * (2 if kind == "heading1" else 1)
            if is_major_numbered_item(line) and index + 1 < len(lines) and used:
                next_needed = rule_gap * (2 if lines[index + 1][0] == "heading1" else 1)
                if used + needed + next_needed > panel_height:
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
            if slide and is_major_numbered_item(line) and index + 1 < len(lines) and y > MARGIN_TOP:
                next_kind = lines[index + 1][0]
                if y + needed + line_height(next_kind) > max_y:
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


def main() -> int:
    args = parse_args()
    text = args.text if args.text is not None else args.input.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Input text is empty.")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r'[\\/:*?"<>|\s]+', "-", args.name).strip(".-") or "handwriting-note"
    font_path = find_font(args.font)
    source_lines = text.splitlines()
    first_content_index = next((index for index, line in enumerate(source_lines) if line.strip()), None)
    metadata_title = args.title
    if first_content_index is not None:
        kind, first_content = classify_line(source_lines[first_content_index])
        if kind == "body" and not source_lines[first_content_index].startswith((" ", "\t", "\u00a0")):
            metadata_title = metadata_title or first_content
            text = "\n".join(source_lines[:first_content_index] + source_lines[first_content_index + 1:])
    pages = render_pages(text, args.paper, font_path, args.ink_color, args.slide, args.single_slide, metadata_title or stem)
    pdf_path = output_dir / f"{stem}.pdf"
    pages[0].save(pdf_path, "PDF", resolution=OUTPUT_DPI, save_all=True, append_images=pages[1:], title=metadata_title or stem)
    if not args.pdf_only:
        for number, page in enumerate(pages, start=1):
            page.save(output_dir / f"{stem}-page-{number:02d}.png", "PNG", dpi=(OUTPUT_DPI, OUTPUT_DPI))
    print(f"font={font_path}\npdf={pdf_path}\npages={len(pages)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
