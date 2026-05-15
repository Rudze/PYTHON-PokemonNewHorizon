"""
Configuration PARTAGÉE — chemins de base et données utilisées par client ET serveur.

Règle : n'importer ici que ce qui est réellement nécessaire dans les deux couches.
  - Chemins d'assets communs
  - Données de spawn (client offline + serveur)
  - Chemin des sauvegardes

Pour le rendu / UI → code.client.config
Pour la DB / logique jeu → code.server.config
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Racine du projet
# (code/shared/config/__init__.py → config/ → shared/ → code/ → racine/)
# ---------------------------------------------------------------------------
ROOT_DIR   = Path(__file__).parent.parent.parent.parent
ASSETS_DIR = ROOT_DIR / "assets"

# ---------------------------------------------------------------------------
# Données JSON — modèles Pokémon, moves  (utilisés par shared/models/)
# ---------------------------------------------------------------------------
JSON_DIR = ASSETS_DIR / "json"

# ---------------------------------------------------------------------------
# Sauvegardes — utilisé par server/managers/save_manager.py
# ---------------------------------------------------------------------------
SAVES_DIR = ASSETS_DIR / "saves"

# ---------------------------------------------------------------------------
# Spawn Pokémon — utilisé par server/server.py ET client/managers/spawn_manager.py
# En MMO pur, le serveur enverrait ces données au client via réseau.
# ---------------------------------------------------------------------------
POKEMON_SPAWNS: dict[str, list[dict]] = {
    "route_1": [
        {"pokemon_id": 19, "rarity": 70, "min_level": 10, "max_level": 20},   # Rattata
        {"pokemon_id": 16, "rarity": 30, "min_level": 10, "max_level": 20},   # Roucool
    ],
}
