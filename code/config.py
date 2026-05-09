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
SPRITES_DIR     = ASSETS_DIR / "sprite"
SPRITES_CHARACTER_DIR     = SPRITES_DIR / "character"
SOUNDS_DIR      = ASSETS_DIR / "sounds"
FONTS_DIR       = ASSETS_DIR / "fonts"
JSON_DIR        = ASSETS_DIR / "json"
MAPS_DIR        = ASSETS_DIR / "map"
DIALOGUES_DIR   = ASSETS_DIR / "dialogues"
INTERFACES_DIR  = ASSETS_DIR / "interfaces"
APP_DIR         = ASSETS_DIR / "app"
DB_PATH         = ASSETS_DIR / "base.db"
CREDENTIALS_FILE = SAVES_DIR / "credentials.json"


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
    "background_image": str(ASSETS_DIR / "interfaces" / "backgrounds" / "arceus.jpg"),
    "font": str(ASSETS_DIR / "fonts" / "pokemon.ttf"),
}

# ---------------------------------------------------------------------------
# SFX
# ---------------------------------------------------------------------------
SFX_SETTINGS = {
    "click":        str(SOUNDS_DIR / "HUD" / "select.mp3"),
    "click_volume": 0.5,
}
