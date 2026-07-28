"""
Application entry point for the HR Digitalization Tool.

This module initializes the PyQt6 application, sets the application-wide 
icon and stylesheet, and instantiates the main window. It also passes 
command-line arguments to handle OS-level "Open with..." file operations.
"""

import os
import sys

from PyQt6.QtGui import QIcon 
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils import get_resource_path


def main():
    """
    Initializes and runs the main PyQt6 application loop.
    
    Sets up the application instance, applies the global stylesheet and icon,
    and initializes the MainWindow, passing in any command-line arguments to 
    support opening files directly from the operating system.
    """
    app = QApplication(sys.argv)
    
    icon_path = get_resource_path("LOGO.png")
    app.setWindowIcon(QIcon(icon_path))
    
    qss_path = get_resource_path(os.path.join("assets", "styles.qss"))
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            
    args = sys.argv
    if len(args) > 1:
        full_path = " ".join(args[1:])
        if os.path.exists(full_path):
            args = [args[0], full_path]
    
    window = MainWindow(args)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()