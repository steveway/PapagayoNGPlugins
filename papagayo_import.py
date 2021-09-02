bl_info = {
    "name": "Papagayo-NG 2D Importer",
    "author": "Stefan Murawski", 
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "3D window > Tool Shelf",
    "description": "Create GreasePencil Object with Layers and Keyframes from Papagayo-NG .pg2 files.",
    "warning": "",
    "wiki_url": ""
    "Scripts/Import-Export/Papagayo 2D Importer",
    "tracker_url": "",
    "category": "Import-Export"}

import bpy
import json
import os
from bpy_extras.io_utils import ImportHelper 
from bpy.types import Operator, PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty, PointerProperty

class OT_TestOpenFilebrowser(Operator, ImportHelper): 
    bl_idname = "test.open_filebrowser" 
    bl_label = "Load Papagayo-NG Project" 
    bl_description = 'Load .pg2 or .json files. (Only .pg2 currently)'
    
    filter_glob : StringProperty( default='*.pg2;*.json;', options={'HIDDEN'} )
    
    def execute(self, context): 
        """Do something with the selected file(s).""" 
        filename, extension = os.path.splitext(self.filepath)
        scene = bpy.types.Scene
        scene.pg_path = self.filepath
        return {'FINISHED'}


class BTN_OP_create_grease_objects(Operator):
    bl_idname = 'pg.create_objects'
    bl_label = 'Start Processing'
    bl_description = 'Create Grease Pencil Objects from Papagayo-NG files'

    def execute(self, context):

        scn = context.scene
        obj = context.active_object
        scene = bpy.types.Scene
        create_grease_objects(scene.pg_path)
        scene.pg_objects_created = True
        return {'FINISHED'}
    
class BTN_OP_apply_to_timeline(Operator):
    bl_idname = 'pg.apply_timeline'
    bl_label = 'Start Processing'
    bl_description = 'Create Grease Pencil Objects from Papagayo-NG files'

    def execute(self, context):

        scn = context.scene
        obj = context.active_object
        scene = bpy.types.Scene
        fill_timeline(scene.pg_path)

        return {'FINISHED'}
   
class MyProperties(PropertyGroup):

    rest_frames: BoolProperty(
        name="Enable Rest Frames",
        description="If enabled inserts rest frames into empty frames after words and phrases.",
        default = False
        )
                        
class PapagayoNGImporterUI(bpy.types.Panel):
    bl_id_name = "pg_main_menu"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_label = "Papagayo-NG 2D Importer"
    bl_category = 'Animation'

    def draw(self, context):

        obj = bpy.context.active_object
        scn = bpy.context.scene
        scene = bpy.types.Scene
        layout = self.layout
        col = layout.column()
        mytool = context.scene.my_tool
        col.prop(mytool, "rest_frames")
        col.operator('test.open_filebrowser', text="Select Papagayo-NG Project File")
        col.separator()
        if scene.pg_path:
            col.label(text=os.path.split(scene.pg_path)[1], icon="FILE_FOLDER")
        else:
            col.label(text="No File loaded", icon="FILE_FOLDER")
        col.separator()
        if scene.pg_path:
            col.label(text="Used Phonemes:")
            for phoneme in get_list_of_phonemes(scene.pg_path):
                col.label(text=phoneme)                
            col.operator("pg.create_objects", text="Create Grease Pencil Objects")
        if scene.pg_objects_created:
            col.separator()
            col.label(text="Add the Grease Pencil Objects to your scene.")
            col.label(text="Simply click on the keyframes to edit them.", icon="KEYFRAME")
            col.label(text="Add sound by choosing Add and the Speaker.")
            col.label(text="Draw all Phonemes and press the next button.")
            col.separator()
            col.operator("pg.apply_timeline", text="Apply to Timeline")

def get_list_of_phonemes(file_path):
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
            
def create_grease_objects(file_path):
    papagayo_file = open(file_path, "r")
    papagayo_json = json.load(papagayo_file)
    FPS = papagayo_json["fps"]
    bpy.context.scene.render.fps = FPS
    scene = bpy.types.Scene
    if file_path.endswith(".pg2"):
        sound_path = ""
        if os.path.isabs(papagayo_json["sound_path"]): 
            sound_path = papagayo_json["sound_path"]
        else:
            sound_path = os.path.join(os.path.dirname(file_path), papagayo_json["sound_path"])
        if not bpy.data.sounds.items():
            bpy.ops.sound.open_mono(filepath=sound_path)
        scene.pg_sound_data = bpy.data.sounds[0]
        prev_area_type = bpy.context.area.type
        bpy.context.area.type = 'SEQUENCE_EDITOR'
        bpy.ops.sequencer.sound_strip_add(filepath=sound_path, frame_start=0, channel=1)
        bpy.context.area.type = prev_area_type
        # Audio loads fine, can be used with manually added speaker, but this speaker stays silent...
        """
        if not bpy.data.speakers.items():
            bpy.ops.object.speaker_add()

        speaker = bpy.data.speakers[0]
        speaker.sound = scene.pg_sound_data
        """
        NUM_FRAMES = papagayo_json["sound_duration"]
    else:
        NUM_FRAMES = papagayo_json["end_frame"]
    FRAMES_SPACING = 1  # distance between frames
    bpy.context.scene.frame_start = -1
    bpy.context.scene.frame_end = NUM_FRAMES*FRAMES_SPACING
    bpy.context.scene.frame_current = -1
    if file_path.endswith(".pg2"):
        for voice in papagayo_json["voices"]:
            curr_name = voice["name"]
            if curr_name not in bpy.data.grease_pencils:
                bpy.data.grease_pencils.new(curr_name)
            for phoneme in voice["used_phonemes"]:
                if phoneme not in bpy.data.grease_pencils[curr_name].layers:
                    bpy.data.grease_pencils[curr_name].layers.new(phoneme)
                pho_layer = bpy.data.grease_pencils[curr_name].layers[phoneme]
                try:
                    frame = pho_layer.frames[-1]
                except IndexError:
                    pho_layer.frames.new(-1)
    else:
        curr_name = papagayo_json["name"]
        if curr_name not in bpy.data.grease_pencils:
            bpy.data.grease_pencils.new(curr_name)
        for phoneme in papagayo_json["used_phonemes"]:
            if phoneme not in bpy.data.grease_pencils[curr_name].layers:
                bpy.data.grease_pencils[curr_name].layers.new(phoneme)
            pho_layer = bpy.data.grease_pencils[curr_name].layers[phoneme]
            try:
                frame = pho_layer.frames[-1]
            except IndexError:
                pho_layer.frames.new(-1)
    papagayo_file.close()


def fill_timeline(file_path):
    papagayo_file = open(file_path, "r")
    papagayo_json = json.load(papagayo_file)
    last_pos = 0
    voice_list = []
    if file_path.endswith(".pg2"):
        for voice in papagayo_json["voices"]:
            voice_list.append(voice)
    else:
        voice_list.append(papagayo_json)
    
    for voice in voice_list:
        curr_name = voice["name"]
        if curr_name + "combined" in bpy.data.grease_pencils[curr_name].layers: # TODO: Show a warning and allow to abort
            bpy.data.grease_pencils[curr_name].layers[curr_name + "combined"].clear()
        else:
            bpy.data.grease_pencils[curr_name].layers.new(curr_name + "combined")
        for phrase in voice["phrases"]:
            if bpy.context.scene.my_tool.rest_frames:
                if phrase["start_frame"] > last_pos + 1:
                    base_frame = bpy.data.grease_pencils[curr_name].layers["rest"].frames[-1]
                    new_frame = bpy.data.grease_pencils[curr_name].layers[curr_name + "combined"].frames.copy(base_frame)
                    new_frame.frame_number = last_pos + 1
            for word in phrase["words"]:
                if bpy.context.scene.my_tool.rest_frames:
                    if word["start_frame"] > last_pos + 1:
                        base_frame = bpy.data.grease_pencils[curr_name].layers["rest"].frames[-1]
                        new_frame = bpy.data.grease_pencils[curr_name].layers[curr_name + "combined"].frames.copy(base_frame)
                        new_frame.frame_number = last_pos + 1
                for phoneme in word["phonemes"]:
                    base_frame = bpy.data.grease_pencils[curr_name].layers[phoneme["text"]].frames[-1]
                    new_frame = bpy.data.grease_pencils[curr_name].layers[curr_name + "combined"].frames.copy(base_frame)
                    new_frame.frame_number = phoneme["frame"]
                    last_pos = phoneme["frame"]
            
        """
        if bpy.context.scene.my_tool.rest_frames:
            for frame in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end):
                exists = False
                try:
                    t_frame = bpy.data.grease_pencils[curr_name].layers[curr_name + "combined"].frames[frame]
                    exists = True
                except IndexError:
                    exists = False
                if exists:
                    base_frame = bpy.data.grease_pencils[curr_name].layers["rest"].frames[-1]
                    new_frame = bpy.data.grease_pencils[curr_name].layers[curr_name + "combined"].frames.copy(base_frame)
                    new_frame.frame_number = frame
        """
    papagayo_file.close()
    

def create_keyframes(file_path):
    papagayo_file = open(file_path, "r")
    papagayo_json = json.load(papagayo_file)
    FPS = papagayo_json["fps"]
    bpy.context.scene.render.fps = FPS
    if file_path.endswith(".pg2"):
        NUM_FRAMES = papagayo_json["sound_duration"]
    else: NUM_FRAMES = papagayo_json["end_frame"]
    FRAMES_SPACING = 1  # distance between frames
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = NUM_FRAMES*FRAMES_SPACING
    voice_list = []
    if file_path.endswith(".pg2"):
        for voice in papagayo_json["voices"]:
            voice_list.append(voice)
    else:
        voice_list.append(papagayo_json)

    for voice in voice_list:
        
        curr_name = voice["name"]
        if curr_name not in bpy.data.grease_pencils:
            bpy.data.grease_pencils.new(curr_name)
        for phrase in voice["phrases"]:
            for word in phrase["words"]:
                for phoneme in word["phonemes"]:
                    if phoneme["text"] not in bpy.data.grease_pencils[curr_name].layers:
                        bpy.data.grease_pencils[curr_name].layers.new(phoneme["text"])
                    try:
                        pho_frame = bpy.data.grease_pencils[curr_name].layers[phoneme["text"]].frames.new(phoneme["frame"])
                    except RuntimeError:
                        pass
        
classes = (PapagayoNGImporterUI, BTN_OP_create_grease_objects, BTN_OP_apply_to_timeline, OT_TestOpenFilebrowser, MyProperties)
                    
def register():
    scene = bpy.types.Scene
    scene.pg_path = ""
    scene.pg_objects_created = False
    for cls in classes:
        bpy.utils.register_class(cls)    
    bpy.types.Scene.my_tool = PointerProperty(type=MyProperties)

def unregister(): 
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.my_tool
    
if __name__ == "__main__": 
    register()