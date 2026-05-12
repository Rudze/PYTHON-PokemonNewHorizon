from __future__ import annotations

import pygame

from code.config import CUSTOMIZATION_CATALOG
from code.managers.sound_manager import SoundManager


class CatalogSelector:

    ROW_H   = 38    # hauteur de la ligne (px)
    ROW_W   = 320   # largeur totale (flèches + label)
    BTN_W   = 38    # largeur des boutons flèche

    COLOR_BTN         = (30,  42,  72)
    COLOR_BTN_HOVERED = (50, 130, 230)
    COLOR_LABEL       = (200, 215, 255)
    COLOR_SWATCH_BORDER        = (80,  110, 180)
    COLOR_SWATCH_BORDER_HOVERED = (255, 255, 255)

    def __init__(self, layer_name: str, font: pygame.font.Font) -> None:

        info = CUSTOMIZATION_CATALOG[layer_name]

        self.layer_name = layer_name
        self._label     = info["label"]
        self._variants  = info["variants"]         # dict variant_name → {label, colorable, default_color}
        self._options   = list(self._variants.keys())
        self._font      = font
        self._index     = 0
        self._color: tuple = next(
            (v["default_color"] for v in self._variants.values()
             if v.get("colorable") and v.get("default_color")),
            (200, 200, 200),
        )

        # Rects mis à jour à chaque draw() — utilisés pour la détection de clic
        self.btn_left  = pygame.Rect(0, 0, 0, 0)
        self.btn_right = pygame.Rect(0, 0, 0, 0)
        self.btn_color = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    # Propriétés
    # ------------------------------------------------------------------

    @property
    def variant(self) -> str:
        return self._options[self._index] if self._options else "none"

    @property
    def color(self) -> tuple:
        return self._color

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get_customization(self) -> dict:
        """
        Retourne la contribution de ce sélecteur au dict de customisation.
        Ex: {"hair": "feathered", "hair_color": (120, 80, 40)}
        """
        result = {self.layer_name: self.variant}
        if self._variants.get(self.variant, {}).get("colorable"):
            result[f"{self.layer_name}_color"] = self._color
        return result

    def handle_click(self, pos: tuple, screen) -> bool:
        """
        Traite un clic et retourne True si la customisation a changé.

        Le menu appelant doit alors mettre à jour la preview et jouer un son.
        """
        if not self._options:
            return False

        if self.btn_left.collidepoint(pos):
            self._index = (self._index - 1) % len(self._options)
            return True

        if self.btn_right.collidepoint(pos):
            self._index = (self._index + 1) % len(self._options)
            return True

        if self.btn_color.collidepoint(pos):
            # Import local pour éviter la circularité au niveau du module
            from code.ui.color_picker import ColorPickerMenu
            new_color = ColorPickerMenu(
                screen=screen,
                initial_color=self._color,
                label=f"Couleur : {self._label}",
            ).run()
            if new_color is not None:
                self._color = new_color
                return True

        return False

    def draw(self, display: pygame.Surface, screen_w: int, y: int) -> None:
        """Dessine le sélecteur centré horizontalement à la hauteur y."""
        if not self._options:
            return

        x     = screen_w // 2 - self.ROW_W // 2
        mouse = pygame.mouse.get_pos()

        # ── Flèche gauche
        self.btn_left = pygame.Rect(x, y, self.BTN_W, self.ROW_H)
        hov = self.btn_left.collidepoint(mouse)
        pygame.draw.rect(display, self.COLOR_BTN_HOVERED if hov else self.COLOR_BTN, self.btn_left, border_radius=6)
        _l = self._font.render("<", True, (255, 255, 255))
        display.blit(_l, _l.get_rect(center=self.btn_left.center))

        # ── Flèche droite
        self.btn_right = pygame.Rect(x + self.ROW_W - self.BTN_W, y, self.BTN_W, self.ROW_H)
        hov = self.btn_right.collidepoint(mouse)
        pygame.draw.rect(display, self.COLOR_BTN_HOVERED if hov else self.COLOR_BTN, self.btn_right, border_radius=6)
        _r = self._font.render(">", True, (255, 255, 255))
        display.blit(_r, _r.get_rect(center=self.btn_right.center))

        # ── Libellé  "Catégorie : Variant"
        variant_label = self._variants.get(self.variant, {}).get("label", self.variant)
        text     = f"{self._label} : {variant_label}"
        text_surf = self._font.render(text, True, self.COLOR_LABEL)
        display.blit(text_surf, text_surf.get_rect(center=(x + self.ROW_W // 2, y + self.ROW_H // 2)))

        # ── Carré de couleur (seulement si le variant courant est colorable)
        if self._variants.get(self.variant, {}).get("colorable"):
            swatch_x = self.btn_right.right + 10
            self.btn_color = pygame.Rect(swatch_x, y, self.ROW_H, self.ROW_H)
            pygame.draw.rect(display, self._color, self.btn_color, border_radius=6)
            hov = self.btn_color.collidepoint(mouse)
            border = self.COLOR_SWATCH_BORDER_HOVERED if hov else self.COLOR_SWATCH_BORDER
            pygame.draw.rect(display, border, self.btn_color, width=2, border_radius=6)
        else:
            self.btn_color = pygame.Rect(0, 0, 0, 0)
