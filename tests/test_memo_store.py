from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from memo_store import (
    MEMO_FILENAME,
    MEMO_VERSION,
    MemoBackupError,
    MemoDocument,
    MemoLoadError,
    MemoNoteNotFoundError,
    MemoSaveError,
    MemoStore,
    MemoValidationError,
    create_note,
    delete_note,
    find_note,
    set_note_pinned,
    update_note,
)


T0 = "2026-08-03T08:00:00Z"
T1 = "2026-08-03T08:01:00Z"
T2 = "2026-08-03T08:02:00+00:00"
T3 = "2026-08-03T08:03:00Z"


class MemoDataOperationsTestCase(unittest.TestCase):
    def test_create_update_pin_and_delete_note(self) -> None:
        document = MemoDocument.empty(now=T0)

        note = create_note(
            document,
            title="平台图片要求",
            content="输出 JPG，宽度 1920px",
            note_id="note-1",
            now=T1,
        )

        self.assertEqual(note.id, "note-1")
        self.assertEqual(note.created_at, T1)
        self.assertEqual(note.updated_at, T1)
        self.assertEqual(document.updated_at, T1)
        self.assertIs(find_note(document, "note-1"), note)

        updated = update_note(
            document,
            "note-1",
            title="客户 A 图片要求",
            content="质量 95，清理全部元数据",
            now=T2,
        )
        self.assertIs(updated, note)
        self.assertEqual(updated.title, "客户 A 图片要求")
        self.assertEqual(updated.content, "质量 95，清理全部元数据")
        self.assertEqual(updated.created_at, T1)
        self.assertEqual(updated.updated_at, T2)
        self.assertEqual(document.updated_at, T2)

        pinned = set_note_pinned(document, "note-1", True, now=T3)
        self.assertTrue(pinned.pinned)
        self.assertEqual(pinned.updated_at, T3)
        self.assertEqual(document.updated_at, T3)

        removed = delete_note(document, "note-1", now="2026-08-03T08:04:00Z")
        self.assertIs(removed, note)
        self.assertEqual(document.notes, [])
        self.assertEqual(document.updated_at, "2026-08-03T08:04:00Z")

    def test_noop_update_preserves_timestamps(self) -> None:
        document = MemoDocument.empty(now=T0)
        note = create_note(
            document,
            title="不变",
            content="正文",
            pinned=True,
            note_id="same",
            now=T1,
        )

        update_note(
            document,
            "same",
            title="不变",
            content="正文",
            pinned=True,
            now=T3,
        )

        self.assertEqual(note.updated_at, T1)
        self.assertEqual(document.updated_at, T1)

    def test_data_operations_reject_duplicate_empty_and_missing_ids(self) -> None:
        document = MemoDocument.empty(now=T0)
        create_note(document, note_id="known", now=T1)

        with self.assertRaisesRegex(MemoValidationError, "ID 已存在"):
            create_note(document, note_id="known", now=T2)
        with self.assertRaisesRegex(MemoValidationError, "note_id 必须是非空"):
            create_note(document, note_id="", now=T2)
        with self.assertRaisesRegex(MemoNoteNotFoundError, "missing"):
            find_note(document, "missing")

    def test_schema_validation_reports_the_invalid_field(self) -> None:
        document = MemoDocument.empty(now=T0)
        create_note(document, note_id="valid", now=T1)
        valid = document.to_dict()

        cases: list[tuple[object, str]] = []

        missing_notes = deepcopy(valid)
        del missing_notes["notes"]
        cases.append((missing_notes, "缺少字段 notes"))

        unknown_field = deepcopy(valid)
        unknown_field["unexpected"] = True
        cases.append((unknown_field, "未知字段 unexpected"))

        boolean_version = deepcopy(valid)
        boolean_version["version"] = True
        cases.append((boolean_version, "version 必须是整数"))

        future_version = deepcopy(valid)
        future_version["version"] = MEMO_VERSION + 1
        cases.append((future_version, "不支持的备忘录版本"))

        notes_not_array = deepcopy(valid)
        notes_not_array["notes"] = {}
        cases.append((notes_not_array, "notes 必须是数组"))

        bad_pinned = deepcopy(valid)
        bad_pinned["notes"][0]["pinned"] = 1
        cases.append((bad_pinned, r"notes\[0\]\.pinned"))

        bad_timestamp = deepcopy(valid)
        bad_timestamp["notes"][0]["updated_at"] = "not-a-date"
        cases.append((bad_timestamp, r"notes\[0\]\.updated_at"))

        duplicate = deepcopy(valid)
        duplicate["notes"].append(deepcopy(duplicate["notes"][0]))
        cases.append((duplicate, "与其他备忘录重复"))

        for raw_document, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with self.assertRaisesRegex(MemoValidationError, expected_message):
                    MemoDocument.from_dict(raw_document)


class MemoStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_directory.name) / "用户指定目录"
        self.directory.mkdir(parents=True)
        self.store = MemoStore(self.directory)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def make_document(
        self,
        *,
        title: str = "中文标题",
        content: str = "第一行\n第二行",
        now: str = T1,
    ) -> MemoDocument:
        document = MemoDocument.empty(now=T0)
        create_note(
            document,
            title=title,
            content=content,
            note_id="note-1",
            now=now,
        )
        return document

    def test_fixed_paths_and_missing_file_load_as_empty_document(self) -> None:
        self.assertEqual(self.store.file_path, self.directory / MEMO_FILENAME)
        self.assertEqual(self.store.path, self.store.file_path)
        self.assertEqual(
            self.store.backup_path,
            self.directory / f"{MEMO_FILENAME}.bak",
        )

        document = self.store.load()

        self.assertEqual(document.version, MEMO_VERSION)
        self.assertEqual(document.notes, [])
        self.assertFalse(self.store.file_path.exists())

    def test_deleted_selected_directory_makes_load_and_save_fail_without_recreating_it(
        self,
    ) -> None:
        document = self.make_document()
        self.directory.rmdir()

        with self.assertRaisesRegex(
            MemoLoadError,
            "存储目录不存在.*读取备忘录",
        ):
            self.store.load()
        self.assertFalse(self.directory.exists())

        with self.assertRaisesRegex(
            MemoSaveError,
            "存储目录不存在.*保存备忘录",
        ):
            self.store.save(document)
        self.assertFalse(self.directory.exists())

    def test_deleted_selected_directory_prevents_backup_restore_without_recreating_it(
        self,
    ) -> None:
        self.directory.rmdir()

        with self.assertRaisesRegex(
            MemoBackupError,
            "存储目录不存在.*读取备忘录备份",
        ):
            self.store.restore_backup()

        self.assertFalse(self.directory.exists())

    def test_save_and_load_round_trip_utf8_without_ascii_escaping(self) -> None:
        document = self.make_document()

        self.store.save(document)
        loaded = self.store.load()

        self.assertEqual(loaded, document)
        raw_text = self.store.file_path.read_text(encoding="utf-8")
        self.assertIn("中文标题", raw_text)
        self.assertIn("第一行", raw_text)
        self.assertNotIn("\\u4e2d", raw_text.lower())
        self.assertTrue(raw_text.endswith("\n"))
        self.assertEqual(
            json.loads(raw_text).keys(),
            {"version", "updated_at", "notes"},
        )
        self.assertEqual(list(self.directory.glob(f".{MEMO_FILENAME}.*.tmp")), [])

    def test_second_save_keeps_previous_valid_document_as_backup(self) -> None:
        first_document = self.make_document(content="旧内容", now=T1)
        self.store.save(first_document)

        update_note(first_document, "note-1", content="新内容", now=T2)
        self.store.save(first_document)

        self.assertEqual(self.store.load().notes[0].content, "新内容")
        backup = self.store.load_backup()
        self.assertEqual(backup.notes[0].content, "旧内容")
        self.assertEqual(backup.updated_at, T1)

    def test_invalid_json_load_is_clear_and_never_changes_the_file(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        invalid_bytes = b'{"version": 1, broken'
        self.store.file_path.write_bytes(invalid_bytes)

        with self.assertRaisesRegex(MemoLoadError, r"JSON 已损坏.*第 1 行"):
            self.store.load()

        self.assertEqual(self.store.file_path.read_bytes(), invalid_bytes)
        self.assertFalse(self.store.backup_path.exists())

    def test_blank_existing_file_is_treated_as_damaged_not_as_empty(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.store.file_path.write_text("   \n", encoding="utf-8")

        with self.assertRaisesRegex(MemoLoadError, "JSON 已损坏"):
            self.store.load()

        self.assertEqual(self.store.file_path.read_text(encoding="utf-8"), "   \n")

    def test_normal_save_refuses_to_overwrite_damaged_main_or_backup(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        damaged = b"not valid json"
        original_backup = b"backup must stay untouched"
        self.store.file_path.write_bytes(damaged)
        self.store.backup_path.write_bytes(original_backup)

        with self.assertRaisesRegex(MemoSaveError, "现有备忘录文件 JSON 已损坏"):
            self.store.save(self.make_document())

        self.assertEqual(self.store.file_path.read_bytes(), damaged)
        self.assertEqual(self.store.backup_path.read_bytes(), original_backup)

    def test_save_rejects_invalid_in_memory_data_before_touching_disk(self) -> None:
        document = self.make_document()
        document.notes[0].pinned = 1  # type: ignore[assignment]

        with self.assertRaisesRegex(MemoSaveError, "数据无效.*pinned"):
            self.store.save(document)

        self.assertFalse(self.store.file_path.exists())

    def test_load_reports_schema_path_and_does_not_rewrite_invalid_data(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        raw_document = self.make_document().to_dict()
        raw_document["notes"][0]["content"] = None
        original = json.dumps(raw_document, ensure_ascii=False).encode("utf-8")
        self.store.file_path.write_bytes(original)

        with self.assertRaisesRegex(MemoLoadError, r"notes\[0\]\.content"):
            self.store.load()

        self.assertEqual(self.store.file_path.read_bytes(), original)

    def test_backup_load_and_restore_replace_a_damaged_main_safely(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        backup_document = self.make_document(content="可以恢复", now=T1)
        self.store.backup_path.write_text(
            json.dumps(backup_document.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.store.file_path.write_bytes(b"damaged main")

        loaded_backup = self.store.load_backup()
        restored = self.store.restore_backup()

        self.assertEqual(loaded_backup, backup_document)
        self.assertEqual(restored, backup_document)
        self.assertEqual(self.store.load(), backup_document)
        self.assertEqual(self.store.load_backup(), backup_document)

    def test_invalid_backup_cannot_overwrite_existing_main(self) -> None:
        main_document = self.make_document(content="主文件内容", now=T1)
        self.store.save(main_document)
        original_main = self.store.file_path.read_bytes()
        self.store.backup_path.write_bytes(b"damaged backup")

        with self.assertRaisesRegex(MemoBackupError, "备忘录备份 JSON 已损坏"):
            self.store.restore_backup()

        self.assertEqual(self.store.file_path.read_bytes(), original_main)

    def test_failed_atomic_restore_leaves_existing_main_unchanged(self) -> None:
        main_document = self.make_document(content="当前内容", now=T1)
        self.store.save(main_document)
        original_main = self.store.file_path.read_bytes()
        backup_document = self.make_document(content="备份内容", now=T2)
        self.store.backup_path.write_text(
            json.dumps(backup_document.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )

        with patch("memo_store.os.replace", side_effect=OSError("模拟替换失败")):
            with self.assertRaisesRegex(MemoBackupError, "原文件未改变"):
                self.store.restore_backup()

        self.assertEqual(self.store.file_path.read_bytes(), original_main)
        self.assertEqual(list(self.directory.glob(f".{MEMO_FILENAME}.*.tmp")), [])

    def test_missing_backup_has_a_clear_error(self) -> None:
        with self.assertRaisesRegex(MemoBackupError, "未找到备忘录备份"):
            self.store.load_backup()


if __name__ == "__main__":
    unittest.main()
