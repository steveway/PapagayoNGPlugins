import json
import traceback
from pathlib import Path

from krita import DockWidget, Krita
import os

# Try to import Qt components with fallback for different Krita versions
try:
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFileDialog, 
                                QPushButton, QCheckBox, QMessageBox, QApplication, 
                                QProgressBar, QTextEdit, QHBoxLayout, QFrame)
    from PyQt6.QtCore import Qt, QTimer
except ImportError:
    try:
        from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFileDialog, 
                                    QPushButton, QCheckBox, QMessageBox, QApplication, 
                                    QProgressBar, QTextEdit, QHBoxLayout, QFrame)
        from PyQt5.QtCore import Qt, QTimer
    except ImportError:
        try:
            from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFileDialog, 
                                          QPushButton, QCheckBox, QMessageBox, QApplication, 
                                          QProgressBar, QTextEdit, QHBoxLayout, QFrame)
            from PySide6.QtCore import Qt, QTimer
        except ImportError:
            from PySide2.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFileDialog, 
                                          QPushButton, QCheckBox, QMessageBox, QApplication, 
                                          QProgressBar, QTextEdit, QHBoxLayout, QFrame)
            from PySide2.QtCore import Qt, QTimer

DOCKER_TITLE = 'Papagayo-NG Importer'
VERSION = '1.1.0'

class PapagayoImporter(DockWidget):

    def __init__(self):
        # Helper method for logging to UI and console
        def log(self, message, level="info"):
            prefix = {
                "info": "[INFO]",
                "warning": "[WARNING]",
                "error": "[ERROR]",
                "debug": "[DEBUG]"
            }.get(level, "[INFO]")
            full_msg = f"{prefix} {message}"
            print(full_msg)
            if hasattr(self, "log_output"):
                self.log_output.append(full_msg)
        # Bind the method to the instance
        self.log = log.__get__(self, self.__class__)
        super().__init__()
        self.papagayo_file_path = ""
        self.papagayo_data = None
        self.is_processing = False
        self._application = None
        self._document = None
        self.application = Krita.instance()
        self.document = self.application.activeDocument()
        
        # Load UI from .ui file and wire widgets
        try:
            ui_path = Path(__file__).with_name("papagayo_importer.ui")
            loaded_widget = None
            # Prefer uic if available (PyQt5/6)
            try:
                from PyQt6 import uic as QtUic  # type: ignore
            except Exception:
                try:
                    from PyQt5 import uic as QtUic  # type: ignore
                except Exception:
                    QtUic = None  # type: ignore
            if 'QtUic' in locals() and QtUic is not None:
                loaded_widget = QtUic.loadUi(str(ui_path))
            else:
                # Fallback to QUiLoader (PySide2/6 or PyQt variants)
                QUiLoader = None
                try:
                    from PyQt6.QtUiTools import QUiLoader as _QUiLoader  # type: ignore
                    QUiLoader = _QUiLoader
                except Exception:
                    try:
                        from PyQt5.QtUiTools import QUiLoader as _QUiLoader  # type: ignore
                        QUiLoader = _QUiLoader
                    except Exception:
                        try:
                            from PySide6.QtUiTools import QUiLoader as _QUiLoader  # type: ignore
                            QUiLoader = _QUiLoader
                        except Exception:
                            try:
                                from PySide2.QtUiTools import QUiLoader as _QUiLoader  # type: ignore
                                QUiLoader = _QUiLoader
                            except Exception:
                                QUiLoader = None
                if QUiLoader is not None:
                    # QFile import fallback chain
                    try:
                        from PyQt6.QtCore import QFile  # type: ignore
                    except Exception:
                        try:
                            from PyQt5.QtCore import QFile  # type: ignore
                        except Exception:
                            try:
                                from PySide6.QtCore import QFile  # type: ignore
                            except Exception:
                                from PySide2.QtCore import QFile  # type: ignore
                    qfile = QFile(str(ui_path))
                    if qfile.open(QFile.ReadOnly):
                        loader = QUiLoader()
                        loaded_widget = loader.load(qfile, self)
                        qfile.close()
            if loaded_widget is None:
                # Last-resort minimal UI if loading failed
                loaded_widget = QWidget()
                tmp_layout = QVBoxLayout()
                loaded_widget.setLayout(tmp_layout)
                tmp_layout.addWidget(QLabel("Failed to load UI file."))
            # Set docker widget and title
            self.setWindowTitle(f"{DOCKER_TITLE} v{VERSION}")
            self.setWidget(loaded_widget)
            self.ui = loaded_widget
            
            # Bind child widgets by objectName from .ui
            self.dialog_button = self.ui.findChild(QPushButton, "dialog_button")
            self.file_path_label = self.ui.findChild(QLabel, "file_path_label")
            self.file_info_label = self.ui.findChild(QLabel, "file_info_label")
            self.phoneme_list_text = self.ui.findChild(QTextEdit, "phoneme_list_text")
            self.load_sound_checkbox = self.ui.findChild(QCheckBox, "load_sound_checkbox")
            self.insert_rest_frames = self.ui.findChild(QCheckBox, "insert_rest_frames")
            self.prepare_layers_button = self.ui.findChild(QPushButton, "prepare_layers_button")
            self.fill_timeline_button = self.ui.findChild(QPushButton, "fill_timeline_button")
            self.progress_bar = self.ui.findChild(QProgressBar, "progress_bar")
            self.status_label = self.ui.findChild(QLabel, "status_label")
            self.log_frame = self.ui.findChild(QFrame, "log_frame")
            self.log_output = self.ui.findChild(QTextEdit, "log_output")
            self.show_log_checkbox = self.ui.findChild(QCheckBox, "show_log_checkbox")
            
            # Wire up signals
            if self.dialog_button:
                self.dialog_button.clicked.connect(self.open_file_dialog)
            if self.prepare_layers_button:
                self.prepare_layers_button.clicked.connect(self.prepare_krita_layers)
            if self.fill_timeline_button:
                self.fill_timeline_button.clicked.connect(self.fill_timeline)
            # Log visibility toggle (hidden by default)
            if self.log_frame:
                self.log_frame.setVisible(False)
            if self.show_log_checkbox and self.log_frame:
                self.show_log_checkbox.setChecked(False)
                self.show_log_checkbox.toggled.connect(self.log_frame.setVisible)
        except Exception as e:
            # As a safety net, avoid crashing the docker on UI load errors
            print(f"[UI] Failed to load papagayo_importer.ui: {e}")
            fallback = QWidget()
            fl = QVBoxLayout()
            fallback.setLayout(fl)
            fl.addWidget(QLabel("Papagayo Importer UI failed to load."))
            self.setWindowTitle(f"{DOCKER_TITLE} v{VERSION}")
            self.setWidget(fallback)

    @property
    def application(self):
        return Krita.instance()

    @property
    def document(self):
        return self.application.activeDocument()
    
    @application.setter
    def application(self, app):
        self._application = app
    
    @document.setter
    def document(self, doc):
        self._document = doc

    # notifies when views are added or removed
    # 'pass' means do not do anything
    def canvasChanged(self, canvas):
        pass

    def open_file_dialog(self):
        """Open file dialog and validate the selected Papagayo file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Select Papagayo-NG File', 
            os.path.expanduser("~"),
            "Papagayo-NG Files (*.pg2 *.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            self.set_status("Loading file...", "orange")
            QApplication.processEvents()
            
            # Validate and load the file
            if self.load_papagayo_file(file_path):
                self.papagayo_file_path = file_path
                self.update_ui_after_file_load()
                self.set_status("File loaded successfully", "green")
            else:
                self.set_status("Failed to load file", "red")
                
        except Exception as e:
            self.show_error(f"Error loading file: {str(e)}")
            self.set_status("Error loading file", "red")

    def set_status(self, message, color="black"):
        """Update the status label with a message and color."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")
        QApplication.processEvents()
    
    def show_error(self, message):
        """Show an error message dialog."""
        QMessageBox.critical(self, "Error", message)
        
    def show_info(self, message):
        """Show an information message dialog."""
        QMessageBox.information(self, "Information", message)

    def select_anim_frames(self, frames, layer):
        """Select one or more frames for a specific layer in the Timeline docker.
        Returns True on success, False otherwise.
        """
        try:
            if not frames:
                return False

            # Find timeline view safely
            view = self.find_kis_anim_timeline_view()
            if not view:
                self.log("[Timeline] KisAnimTimelineFramesView not found.", "warning")
                return False

            model = view.model()
            if model is None:
                self.log("[Timeline] Timeline model not available.", "warning")
                return False

            row = self.find_timeline_row_for_layer(layer)
            if row < 0:
                self.log(f"[Timeline] Layer '{layer.name()}' not found in timeline.", "warning")
                return False

            # Lazy import with Qt compatibility
            try:
                from PyQt5.QtCore import QItemSelection, QItemSelectionModel, Qt
            except Exception:
                try:
                    from PySide2.QtCore import QItemSelection, QItemSelectionModel, Qt
                except Exception:
                    try:
                        from PyQt6.QtCore import QItemSelection, QItemSelectionModel, Qt
                    except Exception:
                        from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt

            # Map a given frame number to a model column
            def frame_to_col(frame):
                # Try header mapping first
                try:
                    col_count = model.columnCount()
                except Exception:
                    col_count = 0
                for col in range(col_count):
                    try:
                        hd = model.headerData(col, Qt.Horizontal)
                    except Exception:
                        hd = None
                    if hd is not None and (hd == frame or str(hd) == str(frame)):
                        return col
                # Fallback: assume column 0 is labels, frames start at 1
                return frame + 1

            new_selection = QItemSelection()
            indices = []
            for frame in frames:
                col = frame_to_col(frame)
                index = model.index(row, col)
                if not index.isValid():
                    self.log(f"[Timeline] Invalid index for frame {frame} (row={row}, col={col}).", "warning")
                    continue
                indices.append((frame, index))
                new_selection.select(index, index)

            if not indices:
                return False

            s_model = view.selectionModel()
            # Clear old selection and set new one
            try:
                s_model.clear()
            except Exception:
                pass
            s_model.select(new_selection, QItemSelectionModel.ClearAndSelect)

            # Make last requested frame current, focus and scroll into view
            last_frame, current_index = indices[-1]
            s_model.setCurrentIndex(current_index, QItemSelectionModel.ClearAndSelect)
            try:
                view.scrollTo(current_index)
                view.setFocus()
            except Exception:
                pass

            # Sync document time with selection
            try:
                if self.document:
                    self.document.setCurrentTime(last_frame)
            except Exception:
                pass

            QApplication.processEvents()
            return True
        except Exception as e:
            self.log(f"[Timeline] select_anim_frames failed: {e}", "warning")
            return False


    def find_timeline_docker(self):
        app = self.application
        for docker in app.dockers():
            if docker.objectName() == 'TimelineDocker':
                return docker

    def find_kis_anim_timeline_view(self):
        timeline_docker = self.find_timeline_docker()
        if not timeline_docker:
            return None
        # Ensure QTableView is available regardless of Qt binding
        try:
            from PyQt5.QtWidgets import QTableView
        except Exception:
            try:
                from PySide2.QtWidgets import QTableView
            except Exception:
                try:
                    from PyQt6.QtWidgets import QTableView
                except Exception:
                    from PySide6.QtWidgets import QTableView
        for view in timeline_docker.findChildren(QTableView):
            try:
                if view.metaObject().className() == 'KisAnimTimelineFramesView':
                    return view
            except Exception:
                continue
        return None

    def find_timeline_row_for_layer(self, layer):
        view = self.find_kis_anim_timeline_view()
        if not view:
            return -1
        model = view.model()
        if model is None:
            return -1
        try:
            row_count = model.rowCount()
        except Exception:
            row_count = 0
        for row in range(row_count):
            try:
                if model.data(model.index(row, 0)) == layer.name():
                    return row
            except Exception:
                continue
        return -1
        
    def ensure_keyframe_at_time(self, node, frame_time):
        """Ensure a keyframe exists on 'node' at 'frame_time'.
        Tries add_blank_frame; if it fails (e.g., timeline not selecting this node), falls back to writing a 1x1 transparent pixel.
        """
        try:
            doc = self.document
            if not doc or not node:
                return False
            
            # Activate and set time
            try:
                doc.setActiveNode(node)
            except Exception:
                pass
            doc.setCurrentTime(frame_time)
            
            # Try action first with precise timeline selection
            try:
                self._select_layer_for_timeline(node)
            except Exception:
                pass
            try:
                # Select the specific frame column for this layer in the Timeline docker
                self.select_anim_frames([frame_time], node)
            except Exception:
                pass
            action = self.application.action("add_blank_frame")
            if action:
                action.trigger()

            return node.hasKeyframeAtTime(frame_time)
        except Exception as e:
            self.log(f"ensure_keyframe_at_time failed: {e}", "warning")
            return False

    def _select_layer_for_timeline(self, target_node):
        """Best-effort attempt to make the timeline act on target_node by syncing selection.
        - Deselects all nodes in the Layers docker
        - Selects target_node
        - Sets it active again and processes events
        Note: Depending on Krita version, the Animation docker may keep its own selection.
        """
        doc = self.document
        if not doc or not target_node:
            return False
        root = doc.rootNode()
        # Deselect all nodes recursively
        try:
            stack = [root]
            deselected = 0
            while stack:
                n = stack.pop()
                try:
                    # Not all nodes expose setSelected; guard it
                    if hasattr(n, 'setSelected'):
                        n.setSelected(False)
                        deselected += 1
                except Exception:
                    pass
                for c in getattr(n, 'childNodes', lambda: [])():
                    stack.append(c)
            self.log(f"[Test] Deselect attempt on {deselected} nodes.", "debug")
        except Exception as e:
            self.log(f"[Test] Deselect all nodes failed: {e}", "warning")
        
        # Select and activate the target node
        try:
            if hasattr(target_node, 'setSelected'):
                target_node.setSelected(True)
                self.log(f"[Test] Selected node in Layers docker: {target_node.name()}", "debug")
        except Exception as e:
            self.log(f"[Test] setSelected on target failed: {e}", "warning")
        
        try:
            doc.setActiveNode(target_node)
        except Exception as e:
            self.log(f"[Test] setActiveNode failed: {e}", "warning")
        
        return True
    
    def validate_papagayo_data(self, data):
        """Validate the structure of Papagayo data."""
        required_fields = ["version", "fps"]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Check for voices (pg2 format) or direct voice data (json format)
        if "voices" in data:
            if not isinstance(data["voices"], list) or len(data["voices"]) == 0:
                raise ValueError("No voices found in file")
            
            for voice in data["voices"]:
                if "name" not in voice or "phrases" not in voice:
                    raise ValueError("Invalid voice structure")
                    
                # Check if used_phonemes exists and create if missing
                if "used_phonemes" not in voice:
                    voice["used_phonemes"] = self.extract_used_phonemes_from_voice(voice)
                    self.log(f"Generated used_phonemes for voice '{voice['name']}': {voice['used_phonemes']}")
                    
        elif "name" in data and "phrases" in data:
            # Legacy json format
            if "used_phonemes" not in data:
                data["used_phonemes"] = self.extract_used_phonemes_from_voice(data)
                self.log(f"Generated used_phonemes for legacy format: {data['used_phonemes']}")
        else:
            raise ValueError("Invalid file format: no voices or voice data found")
            
        return True
        
    def extract_used_phonemes_from_voice(self, voice):
        """Extract unique phonemes from a voice's phrases/words/phonemes structure."""
        used_phonemes = set()
        
        try:
            for phrase in voice.get("phrases", []):
                for word in phrase.get("words", []):
                    for phoneme in word.get("phonemes", []):
                        phoneme_text = phoneme.get("text", "")
                        if phoneme_text:
                            used_phonemes.add(phoneme_text)
                            
            # Convert to sorted list for consistent ordering
            return sorted(list(used_phonemes))
            
        except Exception as e:
            self.log(f"Warning: Could not extract phonemes from voice data: {e}")
            return []
        
    def load_papagayo_file(self, file_path):
        """Load and validate a Papagayo file."""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File does not exist: {file_path}")
                
            if not file_path_obj.suffix.lower() in ['.pg2', '.json']:
                raise ValueError("Unsupported file format. Please select a .pg2 or .json file.")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate the data structure
            self.validate_papagayo_data(data)
            self.papagayo_data = data
            return True
            
        except json.JSONDecodeError as e:
            self.show_error(f"Invalid JSON file: {str(e)}")
            return False
        except Exception as e:
            self.show_error(f"Error loading file: {str(e)}")
            return False
    
    def update_ui_after_file_load(self):
        """Update the UI elements after successfully loading a file."""
        if not self.papagayo_data:
            return
            
        # Update file path display
        file_name = Path(self.papagayo_file_path).name
        self.file_path_label.setText(f"📄 {file_name}")
        self.file_path_label.setStyleSheet("color: black; font-weight: bold;")
        
        # Update file info
        fps = self.papagayo_data.get("fps", "Unknown")
        version = self.papagayo_data.get("version", "Unknown")
        duration = self.papagayo_data.get("sound_duration", "Unknown")
        num_voices = len(self.papagayo_data.get("voices", []))
        
        if num_voices == 0 and "name" in self.papagayo_data:
            num_voices = 1  # Legacy format
            
        info_text = f"FPS: {fps} | Duration: {duration} frames | Voices: {num_voices} | Version: {version}"
        self.file_info_label.setText(info_text)
        
        # Update phoneme list
        phoneme_list = self.get_list_of_phonemes()
        self.phoneme_list_text.setPlainText("\n".join(phoneme_list))
        
        # Enable action buttons
        self.prepare_layers_button.setEnabled(True)
        self.fill_timeline_button.setEnabled(True)

    def get_list_of_phonemes(self):
        """Get a formatted list of phonemes from the loaded data."""
        if not self.papagayo_data:
            return []
            
        list_of_used_phonemes = []
        
        try:
            # Handle pg2 format (with voices array)
            if "voices" in self.papagayo_data:
                for voice in self.papagayo_data["voices"]:
                    voice_name = voice.get("name", "Unknown Voice")
                    list_of_used_phonemes.append(f"{voice_name}:")
                    
                    used_phonemes = voice.get("used_phonemes", [])
                    if used_phonemes:
                        # Group phonemes in pairs for better display
                        for i in range(0, len(used_phonemes), 2):
                            if i + 1 < len(used_phonemes):
                                list_of_used_phonemes.append(f"  {used_phonemes[i]}  |  {used_phonemes[i+1]}")
                            else:
                                list_of_used_phonemes.append(f"  {used_phonemes[i]}")
                    else:
                        list_of_used_phonemes.append("  No phonemes found")
            
            # Handle legacy json format
            elif "name" in self.papagayo_data:
                voice_name = self.papagayo_data.get("name", "Unknown Voice")
                list_of_used_phonemes.append(f"{voice_name}:")
                
                used_phonemes = self.papagayo_data.get("used_phonemes", [])
                if used_phonemes:
                    for i in range(0, len(used_phonemes), 2):
                        if i + 1 < len(used_phonemes):
                            list_of_used_phonemes.append(f"  {used_phonemes[i]}  |  {used_phonemes[i+1]}")
                        else:
                            list_of_used_phonemes.append(f"  {used_phonemes[i]}")
                else:
                    list_of_used_phonemes.append("  No phonemes found")
                    
        except Exception as e:
            list_of_used_phonemes = [f"Error reading phonemes: {str(e)}"]
            
        return list_of_used_phonemes

    def prepare_krita_layers(self):
        """Create layer groups and phoneme layers in Krita."""
        if self.is_processing:
            self.show_info("Already processing. Please wait...")
            return
            
        if not self.papagayo_data:
            self.show_error("No Papagayo file loaded. Please select a file first.")
            return
            
        try:
            self.is_processing = True
            self.set_status("Preparing Krita layers...", "orange")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            if not self.document:
                raise RuntimeError("No active Krita document found. Please create or open a document first.")
            
            # Ensure document is properly initialized
            if self.document.width() <= 0 or self.document.height() <= 0:
                raise RuntimeError("Document has invalid dimensions. Please create a proper document first.")
            
            parent_layer = self.document.rootNode()
            if not parent_layer:
                raise RuntimeError("Document root node is invalid. Please create a new document.")
            
            # Set document properties
            fps = self.papagayo_data.get("fps", 24)
            try:
                self.document.setFramesPerSecond(fps)
            except Exception as e:
                self.log(f"Warning: Could not set FPS to {fps}: {e}")
            
            # Handle sound loading
            if self.load_sound_checkbox.isChecked():
                self.load_sound_file(self.document)
            
            # Set up timeline
            num_frames = self.papagayo_data.get("sound_duration", 
                                              self.papagayo_data.get("end_frame", 100))
            self.document.setPlayBackRange(0, num_frames)
            self.document.setCurrentTime(0)
            
            # Get voice list
            voice_list = self.get_voice_list()
            total_steps = sum(len(voice.get("used_phonemes", [])) for voice in voice_list) + len(voice_list)
            current_step = 0
            
            # Process each voice
            for voice in voice_list:
                voice_name = voice.get("name", "Unknown Voice")
                self.set_status(f"Processing voice: {voice_name}", "orange")
                
                # Create or get group layer for voice
                group_layer = self.create_voice_group_layer(parent_layer, voice_name)
                
                # Create phoneme layers
                used_phonemes = voice.get("used_phonemes", [])
                if not used_phonemes:
                    self.log(f"Warning: No phonemes found for voice '{voice_name}'")
                    continue
                    
                for phoneme in used_phonemes:
                    if not phoneme or not isinstance(phoneme, str):
                        self.log(f"Warning: Invalid phoneme data: {phoneme}")
                        continue
                        
                    phoneme_layer = self.create_phoneme_layer(group_layer, phoneme)
                    if phoneme_layer:
                        self.log(f"Created phoneme layer: {phoneme}")
                    else:
                        self.log(f"Failed to create phoneme layer: {phoneme}")
                        
                    current_step += 1
                    progress = int((current_step / total_steps) * 100)
                    self.progress_bar.setValue(progress)
                
                current_step += 1
                progress = int((current_step / total_steps) * 100)
                self.progress_bar.setValue(progress)
            
            self.progress_bar.setValue(100)
            self.set_status("Layers prepared successfully!", "green")
            self.show_info("Krita layers have been prepared successfully!\n\n"
                          "You can now draw on the phoneme layers and then use 'Fill Timeline' "
                          "to apply the timing.")
            
        except Exception as e:
            error_msg = f"Error preparing layers: {str(e)}"
            self.set_status("Error preparing layers", "red")
            self.show_error(error_msg)
            self.log(f"Traceback: {traceback.format_exc()}")
            
        finally:
            self.is_processing = False
            self.progress_bar.setVisible(False)
    
    def load_sound_file(self):
        """Load the sound file referenced in the Papagayo data."""
        try:
            sound_path = self.papagayo_data.get("sound_path", "")
            if not sound_path:
                return
                
            # Handle relative paths
            if not os.path.isabs(sound_path):
                sound_path = os.path.join(os.path.dirname(self.papagayo_file_path), sound_path)
            
            if os.path.exists(sound_path):
                self.document.setAudioTracks([sound_path])
                self.set_status(f"Sound file found: {Path(sound_path).name} (manual import recommended)", "green")
            else:
                self.set_status(f"Sound file not found: {Path(sound_path).name}", "orange")
                
        except Exception as e:
            self.log(f"Warning: Could not load sound file: {e}")
    
    def get_voice_list(self):
        """Get the list of voices from the Papagayo data."""
        if "voices" in self.papagayo_data:
            return self.papagayo_data["voices"]
        elif "name" in self.papagayo_data:
            # Legacy format - wrap in list
            return [self.papagayo_data]
        else:
            return []
    
    def create_voice_group_layer(self, parent_layer, voice_name):
        """Create or get a group layer for a voice."""
        try:
            # Check if layer already exists
            existing_layer = self.document.nodeByName(voice_name)
            if existing_layer:
                return existing_layer
                
            # Create new group layer
            group_layer = self.document.createGroupLayer(voice_name)
            if not group_layer:
                raise RuntimeError(f"Failed to create group layer for voice: {voice_name}")
            
            # Add to parent first
            parent_layer.addChildNode(group_layer, None)
            
            # Refresh document to ensure proper node management
            self.document.refreshProjection()
            
            # Set properties after adding to parent
            try:
                group_layer.setPinnedToTimeline(True)
                group_layer.enableAnimation()
            except Exception as e:
                print(f"Warning: Could not set group layer properties for {voice_name}: {e}")
            
            return group_layer
            
        except Exception as e:
            print(f"Error creating voice group layer '{voice_name}': {e}")
            raise
    
    def create_phoneme_layer(self, group_layer, phoneme):
        """Create a phoneme layer if it doesn't exist."""
        try:
            # Check if phoneme layer already exists
            for child in group_layer.childNodes():
                if child.name() == phoneme:
                    return child
            
            # Create new phoneme layer
            phoneme_layer = self.document.createNode(phoneme, "paintLayer")
            if not phoneme_layer:
                print(f"Warning: Failed to create layer for phoneme: {phoneme}")
                return None
                
            # Add to group layer first, then enable animation
            group_layer.addChildNode(phoneme_layer, None)
            
            # Enable animation after adding to parent
            phoneme_layer.enableAnimation()
            
            # Refresh the document to ensure proper node management
            self.document.refreshProjection()
            
            # Create initial keyframe at frame 0 programmatically
            try:
                self.document.setCurrentTime(0)
                self.document.setActiveNode(phoneme_layer)
                self.application.action("add_blank_frame").trigger()

                
                # Create a blank keyframe by setting the layer as visible
                # This creates a keyframe without using the problematic add_blank_frame action
                phoneme_layer.setVisible(True)
                phoneme_layer.setOpacity(255)  # Full opacity
                
                # Force a paint event to ensure the keyframe is created
                if phoneme_layer.pixelData(0, 0, 1, 1) is None:
                    # If there's no pixel data, we need to paint something
                    # This is a workaround to ensure a keyframe exists
                    phoneme_layer.setPixelData(bytes([0, 0, 0, 0]), 0, 0, 1, 1)
                
                print(f"Created initial keyframe for phoneme layer: {phoneme}")
            except Exception as e:
                print(f"Note: Could not create initial keyframe for {phoneme}: {e}")
            
            return phoneme_layer
            
        except Exception as e:
            print(f"Error creating phoneme layer '{phoneme}': {e}")
            return None

    def fill_timeline(self):
        """Apply phoneme timing to the Krita timeline."""
        if self.is_processing:
            self.show_info("Already processing. Please wait...")
            return
            
        if not self.papagayo_data:
            self.show_error("No Papagayo file loaded. Please select a file first.")
            return
            
        try:
            self.is_processing = True
            self.set_status("Filling timeline with frames...", "orange")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            
            if not self.document:
                raise RuntimeError("No active Krita document found. Please create or open a document first.")
            
            # Get voice list and calculate total operations
            voice_list = self.get_voice_list()
            total_phonemes = 0
            for voice in voice_list:
                for phrase in voice.get("phrases", []):
                    for word in phrase.get("words", []):
                        total_phonemes += len(word.get("phonemes", []))
            
            if total_phonemes == 0:
                raise ValueError("No phonemes found in the file. Please check your Papagayo data.")
            
            current_phoneme = 0
            
            # Process each voice
            for voice in voice_list:
                voice_name = voice.get("name", "Unknown Voice")
                self.set_status(f"Processing timeline for voice: {voice_name}", "orange")
                
                # Get or create the voice group layer
                group_layer = self.document.nodeByName(voice_name)
                if not group_layer:
                    raise RuntimeError(f"Voice group layer '{voice_name}' not found. Please run 'Prepare Krita Layers' first.")
                
                # Create or get combined layer
                combined_layer_name = f"{voice_name}_combined"
                combine_layer = self.get_or_create_combined_layer(group_layer, combined_layer_name)
                self.document.setActiveNode(combine_layer)

                self.log(f"Combined layer has keyframe at frame 0: {combine_layer.hasKeyframeAtTime(0)}")
                self.log(f"Currently active Layer: {self.document.activeNode().name()}")
                self.log(f"Currently Active Layer Animated: {self.document.activeNode().animated()}")
                self.log(f"Currently active Time: {self.document.currentTime()}")
                self.document.setCurrentTime(0)
                self.ensure_keyframe_at_time(combine_layer, 0)
                self.log(f"Combined layer has keyframe at frame 0: {combine_layer.hasKeyframeAtTime(0)}")
                last_pos = 0
                
                # Process phrases
                for phrase in voice.get("phrases", []):
                    # Handle rest frames between phrases
                    if self.insert_rest_frames.isChecked():
                        phrase_start = phrase.get("start_frame", 0)
                        if phrase_start > last_pos + 1:
                            self.insert_rest_frame(group_layer, combine_layer, 
                                                 last_pos + 1)
                    
                    # Process words in phrase
                    for word in phrase.get("words", []):
                        # Handle rest frames between words
                        if self.insert_rest_frames.isChecked():
                            word_start = word.get("start_frame", 0)
                            if word_start > last_pos + 1:
                                self.insert_rest_frame(group_layer, combine_layer, 
                                                     last_pos + 1)
                        
                        # Process phonemes in word
                        for phoneme in word.get("phonemes", []):
                            self.apply_phoneme_to_timeline(group_layer, combine_layer, 
                                                         phoneme)
                            
                            last_pos = phoneme.get("frame", last_pos)
                            current_phoneme += 1
                            progress = int((current_phoneme / total_phonemes) * 100)
                            self.progress_bar.setValue(progress)
            
            self.progress_bar.setValue(100)
            self.set_status("Timeline filled successfully!", "green")
            self.show_info("Timeline has been filled with phoneme frames successfully!\n\n"
                          "Your animation is now ready. You can play the timeline to see the results.")
            
        except Exception as e:
            error_msg = f"Error filling timeline: {str(e)}"
            self.set_status("Error filling timeline", "red")
            self.show_error(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            
        finally:
            self.is_processing = False
            self.progress_bar.setVisible(False)
    
    def get_or_create_combined_layer(self, group_layer, layer_name):
        """Get or create a combined layer for the voice."""
        # Check if combined layer already exists
        if self.document.nodeByName(layer_name):
            return self.document.nodeByName(layer_name)
        else:
            # Create new combined layer
            combine_layer = self.document.createNode(layer_name, "paintLayer")
            # Add to the document tree before enabling animation
            group_layer.addChildNode(combine_layer, None)
            try:
                if not combine_layer.animated():
                    combine_layer.enableAnimation()
            except Exception as e:
                self.log(f"Could not enable animation on new layer '{layer_name}': {e}", "warning")
            return combine_layer

    
    def insert_rest_frame(self, group_layer, combine_layer, frame_time):
        """Insert a rest frame at the specified time."""
        try:
            # Find rest layer
            rest_layer = None
            for child in group_layer.childNodes():
                if child.name() == "rest":
                    rest_layer = child
                    break
            
            if not rest_layer:
                # Create rest layer if it doesn't exist
                rest_layer = document.createNode("rest", "paintLayer")
                group_layer.addChildNode(rest_layer, None)
                self.document.refreshProjection()
                
                rest_layer.enableAnimation()
                self.document.setCurrentTime(0)
                self.document.setActiveNode(rest_layer)
                
                # Create initial keyframe for rest layer programmatically
                try:
                    # Create a blank keyframe by setting the layer as visible
                    rest_layer.setVisible(True)
                    rest_layer.setOpacity(255)  # Full opacity
                    
                    # Force a paint event to ensure the keyframe is created
                    if rest_layer.pixelData(0, 0, 1, 1) is None:
                        # If there's no pixel data, paint a transparent pixel
                        rest_layer.setPixelData(bytes([0, 0, 0, 0]), 0, 0, 1, 1)
                    
                    self.log("Rest layer created with initial keyframe.", "info")
                except Exception as e:
                    self.log(f"Could not create initial keyframe for rest layer: {e}", "warning")
            
            # Copy rest frame to combined layer
            if rest_layer.hasKeyframeAtTime(0):
                self.document.setCurrentTime(0)
                self.document.setActiveNode(rest_layer)
                pixel_data_bounds = rest_layer.bounds()
                pixel_data = rest_layer.pixelData(pixel_data_bounds.x(), pixel_data_bounds.y(), pixel_data_bounds.width(), pixel_data_bounds.height())
                
                self.document.setActiveNode(combine_layer)
                self.document.setCurrentTime(frame_time)
                self.ensure_keyframe_at_time(combine_layer, frame_time)
                combine_layer.setPixelData(pixel_data, pixel_data_bounds.x(), pixel_data_bounds.y(), pixel_data_bounds.width(), pixel_data_bounds.height())
            else:
                self.log(f"Rest layer has no keyframe at frame 0. Skipping rest frame at {frame_time}", "warning")
            
        except Exception as e:
            self.log(f"Could not insert rest frame at {frame_time}: {e}", "error")
    
    def apply_phoneme_to_timeline(self, group_layer, combine_layer, phoneme):
        """Apply a single phoneme to the timeline."""
        try:
            phoneme_text = phoneme.get("text", "")
            phoneme_frame = phoneme.get("frame", 0)
            
            if not phoneme_text:
                return
            
            # Find phoneme layer
            phoneme_layer = None
            for child in group_layer.childNodes():
                if child.name() == phoneme_text:
                    phoneme_layer = child
                    break
            
            if not phoneme_layer:
                self.log(f"Phoneme layer '{phoneme_text}' not found. Skipping.", "warning")
                return
            
            # Copy phoneme frame to combined layer
            self.document.setCurrentTime(0)
            self.document.setActiveNode(phoneme_layer)
            
            # Check if the phoneme layer has a keyframe to copy

            # Copy frame data
            pixel_data_bounds = phoneme_layer.bounds()
            pixel_data = phoneme_layer.pixelData(pixel_data_bounds.x(), pixel_data_bounds.y(), pixel_data_bounds.width(), pixel_data_bounds.height())
            
            self.document.setActiveNode(combine_layer)
            self.document.setCurrentTime(phoneme_frame)
            self.ensure_keyframe_at_time(combine_layer, phoneme_frame)

            combine_layer.setPixelData(pixel_data, pixel_data_bounds.x(), pixel_data_bounds.y(), pixel_data_bounds.width(), pixel_data_bounds.height())

            
        except Exception as e:
            self.log(f"Could not apply phoneme '{phoneme.get('text', 'unknown')}' at frame {phoneme.get('frame', 0)}: {e}", "error")
