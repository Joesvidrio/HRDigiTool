import os
import tempfile
import fitz
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QListWidget, QAbstractItemView, 
                             QListWidgetItem, QMessageBox, QComboBox)
from PyQt6.QtCore import Qt, QTimer
from backend.pdf_core import PDFProcessor


class DraggableListWidget(QListWidget):
    """Custom QListWidget supporting internal drag-and-drop to reorder files.
    
    Attributes:
        parent_view (QWidget | None): A reference to the parent view to trigger UI 
            refreshes after a drag-and-drop operation completes.
    """
    
    def __init__(self, parent=None):
        """Initializes the draggable list widget.
        
        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.parent_view = parent

    def dropEvent(self, event):
        """Handles the drop event to reorder items and refreshes the parent UI.
        
        Args:
            event (QDropEvent): The drop event triggered by the user.
        """
        super().dropEvent(event)
        if self.parent_view:
            QTimer.singleShot(10, self.parent_view.refresh_list_widgets)


class MergeView(QWidget):
    """View module for combining multiple PDFs and Images into a single document.
    
    Provides a drag-and-drop interface to queue, reorder, and merge multiple
    documents (PDF, PNG, JPG, JPEG) into one PDF file.
    
    Attributes:
        navigate_to_organize (callable | None): Callback function to switch the application 
            view to the Organize module after creating a temporary merged PDF.
    """
    
    def __init__(self, navigate_to_organize_cb=None):
        """Initializes the MergeView and sets up drag-and-drop support.
        
        Args:
            navigate_to_organize_cb (callable, optional): Callback to navigate to the 
                organize view. Defaults to None.
        """
        super().__init__()
        self.navigate_to_organize = navigate_to_organize_cb
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        """Constructs the main layout and visual components of the Merge module."""
        layout = QVBoxLayout(self)
        
        title = QLabel("Merge PDFs and Images")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        top_layout = QHBoxLayout()
        
        btn_add = QPushButton("Add Files")
        btn_add.setProperty("class", "SecondaryButton")
        btn_add.clicked.connect(self.select_files)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Original", "A4", "Letter", "Legal"])
        
        top_layout.addWidget(btn_add)
        top_layout.addWidget(QLabel("<b>Page Size:</b>"))
        top_layout.addWidget(self.size_combo)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.list_widget = DraggableListWidget(self)
        layout.addWidget(self.list_widget)

        bottom_layout = QHBoxLayout()
        
        btn_save = QPushButton("Save Merged PDF")
        btn_save.setProperty("class", "SuccessButton")
        btn_save.clicked.connect(self.save_pdf)
        
        btn_organize = QPushButton("Organize PDF")
        btn_organize.clicked.connect(self.send_to_organize)
        
        bottom_layout.addWidget(btn_save)
        bottom_layout.addWidget(btn_organize)
        layout.addLayout(bottom_layout)

    def dragEnterEvent(self, event):
        """Validates dragged items, accepting only supported file types.
        
        Args:
            event (QDragEnterEvent): The drag enter event containing the dragged URLs.
        """
        if event.mimeData().hasUrls():
            valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(valid_extensions) for url in urls):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """Handles the dropped files and adds them to the list widget.
        
        Args:
            event (QDropEvent): The drop event containing the file data.
        """
        valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
        paths = [
            url.toLocalFile() for url in event.mimeData().urls() 
            if url.toLocalFile().lower().endswith(valid_extensions)
        ]
        if paths:
            self.add_files(paths)

    def select_files(self):
        """Opens a file dialog to manually select documents for merging."""
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Files", 
            "", 
            "Documents (*.pdf *.png *.jpg *.jpeg)"
        )
        if files:
            self.add_files(files)

    def load_file(self, file_path):
        """Directly loads file(s) into the list, used by external application modules.
        
        Args:
            file_path (str | list[str]): The absolute path (or list of paths) to the files.
        """
        if isinstance(file_path, str):
            self.add_files([file_path])
        elif isinstance(file_path, list):
            self.add_files(file_path)

    def add_files(self, files: list[str]):
        """Validates, parses, and adds a list of files to the merge queue.
        
        Skips password-protected PDFs and notifies the user.
        
        Args:
            files (list[str]): A list of absolute file paths to be added.
        """
        valid_files = []
        protected_count = 0

        for file_path in files:
            if file_path.lower().endswith('.pdf'):
                try:
                    doc = fitz.open(file_path)
                    if doc.needs_pass:
                        protected_count += 1
                        doc.close()
                        continue
                    doc.close()
                except Exception as e:
                    QMessageBox.critical(
                        self, 
                        "Read Error", 
                        f"Could not read {os.path.basename(file_path)}:\n{str(e)}"
                    )
                    continue
            
            valid_files.append(file_path)

        for file in valid_files:
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, file)
            self.list_widget.addItem(item)
        
        self.refresh_list_widgets()

        if protected_count > 0:
            QMessageBox.warning(
                self, 
                "Protected Files Skipped", 
                f"Skipped <b>{protected_count}</b> password-protected file(s). 🔒<br><br>"
                "Please use the 'Security and Metadata' module to unlock them before merging."
            )

    def remove_item(self, item: QListWidgetItem):
        """Removes a specific item from the list widget.
        
        Args:
            item (QListWidgetItem): The list item to remove.
        """
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)

    def refresh_list_widgets(self):
        """Reconstructs the custom UI widgets for every item in the list widget.
        
        Called after files are added or reordered to maintain the correct visual layout.
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(10, 5, 10, 5)
            
            lbl = QLabel(os.path.basename(file_path))
            
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

    def get_file_list(self) -> list[str]:
        """Retrieves the ordered list of file paths currently in the queue.
        
        Returns:
            list[str]: A list of absolute file paths reflecting the current UI order.
        """
        return [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) 
            for i in range(self.list_widget.count())
        ]

    def save_pdf(self):
        """Merges all files in the queue and saves the resulting PDF to a user-selected location."""
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
        """Merges files to a temporary location and passes the result to the Organize module."""
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