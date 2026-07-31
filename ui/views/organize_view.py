import os
import fitz 
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QListWidget, QFileDialog, QMessageBox, 
                             QListWidgetItem, QAbstractItemView, QComboBox, QCheckBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSplitter,
                             QListView, QTabWidget, QTabBar)
from PyQt6.QtGui import (QPixmap, QImage, QIcon, QDragMoveEvent, QTransform, 
                         QWheelEvent, QPainter, QPen, QColor, QShortcut, QKeySequence)
from PyQt6.QtCore import QSize, Qt, QEvent, pyqtSignal, QTimer, QThread, QObject

from backend.pdf_core import PDFProcessor


class ThumbnailWorker(QObject):
    """Background worker for rendering PDF thumbnails without blocking the main UI thread.

    Attributes:
        progress (pyqtSignal): Emits the page number and its rendered QImage.
        finished (pyqtSignal): Emitted when all pages are processed.
        error (pyqtSignal): Emitted if a critical error occurs during processing.
    """
    progress = pyqtSignal(int, QImage)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.is_cancelled = False

    def run(self):
        """Executes the rendering loop over the PDF pages."""
        try:
            doc = fitz.open(self.file_path)
            mat = fitz.Matrix(0.5, 0.5) 
            for i in range(len(doc)):
                if self.is_cancelled:
                    break
                page = doc[i]
                pix = page.get_pixmap(matrix=mat, alpha=False)
                fmt = QImage.Format.Format_RGB888
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
                self.progress.emit(i + 1, img)
            doc.close()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()


class ZoomableView(QGraphicsView):
    """A custom QGraphicsView that provides a high-resolution, zoomable image viewer."""
    zoom_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setObjectName("ViewerWidget")

    def set_image(self, pixmap: QPixmap, reset_transform: bool = False):
        """Sets the currently displayed high-resolution image."""
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        if reset_transform:
            self.resetTransform()

    def fit_to_window(self):
        """Scales the view to fit the entire page within the window bounds."""
        if not self.pixmap_item.pixmap().isNull():
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def viewportEvent(self, event: QEvent) -> bool:
        """Handles native zoom gestures (e.g., trackpad pinch)."""
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                zoom_factor = 1.0 + event.value()
                self.scale(zoom_factor, zoom_factor)
                self.zoom_changed.emit()
                return True
        return super().viewportEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Allows zooming in and out using Ctrl + Mouse Wheel."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
            self.scale(factor, factor)
            self.zoom_changed.emit()
        else:
            super().wheelEvent(event)


class AutoScrollListWidget(QListWidget):
    """Custom QListWidget that provides automatic edge-scrolling during drag-and-drop operations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Automatically scrolls the list if the user drags an item near the top or bottom edges."""
        super().dragMoveEvent(event)
        pos = event.position().toPoint()
        scrollbar = self.verticalScrollBar()
        if pos.y() < 40: 
            scrollbar.setValue(scrollbar.value() - 8)
        elif pos.y() > self.height() - 40: 
            scrollbar.setValue(scrollbar.value() + 8)

    def wheelEvent(self, event: QWheelEvent):
        """Smoothes out the mouse wheel scrolling behavior."""
        delta = event.angleDelta().y()
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - int(delta / 4))


class OrganizeTab(QWidget):
    """An individual workspace tab for organizing, rotating, removing, and compressing PDF pages."""
    
    title_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.original_items = {} 
        self.current_zoom = 1.0
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(200)
        self.render_timer.timeout.connect(self.update_viewer_vector)

        self.setAcceptDrops(True)
        self.init_ui()
        self.setup_shortcuts() 

    def setup_shortcuts(self):
        """Sets up keyboard shortcuts for quick page navigation."""
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_right.activated.connect(self.next_page)
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_space.activated.connect(self.next_page)
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_left.activated.connect(self.prev_page)

    def next_page(self):
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row == -1: 
                self.list_widget.setCurrentRow(0)
            elif current_row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(current_row + 1)

    def prev_page(self):
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row > 0:
                self.list_widget.setCurrentRow(current_row - 1)

    def init_ui(self):
        """Initializes the layout and UI components of the Organize Tab."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10) 
        self.layout.setSpacing(10)
        
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        title_layout = QHBoxLayout()
        btn_select = QPushButton("Select PDF")
        btn_select.clicked.connect(self.select_file)
        self.file_label = QLabel("No file selected")
        title_layout.addWidget(btn_select)
        title_layout.addWidget(self.file_label)
        title_layout.addStretch()
        top_layout.addLayout(title_layout)

        control_layout = QHBoxLayout()
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Original", "A4", "Letter", "Legal"])
        self.size_combo.setView(QListView()) 
        
        control_layout.addWidget(QLabel("<b>Force Size:</b>"))
        control_layout.addWidget(self.size_combo)
        
        self.range_input = QLineEdit()
        self.range_input.setPlaceholderText("Order (e.g., 1-3, 5)")
        self.range_input.editingFinished.connect(self.sync_from_text)
        control_layout.addWidget(self.range_input)
        
        btn_rotate = QPushButton("Rotate Page")
        btn_rotate.setProperty("class", "SecondaryButton")
        btn_rotate.clicked.connect(self.rotate_selected)
        control_layout.addWidget(btn_rotate)
        
        btn_remove_blank = QPushButton("Detect Blank Pages")
        btn_remove_blank.setProperty("class", "SecondaryButton")
        btn_remove_blank.clicked.connect(self.remove_blank_pages)
        control_layout.addWidget(btn_remove_blank)
        
        btn_toggle_sidebar = QPushButton("Toggle Sidebar")
        btn_toggle_sidebar.setProperty("class", "SecondaryButton")
        btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        control_layout.addWidget(btn_toggle_sidebar)
        
        top_layout.addLayout(control_layout)
        self.layout.addWidget(top_container)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.viewer_container = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = ZoomableView()
        self.viewer.zoom_changed.connect(self.schedule_vector_render)
        viewer_layout.addWidget(self.viewer)
        
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_zoom_out = QPushButton("-")
        btn_fit = QPushButton("⛶ Fit Page")
        btn_zoom_in = QPushButton("+")
        
        btn_zoom_out.clicked.connect(self.zoom_out)
        btn_fit.clicked.connect(self.reset_zoom)
        btn_zoom_in.clicked.connect(self.zoom_in)
        
        for btn in [btn_zoom_out, btn_fit, btn_zoom_in]:
            btn.setProperty("class", "SecondaryButton")
            zoom_controls_layout.addWidget(btn)
            
        viewer_layout.addLayout(zoom_controls_layout)
        self.workspace_splitter.addWidget(self.viewer_container)
        
        self.list_widget = AutoScrollListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(8)
        self.list_widget.setIconSize(QSize(130, 180))
        self.list_widget.setMaximumWidth(300) 
        self.list_widget.setObjectName("ThumbnailList")
        
        self.list_widget.itemChanged.connect(self.sync_from_list)
        self.list_widget.model().rowsMoved.connect(self.sync_from_list)
        self.list_widget.itemSelectionChanged.connect(self.on_page_selected)
        
        self.workspace_splitter.addWidget(self.list_widget)
        self.workspace_splitter.setStretchFactor(0, 7) 
        self.workspace_splitter.setStretchFactor(1, 3) 
        self.workspace_splitter.setSizes([1000, 300]) 
        
        self.layout.addWidget(self.workspace_splitter, 1)

        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        bottom_layout.setSpacing(10)
        
        options_layout = QHBoxLayout()
        self.chk_logo = QCheckBox("Add Kodak Logo (Watermark)")
        self.chk_num = QCheckBox("Add Page Numbers")
        self.chk_compress = QCheckBox("Apply Max Compression")
        
        options_layout.addWidget(self.chk_logo)
        options_layout.addWidget(self.chk_num)
        options_layout.addWidget(self.chk_compress)
        options_layout.addStretch()
        bottom_layout.addLayout(options_layout)

        btn_save = QPushButton("Process and Save PDF")
        btn_save.setProperty("class", "SuccessButton")
        btn_save.clicked.connect(self.save_pdf)
        bottom_layout.addWidget(btn_save)
        
        self.layout.addWidget(bottom_container)

    def toggle_sidebar(self):
        """Hides or shows the thumbnail list sidebar."""
        self.list_widget.setVisible(not self.list_widget.isVisible())

    def reset_zoom(self):
        """Resets the viewer zoom to 1.0 and fits the image within the window."""
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.update_viewer_vector()
        self.viewer.fit_to_window()

    def zoom_in(self):
        """Increases the zoom scale of the viewer up to a maximum limit."""
        if self.current_zoom < 5.0:
            self.viewer.scale(1.15, 1.15)
            self.schedule_vector_render()

    def zoom_out(self):
        """Decreases the zoom scale of the viewer down to a minimum limit."""
        if self.current_zoom > 0.2:
            self.viewer.scale(1 / 1.15, 1 / 1.15)
            self.schedule_vector_render()

    def schedule_vector_render(self):
        """Starts a debounce timer before requesting a high-resolution render."""
        self.render_timer.start()

    def dragEnterEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.load_file(file_path)

    def select_file(self):
        """Opens a file dialog for the user to pick a PDF manually."""
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file: 
            self.load_file(file)

    def load_file(self, file_path):
        """Validates and loads a PDF file into the tab."""
        if isinstance(file_path, list):
            if not file_path:
                return
            file_path = file_path[0]
            
        try:
            doc = fitz.open(file_path)
            if doc.needs_pass:
                doc.close()
                QMessageBox.warning(
                    self, 
                    "Protected PDF", 
                    "This file is password protected. 🔒\n\n"
                    "Please use the 'Security and Metadata' module to unlock it."
                )
                return
            doc.close()
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"The file is damaged:\n{str(e)}")
            return

        self.current_file = file_path
        self.current_zoom = 1.0
        file_name = os.path.basename(file_path)
        self.file_label.setText(file_name)
        self.title_changed.emit(file_name)
        self.load_thumbnails()

    def load_thumbnails(self):
        """Starts the background thread to fetch thumbnails of the PDF."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.original_items.clear()
        
        self.viewer.scene.clear()
        self.viewer.pixmap_item = QGraphicsPixmapItem()
        self.viewer.scene.addItem(self.viewer.pixmap_item)

        # Stop previous background tasks cleanly
        self.clean_up()

        self.worker_thread = QThread()
        self.worker = ThumbnailWorker(self.current_file)
        self.worker.moveToThread(self.worker_thread)
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.add_thumbnail)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.on_thumbnails_loaded)
        
        self.worker_thread.start()

    def add_thumbnail(self, page_num: int, img: QImage):
        """Receives a rendered page thumbnail from the worker thread and adds it to the list."""
        pixmap = QPixmap.fromImage(img)
        painter = QPainter(pixmap)
        pen = QPen(QColor("#9CA3AF")) 
        pen.setWidth(2)               
        painter.setPen(pen)
        painter.drawRect(1, 1, pixmap.width() - 2, pixmap.height() - 2)
        painter.end()
        
        item = QListWidgetItem(QIcon(pixmap), f"Page {page_num}  (0°)")
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled | 
                      Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        
        item.setData(Qt.ItemDataRole.UserRole, page_num)
        item.setData(Qt.ItemDataRole.UserRole + 1, 0)       
        item.setData(Qt.ItemDataRole.UserRole + 2, pixmap)  
        
        self.list_widget.addItem(item)
        self.original_items[page_num] = item

    def on_thumbnails_loaded(self):
        """Called once the worker thread finishes processing all pages."""
        self.list_widget.blockSignals(False)
        self.sync_from_list()
        if self.list_widget.count() > 0 and self.list_widget.currentRow() == -1:
            self.list_widget.setCurrentRow(0)

    def on_page_selected(self):
        """Resets the viewer when the user clicks a different page thumbnail."""
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.viewer.scale(1.5, 1.5)
        self.update_viewer_vector()

    def update_viewer_vector(self):
        """Performs a real-time, high-resolution re-render of the current PDF page matching the zoom level."""
        item = self.list_widget.currentItem()
        if not item or not self.current_file: return
        
        page_num = item.data(Qt.ItemDataRole.UserRole)
        rotation = item.data(Qt.ItemDataRole.UserRole + 1)
        
        try:
            current_scale = self.viewer.transform().m11()
            self.current_zoom *= current_scale
            self.current_zoom = max(0.2, min(self.current_zoom, 5.0))
            
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 2.0
            total_scale = self.current_zoom * dpr
            
            doc = fitz.open(self.current_file)
            page = doc[page_num - 1]
            
            mat = fitz.Matrix(total_scale, total_scale)
            if rotation != 0:
                mat.prerotate(rotation)
                
            pix = page.get_pixmap(matrix=mat, alpha=False)
            fmt = QImage.Format.Format_RGB888
            
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            img.setDevicePixelRatio(dpr)
            
            high_res_pixmap = QPixmap.fromImage(img)
            doc.close()
            
            self.viewer.set_image(high_res_pixmap, reset_transform=True)
        except Exception as e:
            pass

    def rotate_selected(self):
        """Rotates the currently selected page by 90 degrees."""
        item = self.list_widget.currentItem()
        if not item: return
        
        current_rot = item.data(Qt.ItemDataRole.UserRole + 1)
        new_rot = (current_rot + 90) % 360
        item.setData(Qt.ItemDataRole.UserRole + 1, new_rot)
        
        page_num = item.data(Qt.ItemDataRole.UserRole)
        item.setText(f"Page {page_num}  ({new_rot}°)")
        
        original_pixmap = item.data(Qt.ItemDataRole.UserRole + 2)
        transform = QTransform().rotate(new_rot)
        rotated_pixmap = original_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        item.setIcon(QIcon(rotated_pixmap))
        self.update_viewer_vector()

    def remove_blank_pages(self):
        """Scans the document for purely white pages and unchecks them automatically."""
        if not self.current_file:
            return
            
        blank_pages = PDFProcessor.get_blank_pages(self.current_file)
        if not blank_pages:
            return
            
        items_unchecked = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            page_num = item.data(Qt.ItemDataRole.UserRole)
            if page_num in blank_pages and item.checkState() == Qt.CheckState.Checked:
                item.setCheckState(Qt.CheckState.Unchecked)
                items_unchecked += 1
                
        self.sync_from_list() 
        if items_unchecked > 0:
            QMessageBox.information(
                self, 
                "Scan Complete", 
                f"Detected and unchecked {items_unchecked} blank pages.\n"
                "You can review them before saving."
            )

    def sync_from_text(self):
        """Parses the text input field (e.g., '1-3, 5') and reflects it visually in the list widget."""
        text = self.range_input.text().strip()
        parsed_order = []
        parts = text.split(',')
        for part in parts:
            part = part.strip()
            if not part: continue
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    if start <= end:
                        parsed_order.extend(range(start, end + 1))
                except ValueError:
                    pass
            else:
                try:
                    parsed_order.append(int(part))
                except ValueError:
                    pass
                    
        active_pages = []
        seen = set()
        for p in parsed_order:
            if p not in seen:
                seen.add(p)
                active_pages.append(p)
                
        self.list_widget.blockSignals(True)
        items_dict = {}
        original_positions = {}
        count = self.list_widget.count()
        
        for i in range(count):
            item = self.list_widget.item(i)
            page_num = item.data(Qt.ItemDataRole.UserRole)
            items_dict[page_num] = item
            original_positions[page_num] = i
            
        while self.list_widget.count() > 0:
            self.list_widget.takeItem(0)
            
        valid_active = [p for p in active_pages if p in items_dict]
        new_list = [None] * count
        
        for page_num, item in items_dict.items():
            if page_num not in seen:
                pos = original_positions[page_num]
                item.setCheckState(Qt.CheckState.Unchecked)
                new_list[pos] = item
                
        active_idx = 0
        for i in range(count):
            if new_list[i] is None:
                p = valid_active[active_idx]
                item = items_dict[p]
                item.setCheckState(Qt.CheckState.Checked)
                new_list[i] = item
                active_idx += 1
                
        for item in new_list:
            if item is not None:
                self.list_widget.addItem(item)
                
        self.list_widget.blockSignals(False)
        self.sync_from_list()

    def sync_from_list(self, *args):
        """Translates the active visual selection in the list widget back to the string text input."""
        self.range_input.blockSignals(True)
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
                
        if not selected:
            self.range_input.setText("")
        else:
            ranges = []
            start = end = selected[0]
            for p in selected[1:]:
                if p == end + 1:
                    end = p
                else:
                    ranges.append(str(start) if start == end else f"{start}-{end}")
                    start = end = p
            ranges.append(str(start) if start == end else f"{start}-{end}")
            self.range_input.setText(", ".join(ranges))
            self.range_input.blockSignals(False)

    def save_pdf(self):
        """Prompts the user to save and sends the organization data to the backend processor."""
        if not self.current_file: 
            return QMessageBox.warning(self, "Error", "Please select a PDF first.")
        
        page_range = self.range_input.text()
        rotations = {}
        idx = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                rotations[idx] = item.data(Qt.ItemDataRole.UserRole + 1)
                idx += 1

        save_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF (*.pdf)")
        if save_path:
            success, msg = PDFProcessor.process_final_pdf(
                self.current_file, save_path, page_range, self.size_combo.currentText(), rotations,
                self.chk_logo.isChecked(), self.chk_num.isChecked(), self.chk_compress.isChecked()
            )
            if success:
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.critical(self, "Error", msg)

    def clean_up(self):
        """Safely stops threads, intercepts RuntimeError from deleted C++ objects, and releases memory."""
        if hasattr(self, 'render_timer'):
            self.render_timer.stop()
            
        if hasattr(self, 'worker_thread'):
            try:
                if self.worker_thread.isRunning():
                    self.worker.is_cancelled = True
                    try:
                        self.worker.progress.disconnect()
                        self.worker_thread.finished.disconnect()
                    except Exception:
                        pass
                    self.worker_thread.quit()
                    self.worker_thread.wait()
            except RuntimeError:
                pass


class OrganizeView(QWidget):
    """Tab manager for the Organize module.
    
    Hosts multiple OrganizeTabs allowing users to work on multiple PDFs
    concurrently in a browser-like interface.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initializes the main layout containing the TabWidget."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Organize, Edit and Compress PDF")
        title.setObjectName("TitleLabel")
        self.layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        self.layout.addWidget(self.tabs)
        
        btn_add_tab = QPushButton("+")
        btn_add_tab.setProperty("class", "SecondaryButton")
        btn_add_tab.setToolTip("Open New Tab")
        btn_add_tab.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(btn_add_tab, Qt.Corner.TopRightCorner)

        self.add_new_tab()

    def add_new_tab(self, file_path=None):
        """Creates a new Organize workspace tab and assigns a discrete close button.
        
        Args:
            file_path (str, optional): An absolute path to automatically load upon creation.
        """
        tab = OrganizeTab()
        idx = self.tabs.addTab(tab, "New PDF")
        
        close_btn = QPushButton("x")
        close_btn.setProperty("class", "DiscreteCloseButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(lambda checked, t=tab: self.close_tab(self.tabs.indexOf(t)))
        self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, close_btn)
        
        tab.title_changed.connect(lambda title, t=tab: self.update_tab_title(t, title))
        
        self.tabs.setCurrentIndex(idx)
        if file_path:
            tab.load_file(file_path)

    def close_tab(self, index: int):
        """Safely closes and removes a tab based on its dynamically computed index.
        
        Args:
            index (int): The current dynamic index of the tab widget.
        """
        if index < 0:
            return
        widget = self.tabs.widget(index)
        if widget:
            self.tabs.removeTab(index) 
            if hasattr(widget, 'clean_up'):
                widget.clean_up()
            widget.deleteLater()
            
        if self.tabs.count() == 0:
            self.add_new_tab()

    def update_tab_title(self, tab_widget: QWidget, title: str):
        """Updates the title of a specific tab safely based on the loaded file.
        
        Args:
            tab_widget (QWidget): The specific tab instance to update.
            title (str): The new string to display.
        """
        idx = self.tabs.indexOf(tab_widget)
        if idx != -1:
            self.tabs.setTabText(idx, title)

    def add_files(self, files):
        """API for external modules to send files to Organize ensuring stability.
        
        Args:
            files (list[str] or str): The file path(s) received from external modules.
        """
        if isinstance(files, str):
            files = [files]
            
        if not files:
            return
            
        file_path = files[0]
        current_tab = self.tabs.currentWidget()
        
        if current_tab and not current_tab.current_file:
            current_tab.load_file(file_path)
        else:
            self.add_new_tab(file_path)