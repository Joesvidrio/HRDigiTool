import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon 
from utils import get_resource_path

from ui.views.home_view import HomeView
from ui.views.reader_view import ReaderView
from ui.views.merge_view import MergeView
from ui.views.organize_view import OrganizeView
from ui.views.security_view import SecurityView

class MainWindow(QMainWindow):
    """
    Main application window acting as a container and router for all internal views.
    
    Manages navigation, layout, global UI state (sidebar/topbar visibility), 
    and handles OS-level file opening logic (e.g., "Open with...").
    """
    
    def __init__(self, argv=None):
        """
        Initializes the main window, sets up layouts, and loads initial views.

        Args:
            argv (list[str], optional): Command line arguments passed to the application. 
                Used to detect if a file was passed via the OS to open directly. Defaults to None.
        """
        super().__init__()
        self.setWindowTitle("HR Digitalization Tool") 
        self.resize(1200, 800)
        
        logo_path = get_resource_path("LOGO.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        QApplication.setStyle("Fusion")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.setup_sidebar()

        self.right_container = QWidget()
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)
        
        self.top_bar = QWidget()
        self.top_bar.setObjectName("TopBar") 
        self.top_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E5E7EB;")
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(15, 10, 15, 10)
        
        self.btn_toggle_sidebar = QPushButton("☰ Menu")
        self.btn_toggle_sidebar.setFixedSize(85, 36)
        self.btn_toggle_sidebar.setStyleSheet("""
            QPushButton { background-color: transparent; color: #111827; border: 1px solid #D1D5DB; border-radius: 6px; font-weight: bold; padding: 0; }
            QPushButton:hover { background-color: #F3F4F6; border: 1px solid #9CA3AF; }
        """)
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        
        top_bar_layout.addWidget(self.btn_toggle_sidebar)
        top_bar_layout.addStretch() 
        
        self.right_layout.addWidget(self.top_bar)
        
        self.setup_stacked_widget()
        self.main_layout.addWidget(self.right_container)

        self.sidebar.hide()
        self.top_bar.hide()
        self.stacked_widget.setCurrentIndex(0)

        # Handle "Open with..." context logic
        if argv and len(argv) > 1:
            file_path = argv[1]
            if os.path.isfile(file_path) and file_path.lower().endswith('.pdf'):
                self.switch_view(1) # Index 1 is ReaderView
                self.reader_view.load_file(file_path)

    def setup_sidebar(self):
        """
        Constructs the sidebar navigation menu.
        
        Configures the layout, registers routing buttons, and establishes 
        the connections necessary to switch between the application modules.
        """
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar") 
        self.sidebar.setFixedWidth(240) 
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn_home = QPushButton("Main Menu")
        btn_home.setProperty("class", "HomeButton")
        btn_home.clicked.connect(self.go_home)
        sidebar_layout.addWidget(btn_home)
        sidebar_layout.addSpacing(10)

        self.sidebar_buttons = []
        modules = [
            ("PDF Reader", 1),
            ("Merge PDFs and Images", 2), 
            ("Organize and Edit", 3),    
            ("Security and Metadata", 4) 
        ]

        for text, index in modules:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("class", "SidebarButton") 
            btn.clicked.connect(lambda checked, idx=index: self.switch_view(idx))
            self.sidebar_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        self.main_layout.addWidget(self.sidebar)

    def setup_stacked_widget(self):
        """
        Initializes and configures the QStackedWidget containing all application views.
        
        Instantiates the Home, Reader, Merge, Organize, and Security views, passing 
        the required callbacks for inter-module file routing.
        """
        self.stacked_widget = QStackedWidget()
        
        self.home_view = HomeView(navigate_callback=self.switch_view)
        self.stacked_widget.addWidget(self.home_view) # Index 0
        
        self.reader_view = ReaderView(navigate_callback=self.route_file_to_module)
        self.stacked_widget.addWidget(self.reader_view) # Index 1

        self.merge_view = MergeView(navigate_to_organize_cb=self.route_to_organize)
        self.stacked_widget.addWidget(self.merge_view) # Index 2

        self.organize_view = OrganizeView()
        self.stacked_widget.addWidget(self.organize_view) # Index 3

        self.security_view = SecurityView()
        self.stacked_widget.addWidget(self.security_view) # Index 4

        self.right_layout.addWidget(self.stacked_widget)

    def toggle_sidebar(self):
        """Toggles the visibility of the sidebar navigation menu."""
        if self.sidebar.isVisible():
            self.sidebar.hide()
        else:
            self.sidebar.show()

    def route_to_organize(self, temp_pdf_path):
        """
        Routes a temporarily generated PDF to the Organize view and displays it.

        Args:
            temp_pdf_path (str): The absolute path to the generated temporary PDF file.
        """
        self.organize_view.load_file(temp_pdf_path)
        self.switch_view(3)
        
    def route_file_to_module(self, module_index, file_path):
        """
        Forwards a file from the Reader view to a specific destination module and switches to it.

        Args:
            module_index (int): The index of the target view in the stacked widget.
            file_path (str | list[str]): The path (or list of paths depending on the 
                emitter) to the file being routed.
        """
        self.switch_view(module_index)
        if module_index == 2:
            self.merge_view.add_files_from_paths([file_path])
        elif module_index == 3:
            self.organize_view.load_file(file_path)
        elif module_index == 4:
            self.security_view.load_file(file_path)

    def switch_view(self, index):
        """
        Changes the visible view in the stacked widget and synchronizes the UI state.
        
        Hides the sidebar, reveals the top bar, and ensures the correct sidebar 
        navigation button is shown as actively checked.

        Args:
            index (int): The index of the target view within the stacked widget.
        """
        self.stacked_widget.setCurrentIndex(index)
        self.sidebar.hide()
        self.top_bar.show()
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == (index - 1))

    def go_home(self):
        """
        Returns the application to the main Home view.
        
        Resets the navigation UI by hiding both the top bar and sidebar, 
        and unchecking all active module indicators.
        """
        self.stacked_widget.setCurrentIndex(0)
        self.sidebar.hide()
        self.top_bar.hide() 
        for btn in self.sidebar_buttons:
            btn.setChecked(False)