from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import gui
from config import STATUS_CANCELED, STATUS_SUCCESS
from gui import ImageOperationPage, MODE_COMPREHENSIVE, MODE_COMPRESS, STATUS_COLUMN


class ProcessingLifecycleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, condition, timeout: float = 5) -> None:
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), "Background operation did not finish in time")

    def make_images(self, directory: Path, count: int = 4) -> list[Path]:
        paths = [directory / f"image_{index}.jpg" for index in range(count)]
        for index, path in enumerate(paths):
            Image.new("RGB", (96, 80), (index * 40, 80, 120)).save(path)
        return paths

    def close_page(self, page: ImageOperationPage) -> None:
        page.shutdown()
        page.close()
        page.deleteLater()
        self.app.processEvents()

    def test_remove_refreshes_preview_once_with_remaining_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self.make_images(Path(temp_dir))
            page = ImageOperationPage("test", MODE_COMPREHENSIVE, "test")
            try:
                page._add_paths([temp_dir])
                page.table.selectRow(1)
                serial = page.preview_request_serial

                page.remove_button.click()

                self.assertEqual(page.preview_request_serial, serial + 1)
                self.assertEqual(page.pending_preview_request.source_path, paths[2])
                self.assertEqual(page.table.rowCount(), len(page.items))
            finally:
                self.close_page(page)

    def test_preview_thread_exits_without_gui_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.make_images(Path(temp_dir), 1)
            page = ImageOperationPage("test", MODE_COMPRESS, "test")
            try:
                page._add_paths([temp_dir])
                page.preview_timer.stop()
                page._start_pending_preview()
                thread = page.preview_thread

                # No GUI event dispatch while the worker finishes. Its thread
                # must be able to quit without a queued GUI-side quit call.
                self.assertTrue(thread.wait(3000))
                self.wait_for(lambda: page.preview_thread is None)
            finally:
                self.close_page(page)

    def test_processing_waits_for_preview_and_suppresses_new_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self.make_images(Path(temp_dir))
            page = ImageOperationPage("test", MODE_COMPREHENSIVE, "test")
            preview_entered = Event()
            release_preview = Event()
            batch_entered = Event()
            original_preview = gui.render_encoded_preview_image
            original_process = gui.process_image

            def delayed_preview(*args, **kwargs):
                preview_entered.set()
                release_preview.wait(5)
                return original_preview(*args, **kwargs)

            def tracked_process(*args, **kwargs):
                batch_entered.set()
                return original_process(*args, **kwargs)

            try:
                with (
                    patch("gui.render_encoded_preview_image", side_effect=delayed_preview),
                    patch("gui.process_image", side_effect=tracked_process) as process,
                    patch.object(page, "_show_message"),
                ):
                    page._add_paths([temp_dir])
                    page._start_pending_preview()
                    self.wait_for(preview_entered.is_set)
                    page.table.selectRow(1)
                    page.remove_button.click()
                    page.start_button.click()
                    self.assertTrue(page.processing_active)
                    worker = page.worker
                    page._start_processing()
                    self.assertIs(page.worker, worker)

                    page.table.selectRow(0)
                    QTest.qWait(350)
                    self.assertFalse(batch_entered.is_set())
                    self.assertIsNone(page.pending_preview_request)
                    self.assertFalse(page.preview_timer.isActive())

                    release_preview.set()
                    self.wait_for(lambda: not page.processing_active)
                    self.assertEqual(
                        [call.args[0] for call in process.call_args_list],
                        [paths[0], paths[2], paths[3]],
                    )
                    self.assertTrue(page.start_button.isEnabled())
                    self.assertIsNone(page.worker_thread)
                    self.assertEqual(page.progress_bar.value(), 100)
            finally:
                release_preview.set()
                self.close_page(page)

    def test_cancel_while_waiting_for_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.make_images(Path(temp_dir), 2)
            page = ImageOperationPage("test", MODE_COMPRESS, "test")
            preview_entered = Event()
            release_preview = Event()
            original_preview = gui.render_encoded_preview_image

            def delayed_preview(*args, **kwargs):
                preview_entered.set()
                release_preview.wait(5)
                return original_preview(*args, **kwargs)

            try:
                with (
                    patch("gui.render_encoded_preview_image", side_effect=delayed_preview),
                    patch("gui.process_image") as process,
                    patch.object(page, "_show_message") as message,
                ):
                    page._add_paths([temp_dir])
                    page._start_pending_preview()
                    self.wait_for(preview_entered.is_set)
                    page.start_button.click()
                    page.cancel_button.click()
                    release_preview.set()
                    self.wait_for(lambda: not page.processing_active)

                    process.assert_not_called()
                    self.assertEqual(
                        [page.table.item(row, STATUS_COLUMN).text() for row in range(2)],
                        [STATUS_CANCELED, STATUS_CANCELED],
                    )
                    message.assert_called_with("warning", "处理已取消")
            finally:
                release_preview.set()
                self.close_page(page)

    def test_shutdown_during_preview_wait_does_not_restart_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.make_images(Path(temp_dir), 2)
            page = ImageOperationPage("test", MODE_COMPRESS, "test")
            preview_entered = Event()
            release_preview = Event()
            original_preview = gui.render_encoded_preview_image

            def delayed_preview(*args, **kwargs):
                preview_entered.set()
                release_preview.wait(5)
                return original_preview(*args, **kwargs)

            try:
                with (
                    patch("gui.render_encoded_preview_image", side_effect=delayed_preview),
                    patch("gui.process_image") as process,
                    patch.object(page, "_show_message"),
                ):
                    page._add_paths([temp_dir])
                    page._start_pending_preview()
                    self.wait_for(preview_entered.is_set)
                    page.start_button.click()
                    release_preview.set()
                    page.shutdown()
                    # Deliver queued finished notifications after shutdown.
                    QTest.qWait(350)

                    process.assert_not_called()
                    self.assertIsNone(page.worker)
                    self.assertIsNone(page.worker_thread)
                    self.assertIsNone(page.preview_worker)
                    self.assertIsNone(page.preview_thread)
                    self.assertIsNone(page.pending_preview_request)
                    self.assertFalse(page.preview_timer.isActive())
            finally:
                release_preview.set()
                self.close_page(page)

    def test_folder_removals_process_only_remaining_files(self) -> None:
        for removed in ([0], [1], [3], [0, 2], [0, 1, 2, 3]):
            with self.subTest(removed=removed), tempfile.TemporaryDirectory() as temp_dir:
                paths = self.make_images(Path(temp_dir))
                page = ImageOperationPage("test", MODE_COMPREHENSIVE, "test")
                try:
                    with (
                        patch.object(page, "_show_message") as message,
                        patch("gui.process_image", wraps=gui.process_image) as process,
                    ):
                        page._add_paths([temp_dir])
                        selection = page.table.selectionModel()
                        selection.clearSelection()
                        for row in removed:
                            selection.select(
                                page.table.model().index(row, 0),
                                QItemSelectionModel.Select | QItemSelectionModel.Rows,
                            )
                        page.remove_button.click()
                        remaining = [path for row, path in enumerate(paths) if row not in removed]
                        self.assertEqual([item.path for item in page.items], remaining)
                        self.assertEqual(page.table.rowCount(), len(remaining))

                        page.start_button.click()
                        self.wait_for(lambda: not page.processing_active)

                        if remaining:
                            message.assert_called_with("success", "图片处理完成")
                            self.assertEqual(
                                [page.table.item(row, STATUS_COLUMN).text() for row in range(len(remaining))],
                                [STATUS_SUCCESS] * len(remaining),
                            )
                        else:
                            message.assert_called_with("warning", "请先导入图片")
                        self.assertEqual(
                            [call.args[0] for call in process.call_args_list], remaining
                        )
                        outputs = [call.args[1] for call in process.call_args_list]
                        self.assertTrue(all(path.is_file() for path in outputs))
                finally:
                    self.close_page(page)


if __name__ == "__main__":
    unittest.main()
