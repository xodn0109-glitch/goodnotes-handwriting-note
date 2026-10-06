---
name: goodnotes-handwriting-note
description: Create Goodnotes-ready handwriting-style study notes from supplied text or textbook-page captures, with PDF/PNG exports and optional review blanks. Use for note-making, not editable word-processing documents.
---

# Goodnotes Handwriting Note

Use `scripts/make_note.py` to render Korean text deterministically with bundled `학교안심 받아쓰기` fonts. The outputs are raster PDF pages and companion PNGs for import into Goodnotes, not editable text or native pen strokes. Do not use image generation to render Korean body text.

## Choose the source mode

- **Supplied note text:** Preserve its wording and sequence. Markdown heading markers may establish hierarchy; do not silently summarize or impose the textbook numbering scheme on ordinary text.
- **Textbook content:** When a legible textbook-page capture is supplied in this note-making workflow, proceed without requiring separate transcription directions. Use the reconstruction rules below. An explicit request for verbatim transcription takes precedence.
- **Style reference:** Use a handwriting or paper sample only for visual style. Do not copy its words into the note unless the user also identifies it as content. A textbook content capture is not merely a style reference.

Keep the source and the working note draft separate. Resolve unreadable essential headings, terms, numbers, or factual relationships before using them; request a clearer capture only when that uncertainty prevents a faithful note. Preserve the user's requested scope, format, and destination.

## Reconstruct textbook content

교과서나 교재는 개념·사례·인과 관계의 출처로 사용하되, 필기노트의 학습 구조는 새로 설계한다. 개념 → 비교 기준 → 사상가·사례 → 적용의 흐름은 해당 내용이 있을 때 활용한다. 교과서의 페이지 배치, 문단 순서, 소제목·번호를 그대로 복제할 필요는 없다.

- 사실, 개념, 분류, 비교 축, 인과 관계를 정확히 보존한다. 학습 목표에 직접 연결되는 본문·자료 상자·표·토론 자료는 하나의 흐름에 통합할 수 있다. 원문에 없는 사실·사례·결론을 추가하지 않는다.
- 설명문은 뜻이 유지되는 간결한 명사형으로 정리하고, 자연스러운 범위에서 한자어 개념 용어를 활용한다. 핵심 정보의 누락·왜곡 여부를 원문과 대조한다.
- 번호 체계는 `1.` → `1)` → `(1)` → `a.` → `-`로 구성한다. 내용의 학습 관계에 맞춰 상하위 항목을 설계하며, 포함한 부모와 자식 사이의 단계를 건너뛰지 않는다. 연속 노트의 첫 항목은 기존 순서에 따라 `2)`처럼 시작할 수 있으며, 생략된 상위 항목을 임의로 만들지 않는다.
- 대단원 표시는 원문에서 확인되는 경우에만 사용한다. `Ⅱ`는 2단원의 예시이며, 모든 노트에 붙이는 고정 표지가 아니다. 관련 노트와 수업용·복습용 사이의 번호는 일치시킨다.
- Markdown에서 각 하위 단계에 선행 공백을 하나씩 추가한다. 렌더러는 이를 단계당 두 칸으로 표시한다(`1)` 두 칸, `(1)` 네 칸, `a.` 여섯 칸, `-` 여덟 칸). `a.`의 자식은 `-`를 쓴다. 주요 `1)` 항목 사이에는 빈 줄 하나를 두고, 같은 하위 단계의 형제 항목은 연속 배치한다.

By default, a textbook capture produces two versions from **one complete note draft**: a student review PDF on the iPad lined-paper preset, and a class-display PDF with all answers visible on one 16:9 slide with two side-by-side note panels. Make a separate copy of that draft for blank markers; remove only the markers to recover the complete draft. Preserve identical words, hierarchy, and order across the versions. Do not add mind maps, textbook images, illustrations, or decoration unless requested.

## Review blanks and curriculum alignment

Use `[[target]]` in the review copy to hide a short, assessable concept while retaining its layout width and adding a pale gray background. Do not add underlines, outlines, or placeholder symbols. Preserve all text outside the markers.

- Prefer technical terms, named classifications, and indispensable short noun phrases. Leave numbering, structural labels, verbs, linking words, and enough context to infer the answer visible.
- Keep recall practice light: usually about 10–20% of substantive body text, adjusted for concept density and age. Do not hide whole clauses or sentences by default.
- For confirmed **2022 revised middle- or high-school** content within the bundled local corpus, use [the curriculum alignment guide](references/2022-curriculum-alignment.md) and `scripts/query_curriculum.py`. The snapshot includes 2,309 standards (136 middle-school and 2,173 high-school) with original source files, explanations, and teaching/assessment context. Retrieve only the relevant school level, course, area, and standards; do not load the whole corpus into context.
- Align textbook-note emphasis and review blanks with both the concepts and the learning actions in the relevant standard (for example, comparison, explanation, inquiry, or application), using only material present in the source. A keyword blank alone does not establish achievement of a standard. Preserve explicitly supplied note text and verbatim-transcription requests; curriculum alignment does not authorize rewriting them or adding content.
- Do not infer the subject from a generic topic alone. The bundle covers the user's local middle/high-school materials, not every national course: high-school subjects in the local corpus, plus middle-school social studies, history, and ethics. For other subjects, another curriculum, or an uncertain match, use ordinary compact-concept blanks or an applicable user-supplied reference. Keep an inferred match provisional; do not invent standards or import another subject's labels.

## Titles and filenames

For textbook notes with a known hierarchy, use `<대단원>-<주제>-<세부노트>_<제목>-<용도>`, for example `2-1-1_정의의-의미와-필요성-수업용` and `2-1-1_정의의-의미와-필요성-복습용`. Derive numbers from the supplied textbook scope and established note sequence. Curriculum areas help check scope but do not establish a publisher's lesson numbering. When the hierarchy is unknown or inapplicable, use a descriptive stem without invented numbers. Honor a requested filename.

Pass the full stem with `--name`; PNG pages share that stem. Place revision labels after the use label. Keep existing outputs unless replacement is authorized; use a new stem for a new version or `--overwrite` for an authorized replacement. Overwriting replaces that export set and removes obsolete numbered PNG pages; with `--pdf-only`, it removes that stem's old companion PNGs as well.

The renderer preserves the first body line by default. Use `--title` for metadata and the slide title bar; it does not remove source text. Only use `--first-line-title` when the first nonempty line is intentionally a metadata title that should not appear in the note body. To print a title on the paper, use a Markdown heading such as `# Heading` or a Unicode Roman chapter heading such as `Ⅲ 물과 지형`; ASCII `III` needs `# III …` for heading styling. Extremely long slide titles are shortened with an ellipsis in the header with a warning; the full title remains in PDF metadata.

## Layout and rendering

The default paper is 2716 × 3492 px at 400 DPI, sized for a 10-inch iPad, with warm off-white paper, a red margin, light gray rules at roughly 5.6 mm spacing, and an empty unruled top area. Body text is pure black `학교안심 받아쓰기` L at about 11.5 pt with a one-render-pixel stroke; headings use B. Fonts load relative to the skill directory and need no system installation. Let paper notes overflow to another page instead of shrinking text. `--paper grid` and `--paper plain` provide alternatives.

Class-display notes use `--slide --single-slide`: a 1920 × 1080 canvas rendered at 2× resolution, with a persistent title bar and two lined panels. Content flows left to right at the largest supported size that fits. `--single-slide` requires `--slide`. If the content exceeds supported readable sizes, preserve the complete draft and report the fit limitation; offer `--slide` for multiple slides or a user-directed scope reduction. Do not silently delete content or shrink below the supported minimum.

For numbered definitions with a colon, keep the start of the explanation on the same line and align wrapped lines immediately after the colon. For numbered items without a colon, align wrapped lines after the marker. These hanging indents apply to `1)`, `(1)`, `a.`, and `-`; an ordinary sentence containing a colon is not automatically a definition.

## Runtime and commands

Requires Python 3.10+ and Pillow; dependencies are listed in `requirements.txt`. Run from the skill directory, or use absolute paths to the script and requirements file. Prefer `--input` with a UTF-8 file for substantial notes.

```bash
# macOS/Linux: create an isolated runtime in the skill directory.
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Render a supplied note; its first body line remains visible.
.venv/bin/python scripts/make_note.py --input /path/to/source.md \
  --output-dir /path/to/output --name biology-review

# Direct text uses actual newlines, not literal backslash-n sequences.
.venv/bin/python scripts/make_note.py --text '# 세포 호흡

포도당은 ATP를 만드는 에너지원이다.' \
  --paper grid --output-dir /path/to/output --name cell-respiration

# Render the complete draft as one class-display slide.
.venv/bin/python scripts/make_note.py --input /path/to/complete-note.md \
  --title '수업용 필기노트' --slide --single-slide \
  --output-dir /path/to/output --name class-display
```

On Windows, create the environment with `py -3 -m venv .venv` and use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Use `--input` to avoid shell-specific multiline quoting. `--pdf-only` omits companion PNGs when requested.

## Verify and deliver

Use the available PDF skill's render-and-inspect workflow. If that skill is unavailable, render the saved PDF with an available PDF viewer or converter such as `pdftoppm` and inspect every page. Companion PNGs help inspect the layout, but do not by themselves verify the saved PDF. If PDF rendering is unavailable, report that verification limit rather than claiming full visual QA.

Check source fidelity, version parity, readable blanks, glyph support, hanging indents, margins, clipping, page breaks, and the complete two-panel slide. Fix layout failures before delivery; do not substitute or omit unsupported characters silently. Keep any unresolved text issue explicit.

Report the PDF and PNG paths, paper/style choices, and any remaining verification or rendering limitation. For requested handwriting styles, use an appropriate font or a supplied font file. For explicitly requested decorative raster assets, use an available image-generation tool, inspect the asset, and keep it clear of text; decoration is outside the renderer's built-in layout.
