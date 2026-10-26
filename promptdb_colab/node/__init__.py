from .prompt_db import PromptDB
from .cast_compat import Krea2CastPick
from .text_join import TextJoinV2

NODE_CLASS_MAPPINGS = {
    "PromptDB": PromptDB,
    "Krea2CastPick": Krea2CastPick,
    "LayerUtility: TextJoinV2": TextJoinV2,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptDB": "Prompt Database",
    "Krea2CastPick": "Krea2 Cast Pick",
    "LayerUtility: TextJoinV2": "LayerUtility: TextJoinV2",
}
WEB_DIRECTORY = "./web"
