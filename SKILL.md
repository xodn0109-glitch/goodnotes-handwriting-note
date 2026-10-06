---
name: goodnotes-handwriting-note
description: Create Goodnotes-ready study notes from local textbook PDFs, chat uploads, captures, or supplied text, including supplementation from multiple publishers around a primary textbook. For textbook note requests, save matched student and teacher summary PDFs in the working folder’s 생성된 노트 subfolder. Use for note-making, not editable word-processing documents.
---

# Goodnotes Handwriting Note

Use `scripts/make_note.py` to render Korean text deterministically with bundled `학교안심 받아쓰기` fonts. The outputs are raster PDFs for import into Goodnotes, with companion PNGs when requested; they are not editable text or native pen strokes. Do not use image generation to render Korean body text.

## Working-folder textbook workflow

When the user says “노트 만들어줘” for textbook material, accept either a local source in the working folder or a file/image uploaded in chat. “노트 만들기” is an example working-folder name, not a fixed directory to create or rename.

- Use the working folder explicitly selected by the user, otherwise the current project folder. Read the explicitly selected or newly uploaded source first. With no selected source, inspect the working folder for textbook PDFs, document originals, and captures; exclude `생성된 노트` and generated/temporary outputs. A single clear source can be used immediately. For a requested comparison across publishers, read [the multi-publisher workflow](references/multi-publisher-notes.md), confirm the user's primary textbook, and use the other supplied books to supplement its requested scope. Otherwise combine multiple files only when they clearly form the same requested unit; ask for the target only when the selection is ambiguous. Do not silently process every textbook in a folder.
- Read or parse the source before drafting. For PDF originals and captures, preserve tables, symbols, headings, numbering, comparisons, and factual relationships; extracted text alone does not verify a figure or equation. An available Korean-document parser may help; otherwise use the available PDF/document/image-reading workflow. Keep originals intact.
- Create `<working-folder>/생성된 노트/`. Deliver exactly two PDFs for each requested note set by default: `요약노트(학생용).pdf` and `요약노트(교사용).pdf`. The student version contains short curriculum-aligned concept blanks; the teacher version shows all answers. Use one complete draft so that removing `[[...]]` markers from the student draft reproduces the teacher text exactly.
- Keep the source’s actual unit/subunit structure and meaningful learning sequence visible in both versions. In multi-publisher mode, the primary textbook supplies this structure; other supplied books may provide relevant missing concepts, explanations, and examples with their sources identified. Use matching achievement standards to check concepts, relationships, and learning actions. Curriculum area numbers do not replace publisher unit numbers, and a textbook sequence does not establish a standard’s official area. Do not impose curriculum content absent from all supplied sources.
- Render both with `--pdf-only`. Keep working Markdown, mapping records, and QA images in a temporary workspace outside `생성된 노트`; they are not extra delivered files. Supply PNGs or editable sources only if requested. Student notes use the iPad lined-paper preset. Teacher notes retain the two-panel 16:9 class-display layout; if one slide cannot fit the complete draft readably, use multiple slide pages in the same teacher PDF.
- Preserve existing note sets. If the user has not authorized replacement, select the same next free revision suffix for both files, such as `요약노트(학생용)_v2.pdf` and `요약노트(교사용)_v2.pdf`. Honor explicitly requested topic stems, filenames, formats, layout, or a different destination.
- Inspect the saved PDFs and verify content parity before reporting completion. Return the two absolute PDF links and a brief note on the source/curriculum scope and any unresolved limitation.

## Choose the source mode

- **Supplied note text:** Preserve its wording and sequence. Markdown heading markers may establish hierarchy; do not silently summarize or impose the textbook numbering scheme on ordinary text.
- **Textbook content:** When a legible textbook-page capture is supplied in this note-making workflow, proceed without requiring separate transcription directions. Use the reconstruction rules below. An explicit request for verbatim transcription takes precedence.
- **Style reference:** Use a handwriting or paper sample only for visual style. Do not copy its words into the note unless the user also identifies it as content. A textbook content capture is not merely a style reference.

Keep the source and the working note draft separate. Resolve unreadable essential headings, terms, numbers, or factual relationships before using them; request a clearer capture only when that uncertainty prevents a faithful note. Preserve the user's requested scope, format, and destination.

## Reconstruct textbook content

교과서나 교재의 실제 대단원·소단원·주제 체계와 학습 순서를 필기노트의 기본 골격으로 삼는다. 교육과정의 해당 과목·영역·성취기준 체계는 핵심 개념과 학습 관계를 점검하는 기준으로 활용한다. 같은 주제 안에서는 개념 → 비교 기준 → 사상가·사례 → 적용의 흐름이 드러나도록 설명을 재구성할 수 있지만, 서로 다른 소단원을 임의로 합치거나 자료의 의미 있는 상하위 관계·번호를 지우지 않는다. 교과서의 페이지 배치나 문단을 그대로 복제할 필요는 없다.

- 사실, 개념, 분류, 비교 축, 인과 관계를 정확히 보존한다. 학습 목표에 직접 연결되는 본문·자료 상자·표·토론 자료는 하나의 흐름에 통합할 수 있다. 여러 출판사 보완 모드에서는 기준 교재에 없는 내용도 제공된 보완 교재에서 직접 확인하고 출처를 남긴 경우에 포함할 수 있다. 어떤 입력 자료에서도 확인되지 않는 사실·사례·결론을 만들어 추가하지 않는다.
- 설명문은 뜻이 유지되는 간결한 명사형으로 정리하고, 자연스러운 범위에서 한자어 개념 용어를 활용한다. 핵심 정보의 누락·왜곡 여부를 원문과 대조한다.
- 번호 체계는 `1.` → `1)` → `(1)` → `a.` → `-`로 구성한다. 내용의 학습 관계에 맞춰 상하위 항목을 설계하며, 포함한 부모와 자식 사이의 단계를 건너뛰지 않는다. 연속 노트의 첫 항목은 기존 순서에 따라 `2)`처럼 시작할 수 있으며, 생략된 상위 항목을 임의로 만들지 않는다.
- 대단원 표시는 원문에서 확인되는 경우에만 사용한다. `Ⅱ`는 2단원의 예시이며, 모든 노트에 붙이는 고정 표지가 아니다. 관련 노트와 수업용·복습용 사이의 번호는 일치시킨다.
- Markdown에서 각 하위 단계에 선행 공백을 하나씩 추가한다. 렌더러는 이를 단계당 두 칸으로 표시한다(`1)` 두 칸, `(1)` 네 칸, `a.` 여섯 칸, `-` 여덟 칸). `a.`의 자식은 `-`를 쓴다. 주요 `1)` 항목 사이에는 빈 줄 하나를 두고, 같은 하위 단계의 형제 항목은 연속 배치한다.

By default, a local or uploaded textbook source produces the two summary PDFs described in the working-folder workflow, from **one complete note draft**: student blanks on the iPad lined-paper preset and a teacher complete version in the two-panel 16:9 class-display layout. Make a separate copy of that draft for blank markers; remove only the markers to recover the complete draft. Preserve identical words, hierarchy, and order across the versions. Do not add mind maps, textbook images, illustrations, or decoration unless requested.

## Review blanks and curriculum alignment

Use `[[target]]` in the review copy to hide a short, assessable concept while retaining its layout width and adding a pale gray background. Do not add underlines, outlines, or placeholder symbols. Preserve all text outside the markers.

- Prefer technical terms, named classifications, and indispensable short noun phrases. Leave numbering, structural labels, verbs, linking words, and enough context to infer the answer visible.
- Keep recall practice light: usually about 10–20% of substantive body text, adjusted for concept density and age. Do not hide whole clauses or sentences by default.
- For confirmed **2022 revised middle- or high-school** content within the bundled local corpus, use [the curriculum alignment guide](references/2022-curriculum-alignment.md) and `scripts/query_curriculum.py`. The snapshot includes 2,887 standards (714 middle-school and 2,173 high-school) with original source files, explanations, and teaching/assessment context. Retrieve only the relevant school level, course, area, and standards; do not load the whole corpus into context.
- Align textbook-note emphasis and review blanks with both the concepts and the learning actions in the relevant standard (for example, comparison, explanation, inquiry, or application), using only material present in the source. A keyword blank alone does not establish achievement of a standard. Preserve explicitly supplied note text and verbatim-transcription requests; curriculum alignment does not authorize rewriting them or adding content.
- Do not infer the subject from a generic topic alone. The bundle covers the user's local middle/high-school materials, not every national course: high-school subjects in the local corpus, plus all middle-school courses supplied in the local corpus, including the eight living-foreign-language courses. For other subjects, another curriculum, or an uncertain match, use ordinary compact-concept blanks or an applicable user-supplied reference. Keep an inferred match provisional; do not invent standards or import another subject's labels.

## Titles and filenames

The working-folder workflow uses the two default filenames above. When a topic-based filename is explicitly requested and textbook notes have a known hierarchy, use `<대단원>-<주제>-<세부노트>_<제목>-<용도>`, for example `2-1-1_정의의-의미와-필요성-수업용` and `2-1-1_정의의-의미와-필요성-복습용`. Derive numbers from the supplied textbook scope and established note sequence. Curriculum areas help check scope but do not establish a publisher's lesson numbering. When the hierarchy is unknown or inapplicable, use a descriptive stem without invented numbers. Honor a requested filename.

Pass the full stem with `--name`; PNG pages share that stem. Place revision labels after the use label. Keep existing outputs unless replacement is authorized; use a new stem for a new version or `--overwrite` for an authorized replacement. Overwriting replaces that export set and removes obsolete numbered PNG pages; with `--pdf-only`, it removes that stem's old companion PNGs as well.

The renderer preserves the first body line by default. Use `--title` for metadata and the slide title bar; it does not remove source text. Only use `--first-line-title` when the first nonempty line is intentionally a metadata title that should not appear in the note body. To print a title on the paper, use a Markdown heading such as `# Heading` or a Unicode Roman chapter heading such as `Ⅲ 물과 지형`; ASCII `III` needs `# III …` for heading styling. Extremely long slide titles are shortened with an ellipsis in the header with a warning; the full title remains in PDF metadata.

## Layout and rendering

The default paper is 2716 × 3492 px at 400 DPI, sized for a 10-inch iPad, with warm off-white paper, a red margin, light gray rules at roughly 5.6 mm spacing, and an empty unruled top area. Body text is pure black `학교안심 받아쓰기` L at about 11.5 pt with a one-render-pixel stroke; headings use B. Fonts load relative to the skill directory and need no system installation. Let paper notes overflow to another page instead of shrinking text. `--paper grid` and `--paper plain` provide alternatives.

Class-display notes use `--slide`; use `--single-slide` when the complete note fits readably on one page: a 1920 × 1080 canvas rendered at 2× resolution, with a persistent title bar and two lined panels. Content flows left to right at the largest supported size that fits. `--single-slide` requires `--slide`. If the complete draft exceeds the readable single-slide capacity, use `--slide` without `--single-slide` for multiple pages in the same teacher PDF. Report a fit limitation only if readable multi-page rendering also fails; any scope reduction requires the user’s direction. Do not silently delete content or shrink below the supported minimum.

For numbered definitions with a colon, keep the start of the explanation on the same line and align wrapped lines immediately after the colon. For numbered items without a colon, align wrapped lines after the marker. These hanging indents apply to `1)`, `(1)`, `a.`, and `-`; an ordinary sentence containing a colon is not automatically a definition.

## Runtime and commands

Requires Python 3.10+ and Pillow; dependencies are listed in `requirements.txt`. Run from the skill directory, or use absolute paths to the script and requirements file. Prefer `--input` with a UTF-8 file for substantial notes.

```bash
# macOS/Linux: create an isolated runtime in the skill directory.
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Textbook workflow: drafts live in a temporary workspace, outputs in the project.
.venv/bin/python scripts/make_note.py --input /tmp/student-note.md \
  --pdf-only --output-dir '/path/to/노트 만들기/생성된 노트' --name '요약노트(학생용)'
.venv/bin/python scripts/make_note.py --input /tmp/teacher-note.md \
  --title '요약노트(교사용)' --slide --pdf-only \
  --output-dir '/path/to/노트 만들기/생성된 노트' --name '요약노트(교사용)'

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

Report the two PDF paths for textbook note sets, paper/style choices, and any remaining verification or rendering limitation. Report PNG paths only when PNG delivery was requested. For requested handwriting styles, use an appropriate font or a supplied font file. For explicitly requested decorative raster assets, use an available image-generation tool, inspect the asset, and keep it clear of text; decoration is outside the renderer's built-in layout.
