"""
grid_placement.py — convertit une position serveur (coin haut-gauche d'une tuile)
en position pixel centrée pour le sprite.

Pourquoi ce module ?
  Les tuiles font 16×16 px. Le serveur envoie les coordonnées du coin haut-gauche
  de la tuile (x, y). Pour centrer horizontalement un sprite sur cette tuile,
  il faut décaler de TILE_SIZE // 2 = 8 px en X.

  Ce calcul était hardcodé à deux endroits différents :
    - wild_pokemon_manager.py  : int(data["x"]) + 8
    - entity.py                : absent → bug de décalage du joueur

  Ce module centralise la règle pour que joueur, joueurs distants et
  Pokémon sauvages utilisent tous la même logique.

Usage
-----
    from code.client.utils.grid_placement import tile_to_center

    cx, cy = tile_to_center(server_x, server_y)
    self.position = pygame.Vector2(cx, cy)
"""

TILE_SIZE = 16


def tile_to_center(x: int, y: int) -> tuple[int, int]:
    """
    Convertit le coin haut-gauche d'une tuile en position de sprite centrée.

    Le décalage est appliqué uniquement en X : le sprite est centré
    horizontalement sur la tuile mais ancré sur le bord haut en Y
    (la hitbox midbottom gère l'alignement vertical).
    """
    return x + TILE_SIZE // 2, y
