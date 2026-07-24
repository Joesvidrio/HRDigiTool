import os
import fitz
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QListWidget, QListWidgetItem, 
                             QAbstractItemView, QMessageBox, QSplitter,
                             QGraphicsView, QGraphicsScene)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QShortcut, QKeySequence
from PyQt6.QtCore import QSize, Qt, pyqtSignal, QEvent

import ui.views.organize_view as org_view


class ReaderGraphicsView(QGraphicsView):
    """
    An exclusive graphics view for reading PDFs with trackpad zoom and Drag & Drop support.
    
    Attributes:
        file_dropped (pyqtSignal): Signal emitted with the file path when a valid PDF is dropped.
    """
    
    # Signal to notify the main view that a file was dropped here
    file_dropped = pyqtSignal(str)

    def __init__(self):
        """Initializes the ReaderGraphicsView and configures rendering and drag modes."""
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.pixmap_item = None
        
        # Enable Drag & Drop in the viewer
        self.setAcceptDrops(True)

    def set_image(self, pixmap: QPixmap):
        """
        Clears the scene and displays the new pixmap.
        
        Args:
            pixmap (QPixmap): The image to render in the viewer.
        """
        self.scene.clear()
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(self.pixmap_item.boundingRect())
        self.fit_to_window()

    def zoom_in(self):
        """Increases the zoom level by a factor of 1.2."""
        if self.pixmap_item:
            self.scale(1.2, 1.2)

    def zoom_out(self):
        """Decreases the zoom level by a factor of 1.2."""
        if self.pixmap_item:
            self.scale(1.0 / 1.2, 1.0 / 1.2)

    def fit_to_window(self):
        """Scales the current image to fit the viewer's window while maintaining aspect ratio."""
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        """
        Handles mouse wheel events for zooming and panning.
        
        On Mac, trackpad pinch gestures are translated as Control + Scroll.
        
        Args:
            event (QWheelEvent): The wheel event triggered by the user.
        """
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # If there is no Control/Pinch, perform normal scrolling (panning)
            super().wheelEvent(event)

    def viewportEvent(self, event: QEvent) -> bool:
        """
        Intercepts native gestures to support trackpad pinch-to-zoom.
        
        Args:
            event (QEvent): The viewport event.
            
        Returns:
            bool: True if the gesture was handled, otherwise falls back to parent processing.
        """
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                # event.value() returns a positive value when zooming in and negative when zooming out
                scale_factor = 1.0 + event.value()
                self.scale(scale_factor, scale_factor)
                return True
        return super().viewportEvent(event)

    def dragEnterEvent(self, event):
        """
        Validates the dragged item, accepting it only if it is a single PDF file.
        
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
        """
        Extracts the file path from the drop event and emits the file_dropped signal.
        
        Args:
            event (QDropEvent): The drop event containing the file data.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.file_dropped.emit(file_path)  # Emits the path to the main view


class ReaderView(QWidget):
    """
    Main View for reading PDFs with a sidebar thumbnail navigator and fullscreen support.
    
    Features keyboard navigation, drag-and-drop loading, and bridges to other app modules 
    (Merge, Organize, Security).
    """
    
    def __init__(self, navigate_callback=None):
        """
        Initializes the ReaderView.
        
        Args:
            navigate_callback (callable, optional): Callback used to send the current file 
                                                    to other modules (Merge, Organize, etc.).
        """
        super().__init__()
        self.navigate_callback = navigate_callback
        self.current_file = None
        self.is_fullscreen = False
        
        # Accept drops in the empty spaces of the main view
        self.setAcceptDrops(True)
        self.init_ui()
        self.setup_shortcuts() 

    def setup_shortcuts(self):
        """Binds keyboard shortcuts for navigating through PDF pages."""
        # Right Arrow
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_right.activated.connect(self.next_page)
        
        # Spacebar
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_space.activated.connect(self.next_page)

        # Left Arrow
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_left.activated.connect(self.prev_page)

    def next_page(self):
        """Advances the sidebar selection to the next page."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row == -1: # If nothing is selected, select the first item
                self.list_widget.setCurrentRow(0)
            elif current_row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(current_row + 1)

    def prev_page(self):
        """Moves the sidebar selection to the previous page."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row > 0:
                self.list_widget.setCurrentRow(current_row - 1)

    def init_ui(self):
        """Constructs the primary layout and visual components of the Reader."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 20)
        self.layout.setSpacing(10)

        # --- Top Header ---
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
        
        title_layout.addWidget(btn_select)
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

        # --- Workspace ---
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Viewer Container
        self.viewer_container = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = ReaderGraphicsView()
        # Connect the viewer's drop signal to the file loading function
        self.viewer.file_dropped.connect(self.load_file) 
        viewer_layout.addWidget(self.viewer)
        
        # --- Bottom Controls ---
        zoom_controls_layout = QHBoxLayout()
        
        # 1. Fullscreen
        self.btn_fullscreen = QPushButton("Fullscreen")
        self.btn_fullscreen.setProperty("class", "SecondaryButton")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        zoom_controls_layout.addWidget(self.btn_fullscreen)
            
        zoom_controls_layout.addStretch()
        
        # 2. Zoom
        btn_zoom_out = QPushButton("-")
        btn_fit = QPushButton("⛶ Fit Page")
        btn_zoom_in = QPushButton("+")
        
        btn_zoom_out.clicked.connect(self.viewer.zoom_out)
        btn_fit.clicked.connect(self.viewer.fit_to_window)
        btn_zoom_in.clicked.connect(self.viewer.zoom_in)
        
        for btn in [btn_zoom_out, btn_fit, btn_zoom_in]:
            btn.setProperty("class", "SecondaryButton")
            zoom_controls_layout.addWidget(btn)
            
        zoom_controls_layout.addStretch()
        
        # 3. Toggle Sidebar
        btn_toggle_sidebar = QPushButton("Toggle Sidebar")
        btn_toggle_sidebar.setProperty("class", "SecondaryButton")
        btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        zoom_controls_layout.addWidget(btn_toggle_sidebar)
        
        viewer_layout.addLayout(zoom_controls_layout)
        self.workspace_splitter.addWidget(self.viewer_container)
        
        # --- Thumbnail List ---
        self.list_widget = org_view.AutoScrollListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(8)
        
        # MODIFIED: Increased thumbnail icon size to fit the larger sidebar perfectly
        self.list_widget.setIconSize(QSize(130, 180)) 
        self.list_widget.setStyleSheet("background-color: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 4px;")
        self.list_widget.itemSelectionChanged.connect(self.update_viewer)
        self.list_widget.setAcceptDrops(False) 
        
        self.workspace_splitter.addWidget(self.list_widget)
        
        # MODIFIED: Changed stretch factors from (0, 8) and (1, 2) to (0, 7) and (1, 3) 
        # to give the sidebar 30% of the screen width instead of 20%.
        self.workspace_splitter.setStretchFactor(0, 7)
        self.workspace_splitter.setStretchFactor(1, 3)
        
        self.layout.addWidget(self.workspace_splitter, 1)

    def toggle_sidebar(self):
        """Shows or hides the sidebar thumbnail list."""
        self.list_widget.setVisible(not self.list_widget.isVisible())

    def toggle_fullscreen(self):
        """Toggles a reading mode that hides the top toolbar and sidebar for maximum reading space."""
        self.is_fullscreen = not self.is_fullscreen
        self.top_container.setVisible(not self.is_fullscreen)
        if self.is_fullscreen:
            self.btn_fullscreen.setText("Exit Fullscreen")
            self.list_widget.setVisible(False)
        else:
            self.btn_fullscreen.setText("Fullscreen")
            self.list_widget.setVisible(True)

    def dragEnterEvent(self, event):
        """
        Handles Drag & Drop events outside the main viewer area (e.g., header or margins).
        
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
        """
        Handles dropping a file outside the main viewer area.
        
        Args:
            event (QDropEvent): The drop event.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.load_file(file_path)

    def select_file(self):
        """Opens a file dialog for the user to select a PDF."""
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file: 
            self.load_file(file)

    def load_file(self, file_path: str):
        """
        Validates and loads a PDF file into the reader view.
        
        Args:
            file_path (str): The absolute path to the PDF file.
        """
        if not os.path.exists(file_path):
            return
            
        try:
            doc = fitz.open(file_path)
            if doc.needs_pass:
                doc.close()
                QMessageBox.warning(self, "Protected PDF", "This file is password protected.")
                return
            doc.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read the file:\n{str(e)}")
            return

        self.current_file = file_path
        self.file_label.setText(os.path.basename(file_path))
        self.load_thumbnails()

    def load_thumbnails(self):
        """Generates low-resolution thumbnails of the PDF pages and loads them into the sidebar."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.viewer.scene.clear()
        self.viewer.pixmap_item = None
        
        try:
            doc = fitz.open(self.current_file)
            mat = fitz.Matrix(0.3, 0.3)
            
            for i in range(len(doc)):
                page = doc[i]
                
                pix = page.get_pixmap(matrix=mat)
                fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
                
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
                pixmap = QPixmap.fromImage(img)
                
                item = QListWidgetItem(QIcon(pixmap), f"Page {i + 1}")
                item.setData(Qt.ItemDataRole.UserRole, i + 1)
                self.list_widget.addItem(item)
                
            doc.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating thumbnails:\n{str(e)}")
            
        self.list_widget.blockSignals(False)
        
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def update_viewer(self):
        """Extracts a high-resolution render of the selected page and updates the main viewer."""
        item = self.list_widget.currentItem()
        if not item: return
        
        page_num = item.data(Qt.ItemDataRole.UserRole)
        
        try:
            doc = fitz.open(self.current_file)
            page = doc[page_num - 1]
            
            mat = fitz.Matrix(2.0, 2.0)
            
            pix = page.get_pixmap(matrix=mat)
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            high_res_pixmap = QPixmap.fromImage(img)
            
            doc.close()
            
            self.viewer.set_image(high_res_pixmap)
            
        except Exception as e:
            print(f"Error viewing page: {e}")

    def bridge_to_module(self, module_index: int):
        """
        Forwards the currently active file to a different application module via the callback.
        
        Args:
            module_index (int): The index of the target module in the application's tab/stack layout.
        """
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please open a PDF file first.")
        if self.navigate_callback:
            # We always send the file wrapped in a list [ ] so other modules parse it correctly
            self.navigate_callback(module_index, [self.current_file])