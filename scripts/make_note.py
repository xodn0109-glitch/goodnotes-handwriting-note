#!/usr/bin/env python3
"""Render exact Korean text into Goodnotes-ready lined-paper PNG and PDF pages."""

from __future__ import annotations

import argparse
import re
import sys
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
        color = PAPER if is_blank else ink
        draw.text((cursor, baseline), segment, font=font, fill=color, stroke_width=stroke_width, stroke_fill=color, anchor="ls")
        prefix += segment
        index = end


def paper_page(kind: str) -> Image.Image:
    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), PAPER)
    draw = ImageDraw.Draw(page)
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
    heading = re.match(r"^(#{1,3})\s+", stripped)
    if heading:
        return ("heading1" if len(heading.group(1)) == 1 else "heading2"), stripped[heading.end():]
    if re.match(r"^\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*.+$", plain):
        return "heading1", stripped
    if re.match(r"^\s*<\d+>\s+.+$", plain):
        return "heading1", stripped
    if re.match(r"^\s*\d+\.\s+.+$", plain):
        return "heading2", stripped
    bullet = re.match(r"^\s*([-*•])\s+(.+)$", stripped)
    if bullet:
        return "bullet", "• " + bullet.group(2)
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
    match = re.match(r"^(?P<indent>[\s\u00a0]*)(?P<label>(?:\d+\)|\(\d+\)|[A-Za-z]\.)\s+[^:]+:)(?P<separator>[\s\u00a0]*)(?P<detail>.+)$", content)
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
    match = re.match(r"^(?P<indent>[\s\u00a0]*)(?P<label>(?:\d+\)|\(\d+\)|[A-Za-z]\.)[\s\u00a0]+)(?P<detail>.+)$", content)
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


def render_pages(text: str, paper: str, font_path: Path, ink: str) -> list[Image.Image]:
    prototype = paper_page(paper)
    prototype_draw = ImageDraw.Draw(prototype)
    heading_font = heading_font_path(font_path)
    body, h1, h2 = (load_font(font_path, 64), load_font(heading_font, 85), load_font(heading_font, 78))
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
            needed = RULE_GAP * (2 if kind == "heading1" else 1)
            if y + needed > max_y:
                break
            y += draw_line(draw, (MARGIN_LEFT, y), line, kind, indent, body, h1, h2, ink, body_stroke_width)
            index += 1
        pages.append(page)
        page_number += 1
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
    pages = render_pages(text, args.paper, font_path, args.ink_color)
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
