"""
config.py — source unique de vérité pour les chemins et réglages du jeu.

Tous les modules importent leurs chemins depuis ici.
Aucun chemin relatif (../) ne doit apparaître ailleurs dans le code.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Racine du projet  (code/config.py → code/ → racine/)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Dossiers assets
# ---------------------------------------------------------------------------
ASSETS_DIR      = ROOT_DIR / "assets"
SAVES_DIR       = ASSETS_DIR / "saves"
SPRITES_DIR         = ASSETS_DIR / "sprite"
SPRITES_BATTLE_DIR  = SPRITES_DIR / "battlesprites"   # {id}-{front|back}-{n|s}.gif
SOUNDS_DIR      = ASSETS_DIR / "sounds"
FONTS_DIR       = ASSETS_DIR / "fonts"
JSON_DIR        = ASSETS_DIR / "json"
MAPS_DIR        = ASSETS_DIR / "map"
DIALOGUES_DIR   = ASSETS_DIR / "dialogues"
INTERFACES_DIR  = ASSETS_DIR / "interfaces"
APP_DIR         = ASSETS_DIR / "app"
DB_PATH         = ASSETS_DIR / "base.db"
CREDENTIALS_FILE = SAVES_DIR / "credentials.json"
SPRITES_CHARACTER_DIR = SPRITES_DIR / "character"
SPRITES_PLAYER_DIR    = SPRITES_DIR / "player"
SPRITES_SKIN_DIR   = SPRITES_DIR / "skin"
SPRITES_SHOES_DIR  = SPRITES_DIR / "shoes"
SPRITES_LEGS_DIR   = SPRITES_DIR / "legs"
SPRITES_SHIRTS_DIR = SPRITES_DIR / "shirts"
SPRITES_GLOVES_DIR = SPRITES_DIR / "gloves"
SPRITES_FACE_DIR   = SPRITES_DIR / "face"
SPRITES_EYES_DIR   = SPRITES_DIR / "eyes"
SPRITES_HAIRS_DIR       = SPRITES_DIR / "hairs"
SPRITES_BACK_DIR        = SPRITES_DIR / "back"
SPRITES_FOLLOWERS_DIR   = SPRITES_DIR / "followersprites"
BATTLEBACKS_DIR       = ASSETS_DIR / "Battlebacks"
BATTLE_INTERFACES_DIR = INTERFACES_DIR / "battle"

# ---------------------------------------------------------------------------
# Zones de combat — clé "background" uniquement, les bases ont été supprimées
# ---------------------------------------------------------------------------
BATTLE_ZONE: dict[str, dict] = {
    "default": {"background": BATTLEBACKS_DIR / "battlebgField.png"},
    "route_1": {"background": BATTLEBACKS_DIR / "battlebgField.png"},
}

# ---------------------------------------------------------------------------
# Images d'interface du combat
# ---------------------------------------------------------------------------
BATTLE_UI: dict[str, object] = {
    "enemy_box":        BATTLE_INTERFACES_DIR / "battleBox.png",
    "player_box":       BATTLE_INTERFACES_DIR / "battlePlayerBoxS.png",
    "command":          BATTLE_INTERFACES_DIR / "battleCommand.png",
    "fight_buttons":    BATTLE_INTERFACES_DIR / "battleFightButtons.png",
    "command_buttons":  BATTLE_INTERFACES_DIR / "battleCommandButtons.png",
    "overlay_message":  INTERFACES_DIR / "overlay_message.png",
}

# ---------------------------------------------------------------------------
# Ligne (0-indexée) dans battleFightButtons.png pour chaque type de move.
# Layout : largeur 243 px × hauteur 44 px par cellule.
#          colonne gauche (src_x=0)   = bouton non sélectionné
#          colonne droite (src_x=243) = bouton sélectionné
# ---------------------------------------------------------------------------
MOVE_TYPE_ROW: dict[str, int] = {
    "normal":   0,   # ligne  1
    "fighting": 1,   # ligne  2
    "flying":   2,   # ligne  3
    "poison":   3,   # ligne  4
    "ground":   4,   # ligne  5
    "rock":     5,   # ligne  6
    "bug":      6,   # ligne  7
    "ghost":    7,   # ligne  8
    "steel":    8,   # ligne  9
    "unknown":  9,   # ligne 10
    "fire":     10,  # ligne 11
    "water":    11,  # ligne 12
    "grass":    12,  # ligne 13
    "electric": 13,  # ligne 14
    "psychic":  14,  # ligne 15
    "ice":      15,  # ligne 16
    "dragon":   16,  # ligne 17
    "dark":     17,  # ligne 18
    "fairy":    18,  # ligne 19
}


# ---------------------------------------------------------------------------
# Game config
# ---------------------------------------------------------------------------
GAME_TITLE = "Pokemon NewHorizon"
GAME_ICONE = str(ASSETS_DIR / "app" /"logo_earth.png")

# ---------------------------------------------------------------------------
# Réseau
# ---------------------------------------------------------------------------
AUTH_API_URL = "http://37.59.114.12:8000"

# ---------------------------------------------------------------------------
# Splash screen
# ---------------------------------------------------------------------------
SPLASH_SETTINGS = {
    "image_path":    str(ASSETS_DIR / "interfaces" / "backgrounds" / "splash_screen.png"),
    "duration_ms":   4000,
    "fade_duration": 2000,
}

# ---------------------------------------------------------------------------
# Menu de connexion
# ---------------------------------------------------------------------------
LOGIN_MENU_SETTINGS = {
    "music":  str(SOUNDS_DIR / "Lake.mp3"),
    "volume": 0.01,
    "background_image": str(ASSETS_DIR / "interfaces" / "backgrounds" / "dracaufeu.jpg"),
    "font": str(ASSETS_DIR / "fonts" / "pokemon.ttf"),
}

CUSTOMIZATION_CATALOG: dict[str, dict] = {

    "skin": {
        "label":         "Carnation",
        "sprite_dir":    SPRITES_SKIN_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 0,
        "variants":      {},   # à remplir quand les assets seront créés
    },

    "shoes": {
        "label":         "Chaussures",
        "sprite_dir":    SPRITES_SHOES_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 1,
        "variants":      {},
    },

    "legs": {
        "label":         "Pantalon",
        "sprite_dir":    SPRITES_LEGS_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 2,
        "variants":      {},
    },

    "shirt": {
        "label":         "Haut",
        "sprite_dir":    SPRITES_SHIRTS_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 3,
        "variants":      {},
    },

    "gloves": {
        "label":         "Gants",
        "sprite_dir":    SPRITES_GLOVES_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 4,
        "variants":      {},
    },

    "face": {
        "label":         "Accessoire visage",
        "sprite_dir":    SPRITES_FACE_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 5,
        "variants":      {},
    },

    "eyes": {
        "label":         "Yeux",
        "sprite_dir":    SPRITES_EYES_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 6,
        "variants":      {},
    },

    "hair": {
        "label":         "Coiffure",
        "sprite_dir":    SPRITES_HAIRS_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 7,
        "variants": {
            # variant_name : ce qui est chargé depuis sprite_dir/<variant_name>_topdown.png
            #
            # colorable=True  → sprite en niveaux de gris, le joueur choisit la couleur
            # colorable=False → couleurs intégrées dans le PNG, pas de recoloration
            "none": {
                "label":         "Chauve",
                "colorable":     False,
                "default_color": None,
            },
            "feathered": {
                "label":         "Feathered",
                "colorable":     True,
                "default_color": (120, 80, 40),   # brun naturel par défaut
            },
            # Exemple de coiffure avec couleur fixe dans le PNG :
            # "magic_flame": {
            #     "label":         "Flamme magique",
            #     "colorable":     False,
            #     "default_color": None,
            # },
        },
    },

    "back": {
        "label":         "Sac / Cape",
        "sprite_dir":    SPRITES_BACK_DIR,
        "view_suffix":   "_topdown.png",
        "overlay_order": 8,
        "variants":      {},
    },

    # "bicycle" est exclu du catalogue de preview : affiché uniquement en jeu
}

# Gender

CUSTOMIZATION_SETTINGS = {
    "gender_icon": str(ASSETS_DIR / "icones" / "gender_icons_large.png"),
}

POKEMON_SPAWNS: dict[str, list[dict]] = {
    "route_1": [
        {"pokemon_id": 19, "rarity": 70, "min_level": 10, "max_level": 20},   # Rattata
        {"pokemon_id": 16, "rarity": 30, "min_level": 10, "max_level": 20},   # Roucool
    ],
    # "foret_0": [
    #     {"pokemon_id": 10, "rarity": 50, "min_level": 4, "max_level": 6},  # Chenipan
    #     {"pokemon_id": 13, "rarity": 50, "min_level": 4, "max_level": 6},  # Aspicot
    # ],
}

# ---------------------------------------------------------------------------
# SFX
# ---------------------------------------------------------------------------
SFX_SETTINGS = {
    "click":        str(SOUNDS_DIR / "HUD" / "select.mp3"),
    "click_volume": 0.5,
}
