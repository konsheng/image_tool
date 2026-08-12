from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import blind_watermark_service as service
from blind_watermark_service import (
    BlindWatermarkError,
    BlindWatermarkOptions,
    embed_blind_watermark,
    extract_blind_watermark,
)
from config import (
    BLIND_WATERMARK_FRAME_OVERHEAD_BYTES,
    DEFAULT_BLIND_WATERMARK_TEXT,
    MAX_BLIND_WATERMARK_BIT_LENGTH,
    MIN_BLIND_WATERMARK_BIT_LENGTH,
)


class BlindWatermarkOptionsTestCase(unittest.TestCase):
    def test_authenticated_payload_bit_length_includes_frame_overhead(self) -> None:
        for text in ("A", "图A", DEFAULT_BLIND_WATERMARK_TEXT):
            with self.subTest(text=text):
                options = BlindWatermarkOptions(text, 1, 2)
                expected_bytes = (
                    len(text.encode("utf-8")) + BLIND_WATERMARK_FRAME_OVERHEAD_BYTES
                )

                self.assertEqual(len(options.payload), expected_bytes)
                self.assertEqual(options.bit_length, expected_bytes * 8)

        self.assertEqual(
            BlindWatermarkOptions("A", 1, 2).bit_length,
            MIN_BLIND_WATERMARK_BIT_LENGTH,
        )

    def test_text_is_trimmed_and_bounded_by_utf8_bytes(self) -> None:
        options = BlindWatermarkOptions("  ID-123  ", 1, 2)
        self.assertEqual(options.text, "ID-123")

        with self.assertRaisesRegex(ValueError, "不能为空"):
            BlindWatermarkOptions("   ", 1, 2)
        with self.assertRaisesRegex(ValueError, "32 字节"):
            BlindWatermarkOptions("图" * 11, 1, 2)

    def test_passwords_must_be_positive_bounded_integers(self) -> None:
        for value in (0, -1, True, 2**32, 1.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "正整数"):
                    BlindWatermarkOptions("ID", value, 2)  # type: ignore[arg-type]

    def test_extract_bit_length_requires_a_supported_whole_byte(self) -> None:
        image = Image.new("RGB", (512, 512), "white")
        for bit_length in (
            0,
            MIN_BLIND_WATERMARK_BIT_LENGTH - 8,
            MIN_BLIND_WATERMARK_BIT_LENGTH - 1,
            MIN_BLIND_WATERMARK_BIT_LENGTH + 1,
            MAX_BLIND_WATERMARK_BIT_LENGTH + 8,
            True,
            8.5,
        ):
            with self.subTest(bit_length=bit_length):
                with self.assertRaisesRegex(ValueError, "8 的倍数"):
                    extract_blind_watermark(
                        image,
                        bit_length=bit_length,  # type: ignore[arg-type]
                        password_image=1,
                        password_watermark=2,
                    )

    def test_image_short_edge_and_dynamic_capacity_are_validated(self) -> None:
        options = BlindWatermarkOptions("ID", 1, 2)
        with self.assertRaisesRegex(ValueError, "256 像素"):
            embed_blind_watermark(Image.new("RGB", (255, 512)), options)

        with (
            patch.object(service, "MIN_BLIND_WATERMARK_IMAGE_EDGE", 1),
            self.assertRaisesRegex(ValueError, "容量不足"),
        ):
            service._validate_image(Image.new("RGB", (32, 32)), 256)


class BlindWatermarkDependencyTestCase(unittest.TestCase):
    def test_missing_dependency_has_clear_error(self) -> None:
        real_import = __import__

        def fail_import(name: str, *args: object, **kwargs: object):
            if name == "blind_watermark":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fail_import):
            with self.assertRaisesRegex(BlindWatermarkError, "组件未安装"):
                service._load_dependency()

    def test_wrong_dependency_version_has_clear_error(self) -> None:
        fake_module = types.ModuleType("blind_watermark")
        fake_module.WaterMark = object
        fake_module.__version__ = "9.9.9"
        fake_module.bw_notes = types.SimpleNamespace(close=lambda: None)
        with patch.dict(sys.modules, {"blind_watermark": fake_module}):
            with self.assertRaisesRegex(BlindWatermarkError, "版本不兼容"):
                service._load_dependency()


class BlindWatermarkBackendTestCase(unittest.TestCase):
    def test_embed_uses_fixed_engine_settings_and_utf8_bits(self) -> None:
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy is not installed")
        calls: dict[str, object] = {}

        class FakeEngine:
            def __init__(self, **kwargs: object) -> None:
                calls["init"] = kwargs

            def read_img(self, *, img: object) -> None:
                calls["image"] = img

            def read_wm(self, bits: object, *, mode: str) -> None:
                calls["bits"] = list(bits)  # type: ignore[arg-type]
                calls["mode"] = mode

            def embed(self):
                return calls["image"]

        image = Image.new("RGB", (512, 512), (10, 20, 30))
        options = BlindWatermarkOptions("图A", 11, 22)
        with patch.object(service, "_load_dependency", return_value=(numpy, FakeEngine)):
            result = embed_blind_watermark(image, options)

        self.assertEqual(
            calls["init"],
            {
                "password_img": 11,
                "password_wm": 22,
                "mode": "common",
                "processes": 1,
            },
        )
        self.assertEqual(calls["mode"], "bit")
        self.assertEqual(len(calls["bits"]), options.bit_length)
        self.assertEqual(result.mode, "RGB")

    def test_extract_uses_explicit_bit_length_and_decodes_utf8(self) -> None:
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy is not installed")
        calls: dict[str, object] = {}
        expected = "图A"
        options = BlindWatermarkOptions(expected, 11, 22)
        expected_bits = numpy.unpackbits(
            numpy.frombuffer(options.payload, dtype=numpy.uint8)
        ).astype(float)

        class FakeEngine:
            def __init__(self, **kwargs: object) -> None:
                calls["init"] = kwargs

            def extract(self, **kwargs: object):
                calls["extract"] = kwargs
                return expected_bits

        with patch.object(service, "_load_dependency", return_value=(numpy, FakeEngine)):
            result = extract_blind_watermark(
                Image.new("RGB", (512, 512), (10, 20, 30)),
                bit_length=options.bit_length,
                password_image=options.password_image,
                password_watermark=options.password_watermark,
            )

        self.assertEqual(result, expected)
        self.assertEqual(
            calls["init"],
            {
                "password_img": 11,
                "password_wm": 22,
                "mode": "common",
                "processes": 1,
            },
        )
        extract_call = calls["extract"]
        self.assertEqual(extract_call["wm_shape"], options.bit_length)  # type: ignore[index]
        self.assertEqual(extract_call["mode"], "bit")  # type: ignore[index]

    def test_extract_rejects_an_unexpected_result_length(self) -> None:
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy is not installed")

        class FakeEngine:
            def __init__(self, **_kwargs: object) -> None:
                pass

            def extract(self, **_kwargs: object):
                return numpy.ones(7)

        options = BlindWatermarkOptions("A", 1, 2)
        with patch.object(service, "_load_dependency", return_value=(numpy, FakeEngine)):
            with self.assertRaisesRegex(
                BlindWatermarkError,
                rf"返回 7 位，预期 {options.bit_length} 位",
            ):
                extract_blind_watermark(
                    Image.new("RGB", (512, 512)),
                    bit_length=options.bit_length,
                    password_image=options.password_image,
                    password_watermark=options.password_watermark,
                )

    def test_rgba_alpha_channel_is_preserved_exactly(self) -> None:
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy is not installed")

        class FakeEngine:
            def __init__(self, **_kwargs: object) -> None:
                self.image = None

            def read_img(self, *, img: object) -> None:
                self.image = img

            def read_wm(self, _bits: object, *, mode: str) -> None:
                self.mode = mode

            def embed(self):
                return self.image

        image = Image.new("RGBA", (512, 512), (10, 20, 30, 0))
        alpha = Image.new("L", image.size)
        alpha.putdata([(x + y) % 256 for y in range(512) for x in range(512)])
        image.putalpha(alpha)
        with patch.object(service, "_load_dependency", return_value=(numpy, FakeEngine)):
            result = embed_blind_watermark(image, BlindWatermarkOptions("ID", 1, 2))

        self.assertEqual(result.mode, "RGBA")
        self.assertEqual(result.getchannel("A").tobytes(), alpha.tobytes())

    def test_paths_are_supported_and_exif_orientation_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "source.png"
            Image.new("RGB", (512, 300), "white").save(path)
            loaded = service._load_image(path)

        self.assertEqual(loaded.size, (512, 300))

    def test_third_party_failures_are_wrapped_in_chinese(self) -> None:
        try:
            import numpy
        except ImportError:
            self.skipTest("numpy is not installed")

        class BrokenEngine:
            def __init__(self, **_kwargs: object) -> None:
                raise RuntimeError("boom")

        with patch.object(service, "_load_dependency", return_value=(numpy, BrokenEngine)):
            with self.assertRaisesRegex(BlindWatermarkError, "盲水印嵌入失败：boom"):
                embed_blind_watermark(
                    Image.new("RGB", (512, 512)),
                    BlindWatermarkOptions("ID", 1, 2),
                )


class BlindWatermarkIntegrationTestCase(unittest.TestCase):
    def test_real_dependency_round_trip_when_available(self) -> None:
        try:
            service._load_dependency()
        except BlindWatermarkError:
            self.skipTest("blind-watermark 0.4.4 and dependencies are not installed")

        width = height = 256
        image = Image.new("RGB", (width, height))
        image.putdata(
            [
                (
                    (x * 13 + y * 3) % 256,
                    (x * 5 + y * 11) % 256,
                    (x * 7 + y * 17) % 256,
                )
                for y in range(height)
                for x in range(width)
            ]
        )
        options = BlindWatermarkOptions("A", 31415, 27182)

        embedded = embed_blind_watermark(image, options)
        extracted = extract_blind_watermark(
            embedded,
            bit_length=options.bit_length,
            password_image=options.password_image,
            password_watermark=options.password_watermark,
        )

        self.assertEqual(extracted, options.text)


if __name__ == "__main__":
    unittest.main()
