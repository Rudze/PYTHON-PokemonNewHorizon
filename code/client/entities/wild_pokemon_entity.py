"""
WildPokemonEntity — Pokémon sauvage visible sur la map.

Le mouvement et le spawn sont entièrement gérés par le serveur.
Ce composant ne fait que :
  - charger et découper le spritesheet (grille 4×4 identique au joueur)
  - animer la transition d'une tuile à la suivante quand le serveur envoie
    un event pokemon_moved
  - afficher une animation idle (bob) quand le Pokémon est immobile

API publique (appelée par WildPokemonManager) :
    entity.apply_move(x, y, direction)  →  anime le déplacement d'une tuile
"""
from __future__ import annotations

import math
import random

import pygame

from code.client.config import SPRITES_FOLLOWERS_DIR
from code.client.utils.tool import Tool
from code.client.utils.grid_placement import tile_to_center


class WildPokemonEntity(pygame.sprite.Sprite):
    """Pokémon sauvage affiché en overworld, ajouté au pyscroll group."""

    # Durée de l'animation de déplacement (ms) — doit être < AI_TICK côté serveur
    MOVE_DURATION_MS = 220

    # Animation de frames pendant la marche
    FRAME_MS = 120

    # Bob idle
    BOB_AMP  = 2.0
    BOB_RATE = 0.0025    # rad / ms

    def __init__(
        self,
        pokemon_id: int,
        level:      int,
        shiny:      bool,
        position:   pygame.Vector2,
        spawn_zone: str = "",
    ) -> None:
        super().__init__()

        self.pokemon_id = pokemon_id
        self.level      = level
        self.shiny      = shiny
        self.position   = pygame.Vector2(*tile_to_center(int(position.x), int(position.y)))
        self.spawn_zone = spawn_zone

        # ── Spritesheet → frames (grille 4×4, même que le joueur) ─────
        sheet          = self._load_sheet(pokemon_id, shiny)
        self._frames   = self._build_frames(sheet)

        self.image = self._frames["down"][0]
        self.rect  = self.image.get_rect(center=(int(self.position.x), int(self.position.y)))

        hw = max(8, self.rect.width  // 2)
        hh = max(8, self.rect.height // 2)
        self.hitbox = pygame.Rect(0, 0, hw, hh)
        self.hitbox.midbottom = self.rect.midbottom

        # ── État animation ────────────────────────────────────────────
        self._moving       = False
        self._from_pos     = pygame.Vector2(position)
        self._to_pos       = pygame.Vector2(position)
        self._move_dir     = "down"
        self._current_dir  = "down"
        self._move_elapsed = 0.0
        self._frame_idx    = 0
        self._frame_ms     = 0.0

        self._bob_time  = random.uniform(0.0, math.tau)
        self._last_tick = pygame.time.get_ticks()
        self.frozen = False   # True pendant un combat, bloque apply_move

    # ------------------------------------------------------------------
    # API publique — appelée par WildPokemonManager
    # ------------------------------------------------------------------

    def apply_move(self, x: int, y: int, direction: str) -> None:
        if self.frozen:
            return
        self._from_pos     = pygame.Vector2(self.position)
        self._to_pos       = pygame.Vector2(*tile_to_center(x, y))
        self._move_dir     = direction
        self._current_dir  = direction
        self._move_elapsed = 0.0
        self._frame_idx    = 0
        self._frame_ms     = 0.0
        self._moving       = True

    # ------------------------------------------------------------------
    # Boucle principale — appelée par pyscroll group.update()
    # ------------------------------------------------------------------

    def update(self) -> None:
        now   = pygame.time.get_ticks()
        delta = now - self._last_tick
        self._last_tick = now

        if self._moving:
            self._tick_move(delta)
        else:
            self._tick_idle(delta)

    # ------------------------------------------------------------------
    # Animations internes
    # ------------------------------------------------------------------

    def _tick_move(self, delta: float) -> None:
        self._move_elapsed += delta
        t = min(1.0, self._move_elapsed / self.MOVE_DURATION_MS)

        self.position = self._from_pos.lerp(self._to_pos, t)

        # Cycle de frames pendant la marche
        self._frame_ms += delta
        if self._frame_ms >= self.FRAME_MS:
            self._frame_ms  = 0.0
            self._frame_idx = (self._frame_idx + 1) % 4
        self.image = self._frames[self._move_dir][self._frame_idx]

        if t >= 1.0:
            self.position = pygame.Vector2(self._to_pos)
            self._moving  = False
            self._frame_idx = 0

        self.rect.center      = (int(self.position.x), int(self.position.y))
        self.hitbox.midbottom = self.rect.midbottom

    def _tick_idle(self, delta: float) -> None:
        """Animation de bob (flottaison verticale) quand le Pokémon est immobile."""
        self._bob_time += delta * self.BOB_RATE
        bob_y = math.sin(self._bob_time) * self.BOB_AMP

        self.image = self._frames[self._current_dir][0]
        # Le rect visuel bob, la hitbox reste à la position logique (sans le bob)
        self.rect.center      = (int(self.position.x), int(self.position.y + bob_y))
        self.hitbox.midbottom = (int(self.position.x), int(self.position.y) + self.rect.height // 2)

    # ------------------------------------------------------------------
    # Chargement du spritesheet
    # ------------------------------------------------------------------

    @staticmethod
    def _load_sheet(pokemon_id: int, shiny: bool) -> pygame.Surface:
        suffix = "s" if shiny else "n"
        for path in [
            SPRITES_FOLLOWERS_DIR / f"{pokemon_id}-b-{suffix}.png",
            SPRITES_FOLLOWERS_DIR / f"{pokemon_id}-b-{suffix}-.png",
        ]:
            if path.exists():
                try:
                    return pygame.image.load(str(path)).convert_alpha()
                except pygame.error:
                    pass

        placeholder = pygame.Surface((128, 128), pygame.SRCALPHA)
        placeholder.fill((255, 0, 255, 180))
        return placeholder

    @staticmethod
    def _build_frames(sheet: pygame.Surface) -> dict[str, list[pygame.Surface]]:
        """
        Découpe le spritesheet en frames.
        Grille 4×4 identique à Entity.get_all_images() :
          colonnes 0-3 = frames d'animation
          lignes   0-3 = down / left / right / up
        """
        fw = sheet.get_width()  // 4
        fh = sheet.get_height() // 4
        frames: dict[str, list[pygame.Surface]] = {
            "down": [], "left": [], "right": [], "up": []
        }
        for col in range(4):
            for row, key in enumerate(frames):
                frames[key].append(Tool.split_image(sheet, col * fw, row * fh, fw, fh))
        return frames
