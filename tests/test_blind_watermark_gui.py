from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from blind_watermark_service import BlindWatermarkOptions
from config import (
    COMPREHENSIVE_FEATURE_DEFAULTS,
    DEFAULT_BLIND_WATERMARK_CONTENT_KEY,
    DEFAULT_BLIND_WATERMARK_IMAGE_KEY,
    FEATURE_DEFAULTS,
    STATUS_CANCELED,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from gui import (
    BlindWatermarkExtractionTask,
    BlindWatermarkExtractionWorker,
    ImageListItem,
    ImageOperationPage,
    ImageToolWindow,
    MODE_BLIND_WATERMARK,
    MODE_COMPREHENSIVE,
    ProcessingTask,
    ProcessingWorker,
)


class BlindWatermarkGuiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def process_events(self, cycles: int = 5) -> None:
        for _ in range(cycles):
            self.app.processEvents()

    def close_page(self, page: ImageOperationPage) -> None:
        page.shutdown()
        page.close()
        page.deleteLater()
        self.process_events()

    def make_page(self, mode: str) -> ImageOperationPage:
        page = ImageOperationPage("test", mode, f"{mode}BlindWatermarkTest")
        page.resize(1100, 780)
        page.show()
        self.process_events()
        return page

    def add_item(self, page: ImageOperationPage, source: Path) -> None:
        item = ImageListItem(source, source.suffix.lstrip(".").upper(), "100 × 100", "1KB")
        page.items.append(item)
        page._append_table_row(item)

    def test_independent_and_comprehensive_defaults_expose_separate_hidden_entry_points(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = QSettings(str(Path(temp_dir) / "settings.ini"), QSettings.IniFormat)
            window = ImageToolWindow(settings=settings)
            window.resize(1220, 820)
            window.show()
            self.process_events()
            try:
                self.assertFalse(FEATURE_DEFAULTS[MODE_BLIND_WATERMARK])
                self.assertFalse(COMPREHENSIVE_FEATURE_DEFAULTS[MODE_BLIND_WATERMARK])
                self.assertFalse(window.feature_states[MODE_BLIND_WATERMARK])
                self.assertFalse(window.comprehensive_feature_states[MODE_BLIND_WATERMARK])
                self.assertTrue(window.feature_nav_items[MODE_BLIND_WATERMARK].isHidden())
                self.assertTrue(
                    window.comprehensive_page.feature_sections[
                        MODE_BLIND_WATERMARK
                    ].isHidden()
                )

                page_switch = window.settings_page.feature_switches[MODE_BLIND_WATERMARK]
                comprehensive_switch = (
                    window.settings_page.comprehensive_feature_switches[
                        MODE_BLIND_WATERMARK
                    ]
                )
                self.assertFalse(page_switch.isChecked())
                self.assertFalse(comprehensive_switch.isChecked())

                page_switch.setChecked(True)
                self.process_events()
                self.assertFalse(window.feature_nav_items[MODE_BLIND_WATERMARK].isHidden())
                self.assertTrue(
                    window.comprehensive_page.feature_sections[
                        MODE_BLIND_WATERMARK
                    ].isHidden()
                )

                comprehensive_switch.setChecked(True)
                self.process_events()
                self.assertFalse(
                    window.comprehensive_page.feature_sections[
                        MODE_BLIND_WATERMARK
                    ].isHidden()
                )
            finally:
                window.close()
                window.deleteLater()
                self.process_events()

    def test_independent_page_switches_between_embed_and_extract_states(self) -> None:
        page = self.make_page(MODE_BLIND_WATERMARK)
        try:
            self.assertTrue(page.blind_watermark_embed_radio.isChecked())
            self.assertFalse(page.blind_watermark_extract_radio.isChecked())
            self.assertEqual(page.start_button.text(), "开始嵌入")
            self.assertTrue(page.output_card.isVisible())
            self.assertTrue(page.save_card.isVisible())
            self.assertTrue(page.open_location_button.isVisible())
            self.assertTrue(page.blind_watermark_text_container.isVisible())
            self.assertFalse(page.blind_watermark_extract_container.isVisible())
            self.assertFalse(page.blind_watermark_result_container.isVisible())
            self.assertTrue(page.blind_watermark_text_edit.isEnabled())

            page.blind_watermark_extract_radio.setChecked(True)
            self.process_events()
            self.assertEqual(page.start_button.text(), "开始提取")
            self.assertFalse(page.output_card.isVisible())
            self.assertFalse(page.save_card.isVisible())
            self.assertFalse(page.open_location_button.isVisible())
            self.assertFalse(page.blind_watermark_text_container.isVisible())
            self.assertTrue(page.blind_watermark_extract_container.isVisible())
            self.assertTrue(page.blind_watermark_result_container.isVisible())
            self.assertTrue(page.blind_watermark_bit_length_edit.isEnabled())
            self.assertTrue(page.blind_watermark_image_key_edit.isEnabled())
            self.assertTrue(page.blind_watermark_content_key_edit.isEnabled())

            page._set_processing_state(True)
            for control in (
                page.blind_watermark_embed_radio,
                page.blind_watermark_extract_radio,
                page.blind_watermark_bit_length_edit,
                page.blind_watermark_image_key_edit,
                page.blind_watermark_content_key_edit,
            ):
                self.assertFalse(control.isEnabled())
            page._set_processing_state(False)
            self.assertTrue(page.blind_watermark_extract_radio.isEnabled())
            self.assertTrue(page.blind_watermark_bit_length_edit.isEnabled())
        finally:
            self.close_page(page)

    def test_comprehensive_page_supports_embed_only_and_builds_options_when_checked(self) -> None:
        page = self.make_page(MODE_COMPREHENSIVE)
        try:
            self.assertTrue(hasattr(page, "blind_watermark_checkbox"))
            self.assertFalse(hasattr(page, "blind_watermark_embed_radio"))
            self.assertFalse(hasattr(page, "blind_watermark_extract_radio"))
            self.assertFalse(hasattr(page, "blind_watermark_result_container"))
            self.assertFalse(page.blind_watermark_extract_container.isVisible())

            options, error = page._get_blind_watermark_options()
            self.assertIsNone(options)
            self.assertIsNone(error)

            page.blind_watermark_checkbox.setChecked(True)
            page.blind_watermark_text_edit.setText("订单-A17")
            page.blind_watermark_image_key_edit.setText("31415")
            page.blind_watermark_content_key_edit.setText("27182")
            options, error = page._get_blind_watermark_options()
            self.assertIsNone(error)
            self.assertEqual(
                options,
                BlindWatermarkOptions(
                    text="订单-A17",
                    password_image=31415,
                    password_watermark=27182,
                ),
            )
        finally:
            self.close_page(page)

    def test_extraction_worker_reports_batch_success_and_failure_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sources = [root / "one.png", root / "two.png", root / "three.png"]
            for source in sources:
                source.write_bytes(b"source")
            tasks = [
                BlindWatermarkExtractionTask(index, source)
                for index, source in enumerate(sources)
            ]
            worker = BlindWatermarkExtractionWorker(
                tasks,
                bit_length=248,
                password_image=11,
                password_watermark=22,
            )
            extracted: list[tuple[int, str]] = []
            statuses: list[tuple[int, str]] = []
            finished: list[tuple[object, ...]] = []
            worker.extracted.connect(lambda row, text: extracted.append((row, text)))
            worker.item_finished.connect(lambda row, status: statuses.append((row, status)))
            worker.finished.connect(lambda *args: finished.append(args))

            def fake_extract(path: Path, **kwargs) -> str:
                self.assertEqual(
                    kwargs,
                    {
                        "bit_length": 248,
                        "password_image": 11,
                        "password_watermark": 22,
                    },
                )
                if Path(path).name == "two.png":
                    raise RuntimeError("密钥不匹配")
                return f"result-{Path(path).stem}"

            with patch("gui.extract_blind_watermark", side_effect=fake_extract) as extract:
                worker.run()

            self.assertEqual(extract.call_count, 3)
            self.assertEqual(extracted, [(0, "result-one"), (2, "result-three")])
            self.assertEqual(statuses[0], (0, STATUS_SUCCESS))
            self.assertEqual(statuses[2], (2, STATUS_SUCCESS))
            self.assertEqual(statuses[1][0], 1)
            self.assertTrue(statuses[1][1].startswith(f"{STATUS_FAILED}："))
            self.assertIn("密钥不匹配", statuses[1][1])
            self.assertEqual(finished, [(3, 2, 1, None, False)])
            self.assertFalse(hasattr(worker, "output_committed"))
            self.assertEqual(sorted(path.name for path in root.iterdir()), [
                "one.png",
                "three.png",
                "two.png",
            ])

    def test_extraction_worker_cancellation_marks_remaining_items_and_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sources = [root / f"{index}.png" for index in range(3)]
            for source in sources:
                source.write_bytes(b"unchanged")
            worker = BlindWatermarkExtractionWorker(
                [
                    BlindWatermarkExtractionTask(index, source)
                    for index, source in enumerate(sources)
                ],
                bit_length=112,
                password_image=1,
                password_watermark=2,
            )
            statuses: list[tuple[int, str]] = []
            finished: list[tuple[object, ...]] = []
            worker.item_finished.connect(lambda row, status: statuses.append((row, status)))
            worker.finished.connect(lambda *args: finished.append(args))

            def cancel_after_first(*_args, **_kwargs) -> str:
                worker.request_cancel()
                return "A"

            with patch("gui.extract_blind_watermark", side_effect=cancel_after_first) as extract:
                worker.run()

            extract.assert_called_once()
            self.assertEqual(
                statuses,
                [(0, STATUS_SUCCESS), (1, STATUS_CANCELED), (2, STATUS_CANCELED)],
            )
            self.assertEqual(finished, [(3, 1, 0, None, True)])
            self.assertEqual(
                {path.name: path.read_bytes() for path in root.iterdir()},
                {source.name: b"unchanged" for source in sources},
            )

    def test_extraction_worker_honors_cancellation_before_first_item(self) -> None:
        worker = BlindWatermarkExtractionWorker(
            [BlindWatermarkExtractionTask(0, Path("source.png"))],
            bit_length=112,
            password_image=1,
            password_watermark=2,
        )
        statuses: list[tuple[int, str]] = []
        finished: list[tuple[object, ...]] = []
        worker.item_finished.connect(lambda row, status: statuses.append((row, status)))
        worker.finished.connect(lambda *args: finished.append(args))
        worker.request_cancel()

        with patch("gui.extract_blind_watermark") as extract:
            worker.run()

        extract.assert_not_called()
        self.assertEqual(statuses, [(0, STATUS_CANCELED)])
        self.assertEqual(finished, [(1, 0, 0, None, True)])

    def test_start_processing_extract_branch_bypasses_normal_settings_and_tasks(self) -> None:
        page = self.make_page(MODE_BLIND_WATERMARK)
        try:
            self.add_item(page, Path("source.png"))
            page.blind_watermark_extract_radio.setChecked(True)
            with (
                patch.object(page, "_start_blind_watermark_extraction") as start_extract,
                patch.object(page, "_get_page_settings") as get_settings,
                patch.object(page, "_prepare_tasks") as prepare_tasks,
            ):
                page._start_processing()
            start_extract.assert_called_once_with()
            get_settings.assert_not_called()
            prepare_tasks.assert_not_called()
        finally:
            self.close_page(page)

    def test_extracted_result_follows_selection_and_can_be_copied(self) -> None:
        page = self.make_page(MODE_BLIND_WATERMARK)
        try:
            self.add_item(page, Path("first.png"))
            self.add_item(page, Path("second.png"))
            page.blind_watermark_extract_radio.setChecked(True)
            page.table.selectRow(1)
            self.process_events()

            page._on_blind_watermark_extracted(1, "TRACE-2026-中文")
            self.assertEqual(
                page.blind_watermark_result_edit.toPlainText(),
                "TRACE-2026-中文",
            )
            self.assertTrue(page.blind_watermark_copy_result_button.isEnabled())
            with patch.object(page, "_show_message") as show_message:
                page._copy_blind_watermark_result()
            self.assertEqual(QApplication.clipboard().text(), "TRACE-2026-中文")
            show_message.assert_called_once_with("success", "提取结果已复制")

            page.table.selectRow(0)
            self.process_events()
            page._update_blind_watermark_result_view()
            self.assertEqual(page.blind_watermark_result_edit.toPlainText(), "")
            self.assertFalse(page.blind_watermark_copy_result_button.isEnabled())
        finally:
            self.close_page(page)

    def test_starting_a_new_extraction_clears_stale_result_tooltips(self) -> None:
        page = self.make_page(MODE_BLIND_WATERMARK)
        try:
            self.add_item(page, Path("source.png"))
            page.blind_watermark_extract_radio.setChecked(True)
            status_item = page.table.item(0, 5)
            status_item.setToolTip("旧提取结果")
            with (
                patch.object(
                    page,
                    "_get_blind_watermark_extraction_parameters",
                    return_value=((248, 1, 2), None),
                ),
                patch.object(page, "_set_processing_state"),
                patch("gui.QThread") as thread_class,
                patch("gui.BlindWatermarkExtractionWorker"),
            ):
                thread_class.return_value.started.connect = lambda *_: None
                thread_class.return_value.finished.connect = lambda *_: None
                thread_class.return_value.start = lambda: None
                page._start_blind_watermark_extraction()
            self.assertEqual(status_item.toolTip(), "")
        finally:
            self.close_page(page)

    def test_processing_worker_forwards_blind_watermark_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            output = root / "output.jpg"
            source.write_bytes(b"source bytes")
            task = ProcessingTask(
                row=0,
                source_path=source,
                output_path=output,
                output_format="JPEG",
                apply_logo=False,
                logo_assets=[],
            )
            blind_options = BlindWatermarkOptions(
                text="TRACE-42",
                password_image=DEFAULT_BLIND_WATERMARK_IMAGE_KEY,
                password_watermark=DEFAULT_BLIND_WATERMARK_CONTENT_KEY,
            )
            worker = ProcessingWorker(
                tasks=[task],
                output_size=None,
                quality=95,
                logo_cache={},
                watermark_options=None,
                reference_notice_options=None,
                blind_watermark_options=blind_options,
            )
            statuses: list[tuple[int, str]] = []
            committed: list[object] = []
            worker.item_finished.connect(lambda row, status: statuses.append((row, status)))
            worker.output_committed.connect(committed.append)

            def fake_process(source_path: Path, output_path: Path, options) -> object:
                self.assertEqual(Path(source_path), source)
                self.assertEqual(Path(output_path), output)
                self.assertIs(options.blind_watermark_options, blind_options)
                output.write_bytes(b"processed")
                return SimpleNamespace(output_path=output, output_size=9)

            with patch("gui.process_image", side_effect=fake_process) as process:
                worker.run()

            process.assert_called_once()
            self.assertEqual(statuses, [(0, STATUS_SUCCESS)])
            self.assertEqual(len(committed), 1)
            self.assertEqual(committed[0].source_bytes, len(b"source bytes"))
            self.assertEqual(committed[0].output_bytes, len(b"processed"))


if __name__ == "__main__":
    unittest.main()
