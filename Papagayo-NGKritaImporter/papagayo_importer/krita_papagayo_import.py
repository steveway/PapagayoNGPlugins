from krita import DockWidget
from PyQt5.QtWidgets import QWidget, QTabWidget, QListView, QVBoxLayout, QLabel

DOCKER_TITLE = 'Papagayo-NG Importer'

class PapagayoImporter(DockWidget):

    def __init__(self):
        super().__init__()
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        self.setWindowTitle(DOCKER_TITLE)
        test_label = QLabel("Test")
        layout.addWidget(test_label)
        self.setWidget(widget)  # Add the widget to the docker.
        

    # notifies when views are added or removed
    # 'pass' means do not do anything
    def canvasChanged(self, canvas):
        pass

