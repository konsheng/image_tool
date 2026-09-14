from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible, QAccessibleActionInterface
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qfluentwidgets import CardWidget

from config import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    PROJECT_ISSUES_URL,
    PROJECT_RELEASES_URL,
    PROJECT_URL,
    REFERENCE_NOTICE_FONT_NAME,
)
from gui import (
    ABOUT_CONTENT_MAX_WIDTH,
    AboutActionButton,
    AboutPage,
    OpenSourceLicenseDialog,
)


class AboutPageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def process_events(self, cycles: int = 6) -> None:
        for _ in range(cycles):
            self.app.processEvents()

    def make_page(self, width: int = 1200, height: int = 720) -> AboutPage:
        page = AboutPage()
        page.resize(width, height)
        page.show()
        self.process_events()
        return page

    def close_page(self, page: AboutPage) -> None:
        page.close()
        page.deleteLater()
        self.process_events()

    def test_selected_layout_has_text_identity_and_one_main_panel(self) -> None:
        page = self.make_page()
        try:
            self.assertEqual(page.product_title_label.text(), APP_NAME)
            self.assertEqual(
                page.tagline_label.text(),
                "本地、批量、可预览的图片处理工具",
            )
            self.assertEqual(page.version_label.text(), APP_VERSION)
            self.assertEqual(page.author_label.text(), APP_AUTHOR)
            self.assertEqual(page.privacy_title_label.text(), "隐私与安全")
            self.assertEqual(page.privacy_lead_label.text(), "所有图片均在本机完成处理")
            self.assertEqual(page.no_overwrite_label.text(), "输出文件不会覆盖原图")
            self.assertEqual(page.no_path_storage_label.text(), "不保存图片名称或路径")
            self.assertEqual(
                page.memo_storage_label.text(),
                "备忘录仅保存在用户指定的本地目录",
            )
            self.assertEqual(
                page.font_license_label.text(),
                f"参考图提示字体：{REFERENCE_NOTICE_FONT_NAME} · Adobe · SIL OFL 1.1",
            )
            self.assertEqual(page.support_title_label.text(), "帮助与支持")
            self.assertEqual(
                page.footer_label.text(),
                f"{APP_NAME}  ·  {APP_VERSION}  ·  {APP_AUTHOR}",
            )

            direct_panels = [
                child
                for child in page.content_widget.findChildren(CardWidget)
                if child.parent() is page.content_widget
            ]
            self.assertEqual(direct_panels, [page.about_panel])
            self.assertNotIsInstance(page.product_title_label.parent(), CardWidget)
            self.assertEqual(len(page.action_cards), 4)
            self.assertTrue(
                all(isinstance(card, AboutActionButton) for card in page.action_cards)
            )
            self.assertEqual(
                [card.accessibleName() for card in page.action_cards],
                ["项目主页", "查看最新版本", "反馈问题", "复制版本信息"],
            )
            visible_text = "\n".join(
                label.text() for label in page.findChildren(type(page.footer_label))
            )
            self.assertNotIn("图片导入、尺寸处理", visible_text)
            self.assertLessEqual(page.content_widget.width(), ABOUT_CONTENT_MAX_WIDTH)
            self.assertEqual(page.content_widget.width(), ABOUT_CONTENT_MAX_WIDTH)
        finally:
            self.close_page(page)

    def test_content_and_two_column_actions_fit_at_minimum_window_viewport(self) -> None:
        page = self.make_page(width=870, height=672)
        try:
            margins = page.layout().contentsMargins()
            available_width = page.width() - margins.left() - margins.right()
            self.assertLessEqual(page.content_widget.width(), available_width)
            self.assertLess(page.project_action.geometry().right(), page.release_action.geometry().left())
            self.assertLess(page.feedback_action.geometry().right(), page.copy_version_action.geometry().left())
            for action in page.action_cards:
                self.assertTrue(page.about_panel.rect().contains(action.geometry()))
                self.assertGreaterEqual(
                    action.text_label.width(),
                    action.text_label.sizeHint().width(),
                )
        finally:
            self.close_page(page)

    def test_external_actions_open_the_expected_urls(self) -> None:
        page = self.make_page()
        try:
            for action, expected_url in (
                (page.project_action, PROJECT_URL),
                (page.release_action, PROJECT_RELEASES_URL),
                (page.feedback_action, PROJECT_ISSUES_URL),
            ):
                with self.subTest(action=action.accessibleName()):
                    with patch("gui.QDesktopServices.openUrl", return_value=True) as open_url:
                        QTest.mouseClick(action, Qt.LeftButton)
                        self.process_events()
                    open_url.assert_called_once()
                    self.assertEqual(open_url.call_args.args[0].toString(), expected_url)
        finally:
            self.close_page(page)

    def test_actions_expose_button_accessibility_and_ignore_right_click(self) -> None:
        page = self.make_page()
        try:
            interface = QAccessible.queryAccessibleInterface(page.project_action)
            self.assertIsNotNone(interface)
            self.assertEqual(interface.role(), QAccessible.Role.Button)
            action_interface = interface.actionInterface()
            self.assertIsNotNone(action_interface)
            self.assertIn(
                QAccessibleActionInterface.pressAction(),
                action_interface.actionNames(),
            )

            with patch("gui.QDesktopServices.openUrl", return_value=True) as open_url:
                QTest.mouseClick(page.project_action, Qt.RightButton)
                self.process_events()
            open_url.assert_not_called()
        finally:
            self.close_page(page)

    def test_action_tab_order_follows_the_visual_grid(self) -> None:
        page = self.make_page()
        try:
            for action in page.action_cards:
                self.assertTrue(action.focusPolicy() & Qt.TabFocus)

            page.project_action.setFocus()
            for expected in (
                page.release_action,
                page.feedback_action,
                page.copy_version_action,
            ):
                QTest.keyClick(QApplication.focusWidget(), Qt.Key_Tab)
                self.process_events()
                self.assertIs(QApplication.focusWidget(), expected)
        finally:
            self.close_page(page)

    def test_actions_support_keyboard_and_copy_version_information(self) -> None:
        page = self.make_page()
        try:
            for key in (Qt.Key_Return, Qt.Key_Enter):
                with self.subTest(key=key):
                    with patch(
                        "gui.QDesktopServices.openUrl",
                        return_value=True,
                    ) as open_url:
                        page.project_action.setFocus()
                        QTest.keyClick(page.project_action, key)
                        self.process_events()
                    self.assertTrue(page.project_action.hasFocus())
                    open_url.assert_called_once()
                    self.assertEqual(
                        open_url.call_args.args[0].toString(),
                        PROJECT_URL,
                    )

            with patch.object(page, "_show_message") as show_message:
                page.copy_version_action.setFocus()
                QTest.keyClick(page.copy_version_action, Qt.Key_Space)
                self.process_events()
            self.assertEqual(
                QApplication.clipboard().text(),
                f"{APP_NAME} {APP_VERSION}\n作者：{APP_AUTHOR}",
            )
            show_message.assert_called_once_with("success", "版本信息已复制")
        finally:
            self.close_page(page)

    def test_bundled_font_license_is_available_from_about_page(self) -> None:
        page = self.make_page()
        try:
            with patch("gui.OpenSourceLicenseDialog") as dialog_class:
                QTest.mouseClick(page.font_license_button, Qt.LeftButton)
                self.process_events()
            dialog_class.assert_called_once()
            license_text = dialog_class.call_args.args[0]
            self.assertIn("Copyright 2014-2025 Adobe", license_text)
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", license_text)
            dialog_class.return_value.exec.assert_called_once_with()
        finally:
            self.close_page(page)

    def test_missing_font_license_reports_an_error(self) -> None:
        page = self.make_page()
        try:
            with (
                patch("gui.resource_path", return_value=Path("missing-license.txt")),
                patch.object(page, "_show_message") as show_message,
            ):
                page.font_license_button.click()
            show_message.assert_called_once_with("error", "开源字体许可证文件缺失")
        finally:
            self.close_page(page)

    def test_unreadable_font_license_reports_an_error(self) -> None:
        page = self.make_page()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                invalid_license = Path(temp_dir) / "LICENSE.txt"
                invalid_license.write_bytes(b"\xff\xfe\xfa")
                with (
                    patch("gui.resource_path", return_value=invalid_license),
                    patch.object(page, "_show_message") as show_message,
                ):
                    page.font_license_button.click()
            show_message.assert_called_once_with(
                "error",
                "开源字体许可证文件无法读取",
            )
        finally:
            self.close_page(page)

    def test_failed_browser_open_reports_an_error(self) -> None:
        page = self.make_page()
        try:
            with (
                patch("gui.QDesktopServices.openUrl", return_value=False),
                patch.object(page, "_show_message") as show_message,
            ):
                page.feedback_action.clicked.emit()
            show_message.assert_called_once_with("error", "无法打开浏览器")
        finally:
            self.close_page(page)


if __name__ == "__main__":
    unittest.main()
