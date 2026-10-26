"""Small Unicode-safe TextJoinV2 implementation for the supplied workflow."""


class TextJoinV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"delimiter": ("STRING", {"default": ", "})},
            "optional": {
                f"text_{i}": ("STRING", {"forceInput": True}) for i in range(1, 5)
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "text_join"
    CATEGORY = "text"

    def text_join(self, delimiter=", ", text_1="", text_2="", text_3="", text_4=""):
        ignored = {"IGNORE", "NONE", "BYPASS", "(無)", "SKIP"}
        parts = [value.strip() for value in (text_1, text_2, text_3, text_4)
                 if isinstance(value, str) and value.strip() and value.strip().upper() not in ignored]
        return (delimiter.join(parts),)
