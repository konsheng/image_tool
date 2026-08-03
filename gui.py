from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image
from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QRect,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QCursor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPalette,
    QPixmap,
)
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
    IconWidget,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    NavigationItemPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    RadioButton,
    Slider,
    SmoothScrollArea,
    SpinBox,
    SwitchButton,
    TableWidget,
    Theme,
    TransparentToolButton,
    isDarkTheme,
    qrouter,
    setTheme,
)

from config import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    CUSTOM_SIZE_LABEL,
    DEFAULT_MANUAL_QUALITY,
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
    FEATURE_COMPRESS,
    FEATURE_COMPREHENSIVE,
    FEATURE_DEFAULTS,
    FEATURE_FORMAT,
    FEATURE_LABELS,
    FEATURE_LOGO,
    FEATURE_RESIZE,
    FEATURE_SETTINGS_PREFIX,
    FEATURE_WATERMARK,
    KEEP_ORIGINAL_FORMAT,
    MAX_MANUAL_QUALITY,
    MAX_OUTPUT_DIMENSION,
    MAX_OUTPUT_PIXELS,
    MIN_MANUAL_QUALITY,
    OUTPUT_FORMATS,
    OUTPUT_SIZE_PRESETS,
    PROJECT_ISSUES_URL,
    PROJECT_RELEASES_URL,
    PROJECT_URL,
    STATUS_CANCELED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCESS,
    TABLE_HEADERS,
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
    build_output_file_stem,
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
    render_encoded_preview_image,
    render_preview_image,
    watermark_position_for_layer,
)
from logo_manager import LogoAsset, list_logo_assets, load_logo_assets


MODE_COMPREHENSIVE = FEATURE_COMPREHENSIVE
MODE_RESIZE = FEATURE_RESIZE
MODE_FORMAT = FEATURE_FORMAT
MODE_COMPRESS = FEATURE_COMPRESS
MODE_LOGO = FEATURE_LOGO
MODE_WATERMARK = FEATURE_WATERMARK

COMPREHENSIVE_FEATURES = (
    MODE_RESIZE,
    MODE_FORMAT,
    MODE_COMPRESS,
    MODE_LOGO,
    MODE_WATERMARK,
)

LOGO_ICON_SIZE = QSize(96, 64)
LOGO_GRID_SIZE = QSize(132, 92)
LOGO_ITEM_SIZE = QSize(LOGO_GRID_SIZE.width() - 8, 76)
LOGO_MAX_VISIBLE_ROWS = 2

LOGO_RULE_DEFAULT = "default"
LOGO_RULE_NONE = "none"
LOGO_RULE_CUSTOM = "custom"
LOGO_COLUMN = 4
STATUS_COLUMN = 5

PREVIEW_SIDEBAR_EXPANDED_WIDTH = 340
PREVIEW_SIDEBAR_COLLAPSED_WIDTH = 48
PREVIEW_SIDEBAR_ANIMATION_MS = 180
ABOUT_CONTENT_MAX_WIDTH = 900

THEME_SETTING_KEY = "themeMode"
STATISTICS_PROCESSED_COUNT_KEY = "statistics/processed_count"
STATISTICS_SOURCE_BYTES_KEY = "statistics/source_bytes"
STATISTICS_OUTPUT_BYTES_KEY = "statistics/output_bytes"
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
            "accent_text": "#62dbe2",
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
        "accent_text": "#007f86",
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
        #StatisticsValue {{
            font-size: 20px;
            font-weight: 600;
        }}
        #AboutProductTitle {{
            font-size: 22px;
            font-weight: 600;
        }}
        #AboutTagline {{
            font-size: 14px;
            color: {colors["muted"]};
        }}
        #AboutVersionBadge {{
            background: transparent;
            border: 1px solid {colors["muted"]};
            border-radius: 6px;
        }}
        #AboutPrivacyLead {{
            color: {colors["accent_text"]};
            font-size: 14px;
            font-weight: 600;
        }}
        #AboutDivider {{
            background: {colors["card_border"]};
            border: none;
        }}
        #AboutActionText {{
            font-size: 14px;
        }}
        #AboutFooter {{
            color: {colors["muted"]};
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


def feature_setting_key(feature: str) -> str:
    return f"{FEATURE_SETTINGS_PREFIX}/{feature}/enabled"


def load_feature_states(settings: QSettings) -> dict[str, bool]:
    return {
        feature: settings.value(feature_setting_key(feature), default, type=bool)
        for feature, default in FEATURE_DEFAULTS.items()
    }


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


class AdaptiveLogoListWidget(ListWidget):
    """Keep the LOGO grid compact while exposing up to two full rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def sync_height(self) -> None:
        grid_size = self.gridSize()
        if grid_size.width() <= 0 or grid_size.height() <= 0:
            return

        available_width = max(grid_size.width(), self.viewport().width())
        # QListView keeps a one-pixel trailing boundary before it places the
        # next icon.  Matching that boundary avoids underestimating the row
        # count when the viewport is an exact multiple of the grid width.
        columns = max(1, (available_width - 1) // grid_size.width())
        rows = max(1, (max(1, self.count()) + columns - 1) // columns)
        visible_rows = min(rows, LOGO_MAX_VISIBLE_ROWS)
        target_height = visible_rows * grid_size.height() + self.frameWidth() * 2
        if self.height() != target_height:
            self.setFixedHeight(target_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.sync_height()


@dataclass
class ImageListItem:
    path: Path
    image_format: str
    dimensions: str
    size_text: str
    logo_rule: str = LOGO_RULE_DEFAULT
    logo_assets: list[LogoAsset] = field(default_factory=list)


@dataclass(frozen=True)
class ProcessingTask:
    row: int
    source_path: Path
    output_path: Path
    output_format: str
    apply_logo: bool
    logo_assets: list[LogoAsset]


@dataclass(frozen=True)
class ProcessedOutput:
    source_bytes: int
    output_bytes: int


@dataclass(frozen=True)
class ProcessingStatistics:
    processed_count: int = 0
    source_bytes: int = 0
    output_bytes: int = 0

    @property
    def net_saved_bytes(self) -> int:
        return self.source_bytes - self.output_bytes

    def with_output(self, output: ProcessedOutput) -> ProcessingStatistics:
        return ProcessingStatistics(
            processed_count=self.processed_count + 1,
            source_bytes=self.source_bytes + output.source_bytes,
            output_bytes=self.output_bytes + output.output_bytes,
        )


def _load_nonnegative_setting(settings: QSettings, key: str) -> int:
    try:
        return max(0, int(str(settings.value(key, "0")).strip()))
    except (TypeError, ValueError):
        return 0


def load_processing_statistics(settings: QSettings) -> ProcessingStatistics:
    return ProcessingStatistics(
        processed_count=_load_nonnegative_setting(settings, STATISTICS_PROCESSED_COUNT_KEY),
        source_bytes=_load_nonnegative_setting(settings, STATISTICS_SOURCE_BYTES_KEY),
        output_bytes=_load_nonnegative_setting(settings, STATISTICS_OUTPUT_BYTES_KEY),
    )


def save_processing_statistics(
    settings: QSettings,
    statistics: ProcessingStatistics,
) -> None:
    # Decimal strings preserve Python's unbounded counters across Qt backends.
    settings.setValue(STATISTICS_PROCESSED_COUNT_KEY, str(statistics.processed_count))
    settings.setValue(STATISTICS_SOURCE_BYTES_KEY, str(statistics.source_bytes))
    settings.setValue(STATISTICS_OUTPUT_BYTES_KEY, str(statistics.output_bytes))
    settings.sync()


@dataclass(frozen=True)
class PageSettings:
    output_size: tuple[int, int] | None
    output_choice: str
    quality: int | None
    apply_logo: bool
    logo_assets: list[LogoAsset]
    watermark_options: WatermarkOptions | None


@dataclass(frozen=True)
class PreviewRequest:
    request_id: int
    source_path: Path
    file_name: str
    source_size: int
    options: ProcessOptions
    logo_assets: list[LogoAsset]


@dataclass(frozen=True)
class PreviewOutcome:
    image: Image.Image
    compression: object | None
    file_name: str
    source_size: int
    watermark_options: WatermarkOptions | None


class PreviewWorker(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    finished = Signal()

    def __init__(self, request: PreviewRequest) -> None:
        super().__init__()
        self.request = request

    def run(self) -> None:
        request = self.request
        try:
            logos = load_logo_assets(request.logo_assets) if request.options.apply_logo else []
            options = ProcessOptions(
                output_format=request.options.output_format,
                output_size=request.options.output_size,
                quality=request.options.quality,
                apply_logo=request.options.apply_logo,
                logos=logos,
                watermark_options=request.options.watermark_options,
            )
            if request.options.quality is None:
                image = render_preview_image(request.source_path, options)
                compression = None
            else:
                encoded = render_encoded_preview_image(request.source_path, options)
                image = encoded.image
                compression = encoded.compression

            self.succeeded.emit(
                request.request_id,
                PreviewOutcome(
                    image=image,
                    compression=compression,
                    file_name=request.file_name,
                    source_size=request.source_size,
                    watermark_options=request.options.watermark_options,
                ),
            )
        except Exception as exc:
            self.failed.emit(request.request_id, str(exc) or "图片无法打开")
        finally:
            self.finished.emit()


class ProcessingWorker(QObject):
    item_started = Signal(int, str)
    item_finished = Signal(int, str)
    output_committed = Signal(object)
    progress_changed = Signal(int, int, str, int, int)
    finished = Signal(int, int, int, object, bool)

    def __init__(
        self,
        tasks: list[ProcessingTask],
        output_size: tuple[int, int] | None,
        quality: int | None,
        logo_cache: dict[str, Image.Image],
        watermark_options: WatermarkOptions | None,
    ) -> None:
        super().__init__()
        self.tasks = tasks
        self.output_size = output_size
        self.quality = quality
        self.logo_cache = logo_cache
        self.watermark_options = watermark_options
        self.cancel_requested = False

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        total = len(self.tasks)
        success = 0
        failure = 0
        last_output_dir: Path | None = None
        canceled = False

        for current, task in enumerate(self.tasks, start=1):
            file_name = task.source_path.name
            self.item_started.emit(task.row, file_name)

            try:
                source_size = task.source_path.stat().st_size
                logo_copies: list[Image.Image] = []
                if task.apply_logo:
                    for asset in task.logo_assets:
                        cached_logo = self.logo_cache.get(str(asset.path))
                        if cached_logo is None:
                            raise RuntimeError("内置LOGO加载失败")
                        logo_copies.append(cached_logo.copy())
                result = process_image(
                    task.source_path,
                    task.output_path,
                    ProcessOptions(
                        output_format=task.output_format,
                        output_size=self.output_size,
                        quality=self.quality,
                        apply_logo=task.apply_logo,
                        logos=logo_copies,
                        watermark_options=self.watermark_options,
                    ),
                )
                last_output_dir = result.output_path.parent
                try:
                    output_size = result.output_path.stat().st_size
                except OSError:
                    output_size = result.output_size
                self.output_committed.emit(
                    ProcessedOutput(
                        source_bytes=source_size,
                        output_bytes=output_size,
                    )
                )
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
            self.progress_changed.emit(current, total, file_name, success, failure)

            if self.cancel_requested:
                canceled = True
                for remaining_task in self.tasks[current:]:
                    self.item_finished.emit(remaining_task.row, STATUS_CANCELED)
                break

        self.finished.emit(total, success, failure, last_output_dir, canceled)


class ImageOperationPage(QWidget):
    preview_collapse_requested = Signal(bool)
    output_committed = Signal(object)

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
        self.processing_active = False
        self.preview_thread: QThread | None = None
        self.preview_worker: PreviewWorker | None = None
        self.pending_preview_request: PreviewRequest | None = None
        self.active_preview_request: PreviewRequest | None = None
        self.preview_request_serial = 0
        self.preview_pending_ready = False
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(300)
        self.preview_timer.timeout.connect(self._start_pending_preview)
        self.size_lookup = {size_to_text(size): size for size in OUTPUT_SIZE_PRESETS}
        self.logo_assets: list[LogoAsset] = []
        self.watermark_image_path: Path | None = None
        self.watermark_drag_delta = (0, 0)
        self.current_preview_image_size: tuple[int, int] | None = None
        self.feature_enabled = {feature: True for feature in COMPREHENSIVE_FEATURES}
        self.feature_sections: dict[str, QWidget] = {}

        self.setAcceptDrops(True)
        self._setup_ui()
        self._connect_signals()
        self._update_save_mode()
        self._update_custom_size_state()
        self._update_compression_controls_state()
        self._update_watermark_controls_state()
        self._update_result_labels(0, 0, 0)

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
    def supports_logo_overrides(self) -> bool:
        return self.has_optional_logo or self.always_apply_logo

    @property
    def has_optional_watermark(self) -> bool:
        return self.mode == MODE_COMPREHENSIVE

    @property
    def always_apply_watermark(self) -> bool:
        return self.mode == MODE_WATERMARK

    def is_feature_enabled(self, feature: str) -> bool:
        if self.mode != MODE_COMPREHENSIVE:
            return True
        return self.feature_enabled.get(feature, True)

    def set_feature_enabled(self, feature: str, enabled: bool) -> None:
        if self.mode != MODE_COMPREHENSIVE or feature not in self.feature_enabled:
            return

        self.feature_enabled[feature] = bool(enabled)
        section = self.feature_sections.get(feature)
        if section is not None:
            section.setVisible(bool(enabled))

        if feature == MODE_LOGO:
            self.table.setColumnHidden(
                LOGO_COLUMN,
                not self.supports_logo_overrides or not bool(enabled),
            )
            self._update_logo_grid_state()

        if feature in {MODE_RESIZE, MODE_FORMAT, MODE_COMPRESS}:
            self.output_card.setVisible(
                any(
                    self.is_feature_enabled(output_feature)
                    for output_feature in (MODE_RESIZE, MODE_FORMAT, MODE_COMPRESS)
                )
            )

        if feature == MODE_FORMAT:
            self._reset_save_location()
        elif feature == MODE_RESIZE:
            self._update_custom_size_state()
        elif feature == MODE_COMPRESS:
            self._update_compression_controls_state()
        elif feature == MODE_WATERMARK:
            self._update_watermark_controls_state()
        self._refresh_preview()

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

        self.statistics_card: CardWidget | None = None
        if self.mode == MODE_COMPREHENSIVE:
            self.statistics_card = self._build_statistics_card()
            layout.addWidget(self.statistics_card)

        list_card, list_layout = self._create_card("图片列表")
        self.list_card = list_card
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.import_button = self._create_button(PrimaryPushButton, "导入图片", FIF.ADD)
        self.import_folder_button = self._create_button(PushButton, "导入文件夹", FIF.FOLDER)
        self.remove_button = self._create_button(PushButton, "移除选中", FIF.DELETE)
        self.clear_button = self._create_button(PushButton, "清空列表", FIF.CLEAR_SELECTION)
        button_row.addWidget(self.import_button)
        button_row.addWidget(self.import_folder_button)
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
        header.setSectionResizeMode(LOGO_COLUMN, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(STATUS_COLUMN, QHeaderView.Stretch)
        self.table.setColumnHidden(LOGO_COLUMN, not self.supports_logo_overrides)
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

        if self.has_optional_logo or self.always_apply_logo:
            self.logo_card = self._build_logo_card()
            layout.addWidget(self.logo_card)
            if self.mode == MODE_COMPREHENSIVE:
                self.feature_sections[MODE_LOGO] = self.logo_card

        if self.has_optional_watermark or self.always_apply_watermark:
            self.watermark_card = self._build_watermark_card()
            layout.addWidget(self.watermark_card)
            if self.mode == MODE_COMPREHENSIVE:
                self.feature_sections[MODE_WATERMARK] = self.watermark_card

        self.output_card = self._build_output_card()
        save_card = self._build_save_card()
        if self.has_compression_controls:
            layout.addWidget(self.output_card)
            layout.addWidget(save_card)
        else:
            settings_row = QHBoxLayout()
            settings_row.setSpacing(14)
            settings_row.addWidget(self.output_card, 2)
            settings_row.addWidget(save_card, 2)
            layout.addLayout(settings_row)

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
        result_grid.addWidget(self.total_label, 0, 0)
        result_grid.addWidget(self.success_label, 0, 1)
        result_grid.addWidget(self.failure_label, 0, 2)
        result_grid.addItem(QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum), 0, 3)
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

    def _feature_section_layout(
        self,
        card: CardWidget,
        layout: QVBoxLayout,
        feature: str,
    ) -> QVBoxLayout:
        if self.mode != MODE_COMPREHENSIVE:
            return layout

        section = QWidget(card)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(10)
        layout.addWidget(section)
        self.feature_sections[feature] = section
        return section_layout

    def _build_output_card(self) -> CardWidget:
        title = "输出设置" if self.mode != MODE_COMPRESS else "压缩设置"
        card, layout = self._create_card(title)

        if self.has_size_controls:
            size_layout = self._feature_section_layout(card, layout, MODE_RESIZE)
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
            size_layout.addLayout(size_row)

            self.custom_size_container = QWidget(card)
            custom_row = QHBoxLayout(self.custom_size_container)
            custom_row.setContentsMargins(0, 0, 0, 0)
            self.custom_width_edit = LineEdit(self.custom_size_container)
            self.custom_width_edit.setPlaceholderText("宽")
            self.custom_width_edit.setFixedWidth(76)
            self.custom_height_edit = LineEdit(self.custom_size_container)
            self.custom_height_edit.setPlaceholderText("高")
            self.custom_height_edit.setFixedWidth(76)
            custom_row.addWidget(QLabel(CUSTOM_SIZE_LABEL, self.custom_size_container))
            custom_row.addWidget(self.custom_width_edit)
            custom_row.addWidget(QLabel("×", self.custom_size_container))
            custom_row.addWidget(self.custom_height_edit)
            custom_row.addWidget(QLabel("px", self.custom_size_container))
            custom_row.addStretch(1)
            size_layout.addWidget(self.custom_size_container)
        else:
            self._add_readonly_row(layout, "输出尺寸", "保持原尺寸")

        if self.has_format_controls:
            format_layout = self._feature_section_layout(card, layout, MODE_FORMAT)
            format_row = QHBoxLayout()
            format_row.addWidget(QLabel("输出格式", self))
            self.output_format_combo = ComboBox(self)
            self.output_format_combo.addItems(OUTPUT_FORMATS)
            self.output_format_combo.setCurrentText(DEFAULT_OUTPUT_FORMAT)
            self.output_format_combo.setFixedWidth(150)
            format_row.addWidget(self.output_format_combo)
            format_row.addStretch(1)
            format_layout.addLayout(format_row)
        else:
            self._add_readonly_row(layout, "输出格式", KEEP_ORIGINAL_FORMAT)

        if self.has_compression_controls:
            compression_layout = self._feature_section_layout(card, layout, MODE_COMPRESS)
            quality_row = QHBoxLayout()
            self.quality_label = QLabel("压缩质量", self)
            self.quality_slider = Slider(self)
            self.quality_slider.setOrientation(Qt.Horizontal)
            self.quality_slider.setRange(MIN_MANUAL_QUALITY, MAX_MANUAL_QUALITY)
            self.quality_slider.setValue(DEFAULT_MANUAL_QUALITY)
            self.quality_slider.setMinimumWidth(120)
            self.quality_spinbox = SpinBox(self)
            self.quality_spinbox.setRange(MIN_MANUAL_QUALITY, MAX_MANUAL_QUALITY)
            self.quality_spinbox.setValue(DEFAULT_MANUAL_QUALITY)
            self.quality_spinbox.setFixedWidth(160)
            self.quality_reset_button = self._create_button(
                PushButton,
                "重置为默认值",
                FIF.RETURN,
            )
            self.quality_reset_button.setToolTip(
                f"将压缩质量恢复为 {DEFAULT_MANUAL_QUALITY}"
            )
            quality_row.addWidget(self.quality_label)
            quality_row.addWidget(self.quality_slider, 1)
            quality_row.addWidget(self.quality_spinbox)
            quality_row.addWidget(self.quality_reset_button)
            quality_row.addStretch(1)
            compression_layout.addLayout(quality_row)

            self.compression_hint_label = QLabel(
                "质量设置仅适用于 JPG/WEBP；PNG 将使用无损编码。",
                self,
            )
            self.compression_hint_label.setObjectName("MutedLabel")
            self.compression_hint_label.setWordWrap(True)
            compression_layout.addWidget(self.compression_hint_label)

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

        self.logo_list = AdaptiveLogoListWidget(self)
        self.logo_list.setViewMode(QListView.IconMode)
        self.logo_list.setResizeMode(QListView.Adjust)
        self.logo_list.setMovement(QListView.Static)
        self.logo_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.logo_list.setIconSize(LOGO_ICON_SIZE)
        self.logo_list.setGridSize(LOGO_GRID_SIZE)
        self.logo_list.setSpacing(8)
        self._load_logo_grid()
        layout.addWidget(self.logo_list)

        override_row = QHBoxLayout()
        override_row.setSpacing(10)
        self.logo_apply_selected_button = self._create_button(PushButton, "应用到选中图片", FIF.ACCEPT)
        self.logo_disable_selected_button = self._create_button(PushButton, "选中图片不叠加", FIF.CANCEL)
        self.logo_restore_default_button = self._create_button(PushButton, "恢复默认", FIF.RETURN)
        override_row.addWidget(self.logo_apply_selected_button)
        override_row.addWidget(self.logo_disable_selected_button)
        override_row.addWidget(self.logo_restore_default_button)
        override_row.addStretch(1)
        layout.addLayout(override_row)
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
        self.original_save_radio = RadioButton(self)
        self.original_save_radio.setText("保存到原图位置")
        self.original_save_radio.setChecked(True)
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

    def _build_statistics_card(self) -> CardWidget:
        card = CardWidget(self)
        card.setObjectName("PanelCard")
        card.setToolTip("统计所有功能页成功生成的图片")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(36)

        count_block = QVBoxLayout()
        count_block.setSpacing(2)
        count_caption = QLabel("累计处理图片", self)
        count_caption.setObjectName("MutedLabel")
        self.statistics_count_label = QLabel("0 张", self)
        self.statistics_count_label.setObjectName("StatisticsValue")
        count_block.addWidget(count_caption)
        count_block.addWidget(self.statistics_count_label)

        space_block = QVBoxLayout()
        space_block.setSpacing(2)
        self.statistics_space_caption = QLabel("累计净节省空间", self)
        self.statistics_space_caption.setObjectName("MutedLabel")
        self.statistics_space_label = QLabel("0B", self)
        self.statistics_space_label.setObjectName("StatisticsValue")
        space_block.addWidget(self.statistics_space_caption)
        space_block.addWidget(self.statistics_space_label)

        layout.addLayout(count_block)
        layout.addLayout(space_block)
        layout.addStretch(1)
        return card

    def set_processing_statistics(self, statistics: ProcessingStatistics) -> None:
        if self.mode != MODE_COMPREHENSIVE or self.statistics_card is None:
            return

        self.statistics_count_label.setText(f"{statistics.processed_count:,} 张")
        net_saved = statistics.net_saved_bytes
        if net_saved >= 0:
            self.statistics_space_caption.setText("累计净节省空间")
        else:
            self.statistics_space_caption.setText("累计净增加空间")
        self.statistics_space_label.setText(bytes_to_display(abs(net_saved)))

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
        self.import_folder_button.clicked.connect(self._select_image_folder)
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
            self.quality_slider.valueChanged.connect(self._on_quality_slider_changed)
            self.quality_spinbox.valueChanged.connect(self._on_quality_spinbox_changed)
            self.quality_reset_button.clicked.connect(self._reset_quality_to_default)
        if self.has_optional_logo:
            self.logo_checkbox.stateChanged.connect(self._update_logo_grid_state)
            self.logo_checkbox.stateChanged.connect(self._refresh_preview)
        if hasattr(self, "logo_list"):
            self.logo_list.itemSelectionChanged.connect(self._refresh_preview)
            self.logo_apply_selected_button.clicked.connect(self._apply_current_logos_to_selected_images)
            self.logo_disable_selected_button.clicked.connect(self._disable_logo_for_selected_images)
            self.logo_restore_default_button.clicked.connect(self._restore_default_logo_for_selected_images)
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
                if not url.isLocalFile():
                    continue
                path = Path(url.toLocalFile())
                if path.is_dir() or is_supported_image(path):
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

    def _select_image_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "导入文件夹", "")
        if selected:
            self._add_paths([selected])

    def _add_paths(self, paths: Iterable[str]) -> None:
        existing = {str(item.path.resolve()).lower() for item in self.items}
        unsupported = False
        empty_folder = False
        added = 0
        first_new_row = self.table.rowCount()

        for raw_path in paths:
            path = Path(raw_path)
            candidate_paths: list[Path]
            if path.is_dir():
                candidate_paths = self._folder_image_paths(path)
                if not candidate_paths:
                    empty_folder = True
            elif path.is_file():
                candidate_paths = [path]
            else:
                continue

            for path in candidate_paths:
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
        if empty_folder:
            self._show_message("warning", "文件夹中没有支持的图片")
        if added:
            self._reset_save_location()
            if not self.table.selectionModel().selectedRows():
                self.table.selectRow(first_new_row)
            self._refresh_preview()

    def _folder_image_paths(self, folder: Path) -> list[Path]:
        try:
            return [
                path
                for path in sorted(folder.iterdir(), key=lambda item: item.name.lower())
                if path.is_file() and is_supported_image(path)
            ]
        except OSError:
            return []

    def _load_logo_grid(self) -> None:
        self.logo_assets = list_logo_assets()
        self.logo_list.clear()

        if not self.logo_assets:
            item = QListWidgetItem("无可用LOGO")
            item.setFlags(Qt.NoItemFlags)
            item.setSizeHint(LOGO_ITEM_SIZE)
            self.logo_list.addItem(item)
            QTimer.singleShot(0, self.logo_list.sync_height)
            return

        for index, asset in enumerate(self.logo_assets):
            item = QListWidgetItem(self._logo_preview_icon(asset.path), asset.name)
            item.setData(Qt.UserRole, index)
            item.setToolTip(asset.path.name)
            item.setTextAlignment(Qt.AlignCenter)
            item.setSizeHint(LOGO_ITEM_SIZE)
            self.logo_list.addItem(item)

        self.logo_list.item(0).setSelected(True)
        self.logo_list.setCurrentRow(0)
        QTimer.singleShot(0, self.logo_list.sync_height)

    def _logo_preview_icon(self, path: Path) -> QIcon:
        """Build a compact preview without changing the source overlay asset."""
        try:
            with Image.open(path) as image:
                preview = image.convert("RGBA")
                alpha_bounds = preview.getchannel("A").getbbox()
                if alpha_bounds is not None:
                    preview = preview.crop(alpha_bounds)
                preview.thumbnail(
                    (LOGO_ICON_SIZE.width(), LOGO_ICON_SIZE.height()),
                    Image.Resampling.LANCZOS,
                )

                buffer = BytesIO()
                preview.save(buffer, format="PNG")
                pixmap = QPixmap()
                if pixmap.loadFromData(buffer.getvalue(), "PNG"):
                    return QIcon(pixmap)
        except Exception:
            pass

        return QIcon(str(path))

    def _update_logo_grid_state(self, *_args) -> None:
        if hasattr(self, "logo_list"):
            self.logo_list.setEnabled(not self.processing_active)
        self._refresh_preview()

    def _selected_table_rows(self) -> list[int]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return []
        return sorted({index.row() for index in selection_model.selectedRows()})

    def _apply_current_logos_to_selected_images(self, *_args) -> None:
        rows = self._selected_table_rows()
        if not rows:
            self._show_message("warning", "请选择图片")
            return

        logo_assets = self._get_selected_logo_assets(respect_apply_logo=False)
        if not logo_assets:
            self._show_message("warning", "请选择LOGO")
            return

        for row in rows:
            if 0 <= row < len(self.items):
                self.items[row].logo_rule = LOGO_RULE_CUSTOM
                self.items[row].logo_assets = list(logo_assets)
                self._update_logo_cell(row)
        self._refresh_preview()

    def _disable_logo_for_selected_images(self, *_args) -> None:
        rows = self._selected_table_rows()
        if not rows:
            self._show_message("warning", "请选择图片")
            return

        for row in rows:
            if 0 <= row < len(self.items):
                self.items[row].logo_rule = LOGO_RULE_NONE
                self.items[row].logo_assets = []
                self._update_logo_cell(row)
        self._refresh_preview()

    def _restore_default_logo_for_selected_images(self, *_args) -> None:
        rows = self._selected_table_rows()
        if not rows:
            self._show_message("warning", "请选择图片")
            return

        for row in rows:
            if 0 <= row < len(self.items):
                self.items[row].logo_rule = LOGO_RULE_DEFAULT
                self.items[row].logo_assets = []
                self._update_logo_cell(row)
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

        processing = self.processing_active
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

        self.preview_request_serial += 1
        request_id = self.preview_request_serial
        self.preview_timer.stop()
        self.pending_preview_request = None
        self.preview_pending_ready = False
        self._update_compression_format_hint()

        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            self._set_preview_message("请选择图片")
            return

        row = rows[0].row()
        if row < 0 or row >= len(self.items):
            self._set_preview_message("请选择图片")
            return

        output_size = self._get_output_size()
        if (
            self.has_size_controls
            and self.is_feature_enabled(MODE_RESIZE)
            and output_size is None
        ):
            self._set_preview_message("请输入正确的输出尺寸")
            return

        quality = self._get_manual_quality()
        if (
            self.has_compression_controls
            and self.is_feature_enabled(MODE_COMPRESS)
            and quality is None
        ):
            self._set_preview_message("请输入正确的压缩质量")
            return

        apply_logo, logo_assets = self._effective_logo_for_item(self.items[row])
        if apply_logo and not logo_assets:
            self._set_preview_message("请选择LOGO")
            return

        watermark_options, watermark_error = self._get_watermark_options()
        if watermark_error:
            self._set_preview_message(watermark_error)
            return

        try:
            item = self.items[row]
            output_format, _ = resolve_output_format(self._get_output_choice(), item.path)
            source_size = item.path.stat().st_size
            request = PreviewRequest(
                request_id=request_id,
                source_path=item.path,
                file_name=item.path.name,
                source_size=source_size,
                options=ProcessOptions(
                    output_format=output_format,
                    output_size=output_size,
                    quality=quality,
                    apply_logo=apply_logo,
                    logos=[],
                    watermark_options=watermark_options,
                ),
                logo_assets=list(logo_assets),
            )
        except Exception as exc:
            self._set_preview_message(self._preview_error_message(str(exc)))
            return

        self.pending_preview_request = request
        self.preview_info_label.setText("正在生成预览…")
        self.preview_timer.start()

    def _start_pending_preview(self) -> None:
        self.preview_pending_ready = True
        if self.preview_thread is not None:
            return

        request = self.pending_preview_request
        if request is None or request.request_id != self.preview_request_serial:
            self.preview_pending_ready = False
            return

        self.pending_preview_request = None
        self.preview_pending_ready = False
        self.active_preview_request = request
        thread = QThread(self)
        worker = PreviewWorker(request)
        self.preview_thread = thread
        self.preview_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_preview_succeeded)
        worker.failed.connect(self._on_preview_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_preview_thread_finished)
        thread.start()

    def _on_preview_succeeded(self, request_id: int, outcome: object) -> None:
        if request_id != self.preview_request_serial or not isinstance(outcome, PreviewOutcome):
            return
        self._set_preview_image(
            outcome.image,
            outcome.file_name,
            outcome.watermark_options,
            outcome.compression,
            outcome.source_size,
        )

    def _on_preview_failed(self, request_id: int, reason: str) -> None:
        if request_id != self.preview_request_serial:
            return
        self._set_preview_message(self._preview_error_message(reason))

    def _on_preview_thread_finished(self) -> None:
        self.preview_worker = None
        self.preview_thread = None
        self.active_preview_request = None
        if self.pending_preview_request is None:
            return
        if self.preview_pending_ready:
            self._start_pending_preview()
        elif not self.preview_timer.isActive():
            self.preview_timer.start()

    def _preview_error_message(self, reason: str) -> str:
        reason = reason or "图片无法打开"
        if "内置LOGO" in reason:
            return "内置LOGO加载失败"
        if "水印图片加载失败" in reason:
            return "水印图片加载失败"
        if "请选择水印图片" in reason:
            return "请选择水印图片"
        if "请输入水印文字" in reason:
            return "请输入水印文字"
        if "图片无法打开" in reason:
            return "图片无法打开"
        return "预览生成失败"

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
        compression: object | None = None,
        source_size: int | None = None,
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
        self.preview_image_label.set_drag_enabled(watermark_options is not None and not self.processing_active)
        self.current_preview_image_size = image.size
        lines = [f"{file_name}    {image.width}×{image.height}"]
        if compression is not None:
            output_size = getattr(compression, "size", None)
            lines.append(
                f"原始大小：{bytes_to_display(source_size)}    "
                f"预计输出：{bytes_to_display(output_size)}"
            )
            if source_size and isinstance(output_size, int):
                size_delta = (output_size / source_size - 1) * 100
                if size_delta > 0:
                    detail_parts = [f"增大比例：{size_delta:.1f}%"]
                else:
                    detail_parts = [f"缩减比例：{-size_delta:.1f}%"]
            else:
                detail_parts = ["缩减比例：-"]

            actual_quality = getattr(compression, "quality", None)
            if isinstance(actual_quality, int):
                detail_parts.append(f"实际质量：{actual_quality}")
            else:
                detail_parts.append("编码：PNG 无损")
            lines.append("    ".join(detail_parts))
        self.preview_info_label.setText("\n".join(lines))

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
        values = [
            item.path.name,
            item.image_format,
            item.dimensions,
            item.size_text,
            self._logo_display_text(item),
            STATUS_PENDING,
        ]
        for column, value in enumerate(values):
            table_item = QTableWidgetItem(value)
            table_item.setTextAlignment(Qt.AlignCenter if column else Qt.AlignVCenter | Qt.AlignLeft)
            if column == 0:
                table_item.setData(Qt.UserRole, str(item.path))
            if column == LOGO_COLUMN:
                table_item.setToolTip(self._logo_tooltip_text(item))
            self.table.setItem(row, column, table_item)
        self.table.setRowHeight(row, 38)

    def _logo_display_text(self, item: ImageListItem) -> str:
        if not self.supports_logo_overrides:
            return "-"
        if item.logo_rule == LOGO_RULE_NONE:
            return "不叠加"
        if item.logo_rule == LOGO_RULE_CUSTOM:
            return f"自定义：{len(item.logo_assets)}个"
        return "默认"

    def _logo_tooltip_text(self, item: ImageListItem) -> str:
        if item.logo_rule != LOGO_RULE_CUSTOM or not item.logo_assets:
            return self._logo_display_text(item)
        names = "、".join(asset.name for asset in item.logo_assets)
        return f"{self._logo_display_text(item)}\n{names}"

    def _update_logo_cell(self, row: int) -> None:
        if not self.supports_logo_overrides or row < 0 or row >= len(self.items):
            return
        table_item = self.table.item(row, LOGO_COLUMN)
        if table_item is None:
            table_item = QTableWidgetItem()
            table_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, LOGO_COLUMN, table_item)
        table_item.setText(self._logo_display_text(self.items[row]))
        table_item.setToolTip(self._logo_tooltip_text(self.items[row]))

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
        self._update_result_labels(0, 0, 0)
        self.progress_bar.setValue(0)
        self.progress_text.setText("总数：0    当前：0/0    文件：-")
        self._refresh_preview()

    def _update_custom_size_state(self, *_args) -> None:
        if not self.has_size_controls:
            return
        custom_selected = self.size_combo.currentText() == CUSTOM_SIZE_LABEL
        was_hidden = self.custom_size_container.isHidden()
        self.custom_size_container.setVisible(custom_selected)
        enabled = (
            custom_selected
            and self.is_feature_enabled(MODE_RESIZE)
            and not self.processing_active
        )
        self.custom_width_edit.setEnabled(enabled)
        self.custom_height_edit.setEnabled(enabled)
        if enabled and was_hidden:
            self.custom_width_edit.setFocus()

    def _update_compression_controls_state(self, *_args) -> None:
        if not self.has_compression_controls:
            return

        quality_enabled = (
            self.is_feature_enabled(MODE_COMPRESS)
            and not self.processing_active
        )
        self.quality_label.setEnabled(quality_enabled)
        self.quality_slider.setEnabled(quality_enabled)
        self.quality_spinbox.setEnabled(quality_enabled)
        self._update_quality_reset_button_state()
        self._update_compression_format_hint()

    def _on_quality_slider_changed(self, value: int) -> None:
        self._update_quality_reset_button_state()
        if self.quality_spinbox.value() != value:
            self.quality_spinbox.setValue(value)
            return
        self._refresh_preview()

    def _on_quality_spinbox_changed(self, value: int) -> None:
        self._update_quality_reset_button_state()
        if self.quality_slider.value() != value:
            self.quality_slider.setValue(value)
            return
        self._refresh_preview()

    def _reset_quality_to_default(self, *_args) -> None:
        self.quality_slider.setValue(DEFAULT_MANUAL_QUALITY)
        self._update_quality_reset_button_state()

    def _update_quality_reset_button_state(self) -> None:
        enabled = (
            self.is_feature_enabled(MODE_COMPRESS)
            and not self.processing_active
            and self.quality_spinbox.value() != DEFAULT_MANUAL_QUALITY
        )
        self.quality_reset_button.setEnabled(enabled)

    def _update_compression_format_hint(self) -> None:
        if not self.has_compression_controls:
            return

        output_format: str | None = None
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if rows and 0 <= rows[0].row() < len(self.items):
            output_format, _ = resolve_output_format(
                self._get_output_choice(),
                self.items[rows[0].row()].path,
            )
        elif self.has_format_controls:
            output_format, _ = resolve_output_format(self._get_output_choice(), Path("preview.jpg"))

        if output_format == "PNG":
            text = "当前输出为 PNG：质量设置不生效，将使用无损编码。"
        else:
            text = "质量设置仅适用于 JPG/WEBP；PNG 将使用无损编码。"
        self.compression_hint_label.setText(text)

    def _update_save_mode(self, *_args) -> None:
        choose_mode = self.choose_save_radio.isChecked()
        self.choose_save_button.setEnabled(choose_mode and not self.processing_active)
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
            apply_logo, logo_assets = self._effective_logo_for_item(self.items[0])
            suffix_parts = [asset.output_name for asset in logo_assets] if apply_logo else None
            default_path = source.with_name(f"{build_output_file_stem(source, suffix_parts)}{suffix}")
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

        tasks = self._prepare_tasks(settings)
        if not tasks:
            return

        logo_cache = self._load_task_logo_cache(tasks)
        if logo_cache is None:
            return

        for row in range(self.table.rowCount()):
            self._set_row_status(row, STATUS_PENDING)

        self._set_processing_state(True)
        self._update_result_labels(len(tasks), 0, 0)
        self.progress_bar.setValue(0)
        self.progress_text.setText(f"总数：{len(tasks)}    当前：0/{len(tasks)}    文件：-")
        self.last_output_location = None
        self.open_location_button.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = ProcessingWorker(
            tasks=tasks,
            output_size=settings.output_size,
            quality=settings.quality,
            logo_cache=logo_cache,
            watermark_options=settings.watermark_options,
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.item_started.connect(self._on_item_started)
        self.worker.item_finished.connect(self._on_item_finished)
        self.worker.output_committed.connect(self._forward_output_committed)
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

    def _forward_output_committed(self, output: object) -> None:
        self.output_committed.emit(output)

    def _get_page_settings(self) -> PageSettings | None:
        output_size = self._get_output_size()
        if (
            self.has_size_controls
            and self.is_feature_enabled(MODE_RESIZE)
            and output_size is None
        ):
            self._show_message("warning", "请输入正确的输出尺寸")
            return None

        quality = self._get_manual_quality()
        if (
            self.has_compression_controls
            and self.is_feature_enabled(MODE_COMPRESS)
            and quality is None
        ):
            self._show_message("warning", "请输入正确的压缩质量")
            return None

        logo_assets = self._get_selected_logo_assets(respect_apply_logo=False)
        if self._default_logo_is_required() and not logo_assets:
            self._show_message("warning", "请选择LOGO")
            return None
        if self.is_feature_enabled(MODE_LOGO):
            for item in self.items:
                if item.logo_rule == LOGO_RULE_CUSTOM and not item.logo_assets:
                    self._show_message("warning", "请选择LOGO")
                    return None

        watermark_options, watermark_error = self._get_watermark_options()
        if watermark_error:
            self._show_message("warning", watermark_error)
            return None

        return PageSettings(
            output_size=output_size,
            output_choice=self._get_output_choice(),
            quality=quality,
            apply_logo=self._get_apply_logo(),
            logo_assets=logo_assets,
            watermark_options=watermark_options,
        )

    def _prepare_tasks(self, settings: PageSettings) -> list[ProcessingTask]:
        if self.choose_save_radio.isChecked() and self.selected_save_path is None:
            if not self._choose_save_location():
                self._show_message("warning", "请选择保存位置")
                return []

        tasks: list[ProcessingTask] = []
        reserved: set[str] = set()

        if self.choose_save_radio.isChecked() and len(self.items) == 1:
            item = self.items[0]
            output_format, suffix = resolve_output_format(settings.output_choice, item.path)
            selected = ensure_suffix(Path(self.selected_save_path), suffix)
            output_path = ensure_unique_path(selected, reserved)
            apply_logo, logo_assets = self._effective_logo_for_item(item, settings.apply_logo, settings.logo_assets)
            tasks.append(
                ProcessingTask(
                    row=0,
                    source_path=item.path,
                    output_path=output_path,
                    output_format=output_format,
                    apply_logo=apply_logo,
                    logo_assets=logo_assets,
                )
            )
            return tasks

        for row, item in enumerate(self.items):
            output_format, _ = resolve_output_format(settings.output_choice, item.path)
            if self.original_save_radio.isChecked():
                output_dir = item.path.parent
            else:
                output_dir = Path(self.selected_save_path)
            apply_logo, logo_assets = self._effective_logo_for_item(item, settings.apply_logo, settings.logo_assets)
            suffix_parts = [asset.output_name for asset in logo_assets] if apply_logo else None
            output_path = build_default_output_path(
                item.path,
                output_dir,
                settings.output_choice,
                reserved,
                suffix_parts,
            )
            tasks.append(
                ProcessingTask(
                    row=row,
                    source_path=item.path,
                    output_path=output_path,
                    output_format=output_format,
                    apply_logo=apply_logo,
                    logo_assets=logo_assets,
                )
            )

        return tasks

    def _get_output_choice(self) -> str:
        if self.has_format_controls and self.is_feature_enabled(MODE_FORMAT):
            return self.output_format_combo.currentText()
        return KEEP_ORIGINAL_FORMAT

    def _get_output_size(self) -> tuple[int, int] | None:
        if not self.has_size_controls or not self.is_feature_enabled(MODE_RESIZE):
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
        if width > MAX_OUTPUT_DIMENSION or height > MAX_OUTPUT_DIMENSION:
            return None
        if width * height > MAX_OUTPUT_PIXELS:
            return None
        return width, height

    def _get_manual_quality(self) -> int | None:
        if (
            not self.has_compression_controls
            or not self.is_feature_enabled(MODE_COMPRESS)
        ):
            return None
        value = self.quality_spinbox.value()
        if value < MIN_MANUAL_QUALITY or value > MAX_MANUAL_QUALITY:
            return None
        return value

    def _get_apply_logo(self) -> bool:
        if not self.is_feature_enabled(MODE_LOGO):
            return False
        if self.always_apply_logo:
            return True
        if self.has_optional_logo:
            return self.logo_checkbox.isChecked()
        return False

    def _get_selected_logo_assets(self, respect_apply_logo: bool = True) -> list[LogoAsset]:
        if respect_apply_logo and not self._get_apply_logo():
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

    def _effective_logo_for_item(
        self,
        item: ImageListItem,
        default_apply_logo: bool | None = None,
        default_logo_assets: list[LogoAsset] | None = None,
    ) -> tuple[bool, list[LogoAsset]]:
        if not self.supports_logo_overrides or not self.is_feature_enabled(MODE_LOGO):
            return False, []

        if item.logo_rule == LOGO_RULE_CUSTOM:
            return True, list(item.logo_assets)
        if item.logo_rule == LOGO_RULE_NONE:
            return False, []

        apply_logo = self._get_apply_logo() if default_apply_logo is None else default_apply_logo
        if not apply_logo:
            return False, []

        logo_assets = (
            self._get_selected_logo_assets(respect_apply_logo=False)
            if default_logo_assets is None
            else default_logo_assets
        )
        return True, list(logo_assets)

    def _default_logo_is_required(self) -> bool:
        if not self.supports_logo_overrides or not self._get_apply_logo():
            return False
        return any(item.logo_rule == LOGO_RULE_DEFAULT for item in self.items)

    def _load_task_logo_cache(self, tasks: list[ProcessingTask]) -> dict[str, Image.Image] | None:
        unique_assets: dict[str, LogoAsset] = {}
        for task in tasks:
            if not task.apply_logo:
                continue
            if not task.logo_assets:
                self._show_message("warning", "请选择LOGO")
                return None
            for asset in task.logo_assets:
                unique_assets.setdefault(str(asset.path), asset)

        if not unique_assets:
            return {}

        assets = list(unique_assets.values())
        try:
            loaded_logos = load_logo_assets(assets)
        except Exception:
            self._show_message("error", "内置LOGO加载失败")
            return None

        return {str(asset.path): logo for asset, logo in zip(assets, loaded_logos)}

    def _get_apply_watermark(self) -> bool:
        if not self.is_feature_enabled(MODE_WATERMARK):
            return False
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
        self.processing_active = processing
        self.import_button.setEnabled(not processing)
        self.import_folder_button.setEnabled(not processing)
        self.remove_button.setEnabled(not processing)
        self.clear_button.setEnabled(not processing)
        self.start_button.setEnabled(not processing)
        self.cancel_button.setEnabled(processing)

        if self.has_size_controls:
            self.size_combo.setEnabled(not processing)
            self._update_custom_size_state()
        if self.has_format_controls:
            self.output_format_combo.setEnabled(not processing)
        if self.has_optional_logo:
            self.logo_checkbox.setEnabled(not processing)
        if hasattr(self, "logo_list"):
            self.logo_list.setEnabled(not processing)
            self.logo_apply_selected_button.setEnabled(not processing)
            self.logo_disable_selected_button.setEnabled(not processing)
            self.logo_restore_default_button.setEnabled(not processing)
        if self.has_compression_controls:
            self._update_compression_controls_state()
        if self.has_optional_watermark or self.always_apply_watermark:
            self._update_watermark_controls_state()
        for button in self.save_group.buttons():
            button.setEnabled(not processing)
        self.choose_save_button.setEnabled(not processing and self.choose_save_radio.isChecked())
        if processing:
            self.preview_image_label.set_drag_enabled(False)

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
    ) -> None:
        value = int(current / total * 100) if total else 0
        self.progress_bar.setValue(value)
        self.progress_text.setText(f"总数：{total}    当前：{current}/{total}    文件：{file_name}")
        self._update_result_labels(total, success, failure)

    def _on_processing_finished(
        self,
        total: int,
        success: int,
        failure: int,
        last_output_dir: object,
        canceled: bool,
    ) -> None:
        self._update_result_labels(total, success, failure)
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
        if self.processing_active:
            self._set_processing_state(False)
            self._refresh_preview()

    def shutdown(self) -> None:
        """Wait for page-owned workers before Qt destroys their threads."""
        self.preview_request_serial += 1
        self.preview_timer.stop()
        self.pending_preview_request = None
        self.preview_pending_ready = False

        preview_thread = self.preview_thread
        if preview_thread is not None and preview_thread.isRunning():
            preview_thread.quit()
            preview_thread.wait()
        self.preview_worker = None
        self.preview_thread = None
        self.active_preview_request = None

        if self.worker is not None:
            self.worker.request_cancel()
        processing_thread = self.worker_thread
        if processing_thread is not None and processing_thread.isRunning():
            processing_thread.quit()
            processing_thread.wait()
        self.worker = None
        self.worker_thread = None

    def _set_row_status(self, row: int, status: str) -> None:
        item = self.table.item(row, STATUS_COLUMN)
        if item is not None:
            item.setText(status)

    def _update_result_labels(self, total: int, success: int, failure: int) -> None:
        self.total_label.setText(f"总数：{total}")
        self.success_label.setText(f"成功：{success}")
        self.failure_label.setText(f"失败：{failure}")

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
    def __init__(
        self,
        current_theme: str,
        on_theme_changed,
        feature_states: dict[str, bool],
        on_feature_changed,
    ) -> None:
        super().__init__()
        self.setObjectName("settingsPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.on_theme_changed = on_theme_changed
        self.on_feature_changed = on_feature_changed
        self.feature_switches: dict[str, SwitchButton] = {}

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

        feature_card = CardWidget(self)
        feature_card.setObjectName("PanelCard")
        feature_layout = QVBoxLayout(feature_card)
        feature_layout.setContentsMargins(18, 16, 18, 16)
        feature_layout.setSpacing(12)

        feature_title = QLabel("功能开关", self)
        feature_title.setObjectName("SectionTitle")
        feature_layout.addWidget(feature_title)

        feature_hint = QLabel(
            "关闭后会隐藏对应入口；尺寸、格式、压缩、LOGO和水印也会从综合处理中停用。",
            self,
        )
        feature_hint.setObjectName("MutedLabel")
        feature_hint.setWordWrap(True)
        feature_layout.addWidget(feature_hint)

        for feature, label in FEATURE_LABELS.items():
            row = QHBoxLayout()
            row.setSpacing(10)
            display_label = f"{label}（默认关闭）" if feature == MODE_WATERMARK else label
            row.addWidget(QLabel(display_label, self))
            row.addStretch(1)
            switch = SwitchButton(feature_card)
            switch.setOnText("开启")
            switch.setOffText("关闭")
            switch.setChecked(feature_states.get(feature, FEATURE_DEFAULTS[feature]))
            row.addWidget(switch)
            feature_layout.addLayout(row)
            self.feature_switches[feature] = switch

        root_layout.addWidget(feature_card)
        root_layout.addStretch(1)

        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        for feature, switch in self.feature_switches.items():
            switch.checkedChanged.connect(
                lambda checked, feature=feature: self.on_feature_changed(feature, checked)
            )
        self.apply_theme_styles()

    def apply_theme_styles(self) -> None:
        apply_background(self, theme_colors()["page"])
        self.setStyleSheet(theme_stylesheet())

    def _theme_changed(self, label: str) -> None:
        self.on_theme_changed(THEME_LABELS.get(label, "light"))


class AboutActionButton(PushButton):
    """Native button styled as the full-width About page action row."""

    def __init__(
        self,
        text: str,
        icon,
        accessible_description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AboutActionButton")
        self.setText("")
        self.setFixedHeight(50)
        self.setAccessibleName(text)
        self.setAccessibleDescription(accessible_description)
        self.setToolTip(accessible_description)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(12)

        self.icon_widget = IconWidget(self)
        self.icon_widget.setIcon(icon)
        self.icon_widget.setFixedSize(20, 20)
        self.text_label = QLabel(text, self)
        self.text_label.setObjectName("AboutActionText")
        self.arrow_widget = IconWidget(self)
        self.arrow_widget.setIcon(FIF.CHEVRON_RIGHT)
        self.arrow_widget.setFixedSize(16, 16)

        for child in (self.icon_widget, self.text_label, self.arrow_widget):
            child.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout.addWidget(self.icon_widget)
        layout.addWidget(self.text_label)
        layout.addStretch(1)
        layout.addWidget(self.arrow_widget)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not event.isAutoRepeat():
                self.click()
            event.accept()
            return
        super().keyReleaseEvent(event)


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

        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("AboutContent")
        self.content_widget.setMaximumWidth(ABOUT_CONTENT_MAX_WIDTH)
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 4, 0, 0)
        content_layout.setSpacing(22)

        identity_widget = QWidget(self.content_widget)
        identity_layout = QVBoxLayout(identity_widget)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(6)

        self.product_title_label = QLabel(APP_NAME, identity_widget)
        self.product_title_label.setObjectName("AboutProductTitle")
        self.tagline_label = QLabel("本地、批量、可预览的图片处理工具", identity_widget)
        self.tagline_label.setObjectName("AboutTagline")
        self.tagline_label.setWordWrap(True)

        metadata_row = QHBoxLayout()
        metadata_row.setContentsMargins(0, 6, 0, 0)
        metadata_row.setSpacing(12)
        self.version_badge = QFrame(identity_widget)
        self.version_badge.setObjectName("AboutVersionBadge")
        self.version_badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        version_layout = QHBoxLayout(self.version_badge)
        version_layout.setContentsMargins(10, 3, 10, 3)
        self.version_label = QLabel(APP_VERSION, self.version_badge)
        version_layout.addWidget(self.version_label)
        self.author_label = QLabel(APP_AUTHOR, identity_widget)
        self.author_label.setObjectName("MutedLabel")
        metadata_row.addWidget(self.version_badge)
        metadata_row.addWidget(self.author_label)
        metadata_row.addStretch(1)

        identity_layout.addWidget(self.product_title_label)
        identity_layout.addWidget(self.tagline_label)
        identity_layout.addLayout(metadata_row)
        content_layout.addWidget(identity_widget)

        self.about_panel = CardWidget(self.content_widget)
        self.about_panel.setObjectName("PanelCard")
        panel_layout = QVBoxLayout(self.about_panel)
        panel_layout.setContentsMargins(20, 18, 20, 20)
        panel_layout.setSpacing(12)

        self.privacy_title_label = QLabel("隐私与安全", self.about_panel)
        self.privacy_title_label.setObjectName("SectionTitle")
        self.privacy_lead_label = QLabel("所有图片均在本机完成处理", self.about_panel)
        self.privacy_lead_label.setObjectName("AboutPrivacyLead")
        self.no_overwrite_label = QLabel("输出文件不会覆盖原图", self.about_panel)
        self.no_path_storage_label = QLabel("不保存图片名称或路径", self.about_panel)
        panel_layout.addWidget(self.privacy_title_label)
        panel_layout.addWidget(self.privacy_lead_label)
        panel_layout.addWidget(self.no_overwrite_label)
        panel_layout.addWidget(self.no_path_storage_label)

        self.divider = QFrame(self.about_panel)
        self.divider.setObjectName("AboutDivider")
        self.divider.setFrameShape(QFrame.HLine)
        self.divider.setFixedHeight(1)
        panel_layout.addWidget(self.divider)

        self.support_title_label = QLabel("帮助与支持", self.about_panel)
        self.support_title_label.setObjectName("SectionTitle")
        panel_layout.addWidget(self.support_title_label)

        action_grid = QGridLayout()
        action_grid.setContentsMargins(0, 0, 0, 0)
        action_grid.setHorizontalSpacing(10)
        action_grid.setVerticalSpacing(10)
        action_grid.setColumnStretch(0, 1)
        action_grid.setColumnStretch(1, 1)

        self.project_action = AboutActionButton(
            "项目主页",
            FIF.HOME,
            "在浏览器中打开项目主页",
            self.about_panel,
        )
        self.release_action = AboutActionButton(
            "查看最新版本",
            FIF.SYNC,
            "在浏览器中查看最新版本",
            self.about_panel,
        )
        self.feedback_action = AboutActionButton(
            "反馈问题",
            FIF.MESSAGE,
            "在浏览器中打开问题反馈页面",
            self.about_panel,
        )
        self.copy_version_action = AboutActionButton(
            "复制版本信息",
            FIF.COPY,
            "复制软件名称、版本和作者",
            self.about_panel,
        )
        self.action_cards = (
            self.project_action,
            self.release_action,
            self.feedback_action,
            self.copy_version_action,
        )

        action_grid.addWidget(self.project_action, 0, 0)
        action_grid.addWidget(self.release_action, 0, 1)
        action_grid.addWidget(self.feedback_action, 1, 0)
        action_grid.addWidget(self.copy_version_action, 1, 1)
        panel_layout.addLayout(action_grid)
        content_layout.addWidget(self.about_panel)

        self.footer_label = QLabel(
            f"{APP_NAME}  ·  {APP_VERSION}  ·  {APP_AUTHOR}",
            self.content_widget,
        )
        self.footer_label.setObjectName("AboutFooter")
        content_layout.addWidget(self.footer_label)

        root_layout.addWidget(self.content_widget)
        root_layout.addStretch(1)

        self.project_action.clicked.connect(
            lambda: self._open_external_url(PROJECT_URL)
        )
        self.release_action.clicked.connect(
            lambda: self._open_external_url(PROJECT_RELEASES_URL)
        )
        self.feedback_action.clicked.connect(
            lambda: self._open_external_url(PROJECT_ISSUES_URL)
        )
        self.copy_version_action.clicked.connect(self._copy_version_information)
        self.apply_theme_styles()

    @staticmethod
    def version_information_text() -> str:
        return f"{APP_NAME} {APP_VERSION}\n作者：{APP_AUTHOR}"

    def _open_external_url(self, url: str) -> None:
        if QDesktopServices.openUrl(QUrl(url)):
            return
        self._show_message("error", "无法打开浏览器")

    def _copy_version_information(self) -> None:
        QApplication.clipboard().setText(self.version_information_text())
        self._show_message("success", "版本信息已复制")

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
        else:
            InfoBar.error(**kwargs)

    def apply_theme_styles(self) -> None:
        apply_background(self, theme_colors()["page"])
        self.setStyleSheet(theme_stylesheet())


class ImageToolWindow(FluentWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        settings = settings or QSettings("ImageTool", APP_NAME)
        theme_value = load_theme_value(settings)
        feature_states = load_feature_states(settings)
        processing_statistics = load_processing_statistics(settings)
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
        self.feature_states = feature_states
        self.processing_statistics = processing_statistics
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
        self.settings_page = SettingsPage(
            self.theme_value,
            self._set_theme_mode,
            self.feature_states,
            self._set_feature_enabled,
        )
        self.about_page = AboutPage()
        self.feature_pages = {
            MODE_COMPREHENSIVE: self.comprehensive_page,
            MODE_RESIZE: self.resize_page,
            MODE_FORMAT: self.format_page,
            MODE_COMPRESS: self.compress_page,
            MODE_LOGO: self.logo_page,
            MODE_WATERMARK: self.watermark_page,
        }
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
            page.output_committed.connect(self._record_processed_output)

        self.comprehensive_page.set_processing_statistics(self.processing_statistics)

        feature_navigation = (
            (MODE_COMPREHENSIVE, self.comprehensive_page, FIF.HOME),
            (MODE_RESIZE, self.resize_page, FIF.FIT_PAGE),
            (MODE_FORMAT, self.format_page, FIF.IMAGE_EXPORT),
            (MODE_COMPRESS, self.compress_page, FIF.ZIP_FOLDER),
            (MODE_LOGO, self.logo_page, FIF.EDIT),
            (MODE_WATERMARK, self.watermark_page, FIF.TAG),
        )
        self.feature_nav_items = {}
        for feature, page, icon in feature_navigation:
            self.feature_nav_items[feature] = self.addSubInterface(
                page,
                icon,
                FEATURE_LABELS[feature],
            )
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
        for feature, enabled in self.feature_states.items():
            self._set_feature_enabled(
                feature,
                enabled,
                persist=False,
                ensure_current=False,
            )
        self.switchTo(self._first_enabled_page())
        self._apply_theme_styles()

    def center_on_screen(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return

        available_geometry = screen.availableGeometry()
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(available_geometry.center())
        self.move(frame_geometry.topLeft())

    def closeEvent(self, event: QCloseEvent) -> None:
        for page in self.operation_pages:
            page.shutdown()
        # Flush queued per-image completion signals after workers have stopped,
        # so closing during a batch does not lose an already-written result.
        QApplication.processEvents()
        qrouter.history = [
            item for item in qrouter.history if item.stacked is not self.stackedWidget
        ]
        qrouter.stackHistories.pop(self.stackedWidget, None)
        qrouter.emptyChanged.emit(not bool(qrouter.history))
        super().closeEvent(event)

    def _first_enabled_page(self) -> QWidget:
        for feature in FEATURE_DEFAULTS:
            if self.feature_states.get(feature, FEATURE_DEFAULTS[feature]):
                return self.feature_pages[feature]
        return self.settings_page

    def _set_feature_enabled(
        self,
        feature: str,
        enabled: bool,
        *,
        persist: bool = True,
        ensure_current: bool = True,
    ) -> None:
        if feature not in self.feature_pages:
            return

        enabled = bool(enabled)
        self.feature_states[feature] = enabled

        page = self.feature_pages[feature]
        if not enabled:
            fallback_page = self._first_enabled_page()
            stack_history = qrouter.stackHistories.get(self.stackedWidget)
            if stack_history is not None and stack_history.defaultRouteKey == page.objectName():
                qrouter.setDefaultRouteKey(
                    self.stackedWidget,
                    fallback_page.objectName(),
                )

            if ensure_current and self.stackedWidget.currentWidget() is page:
                self.switchTo(fallback_page)

            # Navigation items can be hidden while their route remains in the
            # FluentWindow back stack.  Remove it so the return button cannot
            # reopen a feature that the user has switched off.
            if stack_history is not None:
                stack_history.remove(page.objectName())
            qrouter.history = [
                item
                for item in qrouter.history
                if not (
                    item.stacked is self.stackedWidget
                    and item.routeKey == page.objectName()
                )
            ]
            qrouter.emptyChanged.emit(not bool(qrouter.history))

        page.setEnabled(enabled)

        nav_item = self.feature_nav_items.get(feature)
        if nav_item is not None:
            nav_item.setVisible(enabled)

        if feature in COMPREHENSIVE_FEATURES:
            self.comprehensive_page.set_feature_enabled(feature, enabled)

        if persist:
            self.settings.setValue(feature_setting_key(feature), enabled)

    def _set_theme_mode(self, value: str) -> None:
        if value not in THEME_MAP:
            value = "light"
        self.theme_value = value
        self.settings.setValue(THEME_SETTING_KEY, value)
        setTheme(THEME_MAP[value])
        self._apply_theme_styles()

    def _record_processed_output(self, output: object) -> None:
        if not isinstance(output, ProcessedOutput):
            return
        if output.source_bytes < 0 or output.output_bytes < 0:
            return

        self.processing_statistics = self.processing_statistics.with_output(output)
        save_processing_statistics(self.settings, self.processing_statistics)
        self.comprehensive_page.set_processing_statistics(self.processing_statistics)

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
