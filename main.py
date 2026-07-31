import os
import sys

# Agregamos QTimer a la importación
from PyQt6.QtCore import QEvent, QTimer 
from PyQt6.QtGui import QIcon 
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from ui.main_window import MainWindow
from utils import get_resource_path

SERVER_NAME = "HR_Digitalization_Tool_SingleInstance"


class SingleApplication(QApplication):
    """Application class that enforces a single running instance via QLocalSockets
    and intercepts native OS file opening events safely.

    Attributes:
        main_window (MainWindow): Reference to the primary application window.
        is_running (bool): Flag indicating if another instance is already active.
        socket (QLocalSocket): Socket used to verify active instances.
        server (QLocalServer): Server used to listen for incoming external files.
        _pending_file (str): Temporary storage for file paths received before window init.
    """

    def __init__(self, argv):
        super().__init__(argv)
        self.main_window = None
        self.is_running = False
        self._pending_file = None
        
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

    def event(self, event: QEvent) -> bool:
        """Overrides application event handling to capture native OS file open events.
        Defers UI updates to prevent macOS thread blocking and crashes.
        """
        if event.type() == QEvent.Type.FileOpen:
            file_path = event.file()
            if file_path and os.path.exists(file_path):
                if self.main_window:
                    # CRÍTICO: Diferimos la carga del PDF para no bloquear el evento nativo de macOS
                    QTimer.singleShot(0, lambda: self._safe_open_file(file_path))
                else:
                    self._pending_file = file_path
            return True
        return super().event(event)

    def _safe_open_file(self, file_path: str):
        """Safely loads an external file into the main window after the event loop stabilizes."""
        self.main_window.handle_external_file(file_path)
        self.main_window.showMaximized()
        self.main_window.activateWindow()

    def handle_new_connection(self):
        """Processes incoming connections from secondary instances and triggers file loading."""
        socket = self.server.nextPendingConnection()
        if socket.waitForReadyRead(500):
            file_path = socket.readAll().data().decode('utf-8')
            if self.main_window and os.path.exists(file_path):
                # También diferimos aquí por extrema precaución y estabilidad
                QTimer.singleShot(0, lambda: self._safe_open_file(file_path))


def main():
    """Initializes and runs the main PyQt6 application loop."""
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
    
    if app._pending_file:
        window.handle_external_file(app._pending_file)
        
    window.showMaximized()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()