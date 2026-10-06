#!/usr/bin/env python3
"""Query the generated achievement-standard index and report canonical source lines."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1] / "references" / "curriculum-2022"
STANDARDS_PATH = ROOT / "standards.json"
SOURCE_ISSUES = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["known_source_issues"]
TRANSLATE_CODE = str.maketrans({"–": "-", "—": "-", "−": "-", "∼": "~", "～": "~"})


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def folded(value: str) -> str:
    return nfc(value).casefold()


def canonical_code(value: str) -> str:
    value = nfc(value).translate(TRANSLATE_CODE).strip()
    value = re.sub(r"\s+", "", value)
    return value if value.startswith("[") else f"[{value}]"


def resolve_nfc_path(filename: str) -> Path:
    wanted = nfc(filename)
    for path in ROOT.iterdir():
        if nfc(path.name) == wanted:
            return path
    raise FileNotFoundError(f"Cannot resolve indexed file: {filename}")


def h1_physical_line(lines: list[str]) -> int:
    in_frontmatter = bool(lines and lines[0] == "---")
    frontmatter_closed = not in_frontmatter
    for physical, line in enumerate(lines, start=1):
        if in_frontmatter and physical > 1 and line == "---":
            in_frontmatter = False
            frontmatter_closed = True
            continue
        if frontmatter_closed and line.startswith("# "):
            return physical
    raise ValueError("Canonical H1 heading not found")


def extract_source_text(line: str, code: str) -> str:
    """Extract one standard when an HTML table stores several standards on one line."""
    normalized_line = line.translate(TRANSLATE_CODE)
    normalized_code = canonical_code(code)
    start = normalized_line.find(normalized_code)
    if start >= 0:
        next_code = normalized_line.find("[", start + len(normalized_code))
        next_break = normalized_line.find("<br", start + len(normalized_code))
        boundaries = [value for value in (next_code, next_break) if value >= 0]
        end = min(boundaries) if boundaries else len(line)
        line = line[start:end]
    line = re.sub(r"<br\s*/?>", " ", line, flags=re.IGNORECASE)
    line = re.sub(r"<[^>]+>", "", line)
    return html.unescape(line).strip()


def enrich(record: dict[str, Any], cache: dict[str, tuple[list[str], int]]) -> dict[str, Any]:
    filename = record["file"]
    if filename not in cache:
        path = resolve_nfc_path(filename)
        lines = path.read_text(encoding="utf-8").splitlines()
        cache[filename] = (lines, h1_physical_line(lines))
    lines, h1_line = cache[filename]
    physical = h1_line + int(record["line"]) - 1
    if not 1 <= physical <= len(lines):
        raise ValueError(f"Indexed line is outside {filename}: {record['line']}")
    source_text = extract_source_text(lines[physical - 1].strip(), record["code"])
    issues = [issue["reason"] for issue in SOURCE_ISSUES
              if (issue["file"], issue["code"]) == (filename, record["code"])]
    return {
        **record,
        "source_issues": issues,
        "physical_line": physical,
        "source_text": source_text,
        "source": f"{filename}:{physical}",
    }


def matches_metadata(record: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.level and args.level != record.get("school_level"):
        return False
    if args.code and canonical_code(record["code"]) != canonical_code(args.code):
        return False
    if args.subject and folded(args.subject) not in folded(record["subject"]):
        return False
    if args.area and folded(args.area) not in folded(record.get("area_name") or ""):
        return False
    if args.file and folded(args.file) not in folded(record["file"]):
        return False
    return True


def matches_text(record: dict[str, Any], text: str | None) -> bool:
    if not text:
        return True
    haystack = " ".join(
        str(record.get(key) or "")
        for key in ("code", "subject", "area_name", "source_text")
    )
    return folded(text) in folded(haystack)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query standards.json and report canonical physical source lines."
    )
    parser.add_argument("--level", choices=("중학교", "고등학교"), help="School level")
    parser.add_argument("--code", help="Exact standard code, with or without brackets")
    parser.add_argument("--subject", help="Substring of the official course name")
    parser.add_argument("--area", help="Substring of the achievement-standard area name")
    parser.add_argument("--file", help="Substring of the canonical source filename")
    parser.add_argument("--text", help="Substring in code, course, area, or standard statement")
    parser.add_argument("--limit", type=int, default=50, help="Maximum results (default: 50)")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    if not any((args.level, args.code, args.subject, args.area, args.file, args.text)):
        parser.error("provide at least one query filter")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def render_markdown(results: list[dict[str, Any]], total: int, limit: int) -> str:
    lines = [f"# Achievement standards: {len(results)} shown / {total} matched", ""]
    for record in results:
        area = record.get("area_name") or "(no named area)"
        lines.extend(
            [
                f"- {record['code']} | {record['school_level']} | {record['subject']} | {record['area_no']}. {area}",
                f"  - source: {record['source']} (H1-relative line {record['line']})",
                f"  - text: {record['source_text']}",
            ]
        )
        for issue in record.get("source_issues", []):
            lines.append(f"  - source issue: {issue}")
    if total > limit:
        lines.extend(["", f"Result truncated at --limit {limit}; refine filters or raise the limit."])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if not STANDARDS_PATH.exists():
        print(f"Missing generated index: {STANDARDS_PATH}", file=sys.stderr)
        return 2
    raw = json.loads(STANDARDS_PATH.read_text(encoding="utf-8"))
    cache: dict[str, tuple[list[str], int]] = {}
    candidates = [record for record in raw if matches_metadata(record, args)]
    enriched = [enrich(record, cache) for record in candidates]
    matched = [record for record in enriched if matches_text(record, args.text)]
    shown = matched[: args.limit]
    if args.format == "json":
        print(
            json.dumps(
                {"matched": len(matched), "shown": len(shown), "results": shown},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render_markdown(shown, len(matched), args.limit))
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
