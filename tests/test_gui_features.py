from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QSize
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListView, QListWidgetItem
from qfluentwidgets import qrouter

from config import (
    COMPREHENSIVE_FEATURE_DEFAULTS,
    CUSTOM_SIZE_LABEL,
    DEFAULT_MANUAL_QUALITY,
    FEATURE_DEFAULTS,
    MAX_OUTPUT_DIMENSION,
    MAX_OUTPUT_PIXELS,
)
from gui import (
    AdaptiveLogoListWidget,
    COMPREHENSIVE_FEATURES,
    ImageListItem,
    ImageOperationPage,
    ImageToolWindow,
    LOGO_RULE_CUSTOM,
    MODE_COMPRESS,
    MODE_COMPREHENSIVE,
    MODE_FORMAT,
    MODE_LOGO,
    MODE_RESIZE,
    MODE_WATERMARK,
    PageSettings,
    comprehensive_feature_setting_key,
    feature_setting_key,
)
from logo_manager import LogoAsset


class GuiFeatureTestCase(unittest.TestCase):
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

    def test_page_and_comprehensive_feature_defaults_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window, _ = self.make_window(Path(temp_dir) / "settings.ini")
            try:
                self.assertEqual(window.feature_states, FEATURE_DEFAULTS)
                self.assertEqual(
                    window.comprehensive_feature_states,
                    COMPREHENSIVE_FEATURE_DEFAULTS,
                )
                for page in (window.comprehensive_page, window.compress_page):
                    self.assertFalse(hasattr(page, "warning_label"))
                    self.assertEqual(page.quality_slider.value(), DEFAULT_MANUAL_QUALITY)
                    self.assertEqual(page.quality_spinbox.value(), DEFAULT_MANUAL_QUALITY)
                    self.assertEqual(page.quality_spinbox.text(), str(DEFAULT_MANUAL_QUALITY))
                self.assertFalse(page.quality_reset_button.isEnabled())
                self.assertTrue(window.feature_nav_items[MODE_WATERMARK].isHidden())
                self.assertTrue(
                    window.comprehensive_page.feature_sections[MODE_WATERMARK].isHidden()
                )

                window.settings_page.comprehensive_feature_switches[
                    MODE_WATERMARK
                ].setChecked(True)
                self.process_events()
                self.assertTrue(window.feature_nav_items[MODE_WATERMARK].isHidden())
                self.assertFalse(
                    window.comprehensive_page.feature_sections[MODE_WATERMARK].isHidden()
                )

                window.comprehensive_page.watermark_checkbox.setChecked(True)
                self.assertTrue(window.comprehensive_page._get_apply_watermark())
                watermark_options, watermark_error = (
                    window.comprehensive_page._get_watermark_options()
                )
                self.assertIsNotNone(watermark_options)
                self.assertIsNone(watermark_error)

                for feature in (
                    MODE_COMPREHENSIVE,
                    MODE_RESIZE,
                    MODE_FORMAT,
                    MODE_COMPRESS,
                    MODE_LOGO,
                ):
                    self.assertFalse(window.feature_nav_items[feature].isHidden())
            finally:
                self.close_window(window)

    def test_page_and_comprehensive_switches_are_independent_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.ini"
            window, settings = self.make_window(settings_path)
            try:
                expected_page_states = dict(FEATURE_DEFAULTS)
                expected_page_states.update(
                    {
                        MODE_RESIZE: False,
                        MODE_FORMAT: True,
                        MODE_COMPRESS: False,
                        MODE_LOGO: True,
                        MODE_WATERMARK: True,
                    }
                )
                expected_comprehensive_states = {
                    MODE_RESIZE: True,
                    MODE_FORMAT: False,
                    MODE_COMPRESS: True,
                    MODE_LOGO: False,
                    MODE_WATERMARK: False,
                }
                for feature, enabled in expected_page_states.items():
                    window.settings_page.feature_switches[feature].setChecked(enabled)
                for feature, enabled in expected_comprehensive_states.items():
                    window.settings_page.comprehensive_feature_switches[feature].setChecked(
                        enabled
                    )
                self.process_events()

                page = window.comprehensive_page
                self.assertEqual(window.feature_states, expected_page_states)
                self.assertEqual(
                    window.comprehensive_feature_states,
                    expected_comprehensive_states,
                )
                for feature, enabled in expected_page_states.items():
                    self.assertEqual(
                        window.feature_nav_items[feature].isHidden(),
                        not enabled,
                    )
                    self.assertEqual(window.feature_pages[feature].isEnabled(), enabled)
                for feature, enabled in expected_comprehensive_states.items():
                    self.assertEqual(page.is_feature_enabled(feature), enabled)
                    self.assertEqual(page.feature_sections[feature].isHidden(), not enabled)
                self.assertIsNotNone(page._get_output_size())
                self.assertEqual(page._get_output_choice(), "保持原格式")
                self.assertEqual(page._get_manual_quality(), DEFAULT_MANUAL_QUALITY)
                self.assertFalse(page._get_apply_logo())
                self.assertFalse(page._get_apply_watermark())
                self.assertFalse(page.output_card.isHidden())
                page_settings = page._get_page_settings()
                self.assertIsNotNone(page_settings)
                assert page_settings is not None
                self.assertIsNotNone(page_settings.output_size)
                self.assertEqual(page_settings.output_choice, "保持原格式")
                self.assertEqual(page_settings.quality, DEFAULT_MANUAL_QUALITY)
                self.assertFalse(page_settings.apply_logo)
                self.assertIsNone(page_settings.watermark_options)

                settings.sync()
            finally:
                self.close_window(window)

            restored, _ = self.make_window(settings_path)
            try:
                self.assertEqual(restored.feature_states, expected_page_states)
                self.assertEqual(
                    restored.comprehensive_feature_states,
                    expected_comprehensive_states,
                )
                for feature, enabled in expected_comprehensive_states.items():
                    self.assertEqual(
                        restored.comprehensive_page.is_feature_enabled(feature),
                        enabled,
                    )
                    self.assertEqual(
                        restored.comprehensive_page.feature_sections[feature].isHidden(),
                        not enabled,
                    )
            finally:
                self.close_window(restored)

    def test_legacy_global_switches_are_migrated_once_then_decoupled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.ini"
            legacy_settings = QSettings(str(settings_path), QSettings.IniFormat)
            legacy_settings.setValue(feature_setting_key(MODE_RESIZE), False)
            legacy_settings.setValue(feature_setting_key(MODE_WATERMARK), True)
            legacy_settings.sync()

            window, settings = self.make_window(settings_path)
            try:
                self.assertFalse(window.feature_states[MODE_RESIZE])
                self.assertTrue(window.feature_states[MODE_WATERMARK])
                self.assertFalse(window.comprehensive_feature_states[MODE_RESIZE])
                self.assertTrue(window.comprehensive_feature_states[MODE_WATERMARK])
                for feature in COMPREHENSIVE_FEATURES:
                    self.assertTrue(
                        settings.contains(comprehensive_feature_setting_key(feature))
                    )

                window.settings_page.feature_switches[MODE_RESIZE].setChecked(True)
                window.settings_page.feature_switches[MODE_WATERMARK].setChecked(False)
                self.process_events()
                settings.sync()
            finally:
                self.close_window(window)

            restored, _ = self.make_window(settings_path)
            try:
                self.assertTrue(restored.feature_states[MODE_RESIZE])
                self.assertFalse(restored.feature_states[MODE_WATERMARK])
                self.assertFalse(restored.comprehensive_feature_states[MODE_RESIZE])
                self.assertTrue(restored.comprehensive_feature_states[MODE_WATERMARK])
            finally:
                self.close_window(restored)

    def test_disabling_current_or_all_pages_keeps_settings_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            window, _ = self.make_window(Path(temp_dir) / "settings.ini")
            try:
                stacked_count = window.stackedWidget.count()
                window.switchTo(window.logo_page)
                window.switchTo(window.settings_page)
                window.settings_page.feature_switches[MODE_LOGO].setChecked(False)
                self.process_events()
                self.assertIsNot(window.stackedWidget.currentWidget(), window.logo_page)
                self.assertFalse(window.logo_page.isEnabled())
                stack_history = qrouter.stackHistories[window.stackedWidget]
                self.assertNotIn(window.logo_page.objectName(), stack_history.history)
                self.assertFalse(
                    any(
                        item.stacked is window.stackedWidget
                        and item.routeKey == window.logo_page.objectName()
                        for item in qrouter.history
                    )
                )
                window.navigationInterface.panel.returnButton.click()
                QTest.qWait(400)
                self.process_events()
                self.assertIsNot(window.stackedWidget.currentWidget(), window.logo_page)

                for switch in window.settings_page.feature_switches.values():
                    switch.setChecked(False)
                self.process_events()
                self.assertIs(window.stackedWidget.currentWidget(), window.settings_page)
                self.assertFalse(
                    window.navigationInterface.widget(window.settings_page.objectName()).isHidden()
                )

                watermark_switch = window.settings_page.feature_switches[MODE_WATERMARK]
                for _ in range(10):
                    watermark_switch.setChecked(not watermark_switch.isChecked())
                self.process_events()
                self.assertEqual(window.stackedWidget.count(), stacked_count)
            finally:
                self.close_window(window)

    def test_disabled_default_route_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.ini"
            settings = QSettings(str(settings_path), QSettings.IniFormat)
            settings.setValue("features/comprehensive/enabled", False)
            settings.sync()

            window, _ = self.make_window(settings_path)
            try:
                stack_history = qrouter.stackHistories[window.stackedWidget]
                self.assertNotEqual(
                    stack_history.defaultRouteKey,
                    window.comprehensive_page.objectName(),
                )
                self.assertIsNot(
                    window.stackedWidget.currentWidget(),
                    window.comprehensive_page,
                )
                self.assertFalse(window.comprehensive_page.isEnabled())
            finally:
                self.close_window(window)

    def test_logo_grid_height_adapts_to_rows_and_is_bounded(self) -> None:
        page = ImageOperationPage("LOGO", MODE_LOGO, "logoAdaptiveTest")
        try:
            page.resize(1060, 820)
            page.show()
            self.process_events()
            for row in range(page.logo_list.count()):
                item = page.logo_list.item(row)
                self.assertLessEqual(
                    page.logo_list.visualItemRect(item).height(),
                    page.logo_list.gridSize().height(),
                )
                if page.logo_assets:
                    self.assertFalse(item.icon().isNull())
            page.logo_list.clear()
            page.logo_list.addItem(QListWidgetItem("one-row"))
            page.logo_list.sync_height()
            self.process_events()
            one_row_height = page.logo_list.height()
            self.assertLessEqual(page.logo_card.height(), 300)

            page.resize(800, 820)
            for index in range(3):
                page.logo_list.addItem(QListWidgetItem(f"second-row-{index}"))
            page.logo_list.sync_height()
            self.process_events()
            two_row_height = page.logo_list.height()
            self.assertGreater(two_row_height, one_row_height)

            for index in range(8):
                page.logo_list.addItem(QListWidgetItem(f"extra-{index}"))
            page.logo_list.sync_height()
            page.logo_list.doItemsLayout()
            self.process_events()
            self.assertEqual(page.logo_list.height(), two_row_height)
            self.assertGreater(page.logo_list.verticalScrollBar().maximum(), 0)
        finally:
            page.shutdown()
            page.close()
            page.deleteLater()
            self.process_events()

    def test_logo_display_indexes_are_omitted_from_generated_filenames(self) -> None:
        page = ImageOperationPage("LOGO", MODE_LOGO, "logoFilenameTest")
        assets = [
            LogoAsset(name="01生润食品", path=Path("01生润食品.png")),
            LogoAsset(name="02冰润鲜", path=Path("02冰润鲜.png")),
        ]
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                source = Path(temp_dir) / "原图.jpg"
                page.items = [
                    ImageListItem(
                        path=source,
                        image_format="JPG",
                        dimensions="100 × 100",
                        size_text="1KB",
                        logo_rule=LOGO_RULE_CUSTOM,
                        logo_assets=assets,
                    )
                ]

                page.choose_save_radio.setChecked(True)
                chosen_default_path: list[Path] = []

                def choose_default_path(*args):
                    default_path = Path(args[2])
                    chosen_default_path.append(default_path)
                    return str(default_path), ""

                with patch(
                    "gui.QFileDialog.getSaveFileName",
                    side_effect=choose_default_path,
                ):
                    self.assertTrue(page._choose_save_location())

                self.assertEqual(
                    chosen_default_path[0].name,
                    "原图_生润食品_冰润鲜.jpg",
                )

                page.original_save_radio.setChecked(True)
                settings = PageSettings(
                    output_size=None,
                    output_choice="保持原格式",
                    quality=None,
                    apply_logo=True,
                    logo_assets=assets,
                    watermark_options=None,
                )
                tasks = page._prepare_tasks(settings)

                self.assertEqual(tasks[0].output_path.name, "原图_生润食品_冰润鲜.jpg")
                self.assertEqual([asset.name for asset in assets], ["01生润食品", "02冰润鲜"])
        finally:
            page.shutdown()
            page.close()
            page.deleteLater()
            self.process_events()

    def test_feature_controls_resync_after_processing_cycle(self) -> None:
        page = ImageOperationPage("综合处理", MODE_COMPREHENSIVE, "featureStateCycleTest")
        try:
            page.watermark_checkbox.setChecked(True)
            page._update_compression_controls_state()
            page._update_watermark_controls_state()
            self.assertTrue(page.quality_slider.isEnabled())
            self.assertTrue(page.watermark_type_combo.isEnabled())

            page.quality_slider.setValue(73)
            self.process_events()
            self.assertTrue(page.quality_reset_button.isEnabled())

            page.set_feature_enabled(MODE_COMPRESS, False)
            page.set_feature_enabled(MODE_WATERMARK, False)
            self.assertFalse(page.quality_slider.isEnabled())
            self.assertFalse(page.quality_spinbox.isEnabled())
            self.assertFalse(page.quality_reset_button.isEnabled())
            page._set_processing_state(True)
            page._set_processing_state(False)
            page.set_feature_enabled(MODE_COMPRESS, True)
            page.set_feature_enabled(MODE_WATERMARK, True)

            self.assertTrue(page.quality_slider.isEnabled())
            self.assertTrue(page.quality_spinbox.isEnabled())
            self.assertTrue(page.quality_reset_button.isEnabled())
            self.assertTrue(page.watermark_checkbox.isChecked())
            self.assertTrue(page.watermark_type_combo.isEnabled())
            self.assertTrue(page.watermark_text_edit.isEnabled())

            page._set_processing_state(True)
            self.assertFalse(page.quality_reset_button.isEnabled())
            page._set_processing_state(False)
            self.assertTrue(page.quality_reset_button.isEnabled())
        finally:
            page.shutdown()
            page.close()
            page.deleteLater()
            self.process_events()

    def test_custom_output_size_is_bounded_before_processing(self) -> None:
        page = ImageOperationPage("尺寸处理", MODE_RESIZE, "boundedOutputSizeTest")
        try:
            self.assertTrue(page.custom_size_container.isHidden())

            page.size_combo.setCurrentText(CUSTOM_SIZE_LABEL)
            self.process_events()
            self.assertFalse(page.custom_size_container.isHidden())
            self.assertTrue(page.custom_width_edit.isEnabled())
            self.assertTrue(page.custom_height_edit.isEnabled())

            page.custom_width_edit.setText(str(MAX_OUTPUT_DIMENSION + 1))
            page.custom_height_edit.setText("1")
            self.assertIsNone(page._get_output_size())

            page.custom_width_edit.setText(str(MAX_OUTPUT_DIMENSION))
            page.custom_height_edit.setText(
                str(MAX_OUTPUT_PIXELS // MAX_OUTPUT_DIMENSION + 1)
            )
            self.assertIsNone(page._get_output_size())

            page.custom_width_edit.setText("8000")
            page.custom_height_edit.setText("4000")
            self.assertEqual(page._get_output_size(), (8000, 4000))

            page.size_combo.setCurrentIndex(0)
            self.process_events()
            self.assertTrue(page.custom_size_container.isHidden())

            page.size_combo.setCurrentText(CUSTOM_SIZE_LABEL)
            self.process_events()
            self.assertFalse(page.custom_size_container.isHidden())
            self.assertEqual(page.custom_width_edit.text(), "8000")
            self.assertEqual(page.custom_height_edit.text(), "4000")

            page._set_processing_state(True)
            self.assertFalse(page.custom_size_container.isHidden())
            self.assertFalse(page.custom_width_edit.isEnabled())
            self.assertFalse(page.custom_height_edit.isEnabled())

            page._set_processing_state(False)
            self.assertFalse(page.custom_size_container.isHidden())
            self.assertTrue(page.custom_width_edit.isEnabled())
            self.assertTrue(page.custom_height_edit.isEnabled())
        finally:
            page.shutdown()
            page.close()
            page.deleteLater()
            self.process_events()

    def test_quality_slider_shows_live_numeric_value(self) -> None:
        page = ImageOperationPage("图片压缩", MODE_COMPRESS, "qualityPercentageTest")
        try:
            page.quality_slider.setValue(73)
            self.process_events()
            self.assertEqual(page.quality_spinbox.value(), 73)
            self.assertEqual(page.quality_spinbox.text(), "73")
            self.assertTrue(page.quality_reset_button.isEnabled())
            self.assertGreaterEqual(
                page.quality_spinbox.width(),
                page.quality_spinbox.minimumSizeHint().width(),
            )

            page.quality_reset_button.click()
            self.process_events()
            self.assertEqual(page.quality_slider.value(), DEFAULT_MANUAL_QUALITY)
            self.assertEqual(page.quality_spinbox.value(), DEFAULT_MANUAL_QUALITY)
            self.assertFalse(page.quality_reset_button.isEnabled())

            page.quality_spinbox.setValue(41)
            self.process_events()
            self.assertEqual(page.quality_slider.value(), 41)
            self.assertEqual(page.quality_spinbox.text(), "41")
            self.assertTrue(page.quality_reset_button.isEnabled())
            expected_handle_x = int(
                (41 - page.quality_slider.minimum())
                / (page.quality_slider.maximum() - page.quality_slider.minimum())
                * page.quality_slider.grooveLength
            )
            self.assertEqual(page.quality_slider.handle.x(), expected_handle_x)
        finally:
            page.shutdown()
            page.close()
            page.deleteLater()
            self.process_events()

    def test_png_outputs_hide_quality_controls_without_losing_value(self) -> None:
        comprehensive = ImageOperationPage(
            "综合处理",
            MODE_COMPREHENSIVE,
            "pngQualityVisibilityComprehensiveTest",
        )
        compression = ImageOperationPage(
            "图片压缩",
            MODE_COMPRESS,
            "pngQualityVisibilityCompressionTest",
        )
        try:
            comprehensive.quality_slider.setValue(73)
            comprehensive.output_format_combo.setCurrentText("PNG")
            self.process_events()
            self.assertTrue(comprehensive.quality_controls_container.isHidden())
            self.assertFalse(comprehensive.quality_reset_button.isEnabled())
            self.assertEqual(comprehensive._get_manual_quality(), 73)
            self.assertIn("PNG", comprehensive.compression_hint_label.text())
            self.assertIn("无损", comprehensive.compression_hint_label.text())

            comprehensive.output_format_combo.setCurrentText("JPG")
            self.process_events()
            self.assertFalse(comprehensive.quality_controls_container.isHidden())
            self.assertEqual(comprehensive.quality_spinbox.value(), 73)
            self.assertTrue(comprehensive.quality_reset_button.isEnabled())

            compression.quality_slider.setValue(73)
            self.assertFalse(compression.quality_controls_container.isHidden())
            compression.items = [
                ImageListItem(Path("only.png"), "PNG", "100 × 100", "1KB")
            ]
            compression._update_compression_controls_state()
            self.assertTrue(compression.quality_controls_container.isHidden())
            self.assertFalse(compression.quality_reset_button.isEnabled())
            self.assertEqual(compression._get_manual_quality(), 73)

            compression.items.append(
                ImageListItem(Path("also.jpg"), "JPG", "100 × 100", "1KB")
            )
            compression._update_compression_controls_state()
            self.assertFalse(compression.quality_controls_container.isHidden())
            self.assertEqual(compression.quality_spinbox.value(), 73)
            self.assertTrue(compression.quality_reset_button.isEnabled())
            self.assertIn("批量任务包含 PNG", compression.compression_hint_label.text())

            compression.items.pop()
            compression._update_compression_controls_state()
            self.assertTrue(compression.quality_controls_container.isHidden())

            compression.items.append(
                ImageListItem(Path("fallback.bmp"), "BMP", "100 × 100", "1KB")
            )
            compression._update_compression_controls_state()
            self.assertFalse(compression.quality_controls_container.isHidden())
            self.assertTrue(compression.quality_reset_button.isEnabled())
        finally:
            for page in (comprehensive, compression):
                page.shutdown()
                page.close()
                page.deleteLater()
            self.process_events()

    def test_logo_grid_exact_width_boundaries_match_qt_layout(self) -> None:
        widget = AdaptiveLogoListWidget()
        try:
            widget.setViewMode(QListView.IconMode)
            widget.setResizeMode(QListView.Adjust)
            widget.setMovement(QListView.Static)
            widget.setGridSize(QSize(140, 60))
            for index in range(3):
                widget.addItem(QListWidgetItem(f"logo-{index}"))
            widget.show()
            self.process_events()

            frame_width = widget.frameWidth() * 2
            widget.setFixedWidth(420 + frame_width)
            widget.sync_height()
            widget.doItemsLayout()
            self.process_events()
            self.assertEqual(widget.height(), 120 + frame_width)
            self.assertEqual(widget.verticalScrollBar().maximum(), 0)

            widget.setFixedWidth(421 + frame_width)
            widget.sync_height()
            widget.doItemsLayout()
            self.process_events()
            self.assertEqual(widget.height(), 60 + frame_width)
            self.assertEqual(widget.verticalScrollBar().maximum(), 0)
            self.assertEqual(widget.horizontalScrollBar().maximum(), 0)
        finally:
            widget.close()
            widget.deleteLater()
            self.process_events()


if __name__ == "__main__":
    unittest.main()
