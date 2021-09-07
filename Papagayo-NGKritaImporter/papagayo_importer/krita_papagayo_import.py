import json

from krita import DockWidget, Krita
import os
from PyQt5.QtWidgets import QWidget, QTabWidget, QListView, QVBoxLayout, QLabel, QFileDialog, QPushButton, QCheckBox

DOCKER_TITLE = 'Papagayo-NG Importer'

class PapagayoImporter(DockWidget):

    def __init__(self):
        super().__init__()
        self.papagayo_file_path = ""
        widget = QWidget()
        self.layout = QVBoxLayout()
        widget.setLayout(self.layout)
        self.setWindowTitle(DOCKER_TITLE)
        self.setWidget(widget)  # Add the widget to the docker.
        dialog_button = QPushButton("Open Papagayo-NG File")
        dialog_button.clicked.connect(self.open_file_dialog)
        self.layout.addWidget(dialog_button)
        self.file_path_label = QLabel("")
        self.layout.addWidget(self.file_path_label)
        self.phoneme_list_label = QLabel("")
        self.layout.addWidget(self.phoneme_list_label)
        self.load_sound_checkbox = QCheckBox("Load Sound from File")
        self.layout.addWidget(self.load_sound_checkbox)
        self.prepare_layers_button = QPushButton("Prepare Krita Layers")
        self.prepare_layers_button.clicked.connect(self.prepare_krita_layers)
        self.layout.addWidget(self.prepare_layers_button)

    # notifies when views are added or removed
    # 'pass' means do not do anything
    def canvasChanged(self, canvas):
        pass

    def open_file_dialog(self):
        self.papagayo_file_path, _ = QFileDialog.getOpenFileName(self, 'Open file', os.path.expanduser("~"),
                                                              "Papagayo-NG Files (*.json *.pg2)")
        if self.papagayo_file_path:
            self.file_path_label.setText(self.papagayo_file_path)
            phoneme_list = self.get_list_of_phonemes(self.papagayo_file_path)
            phoneme_string = "\n".join(ph for ph in phoneme_list)
            self.phoneme_list_label.setText(phoneme_string)

    def get_list_of_phonemes(self, file_path):
        papagayo_file = open(file_path, "r")
        papagayo_json = json.load(papagayo_file)
        list_of_used_phonemes = []
        if file_path.endswith(".pg2"):
            for voice in papagayo_json["voices"]:
                list_of_used_phonemes.append(voice["name"] + ":")
                for phoneme_left, phoneme_right in zip(voice["used_phonemes"][::2], voice["used_phonemes"][1::2]):
                    list_of_used_phonemes.append("{}  |  {}".format(phoneme_left, phoneme_right))
        else:
            list_of_used_phonemes.append(papagayo_json["name"] + ":")
            for phoneme_left, phoneme_right in zip(papagayo_json["used_phonemes"][::2], papagayo_json["used_phonemes"][1::2]):
                list_of_used_phonemes.append("{}  |  {}".format(phoneme_left, phoneme_right))
        papagayo_file.close()
        return list_of_used_phonemes

    def prepare_krita_layers(self):
        file_path = self.papagayo_file_path
        papagayo_file = open(file_path, "r")
        papagayo_json = json.load(papagayo_file)
        FPS = papagayo_json["fps"]
        application = Krita.instance()
        currentDoc = application.activeDocument()
        parent_layer = currentDoc.rootNode()
        if currentDoc:
            currentLayer = currentDoc.activeNode()
            currentDoc.setFramesPerSecond(FPS)
        sound_path = ""
        if self.load_sound_checkbox.isChecked():
            if os.path.isabs(papagayo_json["sound_path"]):
                sound_path = papagayo_json["sound_path"]
            else:
                sound_path = os.path.join(os.path.dirname(file_path), papagayo_json["sound_path"])

        if file_path.endswith(".pg2"):
            NUM_FRAMES = papagayo_json["sound_duration"]
        else:
            NUM_FRAMES = papagayo_json["end_frame"]
        FRAMES_SPACING = 1  # distance between frames
        currentDoc.setPlayBackRange(0, NUM_FRAMES * FRAMES_SPACING)
        currentDoc.setCurrentTime(0)
        voice_list = []
        if file_path.endswith(".pg2"):
            voice_list = papagayo_json["voices"]
        else:
            voice_list.append(papagayo_json)
        for voice in voice_list:
            curr_name = voice["name"]
            if not currentDoc.nodeByName(curr_name):
                group_layer = currentDoc.createGroupLayer(curr_name)
                group_layer.setPinnedToTimeline(True)
                parent_layer.addChildNode(group_layer, None)
            for phoneme in voice["used_phonemes"]:
                group_layer = currentDoc.nodeByName(curr_name)
                phoneme_layer = None
                for child in group_layer.childNodes():
                    if child.name == phoneme:
                        phoneme_layer = child
                if not phoneme_layer:
                    phoneme_layer = currentDoc.createNode(phoneme, "paintLayer")
                    group_layer.addChildNode(phoneme_layer, None)
        papagayo_file.close()

