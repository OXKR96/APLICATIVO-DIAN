from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from .download_tab import DownloadTab
from .validator_tab import ValidatorTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DIAN Processor')
        self.setMinimumSize(1200, 800)
        
        # Widget principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Barra de navegación
        nav_bar = QWidget()
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setSpacing(10)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        
        # Estilo común para los botones
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                min-height: 40px;
            }
            QPushButton[active="true"] {
                background-color: #0056b3;
                color: white;
                border: none;
            }
            QPushButton[active="false"] {
                background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #dee2e6;
            }
            QPushButton[active="false"]:hover {
                background-color: #e9ecef;
            }
            QPushButton[active="true"]:hover {
                background-color: #004494;
            }
        """
        
        # Botones de navegación
        self.download_btn = QPushButton(" Descargar de DIAN")
        self.download_btn.setIcon(QIcon("icons/download.png"))
        self.download_btn.setStyleSheet(button_style)
        
        self.validator_btn = QPushButton(" Validar Documentos")
        self.validator_btn.setIcon(QIcon("icons/validate.png"))
        self.validator_btn.setStyleSheet(button_style)
        
        nav_layout.addWidget(self.download_btn)
        nav_layout.addWidget(self.validator_btn)
        nav_layout.addStretch()
        
        # Stack de widgets
        self.stack = QStackedWidget()
        self.download_tab = DownloadTab()
        self.validator_tab = ValidatorTab()
        
        self.stack.addWidget(self.download_tab)
        self.stack.addWidget(self.validator_tab)
        
        # Conectar señales
        self.download_btn.clicked.connect(self.show_download)
        self.validator_btn.clicked.connect(self.show_validator)
        
        # Agregar widgets al layout principal
        layout.addWidget(nav_bar)
        layout.addWidget(self.stack)
        
        # Mostrar pestaña de descarga por defecto
        self.show_download()
    
    def show_download(self):
        self.stack.setCurrentWidget(self.download_tab)
        self.download_btn.setProperty('active', True)
        self.validator_btn.setProperty('active', False)
        self.download_btn.style().unpolish(self.download_btn)
        self.download_btn.style().polish(self.download_btn)
        self.validator_btn.style().unpolish(self.validator_btn)
        self.validator_btn.style().polish(self.validator_btn)
    
    def show_validator(self):
        self.stack.setCurrentWidget(self.validator_tab)
        self.download_btn.setProperty('active', False)
        self.validator_btn.setProperty('active', True)
        self.download_btn.style().unpolish(self.download_btn)
        self.download_btn.style().polish(self.download_btn)
        self.validator_btn.style().unpolish(self.validator_btn)
        self.validator_btn.style().polish(self.validator_btn)