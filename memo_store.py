from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final


MEMO_VERSION: Final = 1
MEMO_FILENAME: Final = "图片处理工具_备忘录.json"
MEMO_BACKUP_SUFFIX: Final = ".bak"

_DOCUMENT_FIELDS: Final = {"version", "updated_at", "notes"}
_NOTE_FIELDS: Final = {
    "id",
    "title",
    "content",
    "pinned",
    "created_at",
    "updated_at",
}
_UNSET: Final = object()


class MemoStoreError(Exception):
    """Base exception for memo persistence and data operations."""


class MemoValidationError(MemoStoreError):
    """Raised when memo data does not match the supported JSON schema."""


class MemoLoadError(MemoStoreError):
    """Raised when a memo file exists but cannot be read safely."""


class MemoSaveError(MemoStoreError):
    """Raised when memo data cannot be saved safely."""


class MemoBackupError(MemoStoreError):
    """Raised when a memo backup cannot be loaded or restored safely."""


class MemoNoteNotFoundError(MemoStoreError, LookupError):
    """Raised when a requested note ID is not present in a document."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _validated_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoValidationError(f"{field_name} 必须是非空的 ISO 时间字符串")

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise MemoValidationError(
            f"{field_name} 不是有效的 ISO 时间字符串：{value!r}"
        ) from exc
    return value


def _operation_timestamp(value: str | None) -> str:
    return _validated_timestamp(value if value is not None else _utc_now(), "操作时间")


def _validated_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise MemoValidationError(f"{field_name} 必须是字符串")
    return value


def _validated_note_id(value: object, field_name: str = "note.id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoValidationError(f"{field_name} 必须是非空字符串")
    return value


def _require_exact_fields(
    value: dict[str, object],
    expected: set[str],
    location: str,
) -> None:
    if not all(isinstance(key, str) for key in value):
        raise MemoValidationError(f"{location} 的字段名必须是字符串")
    missing = sorted(expected.difference(value))
    unexpected = sorted(set(value).difference(expected))
    problems: list[str] = []
    if missing:
        problems.append(f"缺少字段 {', '.join(missing)}")
    if unexpected:
        problems.append(f"包含未知字段 {', '.join(unexpected)}")
    if problems:
        raise MemoValidationError(f"{location} {'；'.join(problems)}")


@dataclass(slots=True)
class MemoNote:
    id: str
    title: str
    content: str
    pinned: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "pinned": self.pinned,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: object, *, index: int | None = None) -> MemoNote:
        location = "note" if index is None else f"notes[{index}]"
        if not isinstance(value, dict):
            raise MemoValidationError(f"{location} 必须是 JSON 对象")
        _require_exact_fields(value, _NOTE_FIELDS, location)

        pinned = value["pinned"]
        if not isinstance(pinned, bool):
            raise MemoValidationError(f"{location}.pinned 必须是布尔值")

        return cls(
            id=_validated_note_id(value["id"], f"{location}.id"),
            title=_validated_text(value["title"], f"{location}.title"),
            content=_validated_text(value["content"], f"{location}.content"),
            pinned=pinned,
            created_at=_validated_timestamp(
                value["created_at"], f"{location}.created_at"
            ),
            updated_at=_validated_timestamp(
                value["updated_at"], f"{location}.updated_at"
            ),
        )


@dataclass(slots=True)
class MemoDocument:
    version: int
    updated_at: str
    notes: list[MemoNote] = field(default_factory=list)

    @classmethod
    def empty(cls, *, now: str | None = None) -> MemoDocument:
        return cls(
            version=MEMO_VERSION,
            updated_at=_operation_timestamp(now),
            notes=[],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "notes": [note.to_dict() for note in self.notes],
        }

    @classmethod
    def from_dict(cls, value: object) -> MemoDocument:
        if not isinstance(value, dict):
            raise MemoValidationError("备忘录文档必须是 JSON 对象")
        _require_exact_fields(value, _DOCUMENT_FIELDS, "备忘录文档")

        version = value["version"]
        if not isinstance(version, int) or isinstance(version, bool):
            raise MemoValidationError("version 必须是整数")
        if version != MEMO_VERSION:
            raise MemoValidationError(
                f"不支持的备忘录版本 {version}，当前仅支持版本 {MEMO_VERSION}"
            )

        raw_notes = value["notes"]
        if not isinstance(raw_notes, list):
            raise MemoValidationError("notes 必须是数组")
        notes = [MemoNote.from_dict(note, index=index) for index, note in enumerate(raw_notes)]

        seen_ids: set[str] = set()
        for index, note in enumerate(notes):
            if note.id in seen_ids:
                raise MemoValidationError(
                    f"notes[{index}].id 与其他备忘录重复：{note.id!r}"
                )
            seen_ids.add(note.id)

        return cls(
            version=version,
            updated_at=_validated_timestamp(value["updated_at"], "updated_at"),
            notes=notes,
        )


def find_note(document: MemoDocument, note_id: str) -> MemoNote:
    _validate_document_instance(document)
    note_id = _validated_note_id(note_id, "note_id")
    for note in document.notes:
        if note.id == note_id:
            return note
    raise MemoNoteNotFoundError(f"未找到备忘录：{note_id}")


def create_note(
    document: MemoDocument,
    *,
    title: str = "",
    content: str = "",
    pinned: bool = False,
    note_id: str | None = None,
    now: str | None = None,
) -> MemoNote:
    _validate_document_instance(document)
    title = _validated_text(title, "title")
    content = _validated_text(content, "content")
    if not isinstance(pinned, bool):
        raise MemoValidationError("pinned 必须是布尔值")

    new_id = _validated_note_id(
        str(uuid.uuid4()) if note_id is None else note_id,
        "note_id",
    )
    if any(note.id == new_id for note in document.notes):
        raise MemoValidationError(f"备忘录 ID 已存在：{new_id}")

    timestamp = _operation_timestamp(now)
    note = MemoNote(
        id=new_id,
        title=title,
        content=content,
        pinned=pinned,
        created_at=timestamp,
        updated_at=timestamp,
    )
    document.notes.append(note)
    document.updated_at = timestamp
    return note


def update_note(
    document: MemoDocument,
    note_id: str,
    *,
    title: str | object = _UNSET,
    content: str | object = _UNSET,
    pinned: bool | object = _UNSET,
    now: str | None = None,
) -> MemoNote:
    note = find_note(document, note_id)

    next_title = note.title if title is _UNSET else _validated_text(title, "title")
    next_content = (
        note.content if content is _UNSET else _validated_text(content, "content")
    )
    if pinned is _UNSET:
        next_pinned = note.pinned
    elif isinstance(pinned, bool):
        next_pinned = pinned
    else:
        raise MemoValidationError("pinned 必须是布尔值")

    if (
        next_title == note.title
        and next_content == note.content
        and next_pinned == note.pinned
    ):
        return note

    timestamp = _operation_timestamp(now)
    note.title = next_title
    note.content = next_content
    note.pinned = next_pinned
    note.updated_at = timestamp
    document.updated_at = timestamp
    return note


def delete_note(
    document: MemoDocument,
    note_id: str,
    *,
    now: str | None = None,
) -> MemoNote:
    note = find_note(document, note_id)
    document.notes.remove(note)
    document.updated_at = _operation_timestamp(now)
    return note


def set_note_pinned(
    document: MemoDocument,
    note_id: str,
    pinned: bool,
    *,
    now: str | None = None,
) -> MemoNote:
    return update_note(document, note_id, pinned=pinned, now=now)


def _validate_document_instance(document: object) -> MemoDocument:
    if not isinstance(document, MemoDocument):
        raise MemoValidationError("document 必须是 MemoDocument")
    # Round-tripping through the schema validator also catches invalid data that
    # callers may have assigned directly to a dataclass field.
    try:
        raw_document = document.to_dict()
    except (AttributeError, TypeError) as exc:
        raise MemoValidationError("document 包含无效的备忘录对象") from exc
    return MemoDocument.from_dict(raw_document)


class MemoStore:
    """Load and atomically persist a memo document in a selected directory."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        try:
            self.directory = Path(directory).expanduser()
        except TypeError as exc:
            raise ValueError("备忘录存储目录必须是有效路径") from exc
        self.file_path = self.directory / MEMO_FILENAME
        self.path = self.file_path
        self.backup_path = self.file_path.with_name(
            self.file_path.name + MEMO_BACKUP_SUFFIX
        )

    def load(self) -> MemoDocument:
        self._require_directory(MemoLoadError, "读取备忘录")
        if not self.file_path.exists():
            return MemoDocument.empty()
        return self._load_path(self.file_path, MemoLoadError, "备忘录文件")

    def load_backup(self) -> MemoDocument:
        self._require_directory(MemoBackupError, "读取备忘录备份")
        if not self.backup_path.exists():
            raise MemoBackupError(f"未找到备忘录备份：{self.backup_path}")
        return self._load_path(self.backup_path, MemoBackupError, "备忘录备份")

    def save(self, document: MemoDocument) -> None:
        self._require_directory(MemoSaveError, "保存备忘录")
        try:
            validated = _validate_document_instance(document)
        except MemoValidationError as exc:
            raise MemoSaveError(f"备忘录数据无效，未保存：{exc}") from exc

        try:
            if self.file_path.exists():
                # Never replace an unreadable or malformed source file during a
                # normal save. The caller can explicitly restore a valid backup.
                self._load_path(self.file_path, MemoSaveError, "现有备忘录文件")
                self._atomic_copy(self.file_path, self.backup_path)

            self._atomic_write_json(self.file_path, validated)
        except MemoSaveError:
            raise
        except OSError as exc:
            raise MemoSaveError(
                f"无法保存备忘录到 {self.file_path}：{exc}"
            ) from exc

    def restore_backup(self) -> MemoDocument:
        document = self.load_backup()
        self._require_directory(MemoBackupError, "恢复备忘录备份")
        try:
            # Do not call save(): it would copy the current main file over the
            # backup that the user explicitly chose to restore.
            self._atomic_write_json(self.file_path, document)
        except OSError as exc:
            raise MemoBackupError(
                f"无法从备份恢复到 {self.file_path}，原文件未改变：{exc}"
            ) from exc
        return document

    def _require_directory(
        self,
        error_type: type[MemoStoreError],
        operation: str,
    ) -> None:
        try:
            if not self.directory.exists():
                raise error_type(
                    f"备忘录存储目录不存在，无法{operation}：{self.directory}"
                )
            if not self.directory.is_dir():
                raise error_type(
                    f"备忘录存储路径不是文件夹，无法{operation}：{self.directory}"
                )
        except error_type:
            raise
        except OSError as exc:
            raise error_type(
                f"无法访问备忘录存储目录 {self.directory}，无法{operation}：{exc}"
            ) from exc

    @staticmethod
    def _load_path(
        path: Path,
        error_type: type[MemoStoreError],
        description: str,
    ) -> MemoDocument:
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError as exc:
            raise error_type(
                f"{description} JSON 已损坏（{path}，第 {exc.lineno} 行第 {exc.colno} 列）"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise error_type(f"无法读取{description} {path}：{exc}") from exc

        try:
            return MemoDocument.from_dict(raw)
        except MemoValidationError as exc:
            raise error_type(f"{description}格式无效（{path}）：{exc}") from exc

    @staticmethod
    def _atomic_write_json(path: Path, document: MemoDocument) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(
                    document.to_dict(),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _atomic_copy(source: Path, destination: Path) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                with source.open("rb") as source_handle:
                    shutil.copyfileobj(source_handle, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, destination)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
