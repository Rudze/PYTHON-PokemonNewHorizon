from __future__ import annotations
from dataclasses import dataclass
import pygame


@dataclass
class SpawnZone:
    """
    Zone de spawn de Pokémon sauvages, lue depuis Tiled.

    Correspond à un objet rectangulaire dans le layer 'pokemonspawn'
    avec les custom properties :
        spawn_zone   (string) : identifiant de la zone, ex: "route_1"
        max_pokemon  (int)    : nombre maximum de Pokémon simultanés
    """
    name:        str           # spawn_zone property (ex: "route_1")
    rect:        pygame.Rect   # bounding box de la zone dans le monde
    max_pokemon: int           # plafond d'entités simultanées
