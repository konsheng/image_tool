from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from config import FEATURE_DEFAULTS
from gui import (
    COMPREHENSIVE_FEATURES,
    MEMO_AUTOSAVE_DELAY_MS,
    MEMO_STORAGE_DIRECTORY_SETTING_KEY,
    ImageToolWindow,
    MemoDirectoryChoiceDialog,
    MemoPage,
    MODE_MEMO,
    feature_setting_key,
)
from memo_store import (
    MEMO_FILENAME,
    MemoDocument,
    MemoStore,
    create_note,
    update_note,
)


T0 = "2026-08-03T08:00:00Z"
T1 = "2026-08-03T08:01:00Z"
T2 = "2026-08-03T08:02:00Z"
T3 = "2026-08-03T08:03:00Z"


class MemoGuiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def process_events(self, cycles: int = 6) -> None:
        for _ in range(cycles):
            self.app.processEvents()

    def make_page(self, settings_path: Path) -> tuple[MemoPage, QSettings]:
        settings = QSettings(str(settings_path), QSettings.IniFormat)
        page = MemoPage(settings)
        page.resize(1060, 720)
        page.show()
        self.process_events()
        return page, settings

    def close_page(self, page: MemoPage) -> None:
        page.save_timer.stop()
        page.close()
        page.deleteLater()
        self.process_events()

    def select_first_directory(self, page: MemoPage, directory: Path) -> None:
        with (
            patch(
                "gui.QFileDialog.getExistingDirectory",
                return_value=str(directory),
            ),
            patch.object(page, "_show_message"),
        ):
            page.choose_storage_directory()
            self.process_events()

    @staticmethod
    def write_document(
        directory: Path,
        *,
        note_id: str,
        title: str,
        content: str,
        now: str = T1,
    ) -> MemoDocument:
        directory.mkdir(parents=True, exist_ok=True)
        document = MemoDocument.empty(now=T0)
        create_note(
            document,
            note_id=note_id,
            title=title,
            content=content,
            now=now,
        )
        MemoStore(directory).save(document)
        return document

    def test_first_open_without_directory_has_safe_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.ini"
            page, settings = self.make_page(settings_path)
            try:
                self.assertIsNone(page.storage_directory)
                self.assertIsNone(page.store)
                self.assertFalse(page.storage_ready)
                self.assertEqual(page.document.notes, [])
                self.assertEqual(page.note_list.count(), 0)
                self.assertFalse(page.new_note_button.isEnabled())
                self.assertFalse(page.search_edit.isEnabled())
                self.assertFalse(page.title_edit.isEnabled())
                self.assertFalse(page.content_edit.isEnabled())
                self.assertTrue(page.storage_notice_label.isVisible())
                self.assertFalse(page.storage_message_is_error)
                for removed_control in (
                    "directory_path_edit",
                    "choose_directory_button",
                    "reload_directory_button",
                    "open_directory_button",
                    "restore_backup_button",
                    "directory_error_label",
                ):
                    self.assertFalse(hasattr(page, removed_control))
                self.assertFalse(
                    settings.contains(MEMO_STORAGE_DIRECTORY_SETTING_KEY)
                )
            finally:
                self.close_page(page)

    def test_first_directory_selection_creates_fixed_json_and_is_remembered(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_path = root / "settings.ini"
            storage_directory = root / "用户指定目录"
            storage_directory.mkdir()
            page, settings = self.make_page(settings_path)
            try:
                self.select_first_directory(page, storage_directory)

                expected_path = storage_directory / MEMO_FILENAME
                self.assertTrue(page.storage_ready)
                self.assertEqual(page.storage_directory, storage_directory)
                self.assertEqual(page.store.file_path, expected_path)
                self.assertTrue(expected_path.is_file())
                self.assertEqual(json.loads(expected_path.read_text("utf-8"))["notes"], [])
                self.assertEqual(
                    settings.value(MEMO_STORAGE_DIRECTORY_SETTING_KEY),
                    str(storage_directory),
                )
                settings.sync()
            finally:
                self.close_page(page)

            restored, _ = self.make_page(settings_path)
            try:
                self.assertTrue(restored.storage_ready)
                self.assertEqual(restored.storage_directory, storage_directory)
                self.assertEqual(restored.document.notes, [])
                self.assertFalse(restored.storage_notice_label.isVisible())
            finally:
                self.close_page(restored)

    def test_new_edit_autosaves_after_800ms_and_restores_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_path = root / "settings.ini"
            storage_directory = root / "备忘录"
            storage_directory.mkdir()
            page, settings = self.make_page(settings_path)
            try:
                self.select_first_directory(page, storage_directory)
                page.new_note_button.click()
                self.process_events()

                self.assertEqual(len(page.document.notes), 1)
                self.assertIsNotNone(page.current_note_id)
                page.title_edit.setText("平台图片要求")
                page.content_edit.setPlainText("输出 JPG\n宽度 1920px\n质量 95")
                self.process_events()

                self.assertTrue(page.dirty)
                self.assertTrue(page.save_timer.isActive())
                self.assertEqual(page.save_timer.interval(), MEMO_AUTOSAVE_DELAY_MS)
                self.assertEqual(MEMO_AUTOSAVE_DELAY_MS, 800)

                QTest.qWait(MEMO_AUTOSAVE_DELAY_MS + 250)
                self.process_events()

                self.assertFalse(page.dirty)
                self.assertFalse(page.save_timer.isActive())
                self.assertEqual(page.save_status_label.text(), "已自动保存")
                saved = MemoStore(storage_directory).load()
                self.assertEqual(saved.notes[0].title, "平台图片要求")
                self.assertEqual(
                    saved.notes[0].content,
                    "输出 JPG\n宽度 1920px\n质量 95",
                )
                settings.sync()
            finally:
                self.close_page(page)

            restored, _ = self.make_page(settings_path)
            try:
                self.assertEqual(len(restored.document.notes), 1)
                self.assertEqual(restored.title_edit.text(), "平台图片要求")
                self.assertEqual(
                    restored.content_edit.toPlainText(),
                    "输出 JPG\n宽度 1920px\n质量 95",
                )
                self.assertFalse(restored.dirty)
            finally:
                self.close_page(restored)

    def test_one_click_copy_content_and_copy_title_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            page, _ = self.make_page(root / "settings.ini")
            storage_directory = root / "备忘录"
            storage_directory.mkdir()
            try:
                self.select_first_directory(page, storage_directory)
                page.new_note_button.click()
                page.title_edit.setText("客户 A")
                page.content_edit.setPlainText("第一行\n第二行")
                self.process_events()

                clipboard = QApplication.clipboard()
                clipboard.clear()
                with patch.object(page, "_show_message") as show_message:
                    page.copy_button.button.click()
                    self.process_events()
                    self.assertEqual(clipboard.text(), "第一行\n第二行")
                    show_message.assert_called_once()

                    show_message.reset_mock()
                    page.copy_full_action.trigger()
                    self.process_events()
                    self.assertEqual(clipboard.text(), "客户 A\n\n第一行\n第二行")
                    show_message.assert_called_once()
            finally:
                self.close_page(page)

    def test_searches_title_and_content_and_pinned_notes_sort_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            page, _ = self.make_page(root / "settings.ini")
            storage_directory = root / "备忘录"
            storage_directory.mkdir()
            try:
                self.select_first_directory(page, storage_directory)
                alpha = create_note(
                    page.document,
                    note_id="alpha",
                    title="平台要求",
                    content="普通内容",
                    now=T1,
                )
                beta = create_note(
                    page.document,
                    note_id="beta",
                    title="客户说明",
                    content="透明背景 PNG",
                    now=T3,
                )
                gamma = create_note(
                    page.document,
                    note_id="gamma",
                    title="常用参数",
                    content="质量 95",
                    pinned=True,
                    now=T2,
                )
                assert page.store is not None
                page.store.save(page.document)
                page._refresh_note_list()
                self.process_events()

                visible_ids = [
                    page.note_list.item(index).data(Qt.UserRole)
                    for index in range(page.note_list.count())
                ]
                self.assertEqual(visible_ids, [gamma.id, beta.id, alpha.id])

                page.search_edit.setText("透明背景")
                self.process_events()
                self.assertEqual(page.note_list.count(), 1)
                self.assertEqual(page.note_list.item(0).data(Qt.UserRole), beta.id)

                page.search_edit.setText("平台")
                self.process_events()
                self.assertEqual(page.note_list.count(), 1)
                self.assertEqual(page.note_list.item(0).data(Qt.UserRole), alpha.id)

                page.search_edit.clear()
                self.process_events()
                for index in range(page.note_list.count()):
                    if page.note_list.item(index).data(Qt.UserRole) == alpha.id:
                        page.note_list.setCurrentRow(index)
                        break
                page.pin_button.click()
                self.process_events()

                self.assertTrue(alpha.pinned)
                reordered_ids = [
                    page.note_list.item(index).data(Qt.UserRole)
                    for index in range(page.note_list.count())
                ]
                self.assertEqual(set(reordered_ids[:2]), {alpha.id, gamma.id})
                self.assertEqual(reordered_ids[-1], beta.id)
            finally:
                self.close_page(page)

    def test_delete_requires_confirmation_and_persists_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            page, _ = self.make_page(root / "settings.ini")
            storage_directory = root / "备忘录"
            storage_directory.mkdir()
            try:
                self.select_first_directory(page, storage_directory)
                page.new_note_button.click()
                page.title_edit.setText("待删除")
                page.content_edit.setPlainText("仍应保留")
                self.assertTrue(page._save_now())

                with patch("gui.MessageBox.exec", return_value=False) as confirm:
                    page.delete_note_button.click()
                    self.process_events()
                confirm.assert_called_once()
                self.assertEqual(len(page.document.notes), 1)
                self.assertEqual(len(MemoStore(storage_directory).load().notes), 1)

                with (
                    patch("gui.MessageBox.exec", return_value=True) as confirm,
                    patch.object(page, "_show_message"),
                ):
                    page.delete_note_button.click()
                    self.process_events()
                confirm.assert_called_once()
                self.assertEqual(page.document.notes, [])
                self.assertEqual(MemoStore(storage_directory).load().notes, [])
                self.assertEqual(page.note_list.count(), 0)
            finally:
                self.close_page(page)

    def test_directory_switch_supports_migrate_read_and_empty(self) -> None:
        cases = (
            (MemoDirectoryChoiceDialog.MIGRATE, False, "source"),
            (MemoDirectoryChoiceDialog.READ, True, "target"),
            (MemoDirectoryChoiceDialog.EMPTY, True, None),
        )
        for choice, target_has_file, expected_note_id in cases:
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                source_directory = root / "源目录"
                target_directory = root / "新目录"
                self.write_document(
                    source_directory,
                    note_id="source",
                    title="当前备忘录",
                    content="需要迁移的内容",
                )
                target_directory.mkdir()
                if target_has_file:
                    self.write_document(
                        target_directory,
                        note_id="target",
                        title="目标目录备忘录",
                        content="目标内容",
                        now=T2,
                    )

                settings_path = root / "settings.ini"
                settings = QSettings(str(settings_path), QSettings.IniFormat)
                settings.setValue(
                    MEMO_STORAGE_DIRECTORY_SETTING_KEY,
                    str(source_directory),
                )
                settings.sync()
                page, settings = self.make_page(settings_path)
                try:
                    with (
                        patch(
                            "gui.QFileDialog.getExistingDirectory",
                            return_value=str(target_directory),
                        ),
                        patch.object(
                            page,
                            "_ask_directory_choice",
                            return_value=choice,
                        ) as ask_choice,
                        patch.object(page, "_show_message"),
                    ):
                        page.choose_storage_directory()
                        self.process_events()

                    ask_choice.assert_called_once_with(
                        target_directory,
                        has_current_notes=True,
                        has_existing_file=target_has_file,
                    )
                    self.assertTrue(page.storage_ready)
                    self.assertEqual(page.storage_directory, target_directory)
                    self.assertEqual(
                        settings.value(MEMO_STORAGE_DIRECTORY_SETTING_KEY),
                        str(target_directory),
                    )
                    loaded = MemoStore(target_directory).load()
                    if expected_note_id is None:
                        self.assertEqual(loaded.notes, [])
                        self.assertEqual(page.document.notes, [])
                    else:
                        self.assertEqual([note.id for note in loaded.notes], [expected_note_id])
                        self.assertEqual(
                            [note.id for note in page.document.notes],
                            [expected_note_id],
                        )
                finally:
                    self.close_page(page)

    def test_directory_switch_aborts_when_pending_changes_cannot_be_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_directory = root / "旧目录"
            target_directory = root / "新目录"
            target_directory.mkdir()
            self.write_document(
                source_directory,
                note_id="source",
                title="未保存内容测试",
                content="已保存版本",
            )
            settings_path = root / "settings.ini"
            settings = QSettings(str(settings_path), QSettings.IniFormat)
            settings.setValue(
                MEMO_STORAGE_DIRECTORY_SETTING_KEY,
                str(source_directory),
            )
            settings.sync()
            page, settings = self.make_page(settings_path)
            try:
                shutil.rmtree(source_directory)
                page.content_edit.setPlainText("必须保留在内存中的新内容")
                self.process_events()
                self.assertTrue(page.dirty)

                with (
                    patch(
                        "gui.QFileDialog.getExistingDirectory",
                        return_value=str(target_directory),
                    ),
                    patch.object(
                        page,
                        "_ask_directory_choice",
                        return_value=MemoDirectoryChoiceDialog.EMPTY,
                    ) as ask_choice,
                    patch.object(page, "_show_message"),
                ):
                    page.choose_storage_directory()
                    self.process_events()

                ask_choice.assert_not_called()
                self.assertEqual(page.storage_directory, source_directory)
                self.assertEqual(
                    settings.value(MEMO_STORAGE_DIRECTORY_SETTING_KEY),
                    str(source_directory),
                )
                self.assertEqual(
                    page.content_edit.toPlainText(),
                    "必须保留在内存中的新内容",
                )
                self.assertEqual(page.document.notes[0].content, "必须保留在内存中的新内容")
                self.assertTrue(page.dirty)
                self.assertFalse(source_directory.exists())
                self.assertFalse((target_directory / MEMO_FILENAME).exists())
            finally:
                page.save_timer.stop()
                page.close()
                page.deleteLater()
                self.process_events()

    def test_missing_remembered_directory_fails_save_without_recreating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            page, _ = self.make_page(root / "settings.ini")
            storage_directory = root / "移动硬盘"
            storage_directory.mkdir()
            try:
                self.select_first_directory(page, storage_directory)
                page.new_note_button.click()
                page.content_edit.setPlainText("已保存内容")
                self.assertTrue(page._save_now())

                shutil.rmtree(storage_directory)
                page.content_edit.setPlainText("目录丢失后的修改")
                self.process_events()

                self.assertFalse(page._save_now())
                self.assertTrue(page.dirty)
                self.assertFalse(storage_directory.exists())
                self.assertIn("不存在", page.last_save_error)
                self.assertTrue(page.storage_notice_label.isVisible())
                self.assertTrue(page.storage_message_is_error)
                self.assertEqual(page.save_status_label.text(), "保存失败，请检查存储目录")
            finally:
                self.close_page(page)

    def test_backup_restore_reloads_editor_and_replaces_main_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_directory = root / "备忘录"
            document = self.write_document(
                storage_directory,
                note_id="note-1",
                title="恢复测试",
                content="备份内容",
                now=T1,
            )
            update_note(document, "note-1", content="当前内容", now=T2)
            store = MemoStore(storage_directory)
            store.save(document)
            self.assertTrue(store.backup_path.exists())

            settings_path = root / "settings.ini"
            settings = QSettings(str(settings_path), QSettings.IniFormat)
            settings.setValue(
                MEMO_STORAGE_DIRECTORY_SETTING_KEY,
                str(storage_directory),
            )
            settings.sync()
            page, _ = self.make_page(settings_path)
            try:
                self.assertEqual(page.content_edit.toPlainText(), "当前内容")
                with (
                    patch("gui.MessageBox.exec", return_value=True) as confirm,
                    patch.object(page, "_show_message"),
                ):
                    page.restore_backup()
                    self.process_events()

                confirm.assert_called_once()
                self.assertEqual(page.content_edit.toPlainText(), "备份内容")
                self.assertEqual(page.document.notes[0].content, "备份内容")
                self.assertEqual(store.load().notes[0].content, "备份内容")
                self.assertFalse(page.dirty)
            finally:
                self.close_page(page)


class MemoFeatureSwitchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def process_events(self, cycles: int = 6) -> None:
        for _ in range(cycles):
            self.app.processEvents()

    def make_window(self, settings_path: Path) -> tuple[ImageToolWindow, QSettings]:
        settings = QSettings(str(settings_path), QSettings.IniFormat)
        window = ImageToolWindow(settings=settings)
        window.resize(1220, 820)
        window.show()
        self.process_events()
        return window, settings

    def close_window(self, window: ImageToolWindow) -> None:
        window.close()
        window.deleteLater()
        self.process_events()

    def test_memo_storage_controls_exist_only_in_settings_and_drive_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_path = root / "settings.ini"
            storage_directory = root / "备忘录"
            storage_directory.mkdir()
            window, settings = self.make_window(settings_path)
            try:
                page = window.memo_page
                settings_page = window.settings_page
                self.assertIs(settings_page.memo_page, page)
                for page_only_control in (
                    "directory_path_edit",
                    "choose_directory_button",
                    "reload_directory_button",
                    "open_directory_button",
                    "restore_backup_button",
                    "directory_error_label",
                ):
                    self.assertFalse(hasattr(page, page_only_control))

                self.assertTrue(settings_page.memo_directory_path_edit.isReadOnly())
                self.assertEqual(settings_page.memo_directory_path_edit.text(), "")
                self.assertEqual(
                    settings_page.memo_directory_path_edit.placeholderText(),
                    "尚未选择存储目录",
                )
                self.assertEqual(settings_page.memo_choose_directory_button.text(), "选择目录")
                self.assertEqual(
                    settings_page.memo_storage_status_label.text(),
                    page.storage_message,
                )
                self.assertIn("选择", settings_page.memo_storage_status_label.text())
                self.assertFalse(settings_page.memo_reload_directory_button.isEnabled())
                self.assertFalse(settings_page.memo_open_directory_button.isEnabled())
                self.assertTrue(settings_page.memo_restore_backup_button.isHidden())

                with (
                    patch(
                        "gui.QFileDialog.getExistingDirectory",
                        return_value=str(storage_directory),
                    ),
                    patch.object(page, "_show_message"),
                ):
                    settings_page.memo_choose_directory_button.click()
                    self.process_events()

                self.assertTrue(page.storage_ready)
                self.assertEqual(page.storage_directory, storage_directory)
                self.assertTrue((storage_directory / MEMO_FILENAME).is_file())
                self.assertEqual(
                    settings.value(MEMO_STORAGE_DIRECTORY_SETTING_KEY),
                    str(storage_directory),
                )
                self.assertEqual(
                    settings_page.memo_directory_path_edit.text(),
                    str(storage_directory),
                )
                self.assertEqual(settings_page.memo_choose_directory_button.text(), "更改目录")
                self.assertEqual(
                    settings_page.memo_storage_status_label.text(),
                    f"存储正常 · 数据文件：{MEMO_FILENAME}",
                )
                self.assertTrue(settings_page.memo_reload_directory_button.isEnabled())
                self.assertTrue(settings_page.memo_open_directory_button.isEnabled())
                self.assertTrue(settings_page.memo_restore_backup_button.isHidden())

                page._create_note()
                page.title_edit.setText("重新读取测试")
                page.content_edit.setPlainText("版本一")
                self.assertTrue(page._save_now())
                assert page.store is not None
                external_document = page.store.load()
                update_note(
                    external_document,
                    external_document.notes[0].id,
                    content="版本二",
                    now=T3,
                )
                page.store.save(external_document)
                self.assertEqual(page.content_edit.toPlainText(), "版本一")

                with patch.object(page, "_show_message"):
                    settings_page.memo_reload_directory_button.click()
                    self.process_events()
                self.assertEqual(page.content_edit.toPlainText(), "版本二")
                self.assertFalse(settings_page.memo_restore_backup_button.isHidden())
                self.assertTrue(settings_page.memo_restore_backup_button.isEnabled())

                with patch("gui.QDesktopServices.openUrl", return_value=True) as open_url:
                    settings_page.memo_open_directory_button.click()
                    self.process_events()
                open_url.assert_called_once()

                with (
                    patch("gui.MessageBox.exec", return_value=True) as confirm,
                    patch.object(page, "_show_message"),
                ):
                    settings_page.memo_restore_backup_button.click()
                    self.process_events()
                confirm.assert_called_once()
                self.assertEqual(page.content_edit.toPlainText(), "版本一")
                self.assertEqual(page.store.load().notes[0].content, "版本一")
                self.assertEqual(
                    settings_page.memo_storage_status_label.text(),
                    f"存储正常 · 数据文件：{MEMO_FILENAME}",
                )
            finally:
                self.close_window(window)

    def test_settings_can_restore_valid_backup_when_main_json_is_damaged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_directory = root / "备忘录"
            document = MemoGuiTestCase.write_document(
                storage_directory,
                note_id="note-1",
                title="损坏恢复测试",
                content="可恢复版本",
                now=T1,
            )
            store = MemoStore(storage_directory)
            update_note(document, "note-1", content="损坏前的新版", now=T2)
            store.save(document)
            store.file_path.write_bytes(b"damaged main json")

            settings_path = root / "settings.ini"
            settings = QSettings(str(settings_path), QSettings.IniFormat)
            settings.setValue(
                MEMO_STORAGE_DIRECTORY_SETTING_KEY,
                str(storage_directory),
            )
            settings.sync()
            window, _ = self.make_window(settings_path)
            try:
                page = window.memo_page
                settings_page = window.settings_page
                self.assertFalse(page.storage_ready)
                self.assertTrue(page.storage_message_is_error)
                self.assertEqual(
                    settings_page.memo_directory_path_edit.text(),
                    str(storage_directory),
                )
                self.assertEqual(
                    settings_page.memo_storage_status_label.objectName(),
                    "ErrorLabel",
                )
                self.assertFalse(settings_page.memo_restore_backup_button.isHidden())
                self.assertTrue(settings_page.memo_restore_backup_button.isEnabled())

                with (
                    patch("gui.MessageBox.exec", return_value=True),
                    patch.object(page, "_show_message"),
                ):
                    settings_page.memo_restore_backup_button.click()
                    self.process_events()

                self.assertTrue(page.storage_ready)
                self.assertEqual(page.content_edit.toPlainText(), "可恢复版本")
                self.assertEqual(store.load().notes[0].content, "可恢复版本")
                self.assertEqual(
                    settings_page.memo_storage_status_label.text(),
                    f"存储正常 · 数据文件：{MEMO_FILENAME}",
                )
            finally:
                self.close_window(window)

    def test_memo_is_an_independent_persistent_page_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.ini"
            window, settings = self.make_window(settings_path)
            try:
                self.assertTrue(FEATURE_DEFAULTS[MODE_MEMO])
                self.assertTrue(window.feature_states[MODE_MEMO])
                self.assertFalse(window.feature_nav_items[MODE_MEMO].isHidden())
                self.assertNotIn(MODE_MEMO, COMPREHENSIVE_FEATURES)
                self.assertNotIn(
                    MODE_MEMO,
                    window.settings_page.comprehensive_feature_switches,
                )
                self.assertNotIn(
                    MODE_MEMO,
                    window.comprehensive_page.feature_sections,
                )
                comprehensive_before = dict(window.comprehensive_feature_states)

                window.settings_page.feature_switches[MODE_MEMO].setChecked(False)
                self.process_events()
                settings.sync()

                self.assertFalse(window.feature_states[MODE_MEMO])
                self.assertTrue(window.feature_nav_items[MODE_MEMO].isHidden())
                self.assertFalse(window.memo_page.isEnabled())
                self.assertEqual(
                    window.comprehensive_feature_states,
                    comprehensive_before,
                )
                self.assertFalse(
                    settings.value(feature_setting_key(MODE_MEMO), True, type=bool)
                )
            finally:
                self.close_window(window)

            restored, _ = self.make_window(settings_path)
            try:
                self.assertFalse(restored.feature_states[MODE_MEMO])
                self.assertFalse(
                    restored.settings_page.feature_switches[MODE_MEMO].isChecked()
                )
                self.assertTrue(restored.feature_nav_items[MODE_MEMO].isHidden())
                self.assertFalse(restored.memo_page.isEnabled())
                self.assertNotIn(
                    MODE_MEMO,
                    restored.settings_page.comprehensive_feature_switches,
                )
            finally:
                self.close_window(restored)

    def test_memo_page_switch_stays_enabled_when_pending_save_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_path = root / "settings.ini"
            storage_directory = root / "备忘录"
            storage_directory.mkdir()
            MemoStore(storage_directory).save(MemoDocument.empty())
            initial_settings = QSettings(str(settings_path), QSettings.IniFormat)
            initial_settings.setValue(
                MEMO_STORAGE_DIRECTORY_SETTING_KEY,
                str(storage_directory),
            )
            initial_settings.sync()

            window, settings = self.make_window(settings_path)
            try:
                page = window.memo_page
                page._create_note()
                page.content_edit.setPlainText("目录丢失后尚未保存的内容")
                self.assertTrue(page._save_now())
                shutil.rmtree(storage_directory)
                page.content_edit.setPlainText("必须保留在内存中的修改")
                self.assertTrue(page.dirty)

                with patch.object(page, "_show_message") as show_message:
                    window.settings_page.feature_switches[MODE_MEMO].setChecked(False)
                    self.process_events()

                show_message.assert_called_once()
                self.assertTrue(window.feature_states[MODE_MEMO])
                self.assertTrue(
                    window.settings_page.feature_switches[MODE_MEMO].isChecked()
                )
                self.assertFalse(window.feature_nav_items[MODE_MEMO].isHidden())
                self.assertTrue(page.dirty)
                self.assertTrue(
                    settings.value(feature_setting_key(MODE_MEMO), True, type=bool)
                )

                storage_directory.mkdir()
                self.assertTrue(page._save_now())
            finally:
                self.close_window(window)


if __name__ == "__main__":
    unittest.main()
