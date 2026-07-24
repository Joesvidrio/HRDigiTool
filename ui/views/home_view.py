import sys
import os

# Ensure the project root directory is added to sys.path.
# This guarantees that absolute imports (like 'utils') resolve correctly 
# regardless of where the entry point script is executed from.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from utils import get_resource_path


class HomeView(QWidget):
    """
    Initial dashboard view presented to the user upon application launch.
    
    Displays a welcoming interface with a responsive grid of interactive cards, 
    allowing users to navigate seamlessly to the different PDF manipulation modules.
    """

    def __init__(self, navigate_callback=None):
        """
        Initializes the HomeView widget.
        
        Args:
            navigate_callback (callable, optional): Function to trigger when a module 
                                                    card is clicked. It must accept an 
                                                    integer (the target view index).
        """
        super().__init__()
        self.navigate_callback = navigate_callback
        self.init_ui()

    def init_ui(self):
        """
        Constructs and arranges the user interface components, including the 
        branding logo, typography headers, and the dynamic navigation grid.
        """
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        # --- Branding / Main Logo ---
        logo_label = QLabel()
        logo_path = get_resource_path("LOGO.png")
        if os.path.exists(logo_path):
            # Scale smoothly to prevent pixelation on high-DPI displays
            pixmap = QPixmap(logo_path).scaled(
                180, 180, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        # --- Headers & Typography ---
        title = QLabel("HR Digitalization Tool")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #111827; margin-top: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Select a tool to start your workflow")
        subtitle.setStyleSheet("font-size: 16px; color: #4B5563; margin-bottom: 30px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # --- Module Navigation Grid ---
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Configuration matrix for available tools (Title, Description, View Index)
        tools = [
            ("📖 PDF Reader", "View PDFs and easily send them to other tools.", 1),
            ("🔗 Merge PDFs & Images", "Combine multiple files into a single document.", 2),
            ("📑 Organize & Edit", "Reorder, rotate pages, apply watermarks, and compress.", 3),
            ("🔒 Security & Metadata", "Encrypt with password, decrypt, or clean hidden data.", 4)
        ]

        # Populate the grid dynamically (2 columns layout)
        row, col = 0, 0
        for title_text, desc_text, index in tools:
            card_btn = self.create_card(title_text, desc_text, index)
            grid_layout.addWidget(card_btn, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

        layout.addLayout(grid_layout)
        
        # Add stretching space at the bottom to push content upwards
        layout.addStretch()

    def create_card(self, title, description, index):
        """
        Generates an interactive QPushButton formatted as a modern UI card.
        
        This method nests labels inside a QPushButton to create a rich card layout 
        while maintaining the native click functionality and hover states of a button.
        
        Args:
            title (str): The primary header text displayed on the card.
            description (str): Secondary explanatory text below the title.
            index (int): The target view index mapped to the navigation callback.
            
        Returns:
            QPushButton: The fully constructed and styled card widget.
        """
        btn = QPushButton()
        btn.setFixedSize(380, 120)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Apply specific stylesheet directly to prevent global styles from overriding the card look
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                text-align: left;
            }
            QPushButton:hover {
                border: 2px solid #E32322; /* Brand highlight color on hover */
                background-color: #ffffff;
            }
        """)

        # Inner layout for the button to hold the text labels
        card_layout = QVBoxLayout(btn)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #111827; border: none; background: transparent;")
        # Prevent the label from capturing mouse clicks, allowing the underlying button to trigger
        lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        lbl_desc = QLabel(description)
        lbl_desc.setStyleSheet("font-size: 14px; color: #4B5563; border: none; background: transparent;")
        lbl_desc.setWordWrap(True)
        # Prevent the label from capturing mouse clicks
        lbl_desc.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)

        # Wire up the navigation logic if a callback was provided
        if self.navigate_callback:
            # Using lambda with default argument idx=index to capture current value in the loop
            btn.clicked.connect(lambda checked, idx=index: self.navigate_callback(idx))
            
        return btn