---
name: goodnotes-handwriting-note
description: Turn supplied text into a legible, Goodnotes-ready handwritten study note on lined, grid, or blank paper. Use for notes to import into Goodnotes; not for editable word-processing documents.
---

# Goodnotes Handwriting Note

Create a polished, import-ready study note from the user's text. By default, use the sample-derived lined-paper layout, with legible ‘学校安心 받아쓰기’ handwriting typography and PDF plus PNG exports.

## Required approach

- Preserve the supplied text verbatim apart from Markdown markers used only to establish hierarchy. Do not delegate Korean body text to image generation: it can introduce spelling errors.
- Use `scripts/make_note.py` for deterministic paper, typography, pagination, and exports. It accepts `--text` or `--input`; prefer `--input` for long text.
- Before producing a PDF, follow the available PDF skill's create-and-render verification workflow. Inspect every rendered page; revise the layout if text overlaps, clips, or becomes too small.
- Keep the original source text separate from the exported note. Do not overwrite an existing output without the user's explicit request.

## Review-note blanks

When the user asks for a fill-in review note, first make a separate marked copy of the supplied text. Surround each student-completed target with `[[` and `]]`; the renderer preserves its exact width and position and adds a pale gray background behind the blank. Do not add outlines, underlines, or placeholder symbols.

- Select only compact, assessable core concepts: technical terms, named classifications, and short indispensable noun phrases. A multiword term may stay together, but do not blank a whole clause or sentence by default.
- Leave chapter/section numbering, structural labels, verbs, linking words, and enough grammatical context visible for a student to infer what belongs in each blank. Do not blank everything in a paragraph or create trivia blanks.
- Default to a light, readable amount of recall practice: usually about one tenth to one fifth of the substantive body text, adjusted for concept density and age level. Preserve the source text outside the markers exactly.
- Do not blank the chapter marker `Ⅱ` or the hierarchy markers `1.`, `1)`, `(1)`, `a.`, and `-`. The normal and colon-based hanging-indent rules still apply because hidden text retains its original width.

## 2022 통합사회 성취기준 정렬

For a high-school `통합사회1` or `통합사회2` review note, read [2022 통합사회1·2 성취기준](references/2022-통합사회1_2-성취기준.md) before choosing blanks. Identify the closest subject, area, and achievement standard from the note heading and body text. Then give first priority to compact concepts explicitly named in that achievement standard; this makes each blank a cue for curriculum-level learning rather than merely a missing word.

- Use only the achievement-standard sentences in the reference as the alignment source. Do not treat its omitted explanatory material as a standard.
- Keep the note readable: a standard-aligned term is still not blanked if it would remove the essential grammar or most of a sentence. Prefer a concise technical term or noun phrase that the student can supply from context.
- If the note does not map confidently to a single achievement standard, use the ordinary compact-concept blanking rule instead of forcing a match. This reference applies only to the 2022 revised high-school 통합사회1·2 curriculum.

## 교육과정·단원 구조 점검

For a Korean textbook-capture note, check the applicable curriculum reference before drafting the hierarchy. Compare its subject and unit labels with the captured textbook headings, then retain the textbook's actual lesson position and visible numbering.

- Treat the curriculum reference as the scope check and the textbook heading as the authority for the printed number hierarchy. Do not invent a parent heading solely because the curriculum has a broader unit label.
- Include a parent marker such as `2.` only when it is part of the supplied lesson scope or is needed to distinguish the note from another lesson. When a capture is a continuation whose actual starting point is `2)`, begin at `2)` and retain that number.
- Before export, verify that every printed marker follows the fixed order `1.` → `1)` → `(1)` → `a.` → `-`, with no skipped or newly added parent level. Preserve the same lesson numbering across related notes.

## 출력 파일명

Name each exported note `<대단원>-<주제>-<세부노트>_<제목>-<용도>`. Derive the three-part prefix from the curriculum and textbook hierarchy before export, even when the highest parent label is omitted from the printed note.

- Keep the same prefix for the class-display and review versions of one note. For example, use `2-1-1_정의의-의미와-필요성-수업용.pdf` and `2-1-1_정의의-의미와-필요성-복습용.pdf`.
- Use the next sibling number for a distinct note at the same lesson level. Retain revision labels such as `-수정` after the use label, not before the numerical prefix.
- Apply the same stem to companion PNG pages. Pass the complete numbered stem through `make_note.py --name`.


## 교과서 캡처 자동 변환

When the user supplies a legible textbook-page capture in this note-making workflow, automatically turn its learning content into a Goodnotes study note. Do not wait for separate transcription or formatting directions.

- Preserve the chapter headings, concepts, classifications, and factual relationships visible in the capture. Convert explanatory paragraphs into concise note sentences; do not invent facts, examples, or conclusions that are absent from the source.
- By default, produce two PDFs: a student-distribution review note with achievement-standard-aligned blanks on 10-inch iPad lined paper, and a class-display note with every answer visible on one 16:9 slide containing two side-by-side note panels. Preserve identical hierarchy and content, but use the two-panel slide layout for the class-display PDF.
- Render the chapter marker `Ⅱ` above the fixed five-level hierarchy: `1.` → `1)` → `(1)` → `a.` → `-`. Use the existing hanging-indent and colon-continuation rules without asking the user again.
- For Korean textbook-capture notes, convert explanatory prose into concise noun-ending phrases, prioritizing compact Sino-Korean terminology where natural. Preserve the source's concepts and relationships.
- In source Markdown, indent each successive hierarchy level by one additional leading space. Render that hierarchy at two blank-space widths per level: `1)` at two spaces, `(1)` at four, `a.` at six, and `-` at eight. When an `a.` item needs a child item, use `-` as that child marker; do not restart a lower numbered or lettered sequence. Leave one blank ruled line between adjacent major `1)` sections; keep siblings at the same lower level consecutive.
- Do not add a mind map, textbook image, illustration, or decorative visual unless the user explicitly requests it.
- Ask for a clearer capture only when a heading, term, number, or factual relationship needed for the note cannot be read reliably. Otherwise proceed and visually verify both PDF versions before delivery.
## Defaults and choices

Use these defaults unless the user specifies otherwise: the sample-derived lined-paper canvas at 2716 by 3492 px / 400 DPI, pure black `학교안심 받아쓰기` L (about 11.5 pt for body text, with a one-render-pixel black stroke for clear tablet display) and B for headings, roughly 5.6 mm line spacing, and a PDF plus PNG pages. This fixed preset suits a 10-inch iPad; let overflow continue onto the next page rather than shrinking text. The original TTF files are bundled in the skill and are loaded from relative paths, so the same output works on macOS and Windows without installing a font. The layout has a warm off-white page, a wide unruled title area, a red left margin line, and light gray horizontal rules. Keep the entire unruled top area empty. A leading unstructured title is metadata only and is not printed, but a title beginning with a Roman chapter numeral such as `Ⅱ` is rendered below the blank area as a top-level heading using the same font. Treat `# Heading` and `Ⅱ` as top-level headings, and `1.` as the next heading level; preserve numbering such as `1)`, `(1)`, and `a.` as supplied.

For a class-display note, invoke `make_note.py` with `--slide --single-slide`. Render one 1920 by 1080 16:9 canvas at 2x resolution, with a persistent title bar and two lined note panels arranged side by side. Flow the note continuously from the left panel to the right panel; preserve the source hierarchy, hanging indents, and blank-line rules. Fit the complete note on that one screen by selecting the largest body type that prevents clipping.

For a numbered definition with an explanatory colon, such as `1) 정의의 일반적 의미: 설명`, keep the beginning of the explanation on the same ruled line. When it wraps, align every continuation line with the horizontal start position immediately after the colon. Apply this same hanging-indent rule to `(1)`, `a.`, and `-` definition labels. Do not change ordinary sentences merely because they contain a colon.

For a numbered item without a colon, such as `1) 긴 설명`, keep the first line as supplied. When it wraps, align each continuation line with the start of the text immediately after `1)`. Apply the same rule to `(1)`, `a.`, and `-` items.

Ask only when a missing choice materially affects the result. Otherwise proceed. A user's reference image controls visual style only; never transcribe its text as source content without confirmation.

Useful variations:

```bash
# Text in a file; creates biology-review.pdf and biology-review-page-01.png, etc.
python3 scripts/make_note.py --input /path/to/source.md --output-dir /path/to/output --name biology-review

# Direct short note with grid paper and dark ink.
python3 scripts/make_note.py --text '세포 호흡\n\n포도당은 ATP를 만드는 에너지원이다.' \
  --paper grid --ink-color '#1D3557' --output-dir /path/to/output --name cell-respiration

# Single 16:9 class-display slide
python3 scripts/make_note.py --input /path/to/source.md --slide --single-slide --output-dir /path/to/output --name class-display
```

## Style and optional illustrations

For a user's own handwriting sample, use it only as a visual reference and obtain an appropriate installed font or a user-supplied font file; preserve exact body text through `make_note.py`.

If the user explicitly wants a decorative diagram, sticker, or illustration, use the `imagegen` skill to create that raster asset. Inspect it, then place it in a reserved area without covering text. Do not add decoration by default.

Report the final PDF and PNG paths, paper/style choices, and any text that had to remain unrendered because the chosen font did not support it.
