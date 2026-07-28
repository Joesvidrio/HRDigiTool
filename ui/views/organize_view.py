import os
import fitz 
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QListWidget, QFileDialog, QMessageBox, 
                             QListWidgetItem, QAbstractItemView, QComboBox, QCheckBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSplitter)
from PyQt6.QtGui import (QPixmap, QImage, QIcon, QDragMoveEvent, QTransform, 
                         QWheelEvent, QPainter, QPen, QColor, QShortcut, QKeySequence)
from PyQt6.QtCore import QSize, Qt, QEvent, pyqtSignal, QTimer
from backend.pdf_core import PDFProcessor


class ZoomableView(QGraphicsView):
    """A custom QGraphicsView that provides a high-resolution, zoomable image viewer.
    
    Supports panning via drag-and-drop, zooming via keyboard modifiers (Ctrl+Scroll), 
    and native trackpad pinch-to-zoom gestures.
    
    Attributes:
        zoom_changed (pyqtSignal): Emitted whenever a zoom gesture modifies the view's scale.
    """
    zoom_changed = pyqtSignal()
    
    def __init__(self):
        """Initializes the zoomable view and sets up high-quality rendering hints."""
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setStyleSheet("background-color: #E5E7EB; border: 1px solid #D1D5DB; border-radius: 6px;")

    def set_image(self, pixmap: QPixmap, reset_transform: bool = False):
        """Updates the displayed image and adjusts the scene boundaries.
        
        Args:
            pixmap (QPixmap): The image to be displayed in the view.
            reset_transform (bool, optional): If True, resets the current zoom and pan. Defaults to False.
        """
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        
        if reset_transform:
            self.resetTransform()

    def fit_to_window(self):
        """Scales the current image to fit entirely within the viewport boundaries."""
        if not self.pixmap_item.pixmap().isNull():
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def viewportEvent(self, event: QEvent) -> bool:
        """Handles native trackpad gestures for pinch-to-zoom functionality.
        
        Args:
            event (QEvent): The viewport event to process.
            
        Returns:
            bool: True if the event was handled, otherwise delegates to the parent class.
        """
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                zoom_factor = 1.0 + event.value()
                self.scale(zoom_factor, zoom_factor)
                self.zoom_changed.emit()
                return True
        return super().viewportEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Handles mouse wheel events to zoom in or out when the Control key is held.
        
        Args:
            event (QWheelEvent): The wheel event triggered by the user.
        """
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
            self.scale(factor, factor)
            self.zoom_changed.emit()
        else:
            super().wheelEvent(event)


class AutoScrollListWidget(QListWidget):
    """Custom QListWidget that provides automatic edge-scrolling during drag-and-drop operations."""
    
    def __init__(self, parent=None):
        """Initializes the auto-scrolling list widget.
        
        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handles drag movements to scroll automatically when near the edges.
        
        Args:
            event (QDragMoveEvent): The drag move event being processed.
        """
        super().dragMoveEvent(event)
        pos = event.position().toPoint()
        scrollbar = self.verticalScrollBar()
        if pos.y() < 40: 
            scrollbar.setValue(scrollbar.value() - 8)
        elif pos.y() > self.height() - 40: 
            scrollbar.setValue(scrollbar.value() + 8)

    def wheelEvent(self, event: QWheelEvent):
        """Custom scroll wheel behavior for smoother scrolling.
        
        Args:
            event (QWheelEvent): The mouse wheel event.
        """
        delta = event.angleDelta().y()
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - int(delta / 4))


class OrganizeView(QWidget):
    """Main view for organizing, rotating, removing, and compressing PDF pages.
    
    Attributes:
        current_file (str): Path to the currently loaded PDF file.
        original_items (dict): A mapping of page numbers to their respective QListWidgetItem.
        current_zoom (float): The current zoom level applied to the PDF viewer.
        render_timer (QTimer): Timer used to debounce vector rendering updates.
    """
    
    def __init__(self):
        """Initializes the OrganizeView, sets up the UI, and configures event timers."""
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
        """Configures keyboard shortcuts for quick navigation."""
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_right.activated.connect(self.next_page)
        
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.shortcut_space.activated.connect(self.next_page)

        self.shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_left.activated.connect(self.prev_page)

    def next_page(self):
        """Selects the next page in the list widget if available."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row == -1: 
                self.list_widget.setCurrentRow(0)
            elif current_row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(current_row + 1)

    def prev_page(self):
        """Selects the previous page in the list widget if available."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row > 0:
                self.list_widget.setCurrentRow(current_row - 1)

    def init_ui(self):
        """Initializes and lays out the user interface components."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 20) 
        self.layout.setSpacing(10)
        
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        title_layout = QHBoxLayout()
        title = QLabel("Organize, Edit and Compress PDF")
        title.setObjectName("TitleLabel")
        title_layout.addWidget(title)
        
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
        self.list_widget.setStyleSheet("background-color: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 4px;")
        
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
        """Toggles the visibility of the page thumbnail list sidebar."""
        self.list_widget.setVisible(not self.list_widget.isVisible())

    def reset_zoom(self):
        """Resets the zoom level to default and fits the image within the view."""
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
        """Starts the debounce timer to update the high-resolution vector render."""
        self.render_timer.start()

    def dragEnterEvent(self, event: QDragMoveEvent):
        """Accepts the drag event if a valid PDF file is dragged into the view.
        
        Args:
            event (QDragMoveEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.pdf'):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """Handles dropping a PDF file into the application.
        
        Args:
            event (QDropEvent): The drop event containing the file URLs.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.load_file(file_path)

    def select_file(self):
        """Opens a file dialog to allow the user to manually select a PDF file."""
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file: 
            self.load_file(file)

    def load_file(self, file_path):
        """Loads a PDF file into the application and generates thumbnails.
        
        Args:
            file_path (str | list): The path (or list containing the path) to the PDF file.
        """
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
                    "Please use the 'Security and Metadata' module to unlock it before attempting to organize or edit it."
                )
                return
            doc.close()
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"The file is damaged or could not be read:\n{str(e)}")
            return

        self.current_file = file_path
        self.current_zoom = 1.0
        self.file_label.setText(os.path.basename(file_path))
        self.load_thumbnails()

    def load_thumbnails(self):
        """Extracts pages from the loaded PDF and displays them as thumbnails in the list."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.original_items.clear()
        
        self.viewer.scene.clear()
        self.viewer.pixmap_item = QGraphicsPixmapItem()
        self.viewer.scene.addItem(self.viewer.pixmap_item)
        
        doc = fitz.open(self.current_file)
        mat = fitz.Matrix(1.5, 1.5) 
        
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            painter = QPainter(pixmap)
            pen = QPen(QColor("#9CA3AF")) 
            pen.setWidth(2)               
            painter.setPen(pen)
            painter.drawRect(1, 1, pixmap.width() - 2, pixmap.height() - 2)
            painter.end()
            
            page_num = i + 1
            item = QListWidgetItem(QIcon(pixmap), f"Page {page_num}  (0°)")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled | 
                          Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            
            item.setData(Qt.ItemDataRole.UserRole, page_num)
            item.setData(Qt.ItemDataRole.UserRole + 1, 0)       
            item.setData(Qt.ItemDataRole.UserRole + 2, pixmap)  
            
            self.list_widget.addItem(item)
            self.original_items[page_num] = item
            
        doc.close()
            
        self.list_widget.blockSignals(False)
        self.sync_from_list()
        
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def on_page_selected(self):
        """Triggers a fresh render with an initial zoom when a new thumbnail is selected."""
        self.current_zoom = 1.0
        self.viewer.resetTransform()
        self.viewer.scale(1.5, 1.5)
        self.update_viewer_vector()

    def update_viewer_vector(self):
        """Renders the currently selected page directly from PDF vector coordinates."""
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
            print(f"Error vector rendering page: {e}")

    def rotate_selected(self):
        """Rotates the currently selected page 90 degrees clockwise."""
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
        """Scans the PDF for blank pages and unchecks them automatically in the list."""
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please select a PDF first.")
            
        blank_pages = PDFProcessor.get_blank_pages(self.current_file)
        
        if not blank_pages:
            return QMessageBox.information(self, "Info", "No blank pages detected in this document.")
            
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
        """Parses the manual page range input and updates the thumbnail list checks and order."""
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
        """Updates the manual page range text input based on the checked items in the list widget."""
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
        """Processes the PDF with all requested transformations and saves it to a new file."""
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