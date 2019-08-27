import bpy
import json
import os
from bpy_extras.io_utils import ImportHelper 
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty

class OT_TestOpenFilebrowser(Operator, ImportHelper): 
    bl_idname = "test.open_filebrowser" 
    bl_label = "Load Papagayo-NG Project" 
    
    filter_glob = StringProperty( default='*.pg2;*.json;', options={'HIDDEN'} )
    
    def execute(self, context): 
        """Do something with the selected file(s).""" 
        filename, extension = os.path.splitext(self.filepath)
        create_keyframes(self.filepath)
        return {'FINISHED'}

def create_keyframes(file_path):
    papagayo_file = open(file_path, "r")
    papagayo_json = json.load(papagayo_file)
    FPS = papagayo_json["fps"]
    bpy.context.scene.render.fps = FPS

    NUM_FRAMES = papagayo_json["sound_duration"]
    FRAMES_SPACING = 1  # distance between frames
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = NUM_FRAMES*FRAMES_SPACING

    for voice in papagayo_json["voices"]:
        
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
                    
def register(): 
    bpy.utils.register_class(OT_TestOpenFilebrowser) 

def unregister(): 
    bpy.utils.unregister_class(OT_TestOpenFilebrowser) 
    
if __name__ == "__main__": 
    register() 
    # test call 
    bpy.ops.test.open_filebrowser('INVOKE_DEFAULT')