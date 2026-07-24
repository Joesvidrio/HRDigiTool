import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QMessageBox, QLineEdit, QFrame)
from PyQt6.QtCore import Qt
from backend.pdf_core import PDFProcessor


class SecurityView(QWidget):
    """
    View module for PDF encryption, decryption, and metadata sanitization.
    
    Provides a user interface for stripping sensitive metadata, applying AES-256
    encryption with a password, and removing password protection from PDFs.
    """
    
    def __init__(self):
        """Initializes the SecurityView and enables drag-and-drop functionality."""
        super().__init__()
        self.current_file = None
        self.setAcceptDrops(True) # Enable Drag & Drop
        self.init_ui()

    # --- DRAG & DROP FUNCTIONS ---
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
        Handles the dropped file and loads it into the view.
        
        Args:
            event (QDropEvent): The drop event containing the file data.
        """
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.load_file(file_path)
    # ----------------------------------

    def init_ui(self):
        """Constructs the layout and visual components of the Security module."""
        layout = QVBoxLayout(self)
        
        title = QLabel("Security and Metadata")
        title.setObjectName("TitleLabel") 
        layout.addWidget(title)

        file_layout = QHBoxLayout()
        
        # --- Primary Button (Blue by default) ---
        btn_select = QPushButton("Select PDF")
        btn_select.clicked.connect(self.select_file)
        
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #6c757d; font-style: italic;")
        
        file_layout.addWidget(btn_select)
        file_layout.addWidget(self.file_label)
        file_layout.addStretch()
        layout.addLayout(file_layout)

        layout.addSpacing(10)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #D1D5DB;")
        layout.addWidget(line)
        layout.addSpacing(10)

        # Section 1: Metadata Cleanup
        layout.addWidget(QLabel("<b>1. Privacy Cleanup</b>"))
        desc_clean = QLabel("Removes author, creator software, dates, and hidden local paths from the file.")
        desc_clean.setStyleSheet("color: #4B5563; margin-bottom: 10px;")
        layout.addWidget(desc_clean)
        
        # --- Success Button (Green for final actions) ---
        btn_clean = QPushButton("Save Clean PDF")
        btn_clean.setProperty("class", "SuccessButton") 
        btn_clean.clicked.connect(self.clean_metadata)
        layout.addWidget(btn_clean)

        layout.addSpacing(20)

        # Section 2: Encryption
        layout.addWidget(QLabel("<b>2. Protect with Password</b>"))
        desc_encrypt = QLabel("Applies AES-256 encryption to prevent unauthorized users from opening the PDF.")
        desc_encrypt.setStyleSheet("color: #4B5563; margin-bottom: 10px;")
        layout.addWidget(desc_encrypt)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter a strong password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)
        
        # --- Success Button (Green) ---
        btn_encrypt = QPushButton("Save Encrypted PDF")
        btn_encrypt.setProperty("class", "SuccessButton")
        btn_encrypt.clicked.connect(self.encrypt_file)
        layout.addWidget(btn_encrypt)

        layout.addSpacing(20)

        # Section 3: Decryption
        layout.addWidget(QLabel("<b>3. Remove Password (Decrypt)</b>"))
        desc_decrypt = QLabel("Enter the current password to save an unprotected copy of the file.")
        desc_decrypt.setStyleSheet("color: #4B5563; margin-bottom: 10px;")
        layout.addWidget(desc_decrypt)

        self.decrypt_password_input = QLineEdit()
        self.decrypt_password_input.setPlaceholderText("Enter the current PDF password")
        self.decrypt_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.decrypt_password_input)

        # --- Success Button (Green) ---
        btn_decrypt = QPushButton("Save Unprotected PDF")
        btn_decrypt.setProperty("class", "SuccessButton") 
        btn_decrypt.clicked.connect(self.decrypt_file)
        layout.addWidget(btn_decrypt)

        layout.addStretch()

    def select_file(self):
        """Opens a file dialog for the user to select a PDF."""
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file:
            self.current_file = file
            self.file_label.setText(os.path.basename(file))

    def add_files(self, files: list[str]):
        """
        Receives a list of file paths forwarded from other application modules (e.g., Reader).
        
        Args:
            files (list[str]): A list of absolute file paths.
        """
        if files and len(files) > 0:
            # Security only operates on one file at a time, so we take the first item in the list
            self.current_file = files[0]
            self.file_label.setText(os.path.basename(self.current_file))

    def load_file(self, file_path: str):
        """
        Directly loads a file path into the view, used by drag-and-drop or direct string passing.
        
        Args:
            file_path (str): The absolute path to the PDF file.
        """
        if file_path and isinstance(file_path, str):
            self.current_file = file_path
            self.file_label.setText(os.path.basename(file_path))

    def clean_metadata(self):
        """Handles the user flow to strip metadata from the currently loaded PDF and save it."""
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please select a PDF first.")
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Clean PDF", "", "PDF Files (*.pdf)")
        if save_path:
            success, msg = PDFProcessor.remove_metadata(self.current_file, save_path)
            self._show_result(success, msg)

    def encrypt_file(self):
        """Passes the user's password input to the backend encryption algorithm and saves the file."""
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please select a PDF first.")
            
        pwd = self.password_input.text()
        if not pwd:
            return QMessageBox.warning(self, "Warning", "You must enter a password to encrypt the file.")

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Encrypted PDF", "", "PDF Files (*.pdf)")
        if save_path:
            success, msg = PDFProcessor.encrypt_pdf(self.current_file, save_path, pwd)
            self._show_result(success, msg)
            if success:
                self.password_input.clear()

    def decrypt_file(self):
        """Attempts to remove AES protection using the provided password and saves the unprotected file."""
        if not self.current_file:
            return QMessageBox.warning(self, "Warning", "Please select a PDF first.")
            
        pwd = self.decrypt_password_input.text()
        if not pwd:
            return QMessageBox.warning(self, "Warning", "You must enter the current password to decrypt it.")

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Unprotected PDF", "", "PDF Files (*.pdf)")
        if save_path:
            success, msg = PDFProcessor.decrypt_pdf(self.current_file, save_path, pwd)
            self._show_result(success, msg)
            if success:
                self.decrypt_password_input.clear()

    def _show_result(self, success: bool, msg: str):
        """
        Helper UI method to standardize success and error popup messages.
        
        Args:
            success (bool): Indicates if the operation was successful.
            msg (str): The message returned from the backend process to display.
        """
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", msg)