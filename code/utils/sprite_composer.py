"""
sprite_composer.py — composition du spritesheet du personnage en jeu.

POURQUOI CE FICHIER ?
  En jeu, l'Entity utilise un seul pygame.Surface comme spritesheet (4×4 grid).
  Pour afficher les cheveux (ou tout autre calque) par-dessus le personnage,
  on ne peut pas blit frame par frame à chaque update — c'est trop lent.

  La solution : composer une seule fois un spritesheet fusionné AVANT d'entrer
  dans la boucle de jeu. On superpose les calques sur tout le spritesheet en
  UN SEUL blit, puis on passe cette surface à Entity.reload_spritesheet().

FONCTIONNEMENT :
  base (character_walk.png)     ← dessiné en premier
  + hair overlay (teinté)       ← blit par-dessus tout le spritesheet d'un coup
  + shirt overlay (futur)       ← etc.
  ─────────────────────────────
  → spritesheet composé unique prêt à être animé par Entity

UTILISATION :
    from code.utils.sprite_composer import compose_player_spritesheet

    composed = compose_player_spritesheet({
        "hair":       "feathered",
        "hair_color": [120, 80, 40],
    })
    self.player.reload_spritesheet(composed)
"""
from __future__ import annotations

import pygame

from code.config import SPRITES_CHARACTER_DIR, CUSTOMIZATION_CATALOG
from code.utils.sprite_tint import tint_surface

# Calculated once at import time — same sorted order used by CharacterPreview.OVERLAY_ORDER.
_ORDERED_LAYERS: list[tuple[str, dict]] = sorted(
    CUSTOMIZATION_CATALOG.items(),
    key=lambda item: item[1]["overlay_order"],
)


def compose_player_spritesheet(customization: dict) -> pygame.Surface:
    """
    Compose et retourne un spritesheet topdown complet pour le joueur.

    Le spritesheet résultant est identique à character_walk.png MAIS avec
    tous les calques de customisation blit dessus (cheveux, vêtements…).

    Paramètres
    ----------
    customization : dict reçu depuis l'API
        Exemple : {"hair": "feathered", "hair_color": [120, 80, 40], ...}

    Retour
    ------
    pygame.Surface — spritesheet 4×4 prêt à être passé à Entity.reload_spritesheet()

    Si le fichier de base est introuvable, retourne None.
    """
    # ── 1. Sprite de base ──────────────────────────────────────────────
    base_path = SPRITES_CHARACTER_DIR / "character_walk.png"
    if not base_path.exists():
        print(f"[SpriteComposer] ERREUR : sprite de base introuvable ({base_path})")
        return None

    try:
        composite = pygame.image.load(str(base_path)).convert_alpha()
    except pygame.error as exc:
        print(f"[SpriteComposer] ERREUR chargement base : {exc}")
        return None

    # ── 2. Calques optionnels (dans l'ordre overlay_order du catalogue) ──
    for layer_name, info in _ORDERED_LAYERS:
        variant = customization.get(layer_name, "none")

        if variant == "none":
            continue

        path = info["sprite_dir"] / f"{variant}{info['view_suffix']}"
        try:
            overlay = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            continue

        # Vérifier si CE variant précis est colorable (pas toute la catégorie)
        variant_info = info.get("variants", {}).get(variant, {})
        if variant_info.get("colorable", False):
            raw_color = customization.get(f"{layer_name}_color") or variant_info.get("default_color")
            if raw_color is not None:
                overlay = tint_surface(overlay, tuple(raw_color))

        # Blit sur tout le spritesheet d'un coup (toutes les frames et directions)
        composite.blit(overlay, (0, 0))

        print(f"[SpriteComposer] calque '{layer_name}' ({variant}) appliqué")

    return composite
