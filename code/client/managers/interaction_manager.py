"""
InteractionManager — hub central des interactions joueur → monde (touche E).

Architecture scalable : chaque système enregistre une "source" (callable).
Quand E est pressé, le manager interroge toutes les sources dans l'ordre
d'enregistrement et retourne le premier résultat trouvé.

Ajouter un nouveau type d'interaction :
    1. Créer une source : `def ma_source(tx, ty) -> Interaction | None`
    2. L'enregistrer : `interaction_manager.register(ma_source)`
    3. Gérer le résultat dans game.py : `if result.kind == "mon_type": ...`

Kinds actuels :
    "battle"   — combat contre un Pokémon sauvage
    "dialogue" — dialogue avec un PNJ ou un objet  (à venir)
    "item"     — ramasser un objet au sol          (à venir)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pygame

_TILE = 16
_FACING = {
    "left":  (-1,  0),
    "right": ( 1,  0),
    "up":    ( 0, -1),
    "down":  ( 0,  1),
}


@dataclass
class Interaction:
    """Résultat d'une interaction, transmis à game.py pour traitement."""
    kind: str               # "battle" | "dialogue" | "item" | …
    data: dict = field(default_factory=dict)


# Type d'une source : reçoit (tile_x, tile_y), retourne Interaction ou None
InteractionSource = Callable[[int, int], "Interaction | None"]


class InteractionManager:
    """
    Vérifie la tuile devant le joueur et retourne la première
    interaction disponible parmi les sources enregistrées.
    """

    def __init__(self) -> None:
        self._sources: list[InteractionSource] = []

    def register(self, source: InteractionSource) -> None:
        """Enregistre une nouvelle source d'interactions."""
        self._sources.append(source)

    def check(self, player_pos: pygame.Vector2, direction: str) -> Interaction | None:
        """
        Appelé quand le joueur appuie sur E.
        Retourne la première interaction trouvée sur la tuile face au joueur,
        ou None si rien d'interactable.
        """
        dx, dy = _FACING.get(direction, (0, 0))
        tx = int(player_pos.x) // _TILE + dx
        ty = int(player_pos.y) // _TILE + dy

        for source in self._sources:
            result = source(tx, ty)
            if result is not None:
                return result
        return None
