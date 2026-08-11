from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QAbstractButton, QApplication

from config import (
    REFERENCE_NOTICE_FONT_RELATIVE_PATH,
    STATUS_CANCELED,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from gui import (
    ImageOperationPage,
    ImageToolWindow,
    MODE_COMPREHENSIVE,
    ProcessedOutput,
    ProcessingStatistics,
    ProcessingTask,
    ProcessingWorker,
    STATISTICS_OUTPUT_BYTES_KEY,
    STATISTICS_PROCESSED_COUNT_KEY,
    STATISTICS_SOURCE_BYTES_KEY,
    load_processing_statistics,
    resource_path,
)
from image_processor import ReferenceNoticeOptions


class TrackingSettings(QSettings):
    """QSettings backend that records every explicit durability flush."""

    def __init__(self, path: Path) -> None:
        super().__init__(str(path), QSettings.IniFormat)
        self.sync_calls = 0

    def sync(self) -> None:
        self.sync_calls += 1
        super().sync()


class StatisticsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def process_events(self, cycles: int = 6) -> None:
        for _ in range(cycles):
            self.app.processEvents()

    def close_window(self, window: ImageToolWindow) -> None:
        window.close()
        window.deleteLater()
        self.process_events()

    def test_all_operation_pages_accumulate_sync_each_output_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "statistics.ini"
            settings = TrackingSettings(settings_path)
            window = ImageToolWindow(settings=settings)
            window.show()
            self.process_events()

            outputs = [
                ProcessedOutput(1_500, 500),
                ProcessedOutput(2_000, 2_500),
                ProcessedOutput(3_000_000_000, 1_000_000_000),
                ProcessedOutput(4_000, 1_000),
                ProcessedOutput(5_000, 2_000),
                ProcessedOutput(6_000, 3_000),
                ProcessedOutput(7_000, 4_000),
            ]
            expected_source = 0
            expected_output = 0
            baseline_sync_calls = settings.sync_calls

            try:
                self.assertEqual(len(window.operation_pages), 7)
                for index, (page, output) in enumerate(
                    zip(window.operation_pages, outputs, strict=True),
                    start=1,
                ):
                    page.output_committed.emit(output)
                    self.process_events()
                    expected_source += output.source_bytes
                    expected_output += output.output_bytes

                    self.assertEqual(window.processing_statistics.processed_count, index)
                    self.assertEqual(window.processing_statistics.source_bytes, expected_source)
                    self.assertEqual(window.processing_statistics.output_bytes, expected_output)
                    self.assertEqual(
                        str(settings.value(STATISTICS_PROCESSED_COUNT_KEY)),
                        str(index),
                    )
                    self.assertEqual(
                        str(settings.value(STATISTICS_SOURCE_BYTES_KEY)),
                        str(expected_source),
                    )
                    self.assertEqual(
                        str(settings.value(STATISTICS_OUTPUT_BYTES_KEY)),
                        str(expected_output),
                    )
                    self.assertEqual(settings.sync_calls, baseline_sync_calls + index)
                    self.assertEqual(
                        window.comprehensive_page.statistics_count_label.text(),
                        f"{index:,} 张",
                    )
            finally:
                self.close_window(window)

            restored_settings = QSettings(str(settings_path), QSettings.IniFormat)
            restored_window = ImageToolWindow(settings=restored_settings)
            restored_window.show()
            self.process_events()
            try:
                self.assertEqual(
                    restored_window.processing_statistics,
                    ProcessingStatistics(7, expected_source, expected_output),
                )
                self.assertEqual(
                    restored_window.comprehensive_page.statistics_count_label.text(),
                    "7 张",
                )
                self.assertEqual(
                    restored_window.comprehensive_page.statistics_space_caption.text(),
                    "累计净节省空间",
                )
                self.assertEqual(
                    restored_window.comprehensive_page.statistics_space_label.text(),
                    "2GB",
                )
            finally:
                self.close_window(restored_window)

    def test_statistics_copy_distinguishes_net_savings_and_growth(self) -> None:
        page = ImageOperationPage("综合处理", MODE_COMPREHENSIVE, "statisticsCopyTest")
        try:
            page.set_processing_statistics(ProcessingStatistics(2, 1_500, 500))
            self.assertEqual(page.statistics_count_label.text(), "2 张")
            self.assertEqual(page.statistics_space_caption.text(), "累计净节省空间")
            self.assertEqual(page.statistics_space_label.text(), "1KB")

            page.set_processing_statistics(ProcessingStatistics(3, 500, 1_500))
            self.assertEqual(page.statistics_count_label.text(), "3 张")
            self.assertEqual(page.statistics_space_caption.text(), "累计净增加空间")
            self.assertEqual(page.statistics_space_label.text(), "1KB")
            self.assertNotIn("节省", page.statistics_space_caption.text())
        finally:
            page.shutdown()
            page.close()
            page.deleteLater()
            self.process_events()

    def test_invalid_or_negative_settings_load_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "invalid-statistics.ini"
            settings = QSettings(str(settings_path), QSettings.IniFormat)
            settings.setValue(STATISTICS_PROCESSED_COUNT_KEY, "not-a-number")
            settings.setValue(STATISTICS_SOURCE_BYTES_KEY, "-100")
            settings.setValue(STATISTICS_OUTPUT_BYTES_KEY, "")
            settings.sync()

            self.assertEqual(load_processing_statistics(settings), ProcessingStatistics())

            window = ImageToolWindow(
                settings=QSettings(str(settings_path), QSettings.IniFormat)
            )
            try:
                self.assertEqual(window.processing_statistics, ProcessingStatistics())
                self.assertEqual(window.comprehensive_page.statistics_count_label.text(), "0 张")
                self.assertEqual(window.comprehensive_page.statistics_space_label.text(), "0B")
            finally:
                self.close_window(window)

    def test_statistics_card_is_at_top_of_comprehensive_page_without_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window = ImageToolWindow(
                settings=QSettings(
                    str(Path(temp_dir) / "statistics-layout.ini"),
                    QSettings.IniFormat,
                )
            )
            try:
                page = window.comprehensive_page
                layout = page.container.layout()
                self.assertIs(layout.itemAt(0).widget(), page.findChild(type(page.statistics_count_label), "TitleLabel"))
                self.assertEqual(layout.indexOf(page.statistics_card), 1)
                self.assertEqual(layout.indexOf(page.list_card), 2)
                self.assertLess(
                    layout.indexOf(page.statistics_card),
                    layout.indexOf(page.list_card),
                )
                self.assertEqual(page.statistics_card.findChildren(QAbstractButton), [])
                for other_page in window.operation_pages[1:]:
                    self.assertIsNone(other_page.statistics_card)
            finally:
                self.close_window(window)

    def test_worker_reports_actual_sizes_for_successful_outputs_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_sizes = [11, 22, 33, 44]
            tasks: list[ProcessingTask] = []
            for row, source_size in enumerate(source_sizes):
                source_path = root / f"source-{row}.jpg"
                source_path.write_bytes(bytes([row + 1]) * source_size)
                tasks.append(
                    ProcessingTask(
                        row=row,
                        source_path=source_path,
                        output_path=root / f"output-{row}.jpg",
                        output_format="JPG",
                        apply_logo=False,
                        logo_assets=[],
                    )
                )

            reference_notice_options = ReferenceNoticeOptions(
                text="图片仅供参考",
                font_path=resource_path(REFERENCE_NOTICE_FONT_RELATIVE_PATH),
                font_size=0,
                background_opacity=65,
            )
            worker = ProcessingWorker(
                tasks=tasks,
                output_size=None,
                quality=95,
                logo_cache={},
                watermark_options=None,
                reference_notice_options=reference_notice_options,
            )
            committed: list[ProcessedOutput] = []
            statuses: list[tuple[int, str]] = []
            finished: list[tuple[object, ...]] = []
            worker.output_committed.connect(committed.append)

            def handle_finished(row: int, status: str) -> None:
                statuses.append((row, status))
                if row == 2:
                    worker.request_cancel()

            worker.item_finished.connect(handle_finished)
            worker.finished.connect(lambda *args: finished.append(args))

            def fake_process(source_path: Path, output_path: Path, _options: object) -> object:
                row = int(Path(source_path).stem.rsplit("-", 1)[1])
                output_path = Path(output_path)
                if row == 0:
                    output_path.write_bytes(b"a" * 4)
                    return SimpleNamespace(
                        output_path=output_path,
                        output_size=999,
                    )
                if row == 1:
                    output_path.write_bytes(b"b" * 30)
                    return SimpleNamespace(
                        output_path=output_path,
                        output_size=888,
                    )
                if row == 2:
                    output_path.write_bytes(b"partial")
                    raise RuntimeError("deliberate failure")
                raise AssertionError("canceled task must not start")

            with patch("gui.process_image", side_effect=fake_process) as mocked_process:
                worker.run()

            self.assertEqual(mocked_process.call_count, 3)
            for call in mocked_process.call_args_list:
                self.assertIs(
                    call.args[2].reference_notice_options,
                    reference_notice_options,
                )
            self.assertEqual(
                committed,
                [ProcessedOutput(11, 4), ProcessedOutput(22, 30)],
            )
            self.assertEqual(statuses[0], (0, STATUS_SUCCESS))
            self.assertEqual(statuses[1], (1, STATUS_SUCCESS))
            self.assertEqual(statuses[2][0], 2)
            self.assertTrue(statuses[2][1].startswith(STATUS_FAILED))
            self.assertEqual(statuses[3], (3, STATUS_CANCELED))
            self.assertEqual(len(finished), 1)
            total, success, failure, _last_output_dir, canceled = finished[0]
            self.assertEqual((total, success, failure, canceled), (4, 2, 1, True))


if __name__ == "__main__":
    unittest.main()
