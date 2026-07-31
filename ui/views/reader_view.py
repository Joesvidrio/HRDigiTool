import os
import sys
import shutil
import subprocess
import fitz

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QListWidget, QListWidgetItem, 
                             QAbstractItemView, QMessageBox, QSplitter,
                             QGraphicsView, QGraphicsScene, QTabWidget, QTabBar)
from PyQt6.QtGui import (QPixmap, QImage, QIcon, QPainter, QShortcut, 
                         QKeySequence)
from PyQt6.QtCore import QSize, Qt, pyqtSignal, QEvent, QTimer, QThread, QObject
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

import ui.views.organize_view as org_view


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
            mat = fitz.Matrix(0.3, 0.3)
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


class ReaderGraphicsView(QGraphicsView):
    """Custom graphics view based on QGraphicsView for rendering the PDF canvas."""
    
    file_dropped = pyqtSignal(str)
    zoom_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | 
            QPainter.RenderHint.SmoothPixmapTransform | 
            QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.pixmap_item = None
        self.setAcceptDrops(True)

    def set_pixmap(self, pixmap: QPixmap):
        self.scene.clear()
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(self.pixmap_item.boundingRect())

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
            self.scale(factor, factor)
            self.zoom_changed.emit()
        else:
            super().wheelEvent(event)

    def viewportEvent(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                scale_factor = 1.0 + event.value()
                self.scale(scale_factor, scale_factor)
                self.zoom_changed.emit()
                return True
        return super().viewportEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.file_dropped.emit(file_path)


class ReaderTab(QWidget):
    """An individual PDF tab representing a single Reader workspace."""
    
    title_changed = pyqtSignal(str)
    
    def __init__(self, navigate_callback=None):
        super().__init__()
        self.navigate_callback = navigate_callback
        self.current_file = None
        self.doc = None
        self.is_fullscreen = False
        self.current_zoom = 1.2
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(200)
        self.render_timer.timeout.connect(self.update_viewer_vector)
        
        self.setAcceptDrops(True)
        self.init_ui()
        self.setup_shortcuts() 

    def setup_shortcuts(self):
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
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.top_container = QWidget()
        top_layout = QVBoxLayout(self.top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        title_layout = QHBoxLayout()
        btn_select = QPushButton("Open PDF")
        btn_select.clicked.connect(self.select_file)
        self.file_label = QLabel("No file selected")
        btn_print = QPushButton("Print")
        btn_print.clicked.connect(self.print_file)
        
        title_layout.addWidget(btn_select)
        title_layout.addWidget(btn_print)
        title_layout.addWidget(self.file_label)
        title_layout.addStretch()
        top_layout.addLayout(title_layout)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(QLabel("<b>Actions:</b>"))
        
        for name, idx in [("Send to Merge", 2), ("Send to Organize", 3), ("Send to Security", 4)]:
            btn = QPushButton(name)
            btn.setProperty("class", "SecondaryButton")
            btn.clicked.connect(lambda checked, i=idx: self.bridge_to_module(i))
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        top_layout.addLayout(toolbar_layout)
        self.layout.addWidget(self.top_container)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.viewer_container = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = ReaderGraphicsView()
        self.viewer.file_dropped.connect(self.load_file) 
        self.viewer.zoom_changed.connect(self.schedule_vector_render)
        viewer_layout.addWidget(self.viewer)
        
        zoom_controls_layout = QHBoxLayout()
        self.btn_fullscreen = QPushButton("Fullscreen")
        self.btn_fullscreen.setProperty("class", "SecondaryButton")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        zoom_controls_layout.addWidget(self.btn_fullscreen)
        zoom_controls_layout.addStretch()
        
        btn_zoom_out = QPushButton("-")
        btn_reset_zoom = QPushButton("⛶ Fit Page")
        btn_zoom_in = QPushButton("+")
        
        btn_zoom_out.clicked.connect(self.zoom_out)
        btn_reset_zoom.clicked.connect(self.reset_zoom)
        btn_zoom_in.clicked.connect(self.zoom_in)
        
        for btn in [btn_zoom_out, btn_reset_zoom, btn_zoom_in]:
            btn.setProperty("class", "SecondaryButton")
            zoom_controls_layout.addWidget(btn)
            
        zoom_controls_layout.addStretch()
        btn_toggle_sidebar = QPushButton("Toggle Sidebar")
        btn_toggle_sidebar.setProperty("class", "SecondaryButton")
        btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        zoom_controls_layout.addWidget(btn_toggle_sidebar)
        
        viewer_layout.addLayout(zoom_controls_layout)
        self.workspace_splitter.addWidget(self.viewer_container)
        
        self.list_widget = org_view.AutoScrollListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(8)
        self.list_widget.setIconSize(QSize(130, 180)) 
        self.list_widget.setMaximumWidth(235)
        self.list_widget.setStyleSheet("background-color: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 4px;")
        self.list_widget.itemSelectionChanged.connect(self.on_page_changed)
        self.list_widget.setAcceptDrops(False) 
        
        self.workspace_splitter.addWidget(self.list_widget)
        self.workspace_splitter.setStretchFactor(0, 7)
        self.workspace_splitter.setStretchFactor(1, 3)
        self.workspace_splitter.setSizes([1000, 235])
        
        self.layout.addWidget(self.workspace_splitter, 1)

    def schedule_vector_render(self):
        self.render_timer.start()

    def zoom_in(self):
        if self.current_zoom < 5.0:
            self.viewer.scale(1.2, 1.2)
            self.schedule_vector_render()

    def zoom_out(self):
        if self.current_zoom > 0.2:
            self.viewer.scale(1.0 / 1.2, 1.0 / 1.2)
            self.schedule_vector_render()

    def reset_zoom(self):
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.update_viewer_vector()

    def print_file(self):
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please open a PDF file first.")
            return

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                output_file = printer.outputFileName()
                if output_file:
                    shutil.copy(self.current_file, output_file)
                    QMessageBox.information(self, "Success", f"PDF saved to {output_file}")
                    return

                if sys.platform != "win32":
                    cmd = ["lpr"]
                    printer_name = printer.printerName()
                    if printer_name:
                        cmd.extend(["-P", printer_name])
                    
                    copies = printer.copyCount()
                    if copies > 1:
                        cmd.extend(["-#", str(copies)])
                        
                    if printer.printRange() == QPrinter.PrintRange.PageRange:
                        from_p = printer.fromPage()
                        to_p = printer.toPage()
                        cmd.extend(["-o", f"page-ranges={from_p}-{to_p}"])
                    
                    cmd.extend(["-o", "fit-to-page"])
                    cmd.append(self.current_file)
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        QMessageBox.information(self, "Success", "Document sent to printer.")
                        return

                painter = QPainter()
                if not painter.begin(printer):
                    QMessageBox.critical(self, "Print Error", "Could not initialize printer.")
                    return
                
                dpi = printer.resolution()
                zoom = dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)

                doc = self.doc if self.doc else fitz.open(self.current_file)
                for i in range(len(doc)):
                    if i > 0:
                        printer.newPage()
                        
                    page = doc[i]
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    fmt = QImage.Format.Format_RGB888
                    img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
                    
                    target_rect = printer.pageRect(QPrinter.Unit.DevicePixel).toRect()
                    painter.drawImage(target_rect, img)
                    
                painter.end()
                if not self.doc:
                    doc.close()
                QMessageBox.information(self, "Success", "Document sent to printer successfully.")
                
        except Exception as e:
            QMessageBox.critical(self, "Print Error", f"Could not print the file:\n{str(e)}")

    def toggle_sidebar(self):
        self.list_widget.setVisible(not self.list_widget.isVisible())

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.top_container.setVisible(not self.is_fullscreen)
        if self.is_fullscreen:
            self.btn_fullscreen.setText("Exit Fullscreen")
            self.list_widget.setVisible(False)
        else:
            self.btn_fullscreen.setText("Fullscreen")
            self.list_widget.setVisible(True)

    def dragEnterEvent(self, event):
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
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file: 
            self.load_file(file)

    def load_file(self, file_path: str):
        if not os.path.exists(file_path):
            return
            
        try:
            if self.doc:
                self.doc.close()
            
            self.doc = fitz.open(file_path)
            if self.doc.needs_pass:
                self.doc.close()
                self.doc = None
                QMessageBox.warning(self, "Protected PDF", "This file is password protected.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read the file:\n{str(e)}")
            return

        self.current_file = file_path
        self.current_zoom = 1.2
        file_name = os.path.basename(file_path)
        self.file_label.setText(file_name)
        self.title_changed.emit(file_name)
        self.load_thumbnails()

    def load_thumbnails(self):
        """Generates thumbnails for the PDF safely preventing C++ object deletions."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.viewer.scene.clear()
        self.viewer.pixmap_item = None
        
        # Safe thread interruption
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
                pass # C++ object was already deleted, safe to continue

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
        pixmap = QPixmap.fromImage(img)
        item = QListWidgetItem(QIcon(pixmap), f"Page {page_num}")
        item.setData(Qt.ItemDataRole.UserRole, page_num)
        self.list_widget.addItem(item)

    def on_thumbnails_loaded(self):
        self.list_widget.blockSignals(False)
        if self.list_widget.count() > 0 and self.list_widget.currentRow() == -1:
            self.list_widget.setCurrentRow(0)

    def on_page_changed(self):
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.viewer.scale(1.5, 1.5)
        self.update_viewer_vector()

    def update_viewer_vector(self):
        item = self.list_widget.currentItem()
        if not item or not self.doc: return
        
        page_num = item.data(Qt.ItemDataRole.UserRole)
        
        try:
            current_transform_scale = self.viewer.transform().m11()
            self.current_zoom *= current_transform_scale
            self.current_zoom = max(0.2, min(self.current_zoom, 5.0))
            
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 2.0
            total_scale = self.current_zoom * dpr
            
            page = self.doc[page_num - 1]
            mat = fitz.Matrix(total_scale, total_scale) 
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            fmt = QImage.Format.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            img.setDevicePixelRatio(dpr)
            
            high_res_pixmap = QPixmap.fromImage(img)
            
            self.viewer.set_pixmap(high_res_pixmap)
            self.viewer.resetTransform()
            
        except Exception:
            pass

    def bridge_to_module(self, module_index: int):
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please open a PDF file first.")
        if self.navigate_callback:
            self.navigate_callback(module_index, [self.current_file])

    def clean_up(self):
        """Safely stops threads and releases memory before deleting the tab."""
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
                pass # C++ object was already deleted, safe to continue
                
        if hasattr(self, 'doc') and self.doc:
            self.doc.close()


class ReaderView(QWidget):
    """Tab manager for the PDF Reader module.
    
    Hosts multiple ReaderTabs allowing users to navigate and read multiple PDFs
    concurrently in a browser-like interface.
    """
    
    def __init__(self, navigate_callback=None):
        super().__init__()
        self.navigate_callback = navigate_callback
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("PDF Reader")
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
        """Creates a new Reader workspace tab and assigns a discrete close button.
        
        Args:
            file_path (str, optional): An absolute path to automatically load upon creation.
        """
        tab = ReaderTab(self.navigate_callback)
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
            self.tabs.removeTab(index) # Critical fix: Remove from UI before destruction
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
        """API for external modules to send files to the Reader ensuring stability.
        
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