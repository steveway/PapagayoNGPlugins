import json
import time

from krita import DockWidget, Krita
import os
from PyQt5.QtWidgets import QWidget, QTabWidget, QListView, QVBoxLayout, QLabel, QFileDialog, QPushButton, QCheckBox, QMessageBox, QApplication

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
        self.insert_rest_frames = QCheckBox("Insert Rest Frames")
        self.layout.addWidget(self.insert_rest_frames)
        self.fill_timeline_button = QPushButton("Fill Timeline with Frames")
        self.fill_timeline_button.clicked.connect(self.fill_timeline)
        self.layout.addWidget(self.fill_timeline_button)

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
        current_document = application.activeDocument()
        parent_layer = current_document.rootNode()
        if current_document:
            currentLayer = current_document.activeNode()
            current_document.setFramesPerSecond(FPS)
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
        current_document.setPlayBackRange(0, NUM_FRAMES * FRAMES_SPACING)
        current_document.setCurrentTime(0)
        voice_list = []
        if file_path.endswith(".pg2"):
            voice_list = papagayo_json["voices"]
        else:
            voice_list.append(papagayo_json)
        for voice in voice_list:
            curr_name = voice["name"]
            if not current_document.nodeByName(curr_name):
                group_layer = current_document.createGroupLayer(curr_name)
                group_layer.setPinnedToTimeline(True)
                group_layer.enableAnimation()
                parent_layer.addChildNode(group_layer, None)
            group_layer = current_document.nodeByName(curr_name)
            for phoneme in voice["used_phonemes"]:
                phoneme_layer = None
                for child in group_layer.childNodes():
                    if child.name() == phoneme:
                        phoneme_layer = child
                if not phoneme_layer:
                    phoneme_layer = current_document.createNode(phoneme, "paintLayer")
                    phoneme_layer.enableAnimation()
                    group_layer.addChildNode(phoneme_layer, None)
                    #current_document.setCurrentTime(0)
                    current_document.setActiveNode(phoneme_layer)
                    #application.action("add_duplicate_frame").trigger()
                    #current_document.setCurrentTime(0)
            current_document.setCurrentTime(0)
            for child in group_layer.childNodes():
                time.sleep(0.1)
                QApplication.processEvents()  # Otherwise this can crash Krita...
                if child.name() in voice["used_phonemes"]:
                    current_document.setActiveNode(child)
                    if not child.hasKeyframeAtTime(0):
                        application.action('add_blank_frame').trigger()
        papagayo_file.close()

    def fill_timeline(self):
        file_path = self.papagayo_file_path
        papagayo_file = open(file_path, "r")
        papagayo_json = json.load(papagayo_file)
        application = Krita.instance()
        current_document = application.activeDocument()
        parent_layer = current_document.rootNode()
        last_pos = 0
        voice_list = []
        if file_path.endswith(".pg2"):
            for voice in papagayo_json["voices"]:
                voice_list.append(voice)
        else:
            voice_list.append(papagayo_json)

        for voice in voice_list:
            curr_name = voice["name"]
            group_layer = current_document.nodeByName(curr_name)
            combine_layer = None
            for child in group_layer.childNodes():
                if child.name() == curr_name + "_combined":
                    combine_layer = child
            if not combine_layer:
                combine_layer = current_document.createNode(curr_name + "_combined", "paintLayer")
                combine_layer.enableAnimation()
                group_layer.addChildNode(combine_layer, None)
            for phrase in voice["phrases"]:
                if self.insert_rest_frames.isChecked():
                    if phrase["start_frame"] > last_pos + 1:
                        QApplication.processEvents()  # Otherwise this can crash Krita...
                        current_document.setCurrentTime(0)
                        current_group = current_document.nodeByName(curr_name)
                        current_rest = None
                        for child in current_group.childNodes():
                            if child.name() == "rest":
                                current_rest = child
                        current_document.setActiveNode(current_rest)
                        #application.action("add_duplicate_frame").trigger()
                        application.action("copy_frames").trigger()
                        destination_layer = current_document.nodeByName(curr_name + "_combined")
                        current_document.setActiveNode(destination_layer)
                        current_document.setCurrentTime(last_pos + 1)
                        application.action("paste_frames").trigger()
                for word in phrase["words"]:
                    if self.insert_rest_frames.isChecked():
                        if word["start_frame"] > last_pos + 1:
                            QApplication.processEvents()  # Otherwise this can crash Krita...
                            current_document.setCurrentTime(0)
                            current_group = current_document.nodeByName(curr_name)
                            current_rest = None
                            for child in current_group.childNodes():
                                if child.name() == "rest":
                                    current_rest = child
                            current_document.setActiveNode(current_rest)
                            #application.action("add_duplicate_frame").trigger()
                            application.action("copy_frames").trigger()
                            destination_layer = current_document.nodeByName(curr_name + "_combined")
                            current_document.setActiveNode(destination_layer)
                            current_document.setCurrentTime(last_pos + 1)
                            #application.action('add_blank_frame').trigger()
                            application.action("paste_frames").trigger()
                    for phoneme in word["phonemes"]:
                        QApplication.processEvents()  # Otherwise this can crash Krita...
                        current_document.setCurrentTime(0)
                        current_group = current_document.nodeByName(curr_name)
                        phoneme_layer = None
                        for child in current_group.childNodes():
                            if child.name() == phoneme["text"]:
                                phoneme_layer = child
                        current_document.setActiveNode(phoneme_layer)
                        #application.action("add_duplicate_frame").trigger()
                        application.action("copy_frames").trigger()
                        destination_layer = current_document.nodeByName(curr_name + "_combined")
                        current_document.setActiveNode(destination_layer)
                        current_document.setCurrentTime(phoneme["frame"])
                        #application.action('add_blank_frame').trigger()
                        application.action("paste_frames").trigger()
        papagayo_file.close()
