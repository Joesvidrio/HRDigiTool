import os
import sys

from PyQt6.QtGui import QIcon 
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from ui.main_window import MainWindow
from utils import get_resource_path

SERVER_NAME = "HR_Digitalization_Tool_SingleInstance"

class SingleApplication(QApplication):
    """Application class that enforces a single running instance via QLocalSockets.

    Attributes:
        main_window (MainWindow): Reference to the primary application window.
        is_running (bool): Flag indicating if another instance is already active.
        socket (QLocalSocket): Socket used to verify active instances.
        server (QLocalServer): Server used to listen for incoming external files.
    """

    def __init__(self, argv):
        super().__init__(argv)
        self.main_window = None
        self.is_running = False
        
        self.socket = QLocalSocket()
        self.socket.connectToServer(SERVER_NAME)
        
        if self.socket.waitForConnected(500):
            self.is_running = True
            if len(argv) > 1:
                full_path = " ".join(argv[1:])
                if os.path.exists(full_path):
                    self.socket.write(full_path.encode('utf-8'))
                    self.socket.waitForBytesWritten(500)
        else:
            self.server = QLocalServer()
            QLocalServer.removeServer(SERVER_NAME)
            self.server.listen(SERVER_NAME)
            self.server.newConnection.connect(self.handle_new_connection)

    def handle_new_connection(self):
        """Processes incoming connections from secondary instances and triggers file loading."""
        socket = self.server.nextPendingConnection()
        if socket.waitForReadyRead(500):
            file_path = socket.readAll().data().decode('utf-8')
            if self.main_window and os.path.exists(file_path):
                self.main_window.handle_external_file(file_path)
                self.main_window.showMaximized()
                self.main_window.activateWindow()


def main():
    """Initializes and runs the main PyQt6 application loop.
    
    Sets up the application instance, applying the global stylesheet and icon.
    Validates single-instance execution and initializes the MainWindow.
    """
    app = SingleApplication(sys.argv)
    
    if app.is_running:
        sys.exit(0)
        
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
    app.main_window = window
    window.showMaximized()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()