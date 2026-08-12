from __future__ import annotations

import hashlib
import hmac
import struct
import sys
from io import BytesIO
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from config import (
    BLIND_WATERMARK_BIT_LENGTH_STEP,
    BLIND_WATERMARK_FRAME_OVERHEAD_BYTES,
    MAX_BLIND_WATERMARK_BIT_LENGTH,
    MAX_BLIND_WATERMARK_KEY,
    MAX_BLIND_WATERMARK_TEXT_BYTES,
    MIN_BLIND_WATERMARK_BIT_LENGTH,
    MIN_BLIND_WATERMARK_IMAGE_EDGE,
    MIN_BLIND_WATERMARK_KEY,
)

BLIND_WATERMARK_LIBRARY_VERSION = "0.4.4"
_PAYLOAD_MAGIC = b"IWT1"
_PAYLOAD_TAG_BYTES = 8
_PAYLOAD_HEADER_BYTES = len(_PAYLOAD_MAGIC) + 1
_PAYLOAD_OVERHEAD_BYTES = BLIND_WATERMARK_FRAME_OVERHEAD_BYTES
assert _PAYLOAD_OVERHEAD_BYTES == _PAYLOAD_HEADER_BYTES + _PAYLOAD_TAG_BYTES
_EXTRACTION_VALIDATION_MESSAGE = (
    "盲水印提取失败：校验未通过，请检查图片密钥、内容密钥和提取位数"
)


class BlindWatermarkError(RuntimeError):
    """A user-facing blind-watermark failure."""


@dataclass(frozen=True, slots=True)
class BlindWatermarkOptions:
    text: str
    password_image: int
    password_watermark: int
    _payload: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        text_payload = _validate_text(self.text)
        _validate_password(self.password_image, "图片密钥")
        _validate_password(self.password_watermark, "内容密钥")
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(
            self,
            "_payload",
            _encode_payload(
                text_payload,
                password_image=self.password_image,
                password_watermark=self.password_watermark,
            ),
        )

    @property
    def payload(self) -> bytes:
        return self._payload

    @property
    def bit_length(self) -> int:
        return len(self._payload) * 8


def embed_blind_watermark(
    source: Image.Image | str | Path,
    options: BlindWatermarkOptions,
) -> Image.Image:
    image = _load_image(source)
    _validate_image(image, options.bit_length)
    numpy, water_mark = _load_dependency()

    rgb, alpha = _prepare_image(image)
    bgr = numpy.asarray(rgb, dtype=numpy.uint8)[:, :, ::-1].copy()
    bits = numpy.unpackbits(numpy.frombuffer(options.payload, dtype=numpy.uint8)).astype(bool)

    try:
        engine = water_mark(
            password_img=options.password_image,
            password_wm=options.password_watermark,
            mode="common",
            processes=1,
        )
        engine.read_img(img=bgr)
        engine.read_wm(bits, mode="bit")
        embedded_bgr = engine.embed()
    except Exception as exc:
        raise BlindWatermarkError(f"盲水印嵌入失败：{_exception_message(exc)}") from exc

    result = Image.fromarray(numpy.asarray(embedded_bgr, dtype=numpy.uint8)[:, :, ::-1])
    if alpha is not None:
        result.putalpha(alpha)
    return result


def extract_blind_watermark(
    source: Image.Image | str | Path,
    *,
    bit_length: int,
    password_image: int,
    password_watermark: int,
) -> str:
    _validate_bit_length(bit_length)
    _validate_password(password_image, "图片密钥")
    _validate_password(password_watermark, "内容密钥")
    image = _load_image(source)
    _validate_image(image, bit_length)
    numpy, water_mark = _load_dependency()

    rgb, _ = _prepare_image(image)
    bgr = numpy.asarray(rgb, dtype=numpy.uint8)[:, :, ::-1].copy()
    try:
        engine = water_mark(
            password_img=password_image,
            password_wm=password_watermark,
            mode="common",
            processes=1,
        )
        scores = engine.extract(
            embed_img=bgr,
            wm_shape=bit_length,
            mode="bit",
        )
        scores = numpy.asarray(scores).reshape(-1)
        if scores.size != bit_length:
            raise BlindWatermarkError(
                f"盲水印提取失败：组件返回 {scores.size} 位，预期 {bit_length} 位"
            )
        bits = (scores >= 0.5).astype(numpy.uint8)
        payload = numpy.packbits(bits).tobytes()
        return _decode_payload(
            payload,
            password_image=password_image,
            password_watermark=password_watermark,
        )
    except BlindWatermarkError:
        raise
    except Exception as exc:
        raise BlindWatermarkError(f"盲水印提取失败：{_exception_message(exc)}") from exc


def run_blind_watermark_self_test() -> int:
    """Exercise frozen numerical dependencies without touching user files."""
    try:
        size = MIN_BLIND_WATERMARK_IMAGE_EDGE
        image = Image.new("RGB", (size, size))
        image.putdata(
            [
                (
                    (x * 13 + y * 3) % 256,
                    (x * 5 + y * 11) % 256,
                    (x * 7 + y * 17) % 256,
                )
                for y in range(size)
                for x in range(size)
            ]
        )
        options = BlindWatermarkOptions("SELFTEST", 314159, 271828)
        embedded = embed_blind_watermark(image, options)
        encoded = BytesIO()
        embedded.save(encoded, format="PNG")
        encoded.seek(0)
        with Image.open(encoded) as decoded:
            decoded.load()
            extracted = extract_blind_watermark(
                decoded,
                bit_length=options.bit_length,
                password_image=options.password_image,
                password_watermark=options.password_watermark,
            )
        if extracted != options.text:
            raise BlindWatermarkError("盲水印自检失败：提取内容不一致")
        _report_self_test("blind-watermark self-test passed")
        return 0
    except Exception as exc:
        _report_self_test(
            f"blind-watermark self-test failed: {_exception_message(exc)}"
        )
        return 1


def _report_self_test(message: str) -> None:
    stream = getattr(sys, "stdout", None)
    if stream is None:
        return
    try:
        stream.write(message + "\n")
        stream.flush()
    except Exception:
        pass


def _load_dependency() -> tuple[Any, Any]:
    try:
        import numpy
        from blind_watermark import WaterMark, __version__, bw_notes
    except (ImportError, OSError) as exc:
        raise BlindWatermarkError(
            "盲水印组件未安装或无法加载，请安装 blind-watermark==0.4.4 及其依赖"
        ) from exc

    if __version__ != BLIND_WATERMARK_LIBRARY_VERSION:
        raise BlindWatermarkError(
            "盲水印组件版本不兼容："
            f"需要 {BLIND_WATERMARK_LIBRARY_VERSION}，当前为 {__version__}"
        )

    try:
        bw_notes.close()
    except Exception:
        pass
    return numpy, WaterMark


def _load_image(source: Image.Image | str | Path) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.copy()
    try:
        path = Path(source)
    except TypeError as exc:
        raise ValueError("图片来源必须是 PIL Image 或文件路径") from exc
    try:
        with Image.open(path) as image:
            image.load()
            return ImageOps.exif_transpose(image).copy()
    except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
        raise BlindWatermarkError(f"盲水印图片无法打开：{path}") from exc


def _prepare_image(image: Image.Image) -> tuple[Image.Image, Image.Image | None]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A") if _has_alpha(image) else None
    return rgba.convert("RGB"), alpha


def _validate_text(text: str) -> bytes:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("盲水印文字不能为空")
    payload = text.strip().encode("utf-8")
    if len(payload) > MAX_BLIND_WATERMARK_TEXT_BYTES:
        raise ValueError(
            f"盲水印文字 UTF-8 编码后不能超过 {MAX_BLIND_WATERMARK_TEXT_BYTES} 字节"
        )
    return payload


def _encode_payload(
    text_payload: bytes,
    *,
    password_image: int,
    password_watermark: int,
) -> bytes:
    header = _PAYLOAD_MAGIC + bytes((len(text_payload),))
    signed_payload = header + text_payload
    tag = hmac.new(
        _payload_authentication_key(password_image, password_watermark),
        signed_payload,
        hashlib.sha256,
    ).digest()[:_PAYLOAD_TAG_BYTES]
    return signed_payload + tag


def _decode_payload(
    payload: bytes,
    *,
    password_image: int,
    password_watermark: int,
) -> str:
    try:
        if len(payload) < _PAYLOAD_OVERHEAD_BYTES + 1:
            raise ValueError("payload too short")
        if payload[: len(_PAYLOAD_MAGIC)] != _PAYLOAD_MAGIC:
            raise ValueError("magic mismatch")

        text_length = payload[len(_PAYLOAD_MAGIC)]
        expected_length = _PAYLOAD_OVERHEAD_BYTES + text_length
        if len(payload) != expected_length or not 1 <= text_length <= MAX_BLIND_WATERMARK_TEXT_BYTES:
            raise ValueError("length mismatch")

        signed_payload = payload[:-_PAYLOAD_TAG_BYTES]
        actual_tag = payload[-_PAYLOAD_TAG_BYTES:]
        expected_tag = hmac.new(
            _payload_authentication_key(password_image, password_watermark),
            signed_payload,
            hashlib.sha256,
        ).digest()[:_PAYLOAD_TAG_BYTES]
        if not hmac.compare_digest(actual_tag, expected_tag):
            raise ValueError("authentication failed")
        return payload[_PAYLOAD_HEADER_BYTES:-_PAYLOAD_TAG_BYTES].decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise BlindWatermarkError(_EXTRACTION_VALIDATION_MESSAGE) from exc


def _payload_authentication_key(password_image: int, password_watermark: int) -> bytes:
    return struct.pack(">II", password_image, password_watermark)


def _validate_password(value: int, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not MIN_BLIND_WATERMARK_KEY <= value <= MAX_BLIND_WATERMARK_KEY
    ):
        raise ValueError(
            f"{label}必须是 {MIN_BLIND_WATERMARK_KEY} 到 "
            f"{MAX_BLIND_WATERMARK_KEY} 的正整数"
        )


def _validate_bit_length(bit_length: int) -> None:
    if (
        isinstance(bit_length, bool)
        or not isinstance(bit_length, int)
        or not MIN_BLIND_WATERMARK_BIT_LENGTH
        <= bit_length
        <= MAX_BLIND_WATERMARK_BIT_LENGTH
        or bit_length % BLIND_WATERMARK_BIT_LENGTH_STEP != 0
    ):
        raise ValueError(
            f"盲水印位长必须是 {MIN_BLIND_WATERMARK_BIT_LENGTH} 到 "
            f"{MAX_BLIND_WATERMARK_BIT_LENGTH} 之间的 "
            f"{BLIND_WATERMARK_BIT_LENGTH_STEP} 的倍数"
        )


def _validate_image(image: Image.Image, bit_length: int) -> None:
    if min(image.size) < MIN_BLIND_WATERMARK_IMAGE_EDGE:
        raise ValueError(
            f"盲水印要求图片短边至少为 {MIN_BLIND_WATERMARK_IMAGE_EDGE} 像素"
        )
    block_capacity = ((image.width + 1) // 2 // 4) * ((image.height + 1) // 2 // 4)
    if bit_length >= block_capacity:
        raise ValueError(
            f"图片可用盲水印容量不足，当前最多可容纳 {max(0, block_capacity - 1)} 位"
        )


def _exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )
