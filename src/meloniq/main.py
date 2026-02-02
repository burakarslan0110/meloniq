"""
Meloniq uygulaması için ana giriş noktası.
"""

import sys
import os
from pathlib import Path

# PyInstaller frozen desteği
if getattr(sys, 'frozen', False):
    # Derlenmiş EXE olarak çalışıyor
    application_path = Path(sys._MEIPASS)
    os.chdir(application_path)
    
    # Konsolsuz modda "NoneType object has no attribute write" hatası için düzeltme
    class NullWriter:
        def write(self, text): pass
        def flush(self): pass
        def isatty(self): return False
    
    if sys.stdout is None: sys.stdout = NullWriter()
    if sys.stderr is None: sys.stderr = NullWriter()
else:
    # Script olarak çalışıyor
    application_path = Path(__file__).parent

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# PyInstaller uyumluluğu için mutlak içe aktarmalar kullanılıyor
from meloniq.ui.main_window import MainWindow


def main():
    """Ana giriş noktası."""
    # Windows: Görev çubuğu simgesi için AppUserModelID ayarla
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('meloniq.app')
    except:
        pass
    
    # Yüksek DPI desteği
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    
    # Uygulama üst verileri
    app.setApplicationName("Meloniq")
    app.setApplicationDisplayName("Meloniq")
    app.setOrganizationName("MeloniqAudio")
    app.setApplicationVersion("1.0.0")
    
    # Varsayılan yazı tipini ayarla
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    
    # Karanlık tema stil dosyasını uygula
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }
        
        QGroupBox {
            border: 1px solid #555;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        
        QPushButton {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px 12px;
            min-width: 60px;
        }
        
        QPushButton:hover {
            background-color: #4a4a4a;
            border-color: #777;
        }
        
        QPushButton:pressed {
            background-color: #555;
        }
        
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666;
        }
        
        QPushButton:checked {
            background-color: #4a90d9;
            border-color: #5ba0e9;
        }
        
        QSlider::groove:horizontal {
            height: 6px;
            background-color: #444;
            border-radius: 3px;
        }
        
        QSlider::handle:horizontal {
            width: 14px;
            height: 14px;
            margin: -4px 0;
            background-color: #4a90d9;
            border-radius: 7px;
        }
        
        QSlider::handle:horizontal:hover {
            background-color: #5ba0e9;
        }
        
        QTableWidget {
            background-color: #333;
            border: 1px solid #555;
            gridline-color: #444;
        }
        
        QTableWidget::item {
            padding: 4px;
        }
        
        QTableWidget::item:selected {
            background-color: #4a90d9;
        }
        
        QHeaderView::section {
            background-color: #3c3c3c;
            border: 1px solid #555;
            padding: 4px;
        }
        
        QScrollArea {
            border: none;
        }
        
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
            margin: 0;
        }
        
        QScrollBar::handle:vertical {
            background-color: #555;
            border-radius: 4px;
            min-height: 20px;
            margin: 2px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #666;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        
        QProgressDialog {
            background-color: #2b2b2b;
        }
        
        QProgressBar {
            border: 1px solid #555;
            border-radius: 4px;
            text-align: center;
        }
        
        QProgressBar::chunk {
            background-color: #4a90d9;
        }
        
        QMenuBar {
            background-color: #333;
            border-bottom: 1px solid #444;
        }
        
        QMenuBar::item:selected {
            background-color: #4a4a4a;
        }
        
        QMenu {
            background-color: #333;
            border: 1px solid #555;
        }
        
        QMenu::item:selected {
            background-color: #4a90d9;
        }
        
        QStatusBar {
            background-color: #333;
            border-top: 1px solid #444;
        }
        
        QToolBar {
            background-color: #333;
            border-bottom: 1px solid #444;
            spacing: 5px;
            padding: 3px;
        }
        
        QCheckBox {
            spacing: 5px;
        }
        
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        
        QCheckBox::indicator:unchecked {
            border: 1px solid #555;
            background-color: #333;
            border-radius: 3px;
        }
        
        QCheckBox::indicator:checked {
            border: 1px solid #4a90d9;
            background-color: #4a90d9;
            border-radius: 3px;
        }
        
        QLabel {
            color: #e0e0e0;
        }
        
        QSplitter::handle {
            background-color: #444;
        }
        
        QSplitter::handle:horizontal {
            width: 3px;
        }
    """)
    
    # Ana pencereyi oluştur ve göster
    window = MainWindow()
    window.show()
    
    # Komut satırı argümanlarını işle
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.exists():
            window._load_file(path)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
