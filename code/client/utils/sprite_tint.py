"""
sprite_tint.py — coloration dynamique (tinting) de surfaces PyGame.

PRINCIPE — Multiply Blending (multiplication de couleurs)
=========================================================
On part d'un sprite en niveaux de gris (blanc → gris → noir).
On applique une couleur cible par multiplication pixel à pixel :

    résultat_RGB = pixel_original_RGB × couleur_cible_RGB / 255

Conséquences visuelles :
  pixel blanc  (255, 255, 255) × rouge (255, 0, 0)  → rouge vif   (255, 0,  0 )
  pixel gris   (128, 128, 128) × rouge (255, 0, 0)  → rouge sombre (128, 0,  0 )
  pixel noir   (  0,   0,   0) × rouge (255, 0, 0)  → noir         (  0, 0,  0 ) ← ombre conservée

  → Les ombres et détails restent visibles (noir reste noir).
  → La transparence (canal alpha) n'est JAMAIS modifiée.
  → Les sprites doivent être en niveaux de gris pour un résultat propre.

CACHE
=====
Chaque combinaison (surface originale, couleur) est mise en cache.
Si on demande la même combinaison deux fois, la surface déjà calculée
est retournée instantanément sans re-calcul.

La clé de cache utilise id(surface) : l'identifiant mémoire de l'objet surface.
Cet identifiant est stable tant que l'objet surface reste en vie, ce qui est
le cas ici puisque CharacterPreview garde ses sprites en mémoire dans self._layers.
"""

import pygame

# ---------------------------------------------------------------------------
# Cache interne du module
# ---------------------------------------------------------------------------
# Clé   : (id_surface, couleur_rgb)
#           - id_surface = id() de la surface originale (int, unique par objet)
#           - couleur_rgb = tuple (R, G, B)
# Valeur : surface colorée résultante
# ---------------------------------------------------------------------------
_tint_cache: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}


def tint_surface(
    surface: pygame.Surface,
    color: tuple[int, int, int],
) -> pygame.Surface:
    """
    Retourne une copie de `surface` teintée avec `color` (multiply blend).

    La surface originale n'est PAS modifiée — on travaille toujours sur une copie.
    Le résultat est mis en cache : appeler deux fois avec les mêmes arguments
    retourne le même objet sans recalcul.

    Paramètres
    ----------
    surface : pygame.Surface
        Sprite original. Pour un résultat propre, il doit être en niveaux de gris.
    color   : tuple (R, G, B), valeurs 0–255
        La teinte à appliquer.

    Retour
    ------
    pygame.Surface — nouvelle surface teintée, avec transparence préservée.

    Exemple
    -------
        red_hair   = tint_surface(raw_hair_sprite, (220, 50, 50))
        blue_shirt = tint_surface(raw_shirt_sprite, (30, 100, 220))
    """
    # S'assurer que color est un tuple hashable (pas une liste)
    color = tuple(color)
    cache_key = (id(surface), color)

    if cache_key in _tint_cache:
        return _tint_cache[cache_key]

    # --- Calcul du sprite teinté ---

    # 1. Copier la surface originale (préserve les pixels ET le canal alpha)
    tinted = surface.copy()

    # 2. Créer une surface unie remplie avec la couleur cible
    #    On utilise SRCALPHA pour que pygame n'essaie pas de convertir l'alpha
    color_overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    color_overlay.fill((*color, 255))

    # 3. Blit avec BLEND_RGB_MULT :
    #      dst.RGB = dst.RGB × src.RGB / 255
    #    Le canal alpha de `tinted` (dst) est laissé intact par ce flag.
    tinted.blit(color_overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    _tint_cache[cache_key] = tinted
    return tinted


def clear_tint_cache() -> None:
    """
    Vide entièrement le cache de tinting.

    À appeler si les surfaces originales sont rechargées depuis le disque
    (par exemple après un changement de ressource à chaud), pour éviter
    que le cache serve des données liées à d'anciens objets supprimés.
    """
    _tint_cache.clear()


def get_cache_size() -> int:
    """
    Retourne le nombre d'entrées actuellement stockées en cache.
    Utile pour le débogage ou le monitoring de la mémoire.
    """
    return len(_tint_cache)
