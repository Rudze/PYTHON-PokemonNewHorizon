"""
Configuration CLIENT — tout ce qui concerne le rendu, l'UI, l'audio, les inputs.
Aucune logique de jeu ici — voir code.server.config pour le gameplay.
"""
from __future__ import annotations

# Chemins de base importés depuis shared
from code.shared.config import ROOT_DIR, ASSETS_DIR, JSON_DIR

# ---------------------------------------------------------------------------
# Dossiers assets — rendu
# ---------------------------------------------------------------------------
SPRITES_DIR           = ASSETS_DIR / "sprite"
SPRITES_BATTLE_DIR    = SPRITES_DIR / "battlesprites"
SPRITES_CHARACTER_DIR = SPRITES_DIR / "character"
SPRITES_PLAYER_DIR    = SPRITES_DIR / "player"
SPRITES_SKIN_DIR      = SPRITES_DIR / "skin"
SPRITES_SHOES_DIR     = SPRITES_DIR / "shoes"
SPRITES_LEGS_DIR      = SPRITES_DIR / "legs"
SPRITES_SHIRTS_DIR    = SPRITES_DIR / "shirts"
SPRITES_GLOVES_DIR    = SPRITES_DIR / "gloves"
SPRITES_FACE_DIR      = SPRITES_DIR / "face"
SPRITES_EYES_DIR      = SPRITES_DIR / "eyes"
SPRITES_HAIRS_DIR     = SPRITES_DIR / "hairs"
SPRITES_BACK_DIR      = SPRITES_DIR / "back"
SPRITES_FOLLOWERS_DIR = SPRITES_DIR / "followersprites"

FONTS_DIR      = ASSETS_DIR / "fonts"
SOUNDS_DIR     = ASSETS_DIR / "sounds"
MAPS_DIR       = ASSETS_DIR / "map"
DIALOGUES_DIR  = ASSETS_DIR / "dialogues"
INTERFACES_DIR = ASSETS_DIR / "interfaces"
APP_DIR        = ASSETS_DIR / "app"

BATTLEBACKS_DIR       = ASSETS_DIR / "Battlebacks"
BATTLE_INTERFACES_DIR = INTERFACES_DIR / "battle"
MOTISMART_DIR         = INTERFACES_DIR / "motismart"

# Fichier credentials local (auto-login)
CREDENTIALS_FILE = ASSETS_DIR / "saves" / "credentials.json"

# ---------------------------------------------------------------------------
# Fenêtre pygame
# ---------------------------------------------------------------------------
GAME_TITLE = "Pokemon NewHorizon"
GAME_ICONE = str(ASSETS_DIR / "app" / "logo_earth.png")

# ---------------------------------------------------------------------------
# Réseau — URL du serveur d'authentification
# ---------------------------------------------------------------------------
AUTH_API_URL = "http://37.59.114.12:8000"

# ---------------------------------------------------------------------------
# UI combat
# ---------------------------------------------------------------------------
BATTLE_ZONE: dict[str, dict] = {
    "default": {"background": BATTLEBACKS_DIR / "battlebgField.png"},
    "route_1": {"background": BATTLEBACKS_DIR / "battlebgField.png"},
}

BATTLE_UI: dict[str, object] = {
    "enemy_box":       BATTLE_INTERFACES_DIR / "battleBox.png",
    "player_box":      BATTLE_INTERFACES_DIR / "battlePlayerBoxS.png",
    "command":         BATTLE_INTERFACES_DIR / "battleCommand.png",
    "fight_buttons":   BATTLE_INTERFACES_DIR / "battleFightButtons.png",
    "command_buttons": BATTLE_INTERFACES_DIR / "battleCommandButtons.png",
    "overlay_message": INTERFACES_DIR / "overlay_message.png",
}

# Ligne 0-indexée dans battleFightButtons.png par type de move
MOVE_TYPE_ROW: dict[str, int] = {
    "normal": 0, "fighting": 1, "flying": 2, "poison": 3, "ground": 4,
    "rock": 5, "bug": 6, "ghost": 7, "steel": 8, "unknown": 9,
    "fire": 10, "water": 11, "grass": 12, "electric": 13, "psychic": 14,
    "ice": 15, "dragon": 16, "dark": 17, "fairy": 18,
}

# ---------------------------------------------------------------------------
# UI téléphone (Motismart)
# ---------------------------------------------------------------------------
MOTISMART_UI: dict[str, object] = {
    "bg": MOTISMART_DIR / "bg.png",
}

# ---------------------------------------------------------------------------
# Écrans de chargement / connexion
# ---------------------------------------------------------------------------
SPLASH_SETTINGS = {
    "image_path":    str(ASSETS_DIR / "interfaces" / "backgrounds" / "splash_screen.png"),
    "duration_ms":   4000,
    "fade_duration": 2000,
}

LOGIN_MENU_SETTINGS = {
    "music":            str(SOUNDS_DIR / "Lake.mp3"),
    "volume":           0.01,
    "background_image": str(ASSETS_DIR / "interfaces" / "backgrounds" / "arceus-cynthia.jpg"),
    "font":             str(ASSETS_DIR / "fonts" / "pokemon.ttf"),
}

# ---------------------------------------------------------------------------
# Personnalisation du personnage
# ---------------------------------------------------------------------------
CUSTOMIZATION_SETTINGS = {
    "gender_icon": str(ASSETS_DIR / "icones" / "gender_icons_large.png"),
}

CUSTOMIZATION_CATALOG: dict[str, dict] = {
    "skin":   {"label": "Carnation",         "sprite_dir": SPRITES_SKIN_DIR,    "view_suffix": "_topdown.png", "overlay_order": 0, "variants": {}},
    "shoes":  {"label": "Chaussures",         "sprite_dir": SPRITES_SHOES_DIR,   "view_suffix": "_topdown.png", "overlay_order": 1, "variants": {}},
    "legs":   {"label": "Pantalon",           "sprite_dir": SPRITES_LEGS_DIR,    "view_suffix": "_topdown.png", "overlay_order": 2, "variants": {}},
    "shirt":  {"label": "Haut",               "sprite_dir": SPRITES_SHIRTS_DIR,  "view_suffix": "_topdown.png", "overlay_order": 3, "variants": {}},
    "gloves": {"label": "Gants",              "sprite_dir": SPRITES_GLOVES_DIR,  "view_suffix": "_topdown.png", "overlay_order": 4, "variants": {}},
    "face":   {"label": "Accessoire visage",  "sprite_dir": SPRITES_FACE_DIR,    "view_suffix": "_topdown.png", "overlay_order": 5, "variants": {}},
    "eyes":   {"label": "Yeux",               "sprite_dir": SPRITES_EYES_DIR,    "view_suffix": "_topdown.png", "overlay_order": 6, "variants": {}},
    "hair": {
        "label": "Coiffure", "sprite_dir": SPRITES_HAIRS_DIR, "view_suffix": "_topdown.png", "overlay_order": 7,
        "variants": {
            "none":     {"label": "Chauve",    "colorable": False, "default_color": None},
            "feathered": {"label": "Feathered", "colorable": True,  "default_color": (120, 80, 40)},
        },
    },
    "back":   {"label": "Sac / Cape",         "sprite_dir": SPRITES_BACK_DIR,    "view_suffix": "_topdown.png", "overlay_order": 8, "variants": {}},
}

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
SFX_SETTINGS = {
    "click":        str(SOUNDS_DIR / "HUD" / "select.mp3"),
    "click_volume": 0.5,
}
