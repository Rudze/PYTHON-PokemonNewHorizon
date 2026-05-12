"""
WildPokemonManager — gestion côté client des Pokémon sauvages.
"""
from __future__ import annotations

import pygame

from code.entities.wild_pokemon_entity import WildPokemonEntity

_TILE = 16


class WildPokemonManager:
    """Gère les entités WildPokemonEntity à partir d'events serveur."""

    def __init__(self, map_ref) -> None:
        self._map      = map_ref
        self._entities: dict[str, WildPokemonEntity] = {}

    # ------------------------------------------------------------------
    # Events serveur → affichage
    # ------------------------------------------------------------------

    def on_snapshot(self, pokemons: list[dict]) -> None:
        self.clear()
        for data in pokemons:
            self._create(data)

    def on_spawned(self, data: dict) -> None:
        wpid = data.get("wpid")
        if wpid and wpid not in self._entities:
            self._create(data)

    def on_moved(self, data: dict) -> None:
        entity = self._entities.get(data.get("wpid"))
        if entity:
            entity.apply_move(int(data["x"]), int(data["y"]), data["dir"])

    def on_despawned(self, data: dict) -> None:
        entity = self._entities.pop(data.get("wpid"), None)
        if entity:
            entity.kill()

    # ------------------------------------------------------------------
    # Lookup par tuile
    # ------------------------------------------------------------------

    def get_pokemon_at_tile(self, tx: int, ty: int) -> tuple[str, WildPokemonEntity] | None:
        """Retourne (wpid, entity) du Pokémon sur la tuile (tx, ty), ou None."""
        for wpid, entity in self._entities.items():
            if int(entity.position.x) // _TILE == tx and int(entity.position.y) // _TILE == ty:
                return wpid, entity
        return None

    def get_interaction_source(self):
        """
        Retourne une source compatible InteractionManager.
        À enregistrer une fois dans game._setup_game_world().
        """
        from code.managers.interaction_manager import Interaction

        def source(tx: int, ty: int):
            result = self.get_pokemon_at_tile(tx, ty)
            if result is None:
                return None
            wpid, entity = result
            return Interaction("battle", {
                "wpid":       wpid,
                "pokemon_id": entity.pokemon_id,
                "level":      entity.level,
                "shiny":      entity.shiny,
                "zone_name":  entity.spawn_zone,
            })

        return source

    def clear(self) -> None:
        for entity in self._entities.values():
            entity.kill()
        self._entities.clear()

    # ------------------------------------------------------------------
    # Création interne
    # ------------------------------------------------------------------

    def _create(self, data: dict) -> None:
        wpid = data.get("wpid")
        if not wpid:
            return
        entity = WildPokemonEntity(
            pokemon_id=int(data["pokemon_id"]),
            level=int(data["level"]),
            shiny=bool(data.get("shiny", False)),
            position=pygame.Vector2(int(data["x"]), int(data["y"])),
            spawn_zone=data.get("zone_name", ""),
        )
        self._entities[wpid] = entity
        self._map.add_entity(entity)
