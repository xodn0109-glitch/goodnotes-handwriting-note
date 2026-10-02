"""Regression tests for content preservation, fitting, and safe exports."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("make_note", ROOT / "scripts" / "make_note.py")
note = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(note)


class NoteRenderingTests(unittest.TestCase):
    def setUp(self):
        note.configure_canvas(False)
        self.font_path = note.find_font(None)
        self.font = note.load_font(self.font_path, 64)
        self.draw = ImageDraw.Draw(Image.new("RGB", (300, 300)))

    def test_short_single_slide_keeps_all_lines_and_allows_empty_right_panel(self):
        source = "Ⅱ 단원\n1. 주제\n 1) 개념\n  (1) 내용"
        pages = note.render_pages(source, "sample", self.font_path, "black", True, True)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].size, (3840, 2160))
        lines = [("body", "본문", 0)]
        self.assertEqual(note.divide_across_panels(lines, 100, 50), [(0, 1), (1, 1)])

    def test_dense_single_slide_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too dense"):
            note.render_pages("\n".join(["본문 내용"] * 100), "sample", self.font_path, "black", True, True)

    def test_panel_breaks_cover_input_exactly_once(self):
        lines = [("body", str(index), 0) for index in range(6)]
        breaks = note.divide_across_panels(lines, 150, 50)
        self.assertEqual(breaks, [(0, 3), (3, 6)])
        self.assertEqual([index for start, end in breaks for index in range(start, end)], list(range(6)))

    def test_heading_chain_keeps_first_numbered_section_and_child(self):
        lines = [("body", "본문", 0)] * 2 + [
            ("heading1", "Ⅲ 단원", 0),
            ("heading2", "1. 주제", 0),
            ("body", "1) 항목", 0),
            ("body", "(1) 설명", 0),
        ]
        self.assertEqual(note.divide_across_panels(lines, 60, 10), [(0, 2), (2, 6)])

    def test_paper_keeps_major_numbered_item_with_child(self):
        capacity = (note.PAGE_HEIGHT - note.MARGIN_BOTTOM - note.MARGIN_TOP) // note.RULE_GAP
        source = "\n".join(["본문"] * (capacity - 1) + ["1) 주요 개념", "  (1) 설명"])
        with patch.object(note, "draw_line", wraps=note.draw_line) as draw_line:
            pages = note.render_pages(source, "plain", self.font_path, "black")
        self.assertEqual(len(pages), 2)
        parent_call = next(call for call in draw_line.call_args_list if "1) 주요 개념" in call.args[2])
        self.assertEqual(parent_call.args[1][1], note.MARGIN_TOP)

    def test_heading_chain_stays_with_following_content(self):
        lines = [("body", "본문", 0), ("heading1", "단원", 0), ("heading2", "주제", 0), ("blank", "", 0), ("body", "내용", 0)]
        self.assertEqual(note.divide_across_panels(lines, 250, 50), [(0, 1), (1, 5)])

    def test_low_height_heading_does_not_crash_in_either_layout(self):
        for slide in (False, True):
            with self.subTest(slide=slide):
                pages = note.render_pages("# ...\n본문", "plain", self.font_path, "black", slide, slide)
                self.assertEqual(len(pages), 1)

    def test_numbered_colon_inside_blank_stays_balanced(self):
        source = "1) [[핵심: 용어]] 설명"
        pages = note.render_pages(source, "plain", self.font_path, "black")
        self.assertEqual(len(pages), 1)
        self.assertIsNone(note.definition_prefix_and_detail("body", source))

    def test_blank_markers_reject_nesting_and_unmatched_delimiters(self):
        for source in ("[[안쪽 [[중첩]] 바깥]]", "미완성 [[내용", "내용]]"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                note.blank_tokens(source)

    def test_wrapping_keeps_blank_character_states(self):
        source = "보이는[[감추는한국어개념]]부분"
        lines = note.split_to_width(self.draw, source, self.font, 180)
        self.assertGreater(len(lines), 1)
        self.assertEqual([token for line in lines for token in note.blank_tokens(line)], note.blank_tokens(source))

    def test_blank_run_uses_kerned_position(self):
        with patch.object(self.draw, "text", wraps=self.draw.text) as draw_text:
            note.draw_marked_text(self.draw, (10, 100), "A[[V]]", self.font, "black", 0)
        expected = 10 + round(self.draw.textlength("AV", font=self.font) - self.draw.textlength("V", font=self.font))
        self.assertEqual(draw_text.call_args_list[1].args[0][0], expected)
        # Pillow's Windows wheel may use BASIC without RAQM kerning. Both
        # engines must follow their actual metrics; only RAQM shifts this pair.
        if self.font.layout_engine == ImageFont.Layout.RAQM:
            self.assertNotEqual(expected, 10 + round(self.draw.textlength("A", font=self.font)))

    def test_hanging_prefix_does_not_leave_less_than_a_character(self):
        prefix, detail = "1) 매우 긴 이름: ", "가나다라마바사"
        width = round(self.draw.textlength(prefix, font=self.font)) + 5
        lines = note.split_hanging_to_width(self.draw, prefix, detail, self.font, width)
        self.assertGreater(len(lines), 1)
        for content, indent in lines:
            self.assertEqual(indent, 0)
            self.assertLessEqual(self.draw.textbbox((0, 0), note.visible_text(content), font=self.font)[2], width)

    def test_long_slide_title_fits_reserved_header_width(self):
        title, font = note.fit_header_text(self.draw, "아주 긴 제목 " * 200, self.font, 300)
        self.assertTrue(title.endswith("…"))
        self.assertLessEqual(self.draw.textbbox((0, 0), title, font=font)[2], 300)
        short_title, short_font = note.fit_header_text(self.draw, "짧은 제목", self.font, 300)
        self.assertEqual(short_title, "짧은 제목")
        self.assertEqual(short_font.size, self.font.size)

    def test_empty_visible_input_is_rejected(self):
        for source in ("", " \n\t", "[[]]"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "empty"):
                note.render_pages(source, "plain", self.font_path, "black")

    def test_single_slide_requires_slide_mode(self):
        with self.assertRaisesRegex(ValueError, "requires"):
            note.render_pages("내용", "plain", self.font_path, "black", single_slide=True)
        with patch("sys.argv", ["make_note.py", "--text", "내용", "--single-slide", "--output-dir", "/tmp/unused"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                note.parse_args()
        self.assertEqual(caught.exception.code, 2)


class NoteExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.page = Image.new("RGB", (20, 20), "white")

    def run_main(self, extra, *, mock_render=True):
        argv = ["make_note.py", "--output-dir", str(self.output), "--name", "note", *extra]
        with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
            if mock_render:
                with patch.object(note, "render_pages", return_value=[self.page]) as render:
                    note.main()
                    return render.call_args
            return note.main()

    def test_first_body_line_is_preserved_by_default(self):
        call = self.run_main(["--text", "본문 첫 줄\n본문 둘째 줄", "--title", "메타데이터 제목"])
        self.assertEqual(call.args[0], "본문 첫 줄\n본문 둘째 줄")
        self.assertEqual(call.args[-1], "메타데이터 제목")

    def test_legacy_title_removal_requires_explicit_option(self):
        call = self.run_main(["--text", "제목\n본문", "--first-line-title"])
        self.assertEqual(call.args[0], "본문")
        self.assertEqual(call.args[-1], "제목")

    def test_consuming_title_only_input_does_not_export_blank_page(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            self.run_main(["--text", "제목", "--first-line-title"], mock_render=False)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_utf8_bom_input_preserves_heading(self):
        source = self.output / "source.md"
        source.write_text("Ⅱ 단원\n본문", encoding="utf-8-sig")
        call = self.run_main(["--input", str(source)])
        self.assertEqual(call.args[0], "Ⅱ 단원\n본문")

    def test_preflight_protects_even_stale_companion_png(self):
        old = self.output / "note-page-99.png"
        old.write_bytes(b"old content")
        with patch.object(note, "render_pages") as render, self.assertRaises(FileExistsError):
            self.run_main(["--text", "내용"], mock_render=False)
        render.assert_not_called()
        self.assertEqual(old.read_bytes(), b"old content")
        self.assertFalse((self.output / "note.pdf").exists())

    def test_overwrite_removes_only_exact_stem_numbered_pngs(self):
        stem = "note[1]"
        stale = self.output / f"{stem}-page-99.png"
        stale.write_bytes(b"old")
        protected = [self.output / name for name in ("note1-page-99.png", "note[1]-page-draft.png", "note[1]-page-99.png.bak", "note[1]-other.png")]
        for path in protected:
            path.write_bytes(b"keep")
        note.export_pages([self.page], self.output, stem, "title", False, True)
        self.assertFalse(stale.exists())
        self.assertTrue((self.output / f"{stem}-page-01.png").exists())
        self.assertTrue((self.output / f"{stem}.pdf").read_bytes().startswith(b"%PDF"))
        self.assertTrue(all(path.read_bytes() == b"keep" for path in protected))

    def test_failed_encoder_preserves_all_previous_exports(self):
        old_pdf = self.output / "note.pdf"
        stale = self.output / "note-page-99.png"
        old_pdf.write_bytes(b"previous PDF")
        stale.write_bytes(b"previous PNG")
        original_save = Image.Image.save

        def fail_png(image, path, format=None, **kwargs):
            if format == "PNG":
                raise OSError("encoder failure")
            return original_save(image, path, format, **kwargs)

        with patch.object(Image.Image, "save", fail_png), self.assertRaisesRegex(OSError, "encoder failure"):
            note.export_pages([self.page], self.output, "note", "title", False, True)
        self.assertEqual(old_pdf.read_bytes(), b"previous PDF")
        self.assertEqual(stale.read_bytes(), b"previous PNG")
        self.assertEqual(sorted(path.name for path in self.output.iterdir()), ["note-page-99.png", "note.pdf"])

    def test_pdf_only_overwrite_removes_old_companions(self):
        old = self.output / "note-page-01.png"
        old.write_bytes(b"old")
        note.export_pages([self.page], self.output, "note", "title", True, True)
        self.assertFalse(old.exists())
        self.assertTrue((self.output / "note.pdf").exists())

    def test_source_file_cannot_be_replaced_by_export(self):
        source = self.output / "note.pdf"
        source.write_text("source text", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "input source"):
            self.run_main(["--input", str(source), "--overwrite"])
        self.assertEqual(source.read_text(), "source text")


if __name__ == "__main__":
    unittest.main()
