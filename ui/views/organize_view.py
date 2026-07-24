import os
import fitz 
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QListWidget, QFileDialog, QMessageBox, 
                             QListWidgetItem, QAbstractItemView, QComboBox, QCheckBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSplitter)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QDragMoveEvent, QTransform, QWheelEvent, QPainter, QPen, QColor, QShortcut, QKeySequence
from PyQt6.QtCore import QSize, Qt, QEvent
from backend.pdf_core import PDFProcessor


class ZoomableView(QGraphicsView):
    """
    A custom QGraphicsView that provides a high-resolution, zoomable image viewer.
    
    Supports panning via drag-and-drop, zooming via keyboard modifiers (Ctrl+Scroll), 
    and native trackpad pinch-to-zoom gestures.
    """
    
    def __init__(self):
        """Initializes the zoomable view and sets up rendering hints."""
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setStyleSheet("background-color: #E5E7EB; border: 1px solid #D1D5DB; border-radius: 6px;")

    def set_image(self, pixmap: QPixmap):
        """
        Updates the displayed image and adjusts the scene boundaries.
        
        Args:
            pixmap (QPixmap): The image map to be displayed.
        """
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self.fit_to_window()

    def fit_to_window(self):
        """Scales the current image to fit entirely within the viewport while preserving aspect ratio."""
        if not self.pixmap_item.pixmap().isNull():
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self):
        """Increases the zoom level by a factor of 1.15."""
        self.scale(1.15, 1.15)

    def zoom_out(self):
        """Decreases the zoom level by a factor of 1.15."""
        self.scale(1 / 1.15, 1 / 1.15)

    def viewportEvent(self, event: QEvent) -> bool:
        """
        Handles native trackpad gestures, specifically pinch-to-zoom.
        
        Args:
            event (QEvent): The viewport event.
            
        Returns:
            bool: True if the event was handled, otherwise delegates to the parent class.
        """
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                zoom_factor = 1.0 + event.value()
                self.scale(zoom_factor, zoom_factor)
                return True
        return super().viewportEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """
        Handles mouse wheel events to zoom in or out when the Control modifier is held.
        
        Args:
            event (QWheelEvent): The wheel event triggered by the user.
        """
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            super().wheelEvent(event)


class AutoScrollListWidget(QListWidget):
    """
    Custom QListWidget that provides automatic edge-scrolling during drag-and-drop 
    operations and smooth pixel-based scrolling.
    """
    
    def __init__(self, parent=None):
        """Initializes the auto-scroll list widget."""
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def dragMoveEvent(self, event: QDragMoveEvent):
        """
        Checks mouse position during a drag event and scrolls up/down if near the edges.
        
        Args:
            event (QDragMoveEvent): The drag move event containing cursor coordinates.
        """
        super().dragMoveEvent(event)
        pos = event.position().toPoint()
        scrollbar = self.verticalScrollBar()
        # Scroll up if cursor is near the top edge
        if pos.y() < 40: 
            scrollbar.setValue(scrollbar.value() - 8)
        # Scroll down if cursor is near the bottom edge
        elif pos.y() > self.height() - 40: 
            scrollbar.setValue(scrollbar.value() + 8)

    def wheelEvent(self, event: QWheelEvent):
        """
        Custom wheel scrolling behavior for smoother list navigation.
        
        Args:
            event (QWheelEvent): The wheel event.
        """
        delta = event.angleDelta().y()
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - int(delta / 4))


class OrganizeView(QWidget):
    """
    Main View for organizing, rotating, removing, and compressing PDF pages.
    
    Features a two-way synchronization system between a manual drag-and-drop grid 
    and a text-based range input, alongside a high-resolution previewer.
    """
    
    def __init__(self):
        """Initializes the Organize View state and user interface."""
        super().__init__()
        self.current_file = None
        self.original_items = {} 
        self.setAcceptDrops(True)
        self.init_ui()
        self.setup_shortcuts() # Initialize keyboard shortcuts

    # --- NEW KEYBOARD FUNCTIONS ---
    def setup_shortcuts(self):
        """Binds keyboard shortcuts for quick navigation through thumbnails."""
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
        """Advances selection to the next thumbnail in the list."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row == -1: # If nothing is selected, select the first item
                self.list_widget.setCurrentRow(0)
            elif current_row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(current_row + 1)

    def prev_page(self):
        """Moves selection to the previous thumbnail in the list."""
        if self.list_widget.count() > 0:
            current_row = self.list_widget.currentRow()
            if current_row > 0:
                self.list_widget.setCurrentRow(current_row - 1)
    # ----------------------------------------

    def init_ui(self):
        """Constructs the layout and instantiates UI components."""
        # Main view layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 15, 20, 20) # Optimized margins
        self.layout.setSpacing(10)
        
        # --- TOP BLOCK (Compact Controls) ---
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        title_layout = QHBoxLayout()
        title = QLabel("Organize, Edit and Compress PDF")
        title.setObjectName("TitleLabel")
        title_layout.addWidget(title)
        
        # Primary Button (Blue by default)
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
        
        # Secondary Buttons (Gray)
        btn_rotate = QPushButton("🔄 Rotate Page")
        btn_rotate.setProperty("class", "SecondaryButton")
        btn_rotate.clicked.connect(self.rotate_selected)
        control_layout.addWidget(btn_rotate)
        
        btn_remove_blank = QPushButton("🪄 Detect Blank Pages")
        btn_remove_blank.setProperty("class", "SecondaryButton")
        btn_remove_blank.clicked.connect(self.remove_blank_pages)
        control_layout.addWidget(btn_remove_blank)
        
        top_layout.addLayout(control_layout)
        
        self.layout.addWidget(top_container)

        # --- CENTRAL AREA (Workspace: Takes all available space) ---
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.viewer_container = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = ZoomableView()
        viewer_layout.addWidget(self.viewer)
        
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Zoom buttons now use the global SecondaryButton class
        btn_zoom_out = QPushButton("-")
        btn_fit = QPushButton("⛶ Fit Page")
        btn_zoom_in = QPushButton("+")
        
        btn_zoom_out.clicked.connect(self.viewer.zoom_out)
        btn_fit.clicked.connect(self.viewer.fit_to_window)
        btn_zoom_in.clicked.connect(self.viewer.zoom_in)
        
        for btn in [btn_zoom_out, btn_fit, btn_zoom_in]:
            btn.setProperty("class", "SecondaryButton")
            zoom_controls_layout.addWidget(btn)
            
        viewer_layout.addLayout(zoom_controls_layout)
        
        self.workspace_splitter.addWidget(self.viewer_container)
        
        self.list_widget = AutoScrollListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(12)
        self.list_widget.setIconSize(QSize(160, 215))
        self.list_widget.setStyleSheet("background-color: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 4px;")
        
        # Bi-directional sync connections
        self.list_widget.itemChanged.connect(self.sync_from_list)
        self.list_widget.model().rowsMoved.connect(self.sync_from_list)
        self.list_widget.itemSelectionChanged.connect(self.update_viewer)
        
        self.workspace_splitter.addWidget(self.list_widget)
        self.workspace_splitter.setStretchFactor(0, 7) 
        self.workspace_splitter.setStretchFactor(1, 3) 
        
        self.layout.addWidget(self.workspace_splitter, 1)

        # --- BOTTOM BLOCK ---
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

        # Success Button (Green)
        btn_save = QPushButton("Process and Save PDF")
        btn_save.setProperty("class", "SuccessButton")
        btn_save.clicked.connect(self.save_pdf)
        bottom_layout.addWidget(btn_save)
        
        self.layout.addWidget(bottom_container)

    def dragEnterEvent(self, event: QDragMoveEvent):
        """
        Validates single PDF drop.
        
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
        Handles PDF dropped onto the view.
        
        Args:
            event (QDropEvent): The drop event containing the file data.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.load_file(file_path)

    def select_file(self):
        """Opens a native file dialog to select a PDF."""
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file: self.load_file(file)

    def load_file(self, file_path: str):
        """
        Validates and loads a PDF file for organization.
        
        Checks if the file is encrypted before passing it to PyMuPDF to avoid crashes.
        
        Args:
            file_path (str): Absolute path to the PDF.
        """
        # 1. Verify if the file is encrypted BEFORE attempting to process it
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

        # 2. If it is free of passwords, continue normally
        self.current_file = file_path
        self.file_label.setText(os.path.basename(file_path))
        self.load_thumbnails()

    def load_thumbnails(self):
        """
        Extracts pages from the loaded PDF and displays them as thumbnails in the list widget.
        Applies a custom gray border to each thumbnail for better visual distinction.
        """
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.original_items.clear()
        
        self.viewer.scene.clear()
        self.viewer.pixmap_item = QGraphicsPixmapItem()
        self.viewer.scene.addItem(self.viewer.pixmap_item)
        
        # Use fitz directly to force a high-resolution thumbnail (Scale 1.5)
        doc = fitz.open(self.current_file)
        mat = fitz.Matrix(1.5, 1.5) 
        
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            # --- DRAW A GRAY BORDER ON THE THUMBNAIL ---
            painter = QPainter(pixmap)
            pen = QPen(QColor("#9CA3AF")) # Gray color
            pen.setWidth(2)               # Border thickness in pixels
            painter.setPen(pen)
            
            # Draw a rectangle right on the edge
            painter.drawRect(1, 1, pixmap.width() - 2, pixmap.height() - 2)
            painter.end()
            # ---------------------------------------------
            
            page_num = i + 1
            item = QListWidgetItem(QIcon(pixmap), f"Page {page_num}  (0°)")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled | 
                          Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            
            # Store metadata in UserRoles
            item.setData(Qt.ItemDataRole.UserRole, page_num)
            item.setData(Qt.ItemDataRole.UserRole + 1, 0)       # Rotation state
            item.setData(Qt.ItemDataRole.UserRole + 2, pixmap)  # Cached pixmap
            
            self.list_widget.addItem(item)
            self.original_items[page_num] = item
            
        doc.close()
            
        self.list_widget.blockSignals(False)
        self.sync_from_list()
        
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def update_viewer(self):
        """
        Updates the high-resolution viewer when a new thumbnail is selected.
        Applies any pending rotations to the preview dynamically.
        """
        item = self.list_widget.currentItem()
        if not item: return
        
        page_num = item.data(Qt.ItemDataRole.UserRole)
        rotation = item.data(Qt.ItemDataRole.UserRole + 1)
        
        try:
            doc = fitz.open(self.current_file)
            page = doc[page_num - 1]
            
            mat = fitz.Matrix(2.0, 2.0)
            if rotation != 0:
                mat.preRotate(rotation)
                
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            high_res_pixmap = QPixmap.fromImage(img)
            doc.close()
            
            self.viewer.set_image(high_res_pixmap)
        except Exception as e:
            # Fallback to cached low-res thumbnail if high-res extraction fails
            pixmap = item.data(Qt.ItemDataRole.UserRole + 2)
            if rotation != 0:
                transform = QTransform().rotate(rotation)
                pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            self.viewer.set_image(pixmap)

    def rotate_selected(self):
        """Rotates the currently selected thumbnail by 90 degrees clockwise and updates the viewer."""
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
        
        self.update_viewer()

    def remove_blank_pages(self):
        """
        Calls the backend core to scan the document for visually empty pages.
        Unchecks detected blank pages automatically so they are excluded from export.
        """
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
        """
        Parses the manual text input (e.g. '3-5, 1, 6') and physically reorders 
        the thumbnails in the QListWidget to match the typed order.
        """
        text = self.range_input.text().strip()
        
        # 1. Parse the text while maintaining order and removing duplicates
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
        
        # 2. Save items and their original positions
        items_dict = {}
        original_positions = {}
        count = self.list_widget.count()
        
        for i in range(count):
            item = self.list_widget.item(i)
            page_num = item.data(Qt.ItemDataRole.UserRole)
            items_dict[page_num] = item
            original_positions[page_num] = i
            
        # Clear the UI for reordering
        while self.list_widget.count() > 0:
            self.list_widget.takeItem(0)
            
        # 3. Filter active pages to ensure they exist in the PDF
        valid_active = [p for p in active_pages if p in items_dict]
        
        # 4. Create the new list respecting positions
        new_list = [None] * count
        
        # Step A: Unwritten pages stay in their original index and are unchecked
        for page_num, item in items_dict.items():
            if page_num not in seen:
                pos = original_positions[page_num]
                item.setCheckState(Qt.CheckState.Unchecked)
                new_list[pos] = item
                
        # Step B: Empty slots are filled with active pages in the NEW order
        active_idx = 0
        for i in range(count):
            if new_list[i] is None:
                p = valid_active[active_idx]
                item = items_dict[p]
                item.setCheckState(Qt.CheckState.Checked)
                new_list[i] = item
                active_idx += 1
                
        # 5. Reinsert everything into the graphical interface
        for item in new_list:
            if item is not None:
                self.list_widget.addItem(item)
                
        self.list_widget.blockSignals(False)
        self.sync_from_list()

    def sync_from_list(self, *args):
        """
        Reads the currently checked items in the QListWidget in their current 
        visual order and updates the text input string (e.g. converting visual 
        sequence back into '1-3, 5').
        
        Args:
            *args: Variable length argument list to absorb signal emissions.
        """
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
        """
        Collects page order, rotations, and compression settings and triggers 
        the backend compiler to output the final modified PDF.
        """
        if not self.current_file: 
            return QMessageBox.warning(self, "Error", "Please select a PDF first.")
        rango = self.range_input.text()
        
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
                self.current_file, save_path, rango, self.size_combo.currentText(), rotations,
                self.chk_logo.isChecked(), self.chk_num.isChecked(), self.chk_compress.isChecked()
            )
            if success:
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.critical(self, "Error", msg)