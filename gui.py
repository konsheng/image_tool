from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image
from PySide6.QtCore import QEasingCurve, QObject, QPoint, QRect, QSettings, QSize, Qt, QThread, QUrl, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QCursor, QDesktopServices, QDragEnterEvent, QDropEvent, QIcon, QMouseEvent, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QListWidgetItem,
    QSizePolicy,
    QSpacerItem,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    FluentStyleSheet,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    NavigationItemPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    RadioButton,
    SmoothScrollArea,
    TableWidget,
    Theme,
    TransparentToolButton,
    isDarkTheme,
    setTheme,
)

from config import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    CUSTOM_SIZE_LABEL,
    DEFAULT_WATERMARK_ANGLE,
    DEFAULT_WATERMARK_COLOR,
    DEFAULT_WATERMARK_FONT_SIZE,
    DEFAULT_WATERMARK_IMAGE_SCALE,
    DEFAULT_WATERMARK_MARGIN,
    DEFAULT_WATERMARK_OFFSET_X,
    DEFAULT_WATERMARK_OFFSET_Y,
    DEFAULT_WATERMARK_OPACITY,
    DEFAULT_WATERMARK_POSITION,
    DEFAULT_WATERMARK_TEXT,
    DEFAULT_WATERMARK_TILE_OFFSET_X,
    DEFAULT_WATERMARK_TILE_OFFSET_Y,
    DEFAULT_WATERMARK_TILE_SPACING_X,
    DEFAULT_WATERMARK_TILE_SPACING_Y,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_SIZE,
    DEFAULT_TARGET_SIZE_LABEL,
    KEEP_ORIGINAL_FORMAT,
    OUTPUT_FORMATS,
    OUTPUT_SIZE_PRESETS,
    STATUS_CANCELED,
    STATUS_EXCEEDED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCESS,
    TABLE_HEADERS,
    TARGET_SIZE_OPTIONS,
    WATERMARK_COLORS,
    WATERMARK_POSITION_CUSTOM,
    WATERMARK_POSITION_TILE,
    WATERMARK_POSITIONS,
    WATERMARK_TYPE_IMAGE,
    WATERMARK_TYPE_TEXT,
    WATERMARK_TYPES,
    size_to_text,
)
from file_utils import (
    build_default_output_path,
    bytes_to_display,
    ensure_suffix,
    ensure_unique_path,
    format_dimensions,
    is_supported_image,
    resolve_output_format,
)
from image_processor import (
    ProcessOptions,
    WatermarkOptions,
    create_watermark_layer,
    get_image_info,
    process_image,
    render_preview_image,
    watermark_position_for_layer,
)
from logo_manager import LogoAsset, list_logo_assets, load_logo_assets


MODE_COMPREHENSIVE = "comprehensive"
MODE_RESIZE = "resize"
MODE_FORMAT = "format"
MODE_COMPRESS = "compress"
MODE_LOGO = "logo"
MODE_WATERMARK = "watermark"

PREVIEW_SIDEBAR_EXPANDED_WIDTH = 340
PREVIEW_SIDEBAR_COLLAPSED_WIDTH = 48
PREVIEW_SIDEBAR_ANIMATION_MS = 180

THEME_SETTING_KEY = "themeMode"
THEME_LABELS = {
    "浅色": "light",
    "暗色": "dark",
    "跟随系统": "auto",
}
THEME_VALUES = {value: label for label, value in THEME_LABELS.items()}
THEME_MAP = {
    "light": Theme.LIGHT,
    "dark": Theme.DARK,
    "auto": Theme.AUTO,
}


def theme_colors() -> dict[str, str]:
    if isDarkTheme():
        return {
            "text": "#f3f3f3",
            "muted": "#b7b7b7",
            "page": "#111315",
            "card": "#1f2023",
            "card_border": "#34363a",
            "preview_border": "#3f3f46",
            "preview": "#202124",
            "preview_text": "#cfcfcf",
        }

    return {
        "text": "#202020",
        "muted": "#5f6368",
        "page": "#f7f8fa",
        "card": "#ffffff",
        "card_border": "#e5e5e5",
        "preview_border": "#d9d9d9",
        "preview": "#fafafa",
        "preview_text": "#666666",
    }


def apply_background(widget: QWidget | None, color: str) -> None:
    if widget is None:
        return

    qcolor = QColor(color)
    palette = widget.palette()
    palette.setColor(QPalette.Window, qcolor)
    palette.setColor(QPalette.Base, qcolor)
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
    widget.setAttribute(Qt.WA_StyledBackground, True)
    widget.update()


def theme_stylesheet() -> str:
    colors = theme_colors()

    return f"""
        QWidget {{
            font-family: "Microsoft YaHei";
            font-size: 13px;
            color: {colors["text"]};
        }}
        #MainStackedWidget,
        #MainStackedView,
        #NavigationInterface,
        #NavigationPanel,
        #NavigationPanel #scrollWidget,
        #PreviewSidebar,
        #PreviewExpanded,
        #comprehensivePage,
        #resizePage,
        #formatPage,
        #compressPage,
        #logoPage,
        #watermarkPage,
        #settingsPage,
        #aboutPage,
        #PageContainer,
        #PageViewport {{
            background: {colors["page"]};
        }}
        #PageScrollArea {{
            background: {colors["page"]};
            border: none;
        }}
        #PreviewSidebar {{
            background: {colors["page"]};
            border-left: 1px solid {colors["card_border"]};
        }}
        #PanelCard {{
            background: {colors["card"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 8px;
        }}
        #TitleLabel {{
            font-size: 26px;
            font-weight: 600;
            padding: 2px 0 4px 0;
        }}
        #SectionTitle {{
            font-size: 15px;
            font-weight: 600;
            padding-bottom: 4px;
        }}
        #MutedLabel {{
            color: {colors["muted"]};
        }}
        #PreviewImage {{
            border: 1px solid {colors["preview_border"]};
            border-radius: 8px;
            background: {colors["preview"]};
            color: {colors["preview_text"]};
            padding: 8px;
        }}
    """


def load_theme_value(settings: QSettings) -> str:
    value = settings.value(THEME_SETTING_KEY, "light")
    value = str(value)
    return value if value in THEME_MAP else "light"


class PreviewImageLabel(QLabel):
    drag_started = Signal(int, int)
    dragged = Signal(int, int)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._drag_enabled = False
        self._dragging = False
        self._image_size = QSize()
        self._pixmap_size = QSize()

    def set_drag_enabled(self, enabled: bool) -> None:
        self._drag_enabled = enabled
        self.setCursor(Qt.OpenHandCursor if enabled else Qt.ArrowCursor)

    def set_preview_pixmap(self, pixmap: QPixmap, image_size: tuple[int, int]) -> None:
        self._image_size = QSize(image_size[0], image_size[1])
        self._pixmap_size = pixmap.size()
        self.setPixmap(pixmap)

    def clear_preview_state(self) -> None:
        self._dragging = False
        self._image_size = QSize()
        self._pixmap_size = QSize()
        self.set_drag_enabled(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._drag_enabled:
            point = self._image_point(event.position().toPoint())
            if point is not None:
                self._dragging = True
                self.setCursor(Qt.ClosedHandCursor)
                self.drag_started.emit(point.x(), point.y())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            point = self._image_point(event.position().toPoint())
            if point is not None:
                self.dragged.emit(point.x(), point.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor if self._drag_enabled else Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _image_point(self, widget_pos: QPoint) -> QPoint | None:
        rect = self._pixmap_rect()
        if rect.isNull() or not rect.contains(widget_pos):
            return None

        x = int((widget_pos.x() - rect.left()) * self._image_size.width() / rect.width())
        y = int((widget_pos.y() - rect.top()) * self._image_size.height() / rect.height())
        return QPoint(x, y)

    def _pixmap_rect(self) -> QRect:
        if self._image_size.isEmpty() or self._pixmap_size.isEmpty():
            return QRect()

        x = (self.width() - self._pixmap_size.width()) // 2
        y = (self.height() - self._pixmap_size.height()) // 2
        return QRect(x, y, self._pixmap_size.width(), self._pixmap_size.height())


@dataclass
class ImageListItem:
    path: Path
    image_format: str
    dimensions: str
    size_text: str


@dataclass(frozen=True)
class ProcessingTask:
    row: int
    source_path: Path
    output_path: Path
    output_format: str


@dataclass(frozen=True)
class PageSettings:
    output_size: tuple[int, int] | None
    output_choice: str
    target_size: int | None
    apply_logo: bool
    logo_assets: list[LogoAsset]
    watermark_options: WatermarkOptions | None


class ProcessingWorker(QObject):
    item_started = Signal(int, str)
    item_finished = Signal(int, str)
    progress_changed = Signal(int, int, str, int, int, int)
    finished = Signal(int, int, int, int, object, bool)

    def __init__(
        self,
        tasks: list[ProcessingTask],
        output_size: tuple[int, int] | None,
        target_size: int | None,
        apply_logo: bool,
        logos: list[Image.Image],
        watermark_options: WatermarkOptions | None,
    ) -> None:
        super().__init__()
        self.tasks = tasks
        self.output_size = output_size
        self.target_size = target_size
        self.apply_logo = apply_logo
        self.logos = logos
        self.watermark_options = watermark_options
        self.cancel_requested = False

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        total = len(self.tasks)
        success = 0
        failure = 0
        warning = 0
        last_output_dir: Path | None = None
        canceled = False

        for current, task in enumerate(self.tasks, start=1):
            file_name = task.source_path.name
            self.item_started.emit(task.row, file_name)

            try:
                logo_copies = [logo.copy() for logo in self.logos]
                result = process_image(
                    task.source_path,
                    task.output_path,
                    ProcessOptions(
                        output_format=task.output_format,
                        output_size=self.output_size,
                        target_size=self.target_size,
                        apply_logo=self.apply_logo,
                        logos=logo_copies,
                        watermark_options=self.watermark_options,
                    ),
                )
                last_output_dir = result.output_path.parent
                if result.exceeded:
                    warning += 1
                    status = f"{STATUS_EXCEEDED}：最终 {bytes_to_display(result.output_size)}"
                else:
                    success += 1
                    status = STATUS_SUCCESS
            except Exception as exc:
                failure += 1
                reason = str(exc) or "图片无法打开"
                if "内置LOGO" in reason:
                    reason = "内置LOGO加载失败"
                elif "水印图片加载失败" in reason:
                    reason = "水印图片加载失败"
                elif "请输入水印文字" in reason:
                    reason = "请输入水印文字"
                elif "图片无法打开" not in reason:
                    reason = "图片无法打开"
                status = f"{STATUS_FAILED}：{reason}"

            self.item_finished.emit(task.row, status)
            self.progress_changed.emit(current, total, file_name, success, failure, warning)

            if self.cancel_requested:
                canceled = True
                for remaining_task in self.tasks[current:]:
                    self.item_finished.emit(remaining_task.row, STATUS_CANCELED)
                break

        self.finished.emit(total, success, failure, warning, last_output_dir, canceled)


class ImageOperationPage(QWidget):
    preview_collapse_requested = Signal(bool)

    def __init__(self, page_title: str, mode: str, object_name: str) -> None:
        super().__init__()
        self.page_title = page_title
        self.mode = mode
        self.setObjectName(object_name)

        self.items: list[ImageListItem] = []
        self.selected_save_path: Path | None = None
        self.last_output_location: Path | None = None
        self.worker_thread: QThread | None = None
        self.worker: ProcessingWorker | None = None
        self.size_lookup = {size_to_text(size): size for size in OUTPUT_SIZE_PRESETS}
        self.logo_assets: list[LogoAsset] = []
        self.watermark_image_path: Path | None = None
        self.watermark_drag_delta = (0, 0)
        self.current_preview_image_size: tuple[int, int] | None = None

        self.setAcceptDrops(True)
        self._setup_ui()
        self._connect_signals()
        self._update_save_mode()
        self._update_custom_size_state()
        self._update_custom_compression_state()
        self._update_watermark_controls_state()
        self._update_result_labels(0, 0, 0, 0)

    @property
    def has_size_controls(self) -> bool:
        return self.mode in {MODE_COMPREHENSIVE, MODE_RESIZE}

    @property
    def has_format_controls(self) -> bool:
        return self.mode in {MODE_COMPREHENSIVE, MODE_FORMAT}

    @property
    def has_compression_controls(self) -> bool:
        return self.mode in {MODE_COMPREHENSIVE, MODE_COMPRESS}

    @property
    def has_optional_logo(self) -> bool:
        return self.mode == MODE_COMPREHENSIVE

    @property
    def always_apply_logo(self) -> bool:
        return self.mode == MODE_LOGO

    @property
    def has_optional_watermark(self) -> bool:
        return self.mode == MODE_COMPREHENSIVE

    @property
    def always_apply_watermark(self) -> bool:
        return self.mode == MODE_WATERMARK

    def _setup_ui(self) -> None:
        self.setAttribute(Qt.WA_StyledBackground, True)
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setObjectName("PageScrollArea")
        self.scroll_area.setAttribute(Qt.WA_StyledBackground, True)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.viewport().setObjectName("PageViewport")
        self.scroll_area.viewport().setAttribute(Qt.WA_StyledBackground, True)
        root_layout.addWidget(self.scroll_area, 1)

        self.container = QWidget(self)
        self.container.setObjectName("PageContainer")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.scroll_area.setWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(28, 24, 14, 28)
        layout.setSpacing(14)

        title = QLabel(self.page_title, self)
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        list_card, list_layout = self._create_card("图片列表")
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.import_button = self._create_button(PrimaryPushButton, "导入图片", FIF.ADD)
        self.remove_button = self._create_button(PushButton, "移除选中", FIF.DELETE)
        self.clear_button = self._create_button(PushButton, "清空列表", FIF.CLEAR_SELECTION)
        button_row.addWidget(self.import_button)
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        list_layout.addLayout(button_row)

        self.table = TableWidget(self)
        self.table.setColumnCount(len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(245)
        self.table.setAcceptDrops(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        list_layout.addWidget(self.table)

        self.preview_collapsed = False
        self.preview_sidebar = QWidget(self)
        self.preview_sidebar.setObjectName("PreviewSidebar")
        self.preview_sidebar.setAttribute(Qt.WA_StyledBackground, True)
        self.preview_sidebar.setFixedWidth(PREVIEW_SIDEBAR_EXPANDED_WIDTH)
        self.preview_sidebar_layout = QVBoxLayout(self.preview_sidebar)
        self.preview_sidebar_layout.setContentsMargins(18, 24, 18, 28)
        self.preview_sidebar_layout.setSpacing(12)
        self.preview_width_animation = QVariantAnimation(self)
        self.preview_width_animation.setDuration(PREVIEW_SIDEBAR_ANIMATION_MS)
        self.preview_width_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.preview_width_animation.valueChanged.connect(self._set_preview_sidebar_width)
        self.preview_width_animation.finished.connect(self._finish_preview_sidebar_transition)

        self.preview_expanded_widget = QWidget(self.preview_sidebar)
        self.preview_expanded_widget.setObjectName("PreviewExpanded")
        self.preview_expanded_widget.setAttribute(Qt.WA_StyledBackground, True)
        preview_layout = QVBoxLayout(self.preview_expanded_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(10)

        preview_header = QHBoxLayout()
        preview_header.setSpacing(8)
        self.preview_title_label = QLabel("预览", self)
        self.preview_title_label.setObjectName("SectionTitle")
        self.preview_collapse_button = TransparentToolButton(self)
        self.preview_collapse_button.setIcon(FIF.RIGHT_ARROW)
        self.preview_collapse_button.setIconSize(QSize(14, 14))
        self.preview_collapse_button.setFixedSize(30, 30)
        self.preview_collapse_button.setToolTip("收起预览")
        preview_header.addWidget(self.preview_title_label)
        preview_header.addStretch(1)
        preview_header.addWidget(self.preview_collapse_button)
        preview_layout.addLayout(preview_header)

        self.preview_image_label = PreviewImageLabel("请选择图片", self)
        self.preview_image_label.setObjectName("PreviewImage")
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setMinimumSize(260, 260)
        self.preview_image_label.setWordWrap(True)
        self.preview_info_label = QLabel("处理后效果", self)
        self.preview_info_label.setObjectName("MutedLabel")
        self.preview_info_label.setAlignment(Qt.AlignCenter)
        self.preview_info_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_image_label)
        preview_layout.addWidget(self.preview_info_label)
        preview_layout.addStretch(1)

        self.preview_sidebar_layout.addWidget(self.preview_expanded_widget)
        self.preview_expand_button = TransparentToolButton(self.preview_sidebar)
        self.preview_expand_button.setIcon(FIF.VIEW)
        self.preview_expand_button.setIconSize(QSize(18, 18))
        self.preview_expand_button.setFixedSize(40, 40)
        self.preview_expand_button.setToolTip("展开预览")
        self.preview_expand_button.hide()
        self.preview_sidebar_layout.addWidget(self.preview_expand_button, 0, Qt.AlignTop | Qt.AlignHCenter)
        self.preview_sidebar_layout.addStretch(1)
        root_layout.addWidget(self.preview_sidebar, 0)

        layout.addWidget(list_card)

        settings_row = QHBoxLayout()
        settings_row.setSpacing(14)
        settings_row.addWidget(self._build_output_card(), 2)
        settings_row.addWidget(self._build_save_card(), 2)
        layout.addLayout(settings_row)

        if self.has_optional_logo or self.always_apply_logo:
            layout.addWidget(self._build_logo_card())

        if self.has_optional_watermark or self.always_apply_watermark:
            layout.addWidget(self._build_watermark_card())

        progress_card, progress_layout = self._create_card("处理进度")
        self.progress_text = QLabel("总数：0    当前：0/0    文件：-", self)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_text)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_card)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.start_button = self._create_button(PrimaryPushButton, "开始处理", FIF.PLAY)
        self.cancel_button = self._create_button(PushButton, "取消处理", FIF.CLOSE)
        self.cancel_button.setEnabled(False)
        self.open_location_button = self._create_button(PushButton, "打开位置", FIF.FOLDER)
        self.open_location_button.setEnabled(False)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.open_location_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        result_card, result_layout = self._create_card("处理结果")
        result_grid = QGridLayout()
        result_grid.setHorizontalSpacing(30)
        result_grid.setVerticalSpacing(8)
        self.total_label = QLabel(self)
        self.success_label = QLabel(self)
        self.failure_label = QLabel(self)
        self.warning_label = QLabel(self)
        result_grid.addWidget(self.total_label, 0, 0)
        result_grid.addWidget(self.success_label, 0, 1)
        result_grid.addWidget(self.failure_label, 0, 2)
        result_grid.addWidget(self.warning_label, 0, 3)
        result_grid.addItem(QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum), 0, 4)
        result_layout.addLayout(result_grid)
        layout.addWidget(result_card)
        layout.addStretch(1)

        self.apply_theme_styles()

    def apply_theme_styles(self) -> None:
        colors = theme_colors()
        apply_background(self, colors["page"])
        apply_background(self.scroll_area, colors["page"])
        apply_background(self.scroll_area.viewport(), colors["page"])
        apply_background(self.container, colors["page"])
        apply_background(getattr(self, "preview_sidebar", None), colors["page"])
        apply_background(getattr(self, "preview_expanded_widget", None), colors["page"])
        self.setStyleSheet(theme_stylesheet())
        self._apply_preview_theme_styles(colors)

    def _apply_preview_theme_styles(self, colors: dict[str, str]) -> None:
        self.preview_sidebar.setStyleSheet(
            f"""
            #PreviewSidebar {{
                background-color: {colors["page"]};
                border-left: 1px solid {colors["card_border"]};
            }}
            """
        )
        self.preview_expanded_widget.setStyleSheet(
            f"""
            #PreviewExpanded {{
                background-color: {colors["page"]};
                border: none;
            }}
            """
        )
        self.preview_title_label.setStyleSheet(f"color: {colors['text']};")
        self.preview_info_label.setStyleSheet(f"color: {colors['muted']}; background: transparent;")
        self.preview_image_label.setStyleSheet(
            f"""
            #PreviewImage {{
                border: 1px solid {colors["preview_border"]};
                border-radius: 8px;
                background-color: {colors["preview"]};
                color: {colors["preview_text"]};
                padding: 8px;
            }}
            """
        )

    def _build_output_card(self) -> CardWidget:
        title = "输出设置" if self.mode != MODE_COMPRESS else "压缩大小"
        card, layout = self._create_card(title)

        if self.has_size_controls:
            size_row = QHBoxLayout()
            size_row.addWidget(QLabel("输出尺寸", self))
            self.size_combo = ComboBox(self)
            for size in OUTPUT_SIZE_PRESETS:
                self.size_combo.addItem(size_to_text(size))
            self.size_combo.addItem(CUSTOM_SIZE_LABEL)
            self.size_combo.setCurrentText(size_to_text(DEFAULT_OUTPUT_SIZE))
            self.size_combo.setFixedWidth(150)
            size_row.addWidget(self.size_combo)
            size_row.addStretch(1)
            layout.addLayout(size_row)

            custom_row = QHBoxLayout()
            self.custom_width_edit = LineEdit(self)
            self.custom_width_edit.setPlaceholderText("宽")
            self.custom_width_edit.setFixedWidth(76)
            self.custom_height_edit = LineEdit(self)
            self.custom_height_edit.setPlaceholderText("高")
            self.custom_height_edit.setFixedWidth(76)
            custom_row.addWidget(QLabel(CUSTOM_SIZE_LABEL, self))
            custom_row.addWidget(self.custom_width_edit)
            custom_row.addWidget(QLabel("×", self))
            custom_row.addWidget(self.custom_height_edit)
            custom_row.addWidget(QLabel("px", self))
            custom_row.addStretch(1)
            layout.addLayout(custom_row)
        else:
            self._add_readonly_row(layout, "输出尺寸", "保持原尺寸")

        if self.has_format_controls:
            format_row = QHBoxLayout()
            format_row.addWidget(QLabel("输出格式", self))
            self.output_format_combo = ComboBox(self)
            self.output_format_combo.addItems(OUTPUT_FORMATS)
            self.output_format_combo.setCurrentText(DEFAULT_OUTPUT_FORMAT)
            self.output_format_combo.setFixedWidth(150)
            format_row.addWidget(self.output_format_combo)
            format_row.addStretch(1)
            layout.addLayout(format_row)
        else:
            self._add_readonly_row(layout, "输出格式", KEEP_ORIGINAL_FORMAT)

        if self.has_compression_controls:
            layout.addWidget(QLabel("压缩大小", self))
            self.size_group = QButtonGroup(self)
            self.size_radios: dict[str, RadioButton] = {}
            size_grid = QGridLayout()
            size_grid.setHorizontalSpacing(16)
            size_grid.setVerticalSpacing(8)
            for index, label in enumerate(TARGET_SIZE_OPTIONS):
                radio = RadioButton(self)
                radio.setText(label)
                self.size_group.addButton(radio)
                self.size_radios[label] = radio
                size_grid.addWidget(radio, index // 2, index % 2)

            self.custom_size_radio = RadioButton(self)
            self.custom_size_radio.setText(CUSTOM_SIZE_LABEL)
            self.size_group.addButton(self.custom_size_radio)
            custom_row = QHBoxLayout()
            custom_row.addWidget(self.custom_size_radio)
            self.custom_size_edit = LineEdit(self)
            self.custom_size_edit.setPlaceholderText("MB")
            self.custom_size_edit.setFixedWidth(96)
            self.custom_size_edit.setEnabled(False)
            custom_row.addWidget(self.custom_size_edit)
            custom_row.addStretch(1)
            size_grid.addLayout(custom_row, 1, 1)

            self.size_radios[DEFAULT_TARGET_SIZE_LABEL].setChecked(True)
            layout.addLayout(size_grid)

        return card

    def _build_logo_card(self) -> CardWidget:
        card, layout = self._create_card("LOGO")
        if self.has_optional_logo:
            self.logo_checkbox = CheckBox(self)
            self.logo_checkbox.setText("叠加LOGO")
            self.logo_checkbox.setChecked(True)
            layout.addWidget(self.logo_checkbox)
        else:
            self._add_readonly_row(layout, "LOGO", "叠加LOGO")

        self.logo_list = ListWidget(self)
        self.logo_list.setViewMode(QListView.IconMode)
        self.logo_list.setResizeMode(QListView.Adjust)
        self.logo_list.setMovement(QListView.Static)
        self.logo_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.logo_list.setIconSize(QSize(132, 132))
        self.logo_list.setGridSize(QSize(172, 182))
        self.logo_list.setMinimumHeight(220)
        self.logo_list.setSpacing(8)
        self._load_logo_grid()
        layout.addWidget(self.logo_list)
        return card

    def _build_watermark_card(self) -> CardWidget:
        card, layout = self._create_card("水印")
        if self.has_optional_watermark:
            self.watermark_checkbox = CheckBox(self)
            self.watermark_checkbox.setText("添加水印")
            self.watermark_checkbox.setChecked(False)
            layout.addWidget(self.watermark_checkbox)
        else:
            self._add_readonly_row(layout, "水印", "添加水印")

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("水印类型", self))
        self.watermark_type_combo = ComboBox(self)
        self.watermark_type_combo.addItems(WATERMARK_TYPES)
        self.watermark_type_combo.setCurrentText(WATERMARK_TYPE_TEXT)
        self.watermark_type_combo.setFixedWidth(150)
        type_row.addWidget(self.watermark_type_combo)
        type_row.addStretch(1)
        layout.addLayout(type_row)

        text_row = QHBoxLayout()
        text_row.addWidget(QLabel("文字内容", self))
        self.watermark_text_edit = LineEdit(self)
        self.watermark_text_edit.setText(DEFAULT_WATERMARK_TEXT)
        self.watermark_text_edit.setPlaceholderText("水印文字")
        self.watermark_text_edit.setMinimumWidth(180)
        text_row.addWidget(self.watermark_text_edit, 1)
        layout.addLayout(text_row)

        text_option_row = QHBoxLayout()
        text_option_row.addWidget(QLabel("字号", self))
        self.watermark_font_size_edit = LineEdit(self)
        self.watermark_font_size_edit.setText(str(DEFAULT_WATERMARK_FONT_SIZE))
        self.watermark_font_size_edit.setFixedWidth(76)
        text_option_row.addWidget(self.watermark_font_size_edit)
        text_option_row.addWidget(QLabel("颜色", self))
        self.watermark_color_combo = ComboBox(self)
        self.watermark_color_combo.addItems(list(WATERMARK_COLORS.keys()))
        self.watermark_color_combo.setCurrentText(DEFAULT_WATERMARK_COLOR)
        self.watermark_color_combo.setFixedWidth(100)
        text_option_row.addWidget(self.watermark_color_combo)
        text_option_row.addStretch(1)
        layout.addLayout(text_option_row)

        image_row = QHBoxLayout()
        image_row.addWidget(QLabel("水印图片", self))
        self.watermark_image_button = self._create_button(PushButton, "选择水印图片", FIF.PHOTO)
        self.watermark_image_label = QLabel("请选择水印图片", self)
        self.watermark_image_label.setObjectName("MutedLabel")
        self.watermark_image_label.setWordWrap(True)
        image_row.addWidget(self.watermark_image_button)
        image_row.addWidget(self.watermark_image_label, 1)
        image_row.addWidget(QLabel("缩放", self))
        self.watermark_image_scale_edit = LineEdit(self)
        self.watermark_image_scale_edit.setText(str(DEFAULT_WATERMARK_IMAGE_SCALE))
        self.watermark_image_scale_edit.setFixedWidth(70)
        image_row.addWidget(self.watermark_image_scale_edit)
        image_row.addWidget(QLabel("%", self))
        layout.addLayout(image_row)

        common_row = QHBoxLayout()
        common_row.addWidget(QLabel("位置", self))
        self.watermark_position_combo = ComboBox(self)
        self.watermark_position_combo.addItems(WATERMARK_POSITIONS)
        self.watermark_position_combo.setCurrentText(DEFAULT_WATERMARK_POSITION)
        self.watermark_position_combo.setFixedWidth(100)
        common_row.addWidget(self.watermark_position_combo)
        common_row.addWidget(QLabel("透明度", self))
        self.watermark_opacity_edit = LineEdit(self)
        self.watermark_opacity_edit.setText(str(DEFAULT_WATERMARK_OPACITY))
        self.watermark_opacity_edit.setFixedWidth(70)
        common_row.addWidget(self.watermark_opacity_edit)
        common_row.addWidget(QLabel("%", self))
        common_row.addWidget(QLabel("边距", self))
        self.watermark_margin_edit = LineEdit(self)
        self.watermark_margin_edit.setText(str(DEFAULT_WATERMARK_MARGIN))
        self.watermark_margin_edit.setFixedWidth(70)
        common_row.addWidget(self.watermark_margin_edit)
        common_row.addWidget(QLabel("px", self))
        common_row.addWidget(QLabel("角度", self))
        self.watermark_angle_edit = LineEdit(self)
        self.watermark_angle_edit.setText(str(DEFAULT_WATERMARK_ANGLE))
        self.watermark_angle_edit.setFixedWidth(70)
        common_row.addWidget(self.watermark_angle_edit)
        common_row.addWidget(QLabel("°", self))
        common_row.addStretch(1)
        layout.addLayout(common_row)

        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("X偏移", self))
        self.watermark_offset_x_edit = LineEdit(self)
        self.watermark_offset_x_edit.setText(str(DEFAULT_WATERMARK_OFFSET_X))
        self.watermark_offset_x_edit.setFixedWidth(76)
        offset_row.addWidget(self.watermark_offset_x_edit)
        offset_row.addWidget(QLabel("Y偏移", self))
        self.watermark_offset_y_edit = LineEdit(self)
        self.watermark_offset_y_edit.setText(str(DEFAULT_WATERMARK_OFFSET_Y))
        self.watermark_offset_y_edit.setFixedWidth(76)
        offset_row.addWidget(self.watermark_offset_y_edit)
        offset_row.addWidget(QLabel("px", self))
        offset_row.addStretch(1)
        layout.addLayout(offset_row)

        tile_row = QHBoxLayout()
        tile_row.addWidget(QLabel("水平间距", self))
        self.watermark_tile_spacing_x_edit = LineEdit(self)
        self.watermark_tile_spacing_x_edit.setText(str(DEFAULT_WATERMARK_TILE_SPACING_X))
        self.watermark_tile_spacing_x_edit.setFixedWidth(70)
        tile_row.addWidget(self.watermark_tile_spacing_x_edit)
        tile_row.addWidget(QLabel("垂直间距", self))
        self.watermark_tile_spacing_y_edit = LineEdit(self)
        self.watermark_tile_spacing_y_edit.setText(str(DEFAULT_WATERMARK_TILE_SPACING_Y))
        self.watermark_tile_spacing_y_edit.setFixedWidth(70)
        tile_row.addWidget(self.watermark_tile_spacing_y_edit)
        tile_row.addWidget(QLabel("起始X", self))
        self.watermark_tile_offset_x_edit = LineEdit(self)
        self.watermark_tile_offset_x_edit.setText(str(DEFAULT_WATERMARK_TILE_OFFSET_X))
        self.watermark_tile_offset_x_edit.setFixedWidth(70)
        tile_row.addWidget(self.watermark_tile_offset_x_edit)
        tile_row.addWidget(QLabel("起始Y", self))
        self.watermark_tile_offset_y_edit = LineEdit(self)
        self.watermark_tile_offset_y_edit.setText(str(DEFAULT_WATERMARK_TILE_OFFSET_Y))
        self.watermark_tile_offset_y_edit.setFixedWidth(70)
        tile_row.addWidget(self.watermark_tile_offset_y_edit)
        tile_row.addStretch(1)
        layout.addLayout(tile_row)

        return card

    def _build_save_card(self) -> CardWidget:
        card, layout = self._create_card("保存方式")
        self.save_group = QButtonGroup(self)
        self.choose_save_radio = RadioButton(self)
        self.choose_save_radio.setText("处理后选择保存位置")
        self.choose_save_radio.setChecked(True)
        self.original_save_radio = RadioButton(self)
        self.original_save_radio.setText("保存到原图位置")
        self.save_group.addButton(self.choose_save_radio)
        self.save_group.addButton(self.original_save_radio)
        layout.addWidget(self.choose_save_radio)
        layout.addWidget(self.original_save_radio)

        path_row = QHBoxLayout()
        self.choose_save_button = self._create_button(PushButton, "选择保存位置", FIF.SAVE)
        self.save_path_label = QLabel("请选择保存位置", self)
        self.save_path_label.setObjectName("MutedLabel")
        self.save_path_label.setWordWrap(True)
        path_row.addWidget(self.choose_save_button)
        path_row.addWidget(self.save_path_label, 1)
        layout.addLayout(path_row)
        return card

    def _add_readonly_row(self, layout: QVBoxLayout, label: str, value: str) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(label, self))
        value_label = QLabel(value, self)
        value_label.setObjectName("MutedLabel")
        row.addWidget(value_label)
        row.addStretch(1)
        layout.addLayout(row)

    def _create_card(self, title: str) -> tuple[CardWidget, QVBoxLayout]:
        card = CardWidget(self)
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        title_label = QLabel(title, self)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)
        return card, layout

    def _create_button(self, button_class, text: str, icon) -> PushButton:
        button = button_class(self)
        button.setText(text)
        button.setIcon(icon)
        return button

    def _connect_signals(self) -> None:
        self.import_button.clicked.connect(self._select_images)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_list)
        self.choose_save_button.clicked.connect(self._choose_save_location)
        self.start_button.clicked.connect(self._start_processing)
        self.cancel_button.clicked.connect(self._cancel_processing)
        self.open_location_button.clicked.connect(self._open_last_location)
        self.preview_collapse_button.clicked.connect(self._toggle_preview_sidebar)
        self.preview_expand_button.clicked.connect(self._toggle_preview_sidebar)
        self.save_group.buttonClicked.connect(self._update_save_mode)
        self.table.itemSelectionChanged.connect(self._refresh_preview)

        if self.has_size_controls:
            self.size_combo.currentTextChanged.connect(self._update_custom_size_state)
            self.size_combo.currentTextChanged.connect(self._refresh_preview)
            self.custom_width_edit.textChanged.connect(self._refresh_preview)
            self.custom_height_edit.textChanged.connect(self._refresh_preview)
        if self.has_format_controls:
            self.output_format_combo.currentTextChanged.connect(self._reset_save_location)
            self.output_format_combo.currentTextChanged.connect(self._refresh_preview)
        if self.has_compression_controls:
            self.size_group.buttonClicked.connect(self._update_custom_compression_state)
        if self.has_optional_logo:
            self.logo_checkbox.stateChanged.connect(self._update_logo_grid_state)
            self.logo_checkbox.stateChanged.connect(self._refresh_preview)
        if hasattr(self, "logo_list"):
            self.logo_list.itemSelectionChanged.connect(self._refresh_preview)
        if self.has_optional_watermark:
            self.watermark_checkbox.stateChanged.connect(self._update_watermark_controls_state)
            self.watermark_checkbox.stateChanged.connect(self._refresh_preview)
        if self.has_optional_watermark or self.always_apply_watermark:
            self.watermark_type_combo.currentTextChanged.connect(self._update_watermark_controls_state)
            self.watermark_type_combo.currentTextChanged.connect(self._refresh_preview)
            self.watermark_text_edit.textChanged.connect(self._refresh_preview)
            self.watermark_font_size_edit.textChanged.connect(self._refresh_preview)
            self.watermark_color_combo.currentTextChanged.connect(self._refresh_preview)
            self.watermark_image_button.clicked.connect(self._choose_watermark_image)
            self.watermark_image_scale_edit.textChanged.connect(self._refresh_preview)
            self.watermark_position_combo.currentTextChanged.connect(self._update_watermark_controls_state)
            self.watermark_position_combo.currentTextChanged.connect(self._refresh_preview)
            self.watermark_opacity_edit.textChanged.connect(self._refresh_preview)
            self.watermark_margin_edit.textChanged.connect(self._refresh_preview)
            self.watermark_angle_edit.textChanged.connect(self._refresh_preview)
            self.watermark_offset_x_edit.textChanged.connect(self._refresh_preview)
            self.watermark_offset_y_edit.textChanged.connect(self._refresh_preview)
            self.watermark_tile_spacing_x_edit.textChanged.connect(self._refresh_preview)
            self.watermark_tile_spacing_y_edit.textChanged.connect(self._refresh_preview)
            self.watermark_tile_offset_x_edit.textChanged.connect(self._refresh_preview)
            self.watermark_tile_offset_y_edit.textChanged.connect(self._refresh_preview)
            self.preview_image_label.drag_started.connect(self._on_preview_watermark_drag_started)
            self.preview_image_label.dragged.connect(self._on_preview_watermark_dragged)

    def _toggle_preview_sidebar(self, *_args) -> None:
        self.preview_collapse_requested.emit(not self.preview_collapsed)

    def set_preview_collapsed(self, collapsed: bool, animate: bool = False) -> None:
        self.preview_collapsed = collapsed
        self._update_preview_sidebar_state(animate)

    def _set_preview_sidebar_width(self, value) -> None:
        self.preview_sidebar.setFixedWidth(int(value))

    def _update_preview_sidebar_state(self, animate: bool = False) -> None:
        target_width = (
            PREVIEW_SIDEBAR_COLLAPSED_WIDTH
            if self.preview_collapsed
            else PREVIEW_SIDEBAR_EXPANDED_WIDTH
        )
        self.preview_width_animation.stop()

        if animate:
            if self.preview_collapsed:
                self.preview_expand_button.hide()
                self.preview_expanded_widget.show()
            else:
                self.preview_sidebar_layout.setContentsMargins(18, 24, 18, 28)
                self.preview_expand_button.hide()
                self.preview_expanded_widget.show()

            start_width = self.preview_sidebar.width()
            if start_width != target_width:
                self.preview_width_animation.setStartValue(start_width)
                self.preview_width_animation.setEndValue(target_width)
                self.preview_width_animation.start()
                return

        self.preview_sidebar.setFixedWidth(target_width)
        self._finish_preview_sidebar_transition()

    def _finish_preview_sidebar_transition(self) -> None:
        if self.preview_collapsed:
            self.preview_sidebar.setFixedWidth(PREVIEW_SIDEBAR_COLLAPSED_WIDTH)
            self.preview_expanded_widget.hide()
            self.preview_expand_button.show()
            self.preview_sidebar_layout.setContentsMargins(4, 24, 4, 28)
            return

        self.preview_sidebar.setFixedWidth(PREVIEW_SIDEBAR_EXPANDED_WIDTH)
        self.preview_sidebar_layout.setContentsMargins(18, 24, 18, 28)
        self.preview_expand_button.hide()
        self.preview_expanded_widget.show()
        self._refresh_preview()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and is_supported_image(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self._add_paths(paths)
        event.acceptProposedAction()

    def _select_images(self, *_args) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "导入图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp)",
        )
        if files:
            self._add_paths(files)

    def _add_paths(self, paths: Iterable[str]) -> None:
        existing = {str(item.path.resolve()).lower() for item in self.items}
        unsupported = False
        added = 0
        first_new_row = self.table.rowCount()

        for raw_path in paths:
            path = Path(raw_path)
            if not path.is_file():
                continue
            if not is_supported_image(path):
                unsupported = True
                continue

            normalized = str(path.resolve()).lower()
            if normalized in existing:
                continue

            item = self._build_list_item(path)
            self.items.append(item)
            existing.add(normalized)
            self._append_table_row(item)
            added += 1

        if unsupported:
            self._show_message("warning", "图片格式不支持")
        if added:
            self._reset_save_location()
            if not self.table.selectionModel().selectedRows():
                self.table.selectRow(first_new_row)
            self._refresh_preview()

    def _load_logo_grid(self) -> None:
        self.logo_assets = list_logo_assets()
        self.logo_list.clear()

        if not self.logo_assets:
            item = QListWidgetItem("无可用LOGO")
            item.setFlags(Qt.NoItemFlags)
            self.logo_list.addItem(item)
            return

        for index, asset in enumerate(self.logo_assets):
            item = QListWidgetItem(QIcon(str(asset.path)), asset.name)
            item.setData(Qt.UserRole, index)
            item.setToolTip(asset.path.name)
            item.setTextAlignment(Qt.AlignCenter)
            self.logo_list.addItem(item)

        self.logo_list.item(0).setSelected(True)
        self.logo_list.setCurrentRow(0)

    def _update_logo_grid_state(self, *_args) -> None:
        if hasattr(self, "logo_list"):
            self.logo_list.setEnabled(self._get_apply_logo())
        self._refresh_preview()

    def _choose_watermark_image(self, *_args) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择水印图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not selected:
            return

        path = Path(selected)
        if not path.is_file() or not is_supported_image(path):
            self._show_message("warning", "图片格式不支持")
            return

        self.watermark_image_path = path
        self.watermark_image_label.setText(path.name)
        self.watermark_image_label.setToolTip(str(path))
        self._refresh_preview()

    def _update_watermark_controls_state(self, *_args) -> None:
        if not (self.has_optional_watermark or self.always_apply_watermark):
            return

        processing = self.worker is not None
        apply_watermark = self._get_apply_watermark()
        enabled = apply_watermark and not processing
        is_text = self.watermark_type_combo.currentText() == WATERMARK_TYPE_TEXT
        position = self.watermark_position_combo.currentText()
        is_tile = position == WATERMARK_POSITION_TILE
        uses_margin = position not in {WATERMARK_POSITION_CUSTOM, WATERMARK_POSITION_TILE}

        if self.has_optional_watermark:
            self.watermark_checkbox.setEnabled(not processing)
        self.watermark_type_combo.setEnabled(enabled)
        self.watermark_text_edit.setEnabled(enabled and is_text)
        self.watermark_font_size_edit.setEnabled(enabled and is_text)
        self.watermark_color_combo.setEnabled(enabled and is_text)
        self.watermark_image_button.setEnabled(enabled and (not is_text))
        self.watermark_image_scale_edit.setEnabled(enabled and (not is_text))
        self.watermark_position_combo.setEnabled(enabled)
        self.watermark_opacity_edit.setEnabled(enabled)
        self.watermark_margin_edit.setEnabled(enabled and uses_margin)
        self.watermark_angle_edit.setEnabled(enabled)
        self.watermark_offset_x_edit.setEnabled(enabled and not is_tile)
        self.watermark_offset_y_edit.setEnabled(enabled and not is_tile)
        self.watermark_tile_spacing_x_edit.setEnabled(enabled and is_tile)
        self.watermark_tile_spacing_y_edit.setEnabled(enabled and is_tile)
        self.watermark_tile_offset_x_edit.setEnabled(enabled and is_tile)
        self.watermark_tile_offset_y_edit.setEnabled(enabled and is_tile)

    def _refresh_preview(self, *_args) -> None:
        if not hasattr(self, "preview_image_label"):
            return

        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            self._set_preview_message("请选择图片")
            return

        row = rows[0].row()
        if row < 0 or row >= len(self.items):
            self._set_preview_message("请选择图片")
            return

        output_size = self._get_output_size()
        if self.has_size_controls and output_size is None:
            self._set_preview_message("请输入正确的输出尺寸")
            return

        apply_logo = self._get_apply_logo()
        logo_assets = self._get_selected_logo_assets()
        if apply_logo and not logo_assets:
            self._set_preview_message("请选择LOGO")
            return

        watermark_options, watermark_error = self._get_watermark_options()
        if watermark_error:
            self._set_preview_message(watermark_error)
            return

        try:
            logos = load_logo_assets(logo_assets) if apply_logo else []
            preview = render_preview_image(
                self.items[row].path,
                ProcessOptions(
                    output_format=self._get_output_choice(),
                    output_size=output_size,
                    target_size=None,
                    apply_logo=apply_logo,
                    logos=logos,
                    watermark_options=watermark_options,
                ),
            )
            self._set_preview_image(preview, self.items[row].path.name, watermark_options)
        except Exception as exc:
            reason = str(exc) or "图片无法打开"
            if "内置LOGO" in reason:
                reason = "内置LOGO加载失败"
            elif "水印图片加载失败" in reason:
                reason = "水印图片加载失败"
            elif "请选择水印图片" in reason:
                reason = "请选择水印图片"
            elif "请输入水印文字" in reason:
                reason = "请输入水印文字"
            elif "图片无法打开" not in reason:
                reason = "图片无法打开"
            self._set_preview_message(reason)

    def _set_preview_message(self, message: str) -> None:
        self.preview_image_label.clear()
        self.preview_image_label.clear_preview_state()
        self.current_preview_image_size = None
        self.preview_image_label.setText(message)
        self.preview_info_label.setText("处理后效果")

    def _set_preview_image(
        self,
        image: Image.Image,
        file_name: str,
        watermark_options: WatermarkOptions | None,
    ) -> None:
        preview = image.copy()
        max_width = max(220, self.preview_image_label.width() - 24)
        max_height = max(220, self.preview_image_label.height() - 24)
        preview.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        preview.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue(), "PNG")

        self.preview_image_label.setText("")
        self.preview_image_label.set_preview_pixmap(pixmap, image.size)
        self.preview_image_label.set_drag_enabled(watermark_options is not None and self.worker is None)
        self.current_preview_image_size = image.size
        self.preview_info_label.setText(f"{file_name}    {image.width}×{image.height}")

    def _on_preview_watermark_drag_started(self, x: int, y: int) -> None:
        options, error = self._get_watermark_options()
        if error or options is None or self.current_preview_image_size is None:
            return

        if options.position == WATERMARK_POSITION_TILE:
            self.watermark_drag_delta = (x - options.tile_offset_x, y - options.tile_offset_y)
            return

        layer = create_watermark_layer(self.current_preview_image_size, options)
        current_x, current_y = watermark_position_for_layer(self.current_preview_image_size, layer.size, options)
        self.watermark_drag_delta = (x - current_x, y - current_y)

    def _on_preview_watermark_dragged(self, x: int, y: int) -> None:
        options, error = self._get_watermark_options()
        if error or options is None:
            return

        delta_x, delta_y = self.watermark_drag_delta
        new_x = x - delta_x
        new_y = y - delta_y

        if options.position == WATERMARK_POSITION_TILE:
            self._set_line_edit_int(self.watermark_tile_offset_x_edit, new_x)
            self._set_line_edit_int(self.watermark_tile_offset_y_edit, new_y)
        else:
            if self.watermark_position_combo.currentText() != WATERMARK_POSITION_CUSTOM:
                self.watermark_position_combo.setCurrentText(WATERMARK_POSITION_CUSTOM)
            self._set_line_edit_int(self.watermark_offset_x_edit, new_x)
            self._set_line_edit_int(self.watermark_offset_y_edit, new_y)

        self._refresh_preview()

    def _build_list_item(self, path: Path) -> ImageListItem:
        try:
            info = get_image_info(path)
            image_format = info.image_format
            dimensions = format_dimensions(info.width, info.height)
            size_text = bytes_to_display(info.size_bytes)
        except Exception:
            image_format = path.suffix.lstrip(".").upper() or "-"
            dimensions = "-"
            size_text = bytes_to_display(path.stat().st_size if path.exists() else None)

        return ImageListItem(path=path, image_format=image_format, dimensions=dimensions, size_text=size_text)

    def _append_table_row(self, item: ImageListItem) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [item.path.name, item.image_format, item.dimensions, item.size_text, STATUS_PENDING]
        for column, value in enumerate(values):
            table_item = QTableWidgetItem(value)
            table_item.setTextAlignment(Qt.AlignCenter if column else Qt.AlignVCenter | Qt.AlignLeft)
            if column == 0:
                table_item.setData(Qt.UserRole, str(item.path))
            self.table.setItem(row, column, table_item)
        self.table.setRowHeight(row, 38)

    def _remove_selected(self, *_args) -> None:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
            del self.items[row]
        if rows:
            self._reset_save_location()
            if self.items:
                self.table.selectRow(min(rows[-1], len(self.items) - 1))
            self._refresh_preview()

    def _clear_list(self, *_args) -> None:
        self.items.clear()
        self.table.setRowCount(0)
        self._reset_save_location()
        self._update_result_labels(0, 0, 0, 0)
        self.progress_bar.setValue(0)
        self.progress_text.setText("总数：0    当前：0/0    文件：-")
        self._refresh_preview()

    def _update_custom_size_state(self, *_args) -> None:
        if not self.has_size_controls:
            return
        enabled = self.size_combo.currentText() == CUSTOM_SIZE_LABEL
        self.custom_width_edit.setEnabled(enabled)
        self.custom_height_edit.setEnabled(enabled)
        if enabled:
            self.custom_width_edit.setFocus()

    def _update_custom_compression_state(self, *_args) -> None:
        if not self.has_compression_controls:
            return
        self.custom_size_edit.setEnabled(self.custom_size_radio.isChecked())
        if self.custom_size_radio.isChecked():
            self.custom_size_edit.setFocus()

    def _update_save_mode(self, *_args) -> None:
        choose_mode = self.choose_save_radio.isChecked()
        self.choose_save_button.setEnabled(choose_mode)
        if self.original_save_radio.isChecked():
            self.selected_save_path = None
            self.save_path_label.setText("原图位置")
        elif self.selected_save_path is None:
            self.save_path_label.setText("请选择保存位置")

    def _reset_save_location(self, *_args) -> None:
        self.selected_save_path = None
        self._update_save_mode()

    def _choose_save_location(self, *_args) -> bool:
        if not self.items:
            self._show_message("warning", "请先导入图片")
            return False

        if self.original_save_radio.isChecked():
            self.selected_save_path = None
            self.save_path_label.setText("原图位置")
            return True

        output_choice = self._get_output_choice()
        if len(self.items) == 1:
            source = self.items[0].path
            _, suffix = resolve_output_format(output_choice, source)
            default_path = source.with_name(f"{source.stem}_已处理{suffix}")
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "选择保存位置",
                str(default_path),
                f"图片文件 (*{suffix})",
            )
            if not selected:
                return False
            self.selected_save_path = ensure_suffix(Path(selected), suffix)
        else:
            selected = QFileDialog.getExistingDirectory(self, "选择保存位置", "")
            if not selected:
                return False
            self.selected_save_path = Path(selected)

        self.save_path_label.setText(str(self.selected_save_path))
        return True

    def _start_processing(self, *_args) -> None:
        if not self.items:
            self._show_message("warning", "请先导入图片")
            return

        settings = self._get_page_settings()
        if settings is None:
            return

        logos: list[Image.Image] = []
        if settings.apply_logo:
            try:
                logos = load_logo_assets(settings.logo_assets)
            except Exception:
                self._show_message("error", "内置LOGO加载失败")
                return

        tasks = self._prepare_tasks(settings.output_choice)
        if not tasks:
            return

        for row in range(self.table.rowCount()):
            self._set_row_status(row, STATUS_PENDING)

        self._set_processing_state(True)
        self._update_result_labels(len(tasks), 0, 0, 0)
        self.progress_bar.setValue(0)
        self.progress_text.setText(f"总数：{len(tasks)}    当前：0/{len(tasks)}    文件：-")
        self.last_output_location = None
        self.open_location_button.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = ProcessingWorker(
            tasks=tasks,
            output_size=settings.output_size,
            target_size=settings.target_size,
            apply_logo=settings.apply_logo,
            logos=logos,
            watermark_options=settings.watermark_options,
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.item_started.connect(self._on_item_started)
        self.worker.item_finished.connect(self._on_item_finished)
        self.worker.progress_changed.connect(self._on_progress_changed)
        self.worker.finished.connect(self._on_processing_finished)
        self.worker.finished.connect(lambda *_: self.worker_thread.quit())
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._clear_worker_refs)
        self.worker_thread.start()

    def _cancel_processing(self, *_args) -> None:
        if self.worker is None:
            return
        self.worker.request_cancel()
        self.cancel_button.setEnabled(False)
        self.progress_text.setText(self.progress_text.text() + "    正在取消")

    def _get_page_settings(self) -> PageSettings | None:
        output_size = self._get_output_size()
        if self.has_size_controls and output_size is None:
            self._show_message("warning", "请输入正确的输出尺寸")
            return None

        target_size = self._get_target_size()
        if self.has_compression_controls and target_size is None:
            self._show_message("warning", "请输入正确的压缩大小")
            return None

        logo_assets = self._get_selected_logo_assets()
        if self._get_apply_logo() and not logo_assets:
            self._show_message("warning", "请选择LOGO")
            return None

        watermark_options, watermark_error = self._get_watermark_options()
        if watermark_error:
            self._show_message("warning", watermark_error)
            return None

        return PageSettings(
            output_size=output_size,
            output_choice=self._get_output_choice(),
            target_size=target_size,
            apply_logo=self._get_apply_logo(),
            logo_assets=logo_assets,
            watermark_options=watermark_options,
        )

    def _prepare_tasks(self, output_choice: str) -> list[ProcessingTask]:
        if self.choose_save_radio.isChecked() and self.selected_save_path is None:
            if not self._choose_save_location():
                self._show_message("warning", "请选择保存位置")
                return []

        tasks: list[ProcessingTask] = []
        reserved: set[str] = set()

        if self.choose_save_radio.isChecked() and len(self.items) == 1:
            item = self.items[0]
            output_format, suffix = resolve_output_format(output_choice, item.path)
            selected = ensure_suffix(Path(self.selected_save_path), suffix)
            output_path = ensure_unique_path(selected, reserved)
            tasks.append(ProcessingTask(0, item.path, output_path, output_format))
            return tasks

        for row, item in enumerate(self.items):
            output_format, _ = resolve_output_format(output_choice, item.path)
            if self.original_save_radio.isChecked():
                output_dir = item.path.parent
            else:
                output_dir = Path(self.selected_save_path)
            output_path = build_default_output_path(item.path, output_dir, output_choice, reserved)
            tasks.append(ProcessingTask(row, item.path, output_path, output_format))

        return tasks

    def _get_output_choice(self) -> str:
        if self.has_format_controls:
            return self.output_format_combo.currentText()
        return KEEP_ORIGINAL_FORMAT

    def _get_output_size(self) -> tuple[int, int] | None:
        if not self.has_size_controls:
            return None

        current = self.size_combo.currentText()
        if current != CUSTOM_SIZE_LABEL:
            return self.size_lookup.get(current)

        try:
            width = int(self.custom_width_edit.text().strip())
            height = int(self.custom_height_edit.text().strip())
        except ValueError:
            return None

        if width <= 0 or height <= 0:
            return None
        return width, height

    def _get_target_size(self) -> int | None:
        if not self.has_compression_controls:
            return None

        for label, bytes_value in TARGET_SIZE_OPTIONS.items():
            if self.size_radios[label].isChecked():
                return bytes_value

        if self.custom_size_radio.isChecked():
            text = self.custom_size_edit.text().strip()
            try:
                value = float(text)
            except ValueError:
                return None
            if value <= 0:
                return None
            return int(value * 1_000_000)

        return None

    def _get_apply_logo(self) -> bool:
        if self.always_apply_logo:
            return True
        if self.has_optional_logo:
            return self.logo_checkbox.isChecked()
        return False

    def _get_selected_logo_assets(self) -> list[LogoAsset]:
        if not self._get_apply_logo():
            return []

        if not hasattr(self, "logo_list"):
            return []

        selected: list[LogoAsset] = []
        for row in range(self.logo_list.count()):
            item = self.logo_list.item(row)
            if item.isSelected():
                index = item.data(Qt.UserRole)
                if isinstance(index, int) and 0 <= index < len(self.logo_assets):
                    selected.append(self.logo_assets[index])

        if not selected and self.logo_list.count() == 1 and len(self.logo_assets) == 1:
            selected.append(self.logo_assets[0])

        return selected

    def _get_apply_watermark(self) -> bool:
        if self.always_apply_watermark:
            return True
        if self.has_optional_watermark:
            return self.watermark_checkbox.isChecked()
        return False

    def _get_watermark_options(self) -> tuple[WatermarkOptions | None, str | None]:
        if not self._get_apply_watermark():
            return None, None

        watermark_type = self.watermark_type_combo.currentText()
        opacity = self._read_int_value(self.watermark_opacity_edit, 1, 100)
        if opacity is None:
            return None, "请输入正确的水印透明度"

        angle = self._read_int_value(self.watermark_angle_edit, -180, 180)
        if angle is None:
            return None, "请输入正确的水印角度"

        position = self.watermark_position_combo.currentText()
        is_tile = position == WATERMARK_POSITION_TILE
        uses_margin = position not in {WATERMARK_POSITION_CUSTOM, WATERMARK_POSITION_TILE}

        margin = DEFAULT_WATERMARK_MARGIN
        if uses_margin:
            parsed_margin = self._read_int_value(self.watermark_margin_edit, 0, 10000)
            if parsed_margin is None:
                return None, "请输入正确的水印边距"
            margin = parsed_margin

        offset_x = self._read_int_value(self.watermark_offset_x_edit, -100000, 100000)
        offset_y = self._read_int_value(self.watermark_offset_y_edit, -100000, 100000)
        if not is_tile and (offset_x is None or offset_y is None):
            return None, "请输入正确的水印偏移"

        tile_spacing_x = self._read_int_value(self.watermark_tile_spacing_x_edit, 0, 10000)
        tile_spacing_y = self._read_int_value(self.watermark_tile_spacing_y_edit, 0, 10000)
        tile_offset_x = self._read_int_value(self.watermark_tile_offset_x_edit, -100000, 100000)
        tile_offset_y = self._read_int_value(self.watermark_tile_offset_y_edit, -100000, 100000)
        if is_tile and (
            tile_spacing_x is None
            or tile_spacing_y is None
            or tile_offset_x is None
            or tile_offset_y is None
        ):
            return None, "请输入正确的平铺参数"

        if watermark_type == WATERMARK_TYPE_TEXT:
            text = self.watermark_text_edit.text().strip()
            if not text:
                return None, "请输入水印文字"

            font_size = self._read_int_value(self.watermark_font_size_edit, 1, 500)
            if font_size is None:
                return None, "请输入正确的水印字号"

            color = WATERMARK_COLORS.get(self.watermark_color_combo.currentText(), WATERMARK_COLORS[DEFAULT_WATERMARK_COLOR])
            return (
                WatermarkOptions(
                    watermark_type=WATERMARK_TYPE_TEXT,
                    text=text,
                    color=color,
                    opacity=opacity,
                    position=position,
                    margin=margin,
                    font_size=font_size,
                    angle=angle,
                    offset_x=offset_x or 0,
                    offset_y=offset_y or 0,
                    tile_spacing_x=tile_spacing_x or 0,
                    tile_spacing_y=tile_spacing_y or 0,
                    tile_offset_x=tile_offset_x or 0,
                    tile_offset_y=tile_offset_y or 0,
                ),
                None,
            )

        if self.watermark_image_path is None:
            return None, "请选择水印图片"

        image_scale = self._read_int_value(self.watermark_image_scale_edit, 1, 100)
        if image_scale is None:
            return None, "请输入正确的水印缩放"

        try:
            watermark_image = self._load_watermark_image(self.watermark_image_path)
        except Exception:
            return None, "水印图片加载失败"

        return (
            WatermarkOptions(
                watermark_type=WATERMARK_TYPE_IMAGE,
                image=watermark_image,
                opacity=opacity,
                position=position,
                margin=margin,
                image_scale=image_scale,
                angle=angle,
                offset_x=offset_x or 0,
                offset_y=offset_y or 0,
                tile_spacing_x=tile_spacing_x or 0,
                tile_spacing_y=tile_spacing_y or 0,
                tile_offset_x=tile_offset_x or 0,
                tile_offset_y=tile_offset_y or 0,
            ),
            None,
        )

    def _load_watermark_image(self, path: Path) -> Image.Image:
        try:
            with Image.open(path) as image:
                return image.convert("RGBA").copy()
        except Exception as exc:
            raise RuntimeError("水印图片加载失败") from exc

    def _read_int_value(self, edit: LineEdit, minimum: int, maximum: int) -> int | None:
        try:
            value = int(edit.text().strip())
        except ValueError:
            return None
        if value < minimum or value > maximum:
            return None
        return value

    def _set_line_edit_int(self, edit: LineEdit, value: int) -> None:
        previous = edit.blockSignals(True)
        edit.setText(str(value))
        edit.blockSignals(previous)

    def _set_processing_state(self, processing: bool) -> None:
        self.import_button.setEnabled(not processing)
        self.remove_button.setEnabled(not processing)
        self.clear_button.setEnabled(not processing)
        self.start_button.setEnabled(not processing)
        self.cancel_button.setEnabled(processing)

        if self.has_size_controls:
            self.size_combo.setEnabled(not processing)
            custom_enabled = not processing and self.size_combo.currentText() == CUSTOM_SIZE_LABEL
            self.custom_width_edit.setEnabled(custom_enabled)
            self.custom_height_edit.setEnabled(custom_enabled)
        if self.has_format_controls:
            self.output_format_combo.setEnabled(not processing)
        if self.has_optional_logo:
            self.logo_checkbox.setEnabled(not processing)
        if hasattr(self, "logo_list"):
            self.logo_list.setEnabled(not processing and self._get_apply_logo())
        if self.has_compression_controls:
            self.custom_size_edit.setEnabled(not processing and self.custom_size_radio.isChecked())
            for button in self.size_group.buttons():
                button.setEnabled(not processing)
        if self.has_optional_watermark or self.always_apply_watermark:
            self._update_watermark_controls_state()
        for button in self.save_group.buttons():
            button.setEnabled(not processing)
        self.choose_save_button.setEnabled(not processing and self.choose_save_radio.isChecked())

    def _on_item_started(self, row: int, file_name: str) -> None:
        del file_name
        self._set_row_status(row, STATUS_PROCESSING)

    def _on_item_finished(self, row: int, status: str) -> None:
        self._set_row_status(row, status)

    def _on_progress_changed(
        self,
        current: int,
        total: int,
        file_name: str,
        success: int,
        failure: int,
        warning: int,
    ) -> None:
        value = int(current / total * 100) if total else 0
        self.progress_bar.setValue(value)
        self.progress_text.setText(f"总数：{total}    当前：{current}/{total}    文件：{file_name}")
        self._update_result_labels(total, success, failure, warning)

    def _on_processing_finished(
        self,
        total: int,
        success: int,
        failure: int,
        warning: int,
        last_output_dir: object,
        canceled: bool,
    ) -> None:
        self._set_processing_state(False)
        self._update_result_labels(total, success, failure, warning)
        if not canceled:
            self.progress_bar.setValue(100 if total else 0)
        self.last_output_location = last_output_dir if isinstance(last_output_dir, Path) else None
        self.open_location_button.setEnabled(self.last_output_location is not None)

        if canceled:
            self._show_message("warning", "处理已取消")
        elif failure:
            self._show_message("warning", "部分图片处理失败")
        else:
            self._show_message("success", "图片处理完成")

    def _clear_worker_refs(self) -> None:
        self.worker = None
        self.worker_thread = None

    def _set_row_status(self, row: int, status: str) -> None:
        item = self.table.item(row, 4)
        if item is not None:
            item.setText(status)

    def _update_result_labels(self, total: int, success: int, failure: int, warning: int) -> None:
        self.total_label.setText(f"总数：{total}")
        self.success_label.setText(f"成功：{success}")
        self.failure_label.setText(f"失败：{failure}")
        self.warning_label.setText(f"警告：{warning}")

    def _open_last_location(self, *_args) -> None:
        if self.last_output_location is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_location)))

    def _show_message(self, level: str, content: str) -> None:
        kwargs = dict(
            title="提示",
            content=content,
            duration=2200,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self.window(),
        )
        if level == "success":
            InfoBar.success(**kwargs)
        elif level == "error":
            InfoBar.error(**kwargs)
        elif level == "warning":
            InfoBar.warning(**kwargs)
        else:
            InfoBar.info(**kwargs)


class SettingsPage(QWidget):
    def __init__(self, current_theme: str, on_theme_changed) -> None:
        super().__init__()
        self.setObjectName("settingsPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.on_theme_changed = on_theme_changed

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 28)
        root_layout.setSpacing(14)

        title = QLabel("设置", self)
        title.setObjectName("TitleLabel")
        root_layout.addWidget(title)

        card = CardWidget(self)
        card.setObjectName("PanelCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        section_title = QLabel("主题", self)
        section_title.setObjectName("SectionTitle")
        card_layout.addWidget(section_title)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(10)
        theme_row.addWidget(QLabel("主题", self))
        self.theme_combo = ComboBox(self)
        self.theme_combo.addItems(list(THEME_LABELS.keys()))
        self.theme_combo.setCurrentText(THEME_VALUES.get(current_theme, "浅色"))
        self.theme_combo.setFixedWidth(150)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch(1)
        card_layout.addLayout(theme_row)

        root_layout.addWidget(card)
        root_layout.addStretch(1)

        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        self.apply_theme_styles()

    def apply_theme_styles(self) -> None:
        apply_background(self, theme_colors()["page"])
        self.setStyleSheet(theme_stylesheet())

    def _theme_changed(self, label: str) -> None:
        self.on_theme_changed(THEME_LABELS.get(label, "light"))


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("aboutPage")
        self.setAttribute(Qt.WA_StyledBackground, True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 28)
        root_layout.setSpacing(14)

        title = QLabel("关于", self)
        title.setObjectName("TitleLabel")
        root_layout.addWidget(title)

        info_card = CardWidget(self)
        info_card.setObjectName("PanelCard")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(18, 16, 18, 16)
        info_layout.setSpacing(10)

        section_title = QLabel(APP_NAME, self)
        section_title.setObjectName("SectionTitle")
        info_layout.addWidget(section_title)
        self._add_info_row(info_layout, "作者", APP_AUTHOR)
        self._add_info_row(info_layout, "版本", APP_VERSION)

        feature_card = CardWidget(self)
        feature_card.setObjectName("PanelCard")
        feature_layout = QVBoxLayout(feature_card)
        feature_layout.setContentsMargins(18, 16, 18, 16)
        feature_layout.setSpacing(10)

        feature_title = QLabel("功能", self)
        feature_title.setObjectName("SectionTitle")
        feature_layout.addWidget(feature_title)
        feature_text = QLabel("图片导入、尺寸处理、格式转换、图片压缩、LOGO叠加、水印、预览、主题", self)
        feature_text.setWordWrap(True)
        feature_layout.addWidget(feature_text)

        root_layout.addWidget(info_card)
        root_layout.addWidget(feature_card)
        root_layout.addStretch(1)
        self.apply_theme_styles()

    def _add_info_row(self, layout: QVBoxLayout, label: str, value: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel(label, self))
        value_label = QLabel(value, self)
        value_label.setObjectName("MutedLabel")
        row.addWidget(value_label)
        row.addStretch(1)
        layout.addLayout(row)

    def apply_theme_styles(self) -> None:
        apply_background(self, theme_colors()["page"])
        self.setStyleSheet(theme_stylesheet())


class ImageToolWindow(FluentWindow):
    def __init__(self) -> None:
        settings = QSettings("ImageTool", APP_NAME)
        theme_value = load_theme_value(settings)
        setTheme(THEME_MAP[theme_value])

        super().__init__()
        self.setObjectName("MainWindow")
        self.setMicaEffectEnabled(False)
        self.setCustomBackgroundColor("#f7f8fa", "#111315")
        self.stackedWidget.setObjectName("MainStackedWidget")
        self.stackedWidget.setAttribute(Qt.WA_StyledBackground, True)
        if hasattr(self.stackedWidget, "view"):
            self.stackedWidget.view.setObjectName("MainStackedView")
            self.stackedWidget.view.setAttribute(Qt.WA_StyledBackground, True)
        self.navigationInterface.setAttribute(Qt.WA_TranslucentBackground, False)
        if hasattr(self.navigationInterface, "panel"):
            self.navigationInterface.panel.setObjectName("NavigationPanel")
            self.navigationInterface.panel.setAttribute(Qt.WA_TranslucentBackground, False)
            self.navigationInterface.panel.setAttribute(Qt.WA_StyledBackground, True)
        self.settings = settings
        self.theme_value = theme_value
        self.preview_collapsed = False

        self.setWindowTitle(APP_NAME)
        self.resize(1220, 820)
        self.setMinimumSize(1060, 720)

        self.comprehensive_page = ImageOperationPage("综合处理", MODE_COMPREHENSIVE, "comprehensivePage")
        self.resize_page = ImageOperationPage("尺寸处理", MODE_RESIZE, "resizePage")
        self.format_page = ImageOperationPage("格式转换", MODE_FORMAT, "formatPage")
        self.compress_page = ImageOperationPage("图片压缩", MODE_COMPRESS, "compressPage")
        self.logo_page = ImageOperationPage("LOGO叠加", MODE_LOGO, "logoPage")
        self.watermark_page = ImageOperationPage("水印", MODE_WATERMARK, "watermarkPage")
        self.settings_page = SettingsPage(self.theme_value, self._set_theme_mode)
        self.about_page = AboutPage()
        self.operation_pages = [
            self.comprehensive_page,
            self.resize_page,
            self.format_page,
            self.compress_page,
            self.logo_page,
            self.watermark_page,
        ]
        self.theme_pages = [
            *self.operation_pages,
            self.settings_page,
            self.about_page,
        ]

        for page in self.operation_pages:
            page.preview_collapse_requested.connect(self._set_preview_sidebar_collapsed)

        self.addSubInterface(self.comprehensive_page, FIF.HOME, "综合处理")
        self.addSubInterface(self.resize_page, FIF.FIT_PAGE, "尺寸处理")
        self.addSubInterface(self.format_page, FIF.IMAGE_EXPORT, "格式转换")
        self.addSubInterface(self.compress_page, FIF.ZIP_FOLDER, "图片压缩")
        self.addSubInterface(self.logo_page, FIF.EDIT, "LOGO叠加")
        self.addSubInterface(self.watermark_page, FIF.TAG, "水印")
        self.addSubInterface(
            self.settings_page,
            FIF.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.about_page,
            FIF.INFO,
            "关于",
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setObjectName("NavigationInterface")
        self.navigationInterface.setAttribute(Qt.WA_StyledBackground, True)
        self.navigationInterface.setAttribute(Qt.WA_TranslucentBackground, False)
        self.navigationInterface.setExpandWidth(190)
        self.navigationInterface.setMinimumExpandWidth(160)
        self.navigationInterface.expand(useAni=False)
        self.switchTo(self.comprehensive_page)
        self._apply_theme_styles()

    def center_on_screen(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return

        available_geometry = screen.availableGeometry()
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(available_geometry.center())
        self.move(frame_geometry.topLeft())

    def _set_theme_mode(self, value: str) -> None:
        if value not in THEME_MAP:
            value = "light"
        self.theme_value = value
        self.settings.setValue(THEME_SETTING_KEY, value)
        setTheme(THEME_MAP[value])
        self._apply_theme_styles()

    def _set_preview_sidebar_collapsed(self, collapsed: bool) -> None:
        self.preview_collapsed = collapsed
        current_page = self.stackedWidget.currentWidget()
        for page in self.operation_pages:
            page.set_preview_collapsed(collapsed, animate=page is current_page)

    def _apply_theme_styles(self) -> None:
        colors = theme_colors()
        self.setCustomBackgroundColor("#f7f8fa", "#111315")
        self.setBackgroundColor(QColor(colors["page"]))
        apply_background(self, colors["page"])
        apply_background(self.navigationInterface, colors["page"])
        if hasattr(self.navigationInterface, "panel"):
            FluentStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface.panel)
            FluentStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface.panel.scrollWidget)
            nav_background_qss = f"""
                #NavigationPanel,
                #NavigationPanel #scrollWidget {{
                    background: {colors["page"]};
                }}
            """
            self.navigationInterface.panel.setStyleSheet(
                self.navigationInterface.panel.styleSheet() + nav_background_qss
            )
            apply_background(self.navigationInterface.panel, colors["page"])
            apply_background(self.navigationInterface.panel.scrollWidget, colors["page"])
        apply_background(self.stackedWidget, colors["page"])
        if hasattr(self.stackedWidget, "view"):
            apply_background(self.stackedWidget.view, colors["page"])
        self.setStyleSheet(theme_stylesheet())
        if hasattr(self, "stackedWidget"):
            self.stackedWidget.setStyleSheet(theme_stylesheet())
        for page in self.theme_pages:
            page.apply_theme_styles()
        self.update()


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    window = ImageToolWindow()
    window.center_on_screen()
    window.show()
    return app.exec()
