"""
SpawnManager — gestion des Pokémon sauvages visibles en overworld.

Responsabilités :
    - Lire les zones de spawn depuis map.spawn_zones
    - Faire apparaître les Pokémon dans les zones proches du joueur
    - Faire disparaître ceux trop loin
    - Gérer les timers de réapparition par zone
    - Détecter les collisions joueur/Pokémon (déclenchement du combat)
    - Se réinitialiser proprement lors d'un changement de map

UTILISATION (dans game.py) :
    # Création (une seule fois dans _setup_game_world)
    self.spawn_manager = SpawnManager(self.map)

    # Mise à jour (dans update_playing_logic, après map.update())
    encounter = self.spawn_manager.update(self.player.position, self.player.hitbox)
    if encounter:
        # TODO: démarrer le combat avec encounter.pokemon_id / encounter.level
        self.spawn_manager.remove(encounter)

    # Nettoyage lors d'un changement de map
    # → Automatique : SpawnManager détecte le changement en comparant
    #   l'identité de map.spawn_zones (liste recréée à chaque switch_map).
"""
from __future__ import annotations

import random

import pygame

from code.shared.config import POKEMON_SPAWNS
from code.client.entities.wild_pokemon_entity import WildPokemonEntity
from code.client.world.spawn_zone import SpawnZone


class SpawnManager:
    """
    Gère le cycle de vie des Pokémon sauvages sur la map courante.

    Les zones de spawn viennent de map.spawn_zones (parsé depuis Tiled).
    L'appartenance d'un Pokémon à une zone est stockée dans entity.zone,
    ce qui évite de maintenir un dict zone → liste dupliqué.
    """

    # Distance joueur ↔ centre de zone (en px dans le repère monde)
    SPAWN_RANGE   = 480    # au-delà : on ne spawne pas
    DESPAWN_RANGE = 640    # au-delà : on despawne
    RESPAWN_DELAY = 15_000 # ms avant de réessayer de spawner une zone vidée

    def __init__(self, map_ref) -> None:
        """
        map_ref : instance de Map (pas le group directement, car il change à chaque map).
        """
        self._map          = map_ref
        self._entities:    list[WildPokemonEntity] = []
        self._zone_timers: dict[str, float]        = {}   # zone_name → ms restants
        self._known_zones  = None                          # détection changement de map

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def update(
        self,
        player_pos:   pygame.Vector2,
        player_hitbox: pygame.Rect,
    ) -> WildPokemonEntity | None:
        """
        À appeler une fois par frame dans update_playing_logic.

        Gère spawn / despawn / timers, puis retourne le premier
        Pokémon sauvage en collision avec le joueur (None sinon).
        """
        self._handle_map_change()

        zones = self._map.spawn_zones
        delta = self._map.screen.deltatime   # ms depuis la frame précédente

        for zone in zones:
            zone_center = pygame.Vector2(zone.rect.center)
            dist = player_pos.distance_to(zone_center)

            # ── Despawn si le joueur est trop loin ────────────────────
            if dist > self.DESPAWN_RANGE:
                self._despawn_zone(zone.name)
                # Pas de timer : la zone se repeuple dès que le joueur revient
                continue

            # ── Timer de réapparition ─────────────────────────────────
            if zone.name in self._zone_timers:
                self._zone_timers[zone.name] -= delta
                if self._zone_timers[zone.name] > 0:
                    continue
                del self._zone_timers[zone.name]

            # ── Spawn si la zone n'est pas pleine ─────────────────────
            if dist < self.SPAWN_RANGE:
                count = sum(1 for e in self._entities if e.zone.name == zone.name)
                while count < zone.max_pokemon:
                    if not self._spawn_one(zone):
                        break
                    count += 1

        # ── Détection d'encounter ─────────────────────────────────────
        for entity in self._entities:
            if entity.hitbox.colliderect(player_hitbox):
                return entity

        return None

    def remove(self, entity: WildPokemonEntity) -> None:
        """
        Retire un Pokémon du monde (après capture ou fuite du joueur).
        Déclenche le timer de réapparition pour sa zone.
        """
        zone_name = entity.zone.name
        try:
            self._entities.remove(entity)
        except ValueError:
            pass
        entity.kill()   # retire de tous les sprite groups

        # Lancer le timer seulement si la zone est maintenant vide
        remaining = sum(1 for e in self._entities if e.zone.name == zone_name)
        if remaining == 0:
            self._zone_timers[zone_name] = self.RESPAWN_DELAY

    def clear(self) -> None:
        """Retire tous les Pokémon sauvages (appel lors d'un menu ou d'un event)."""
        for entity in self._entities:
            entity.kill()
        self._entities.clear()
        self._zone_timers.clear()

    # ------------------------------------------------------------------
    # Détection de changement de map
    # ------------------------------------------------------------------

    def _handle_map_change(self) -> None:
        """
        La liste map.spawn_zones est recréée à chaque switch_map().
        En comparant son identité (is not), on détecte le changement
        sans avoir besoin d'un callback ou d'un signal explicite.
        """
        current_zones = self._map.spawn_zones
        if current_zones is self._known_zones:
            return

        # Nouvelle map : tout vider
        for entity in self._entities:
            entity.kill()
        self._entities.clear()
        self._zone_timers.clear()

        self._known_zones = current_zones

    # ------------------------------------------------------------------
    # Spawn / despawn
    # ------------------------------------------------------------------

    def _spawn_one(self, zone: SpawnZone) -> bool:
        """
        Tente de spawner un Pokémon dans la zone.
        Retourne False si aucune entrée de spawn n'est configurée pour cette zone.
        """
        entry = _pick_entry(zone.name)
        if entry is None:
            return False

        level    = random.randint(entry["min_level"], entry["max_level"])
        shiny    = random.random() < 0.01   # 1 % de chance de shiny
        position = _random_pos_in_zone(zone)

        entity = WildPokemonEntity(
            pokemon_id=entry["pokemon_id"],
            level=level,
            shiny=shiny,
            zone=zone,
            position=position,
        )

        self._map.add_entity(entity)
        self._entities.append(entity)
        return True

    def _despawn_zone(self, zone_name: str) -> None:
        to_remove = [e for e in self._entities if e.zone.name == zone_name]
        for entity in to_remove:
            self._entities.remove(entity)
            entity.kill()


# ------------------------------------------------------------------
# Fonctions utilitaires pures (pas de self → facilement testables)
# ------------------------------------------------------------------

def _pick_entry(zone_name: str) -> dict | None:
    """
    Sélectionne un Pokémon parmi les entrées de POKEMON_SPAWNS[zone_name]
    en tirant au sort selon le champ 'rarity' (sélection pondérée).
    """
    entries = POKEMON_SPAWNS.get(zone_name, [])
    if not entries:
        return None

    total      = sum(e["rarity"] for e in entries)
    roll       = random.uniform(0, total)
    cumulative = 0.0

    for entry in entries:
        cumulative += entry["rarity"]
        if roll <= cumulative:
            return entry

    return entries[-1]   # sécurité : arrondi flottant


def _random_pos_in_zone(zone: SpawnZone) -> pygame.Vector2:
    """Position aléatoire à l'intérieur de la zone (avec marge de 16 px)."""
    margin = 16
    x = random.randint(zone.rect.left  + margin, zone.rect.right  - margin)
    y = random.randint(zone.rect.top   + margin, zone.rect.bottom - margin)
    return pygame.Vector2(x, y)
