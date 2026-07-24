import os
import tempfile
import fitz
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QListWidget, QAbstractItemView, 
                             QListWidgetItem, QMessageBox, QComboBox)
from PyQt6.QtCore import Qt, QTimer
from backend.pdf_core import PDFProcessor


class DraggableListWidget(QListWidget):
    """
    Custom QListWidget supporting internal drag-and-drop to reorder files.
    
    This widget allows users to intuitively reorder the merging sequence of 
    their documents by dragging list items up or down.
    """
    
    def __init__(self, parent=None):
        """
        Initializes the DraggableListWidget.
        
        Args:
            parent (QWidget, optional): The parent widget (typically MergeView).
        """
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.parent_view = parent

    def dropEvent(self, event):
        """
        Handles the drop event when an item is moved within the list.
        
        Args:
            event (QDropEvent): The event object containing drop context.
        """
        super().dropEvent(event)
        
        # UI Refresh is deferred by 10ms to allow the underlying Qt model 
        # data to settle completely before reconstructing the custom widgets (labels/buttons).
        if self.parent_view:
            QTimer.singleShot(10, self.parent_view.refresh_list_widgets)


class MergeView(QWidget):
    """
    View module for combining multiple PDFs and Images into a single document.
    
    Provides an interface to add files (via dialog or drag-and-drop), reorder them, 
    select an output page size, and either save the merged file directly or 
    forward it to the Organize module for further editing.
    """
    
    def __init__(self, navigate_to_organize_cb=None):
        """
        Initializes the MergeView.
        
        Args:
            navigate_to_organize_cb (callable, optional): Callback to route a temporary 
                                                          merged PDF to the Organize view.
        """
        super().__init__()
        self.navigate_to_organize = navigate_to_organize_cb
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        """Constructs the layout and instantiates UI components."""
        layout = QVBoxLayout(self)
        
        title = QLabel("Merge PDFs and Images")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        # --- Top Control Bar ---
        top_layout = QHBoxLayout()
        
        # Secondary Button (Gray/Outline theme)
        btn_add = QPushButton("Add Files")
        btn_add.setProperty("class", "SecondaryButton")
        btn_add.clicked.connect(self.add_files)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Original", "A4", "Letter", "Legal"])
        
        top_layout.addWidget(btn_add)
        top_layout.addWidget(QLabel("<b>Page Size:</b>"))
        top_layout.addWidget(self.size_combo)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # --- Main List Area ---
        self.list_widget = DraggableListWidget(self)
        layout.addWidget(self.list_widget)

        # --- Bottom Action Bar ---
        bottom_layout = QHBoxLayout()
        
        # Success Button (Green theme for final action)
        btn_save = QPushButton("Save Merged PDF")
        btn_save.setProperty("class", "SuccessButton")
        btn_save.clicked.connect(self.save_pdf)
        
        # Primary/Secondary Button
        btn_organize = QPushButton("Organize PDF")
        btn_organize.clicked.connect(self.send_to_organize)
        
        bottom_layout.addWidget(btn_save)
        bottom_layout.addWidget(btn_organize)
        layout.addLayout(bottom_layout)

    def dragEnterEvent(self, event):
        """
        Validates incoming Drag & Drop items.
        Only accepts URLs pointing to supported document/image extensions.
        
        Args:
            event (QDragEnterEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(valid_extensions) for url in urls):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """
        Extracts file paths from a drop event and populates the list view.
        
        Args:
            event (QDropEvent): The drop event containing the file data.
        """
        valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
        paths = [
            url.toLocalFile() for url in event.mimeData().urls() 
            if url.toLocalFile().lower().endswith(valid_extensions)
        ]
        if paths:
            self.add_files_from_paths(paths)

    def add_files(self):
        """Opens a native file dialog for the user to select files to merge."""
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Files", 
            "", 
            "Documents (*.pdf *.png *.jpg *.jpeg)"
        )
        if files:
            self.add_files_from_paths(files)

    def add_files_from_paths(self, file_paths):
        """
        Processes an explicit list of file paths. Validates PDF accessibility
        and adds them to the UI.
        
        Args:
            file_paths (list[str]): List of absolute paths to the requested files.
        """
        valid_files = []
        protected_count = 0

        for file_path in file_paths:
            # Validate if the PDF is password-protected before accepting it
            if file_path.lower().endswith('.pdf'):
                try:
                    doc = fitz.open(file_path)
                    if doc.needs_pass:
                        protected_count += 1
                        doc.close()
                        continue  # Skip encrypted files
                    doc.close()
                except Exception as e:
                    QMessageBox.critical(
                        self, 
                        "Read Error", 
                        f"Could not read {os.path.basename(file_path)}:\n{str(e)}"
                    )
                    continue
            
            valid_files.append(file_path)

        # Append validated files to the list widget
        for file in valid_files:
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, file)
            self.list_widget.addItem(item)
        
        self.refresh_list_widgets()

        # Notify the user if any encrypted files were deliberately skipped
        if protected_count > 0:
            QMessageBox.warning(
                self, 
                "Protected Files Skipped", 
                f"Skipped <b>{protected_count}</b> password-protected file(s). 🔒<br><br>"
                "Please use the 'Security and Metadata' module to unlock them before merging."
            )

    def remove_item(self, item):
        """
        Removes a specific item from the list widget.
        
        Args:
            item (QListWidgetItem): The item to be removed.
        """
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)

    def refresh_list_widgets(self):
        """
        Re-binds the custom UI widgets (filename labels & close buttons) to the list items.
        Called after files are added or reordered via drag-and-drop.
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(10, 5, 10, 5)
            
            lbl = QLabel(os.path.basename(file_path))
            
            # Close Button (Inherits specific 'CloseButton' styling from QSS)
            btn_x = QPushButton("X")
            btn_x.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_x.setProperty("class", "CloseButton")
            btn_x.clicked.connect(lambda checked, idx_item=item: self.remove_item(idx_item))
            
            layout.addWidget(lbl)
            layout.addStretch()
            layout.addWidget(btn_x)
            
            widget.setMinimumHeight(40)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(item, widget)

    def get_file_list(self):
        """
        Retrieves the ordered list of file paths currently in the UI.
        
        Returns:
            list[str]: A list of absolute file paths.
        """
        return [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) 
            for i in range(self.list_widget.count())
        ]

    def save_pdf(self):
        """Executes the merge operation and prompts the user to save the resulting PDF."""
        files = self.get_file_list()
        if not files: 
            return QMessageBox.warning(self, "Warning", "Please add files first.")
        
        save_path, _ = QFileDialog.getSaveFileName(self, "Save", "", "PDF (*.pdf)")
        if save_path:
            success, msg = PDFProcessor.merge_files_to_temp(
                files, save_path, self.size_combo.currentText()
            )
            if success:
                QMessageBox.information(self, "Result", msg) 
            else:
                QMessageBox.critical(self, "Error", msg)

    def send_to_organize(self):
        """
        Merges files to a temporary location and automatically bridges the user 
        to the Organize View with the newly generated document loaded.
        """
        files = self.get_file_list()
        if not files: 
            return QMessageBox.warning(self, "Warning", "Please add files first.")
        if not self.navigate_to_organize: 
            return
        
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, "temp_merged_pdf_studio.pdf")
        
        success, msg = PDFProcessor.merge_files_to_temp(
            files, temp_file, self.size_combo.currentText()
        )
        
        if success:
            self.list_widget.clear()
            self.navigate_to_organize(temp_file)
        else:
            QMessageBox.critical(self, "Processing Error", msg)