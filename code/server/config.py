"""
Configuration SERVER — logique de jeu, persistance, base de données.
Aucun import pygame ici — voir code.client.config pour le rendu.
"""
from __future__ import annotations

from code.shared.config import ROOT_DIR, ASSETS_DIR, SAVES_DIR, POKEMON_SPAWNS

# ---------------------------------------------------------------------------
# Base de données SQLite locale
# ---------------------------------------------------------------------------
DB_PATH = ASSETS_DIR / "base.db"

# ---------------------------------------------------------------------------
# Serveur de jeu — paramètres temps-réel
# ---------------------------------------------------------------------------
TICK_RATE      = 20       # mises à jour par seconde
MAX_PLAYERS    = 100      # connexions simultanées max
AOI_RADIUS_PX  = 1280     # rayon d'intérêt (Area Of Interest) en pixels

# ---------------------------------------------------------------------------
# Pokémon sauvages — tables de spawn par zone (source de vérité serveur)
# Ré-exporté depuis shared.config car spawn_manager client en a aussi besoin
# pour le mode solo.  En MMO pur, le serveur l'enverrait via réseau.
# ---------------------------------------------------------------------------
SPAWN_TABLES = POKEMON_SPAWNS   # alias sémantique côté serveur

# ---------------------------------------------------------------------------
# Re-exports pratiques (pour que les fichiers server/* n'importent qu'ici)
# ---------------------------------------------------------------------------
__all__ = [
    "ROOT_DIR", "ASSETS_DIR", "SAVES_DIR", "DB_PATH",
    "TICK_RATE", "MAX_PLAYERS", "AOI_RADIUS_PX",
    "SPAWN_TABLES", "POKEMON_SPAWNS",
]
