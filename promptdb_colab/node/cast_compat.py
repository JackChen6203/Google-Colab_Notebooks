"""Pick a few named girls from a 複合動漫 cast when a 複合動作 asks for a count.

Action text carries a marker the image model must never see:

- ``[[krea_cast:2]]`` / ``[[krea_cast:3]]`` keep that many girls, chosen at random
- ``[[krea_cast:lead]]`` keeps the full cast and names one girl as ``[[who:1]]``
- ``[[krea_own_expr]]`` means this action already carries its expression. The
  expression category is dropped and the marker is removed before the prompt
  is encoded.

``[[who:1]]`` ``[[who:2]]`` ``[[who:3]]`` become that girl's name plus hair and eyes.
"""

import random
import re

_CAST_MARK = re.compile(r"\[\[krea_cast:(2|3|lead)\]\]\s*")
_WHO_MARK = re.compile(r"\[\[who:([123])\]\]")
_OWN_EXPR = re.compile(r"\[\[krea_own_expr\]\]\s*")

_HEADER_PREFIXES = (
    "girls from",
    "photorealistic photograph",
    "live-action camera photograph",
    "the full female cast",
    "every girl named here",
    "each girl appears once",
    "each face different",
    "each hairstyle different",
    "only these girls",
    "lined up in two columns",
    "left column and right column",
    "a left column",
    "a right column",
)

# Whole tokens only. Short fragments like "pin" would match "pink".
_TRAIT_TOKENS = {
    "hair", "hairs", "eye", "eyes", "face", "faces", "skin", "ear", "ears",
    "ribbon", "ribbons", "glasses", "glass", "hat", "hats", "bow", "bows",
    "bang", "bangs", "tail", "tails", "braid", "braids", "braided", "mole",
    "scar", "lip", "lips", "nose", "eyebrow", "eyebrows", "brow", "brows",
    "expression", "beauty", "ornament", "ornaments", "clip", "clips",
    "headphone", "headphones", "mask", "wing", "wings", "horn", "horns",
    "fang", "fangs", "tooth", "teeth", "fan", "jaw", "chin", "cheek",
    "cheeks", "smile", "gown", "dress", "collar", "sleeve", "skirt",
    "breast", "breasts", "stature", "wrinkle", "wrinkles", "elderly",
    "lipstick", "androgynous", "byakugan", "forehead", "mark", "marks",
    "marking", "markings", "facial", "heterochromia", "eyepatch", "updo",
    "ponytail", "pigtail", "pigtails", "bun", "buns", "ahoge", "fringe",
    "bob", "hime", "curl", "curls", "wavy", "choker", "tiara", "headband",
    "headpiece", "hairpin", "hairband", "earring", "earrings", "cap",
    "fishnet", "piercing", "pupil", "pupils", "gaze", "stare", "looking",
    "timid", "determined", "tomboy", "idol", "gal", "bassist", "sporty",
    "nerd", "cute", "gentle", "mature", "quiet", "mysterious", "cool",
    "stoic", "chuunibyou", "sighing", "ikemen", "female", "spatula",
    "intense", "refined", "elegant", "handsome", "fragile", "intelligent",
    "cunning", "sleepy", "blank", "tired", "serious", "sharp", "soft",
    "cold", "wide", "troubled", "tsurime", "tareme", "goggles", "sunglasses",
    "accessory", "accessories", "tassel", "tips", "mouth", "tongue",
    "kanzashi", "head", "flower", "flowers", "style", "odango", "drill",
    "drills", "streak", "sidelock", "sidelocks", "freckle", "freckles",
    "build", "body", "petite", "slim", "tall", "short", "long", "medium",
    "eyelash", "eyelashes", "jawline", "hairstyle", "hairstyles",
    "hairpin", "hairpins", "parasol", "blindfold", "lolita", "vibe",
    "aura", "powers", "crown", "hood", "beret", "cane", "scarf",
    "necklace", "scrunchie", "pajamas", "eyeliner", "twintails",
    "twintail", "circles", "aesthetic", "cheekbone", "cheekbones",
    "heritage", "dancer", "mohawk", "parts", "ball", "balls", "energy",
    "nadeshiko", "sweatdrop", "sweatdrops", "optional", "bra",
    "courtesan", "consort", "makeup", "helmet", "bandage", "bandages",
    "screw", "rosary", "model", "warrior", "tied", "length", "view",
    "angle", "silhouette", "confident", "dynamic", "distinct", "camera",
    "robotic", "metallic", "glowing", "armor", "coat", "sword", "agent",
    "gladiator", "fashion", "bulky", "suit", "winglike", "holding",
    "fit", "doll", "piercings", "tanned", "toned", "hoodie", "cape",
    "hairclip", "cigarette", "giantess", "authoritative", "cybernetics",
    "feline", "features", "migratory", "tribe", "ojou", "dragon", "girl",
    "look", "smoking",
}

# One-word clauses that describe a person and are not her name.
_SINGLE_STOP = _TRAIT_TOKENS | {
    "beautiful", "fair", "pale", "dark", "blonde", "young", "youthful",
    "innocent", "kind", "shy", "calm", "wild", "cool", "hot", "sexy",
    "pretty", "lovely", "adorable", "fierce", "stoic", "meek", "bold",
    "plain", "simple", "regal", "noble", "royal", "classic", "modern",
}


def _tokens(clause):
    return re.findall(r"[a-z0-9]+", clause.lower())


def _is_header(clause):
    low = clause.lower().strip()
    return any(low.startswith(prefix) for prefix in _HEADER_PREFIXES)


_FUNCTION_WORDS = {
    "on", "in", "of", "with", "and", "or", "the", "but", "over", "under", "for",
}

_LEADING_ADJ = {
    "white", "black", "pink", "blue", "red", "green", "purple", "brown",
    "blonde", "blond", "grey", "gray", "dark", "pale", "fair", "golden",
    "silver", "orange", "yellow", "light", "teal", "gold", "crimson",
    "violet", "amber", "long", "short", "medium", "high", "low", "side",
    "half", "two", "wild", "gothic", "intellectual", "beautiful", "varied",
    "star", "ghostly", "otaku", "regal", "ice", "cross", "panda", "loyal",
    "suggestive", "mechanical", "robotic", "rich", "commanding",
    "decorative", "fashionable", "gyaru", "sophisticated", "foreign",
    "natural", "padded", "boyish", "motherly", "fierce", "very", "small",
    "large", "big", "tiny", "slim", "thick", "thin", "round", "sharp",
    "soft", "cold", "cute", "pretty", "young", "little", "wide", "straight",
    "wavy", "curly", "spiky", "messy", "open", "closed",
}


def _outside_parens(clause):
    return re.sub(r"\([^)]*\)", " ", clause)


def _is_trait(clause):
    # "from fairy tail" is a name even though the series contains "tail".
    # "(league of legends)" contains "of", which is not a trait of the girl.
    low = clause.lower()
    if "(" in clause:
        outside = _tokens(_outside_parens(low))
        return any(tok in _TRAIT_TOKENS for tok in outside)
    if " from " in f" {low}" or low.startswith("from "):
        head = _tokens(low.split(" from ", 1)[0])
        if head and any(tok in _TRAIT_TOKENS or tok in _LEADING_ADJ for tok in head):
            return True
        return False
    toks = _tokens(clause)
    if not toks:
        return True
    if any(tok in _TRAIT_TOKENS for tok in toks):
        return True
    if any(tok in _FUNCTION_WORDS for tok in toks):
        return True
    if toks[0] in _LEADING_ADJ:
        return True
    if len(toks) == 1 and toks[0] in _SINGLE_STOP:
        return True
    return False


def _looks_like_name(clause):
    if _is_header(clause) or _is_trait(clause):
        return False
    low = clause.lower()
    if " from " in f" {low}" or low.startswith("from ") or "(" in clause:
        return True
    toks = _tokens(clause)
    if len(toks) >= 2:
        return True
    return len(toks) == 1 and len(toks[0]) >= 3 and toks[0] not in _SINGLE_STOP


def parse_cast(character_text):
    """Return a list of ``{"name", "traits"}`` from a 複合動漫 string."""
    if not character_text or not isinstance(character_text, str):
        return []
    clauses = [part.strip() for part in character_text.split(",") if part.strip()]
    body = [clause for clause in clauses if not _is_header(clause)]
    counts = {}
    for clause in body:
        if _is_trait(clause):
            continue
        key = clause.lower()
        counts[key] = counts.get(key, 0) + 1
    series_tags = {key for key, count in counts.items() if count >= 3}

    people = []
    current = None

    def start(name):
        nonlocal current
        if current is not None:
            people.append(current)
        current = {"name": name, "traits": []}

    for clause in body:
        low = clause.lower()
        if low.startswith("from ") and current is not None:
            current["name"] = f"{current['name']}, {clause}"
            continue
        if low in series_tags and current is not None:
            current["name"] = f"{current['name']}, {clause}"
            continue
        if _looks_like_name(clause):
            alias = (
                current is not None
                and not current["traits"]
                and ("(" in clause or len(_tokens(clause)) >= 2)
            )
            if alias:
                current["name"] = f"{current['name']}, {clause}"
                continue
            start(clause)
            continue
        if current is None:
            continue
        current["traits"].append(clause)
    if current is not None:
        people.append(current)
    return [person for person in people if person["name"].strip()]


def _short_who(person):
    picked = []
    for trait in person["traits"]:
        low = trait.lower()
        if "hair" in low or "eye" in low:
            picked.append(trait)
        if len(picked) >= 2:
            break
    if picked:
        return f"{person['name']} ({', '.join(picked)})"
    return person["name"]


def _format_person(person):
    if person["traits"]:
        return person["name"] + ", " + ", ".join(person["traits"][:8])
    return person["name"]


def _rebuild_subset(people):
    return "A group portrait of these adults, each person appears once: " + ", ".join(_format_person(person) for person in people)


_FALLBACK = {1: "the first person", 2: "the second person", 3: "the third person"}


def _as_str(value):
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return value if isinstance(value, str) else str(value or "")


def apply_cast(action_text, character_text="", rng=None):
    """Return ``(action_text, character_text, owns_expr)`` with markers resolved.

    ``owns_expr`` is true when the action carries ``[[krea_own_expr]]``. The
    marker is always removed. A composite action uses that flag to ignore the
    expression category.
    """
    action = action_text if isinstance(action_text, str) else ""
    character = character_text if isinstance(character_text, str) else ""
    owns_expr = _OWN_EXPR.search(action) is not None
    action = _OWN_EXPR.sub("", action)
    match = _CAST_MARK.search(action)
    if match is None:
        return action, character, owns_expr

    mode = match.group(1)
    people = parse_cast(character)
    rng = rng or random
    chosen = []
    if people and mode in ("2", "3"):
        count = min(int(mode), len(people))
        chosen = rng.sample(people, count)
        character = _rebuild_subset(chosen)
    elif people and mode == "lead":
        chosen = [rng.choice(people)]
        character = character.replace(
            "lined up in two columns, left column and right column, ", ""
        )
        character = character.replace("lined up in two columns, ", "")

    who = {index: _short_who(person) for index, person in enumerate(chosen, start=1)}

    def replace_who(found):
        index = int(found.group(1))
        return who.get(index, _FALLBACK[index])

    action = _WHO_MARK.sub(replace_who, action)
    action = _CAST_MARK.sub("", action)
    return action, character, owns_expr


class Krea2CastPick:
    """General cast-marker processing; no action-specific prompt injection."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"action_text": ("STRING", {"forceInput": True})},
                "optional": {"character_text": ("STRING", {"forceInput": True}),
                             "expression_text": ("STRING", {"forceInput": True})}}
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("action_text", "character_text", "expression_text")
    FUNCTION = "pick"
    CATEGORY = "text"
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
    def pick(self, action_text, character_text="", expression_text=""):
        action, character, owns_expression = apply_cast(action_text, character_text)
        return action, character, "" if owns_expression else _as_str(expression_text)
