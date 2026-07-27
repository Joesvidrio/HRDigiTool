import os
import sys
import shutil
import subprocess
import fitz

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QListWidget, QListWidgetItem, 
                             QAbstractItemView, QMessageBox, QSplitter,
                             QGraphicsView, QGraphicsScene)
from PyQt6.QtGui import (QPixmap, QImage, QIcon, QPainter, QShortcut, 
                         QKeySequence)
from PyQt6.QtCore import QSize, Qt, pyqtSignal, QEvent, QTimer
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

import ui.views.organize_view as org_view


class ReaderGraphicsView(QGraphicsView):
    """Custom graphics view based on QGraphicsView for rendering the PDF canvas.
    
    Handles drag-and-drop file loading, custom rendering hints for antialiasing, 
    and native gestures (mouse wheel, trackpad) for smooth zooming.
    
    Attributes:
        file_dropped (pyqtSignal): Signal emitted when a valid PDF file is dropped 
            onto the view. Carries the absolute file path as a string.
        zoom_changed (pyqtSignal): Signal emitted when the user changes the zoom 
            level via gestures or mouse wheel.
        scene (QGraphicsScene): The graphic scene managing the 2D canvas items.
        pixmap_item (QGraphicsPixmapItem | None): The current pixmap item being rendered.
    """
    
    file_dropped = pyqtSignal(str)
    zoom_changed = pyqtSignal()

    def __init__(self):
        """Initializes the custom graphics view with antialiasing and drag modes."""
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | 
            QPainter.RenderHint.SmoothPixmapTransform | 
            QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.pixmap_item = None
        self.setAcceptDrops(True)

    def set_pixmap(self, pixmap: QPixmap):
        """Replaces the current scene content with a new high-resolution pixmap.
        
        Args:
            pixmap (QPixmap): The pixmap image to render on the canvas.
        """
        self.scene.clear()
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(self.pixmap_item.boundingRect())

    def wheelEvent(self, event):
        """Handles mouse wheel events for zooming and scrolling.
        
        Args:
            event (QWheelEvent): The wheel event triggered by the user.
        """
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
            self.scale(factor, factor)
            self.zoom_changed.emit()
        else:
            super().wheelEvent(event)

    def viewportEvent(self, event: QEvent) -> bool:
        """Captures native OS gestures like trackpad pinch-to-zoom.
        
        Args:
            event (QEvent): The viewport event.
            
        Returns:
            bool: True if the native zoom gesture was handled, otherwise falls back 
                to the default behavior.
        """
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                scale_factor = 1.0 + event.value()
                self.scale(scale_factor, scale_factor)
                self.zoom_changed.emit()
                return True
        return super().viewportEvent(event)

    def dragEnterEvent(self, event):
        """Validates incoming drag events to accept only PDF files.
        
        Args:
            event (QDragEnterEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """Processes the dropped file and emits the file_dropped signal.
        
        Args:
            event (QDropEvent): The drop event containing the file URLs.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.file_dropped.emit(file_path)


class ReaderView(QWidget):
    """Main view for the PDF document reader.
    
    Manages the user interface, thumbnail navigation, native OS vector printing, 
    crisp dynamic zoom (Retina/High-DPI), and file hand-offs to other application modules.
    
    Attributes:
        navigate_callback (callable | None): Callback to route files to other modules.
        current_file (str | None): Absolute path to the currently loaded PDF file.
        doc (fitz.Document | None): The active PyMuPDF document instance.
        is_fullscreen (bool): State flag indicating if the reader is in fullscreen mode.
        current_zoom (float): Current rendering scale/zoom factor.
        render_timer (QTimer): Timer used to debounce vector rendering during continuous zoom.
    """
    
    def __init__(self, navigate_callback=None):
        """Initializes the Reader module, setting up UI, timers, and shortcuts.
        
        Args:
            navigate_callback (callable, optional): Callback for inter-module navigation. 
                Defaults to None.
        """
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
        """Registers keyboard shortcuts for rapid page navigation."""
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_right.activated.connect(self.next_page)
        
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_space.activated.connect(self.next_page)

        self.shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_left.activated.connect(self.prev_page)

    def next_page(self):
        """Advances the viewer to the next page if one exists."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row == -1: 
                self.list_widget.setCurrentRow(0)
            elif current_row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(current_row + 1)

    def prev_page(self):
        """Returns the viewer to the previous page if one exists."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row > 0:
                self.list_widget.setCurrentRow(current_row - 1)

    def init_ui(self):
        """Constructs the layout, toolbars, viewports, and thumbnail navigation panel."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 20)
        self.layout.setSpacing(10)

        self.top_container = QWidget()
        top_layout = QVBoxLayout(self.top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        title_layout = QHBoxLayout()
        title = QLabel("PDF Reader")
        title.setObjectName("TitleLabel")
        title_layout.addWidget(title)

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
        """Restarts the debounce timer to update the vector render dynamically."""
        self.render_timer.start()

    def zoom_in(self):
        """Increases the zoom level by a factor of 1.2x, up to a maximum of 500%."""
        if self.current_zoom < 5.0:
            self.viewer.scale(1.2, 1.2)
            self.schedule_vector_render()

    def zoom_out(self):
        """Decreases the zoom level by a factor of 1.2x, down to a minimum of 20%."""
        if self.current_zoom > 0.2:
            self.viewer.scale(1.0 / 1.2, 1.0 / 1.2)
            self.schedule_vector_render()

    def reset_zoom(self):
        """Resets the zoom level to 100% and restores the original transformation."""
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.update_viewer_vector()

    def print_file(self):
        """Triggers the native OS print dialog and routes the document via CUPS or LPR.
        
        Provides cross-platform support for hardware printing, directly passing the 
        file to local system spools, or rendering high-res pixmaps if bypass fails.
        """
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
        """Toggles the visibility of the thumbnail navigation sidebar."""
        self.list_widget.setVisible(not self.list_widget.isVisible())

    def toggle_fullscreen(self):
        """Toggles the full-screen reading mode, hiding the top bar and sidebar."""
        self.is_fullscreen = not self.is_fullscreen
        self.top_container.setVisible(not self.is_fullscreen)
        if self.is_fullscreen:
            self.btn_fullscreen.setText("Exit Fullscreen")
            self.list_widget.setVisible(False)
        else:
            self.btn_fullscreen.setText("Fullscreen")
            self.list_widget.setVisible(True)

    def dragEnterEvent(self, event):
        """Validates incoming drag events strictly for single PDF files.
        
        Args:
            event (QDragEnterEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """Handles the dropped PDF file and initiates its loading process.
        
        Args:
            event (QDropEvent): The drop event containing the file URLs.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.load_file(file_path)

    def select_file(self):
        """Opens a file dialog to allow the user to manually select a PDF to read."""
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file: 
            self.load_file(file)

    def load_file(self, file_path: str):
        """Parses and loads a PDF document into memory.
        
        Args:
            file_path (str): The absolute path to the PDF file to load.
        """
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
        self.file_label.setText(os.path.basename(file_path))
        self.load_thumbnails()

    def load_thumbnails(self):
        """Generates down-sampled pixmaps for each page to populate the navigation sidebar."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.viewer.scene.clear()
        self.viewer.pixmap_item = None
        
        try:
            mat = fitz.Matrix(0.3, 0.3)
            for i in range(len(self.doc)):
                page = self.doc[i]
                pix = page.get_pixmap(matrix=mat)
                fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
                pixmap = QPixmap.fromImage(img)
                
                item = QListWidgetItem(QIcon(pixmap), f"Page {i + 1}")
                item.setData(Qt.ItemDataRole.UserRole, i + 1)
                self.list_widget.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating thumbnails:\n{str(e)}")
            
        self.list_widget.blockSignals(False)
        
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def on_page_changed(self):
        """Resets the canvas transformation and loads the selected page with an initial zoom."""
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.viewer.scale(1.5, 1.5)
        self.update_viewer_vector()

    def update_viewer_vector(self):
        """Renders the current page natively from the PDF's vector coordinates.
        
        Calculates device pixel ratios and dynamic matrix scaling to maintain 
        text crispness on high DPI screens and deep zoom levels.
        """
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
            pix = page.get_pixmap(matrix=mat, alpha=True)
            
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            img.setDevicePixelRatio(dpr)
            
            high_res_pixmap = QPixmap.fromImage(img)
            
            self.viewer.set_pixmap(high_res_pixmap)
            self.viewer.resetTransform()
            
        except Exception as e:
            print(f"Error viewing page: {e}")

    def bridge_to_module(self, module_index: int):
        """Triggers the navigate callback to route the open file to a target tool.
        
        Args:
            module_index (int): The stacked widget index of the target module view.
        """
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please open a PDF file first.")
        if self.navigate_callback:
            self.navigate_callback(module_index, [self.current_file])

    def closeEvent(self, event):
        """Handles widget shutdown, ensuring file handles are closed properly.
        
        Args:
            event (QCloseEvent): The close event.
        """
        if self.doc:
            self.doc.close()
        super().closeEvent(event)