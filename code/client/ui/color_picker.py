"""
ColorPickerMenu — sélecteur de couleur réutilisable.

Affiche un panneau de couleurs prédéfinies par-dessus le menu parent,
qui reste visible en arrière-plan (gelé + assombri).

UTILISATION DEPUIS N'IMPORTE QUEL MENU :
    from code.client.ui.color_picker import ColorPickerMenu

    new_color = ColorPickerMenu(
        screen=self.screen,
        initial_color=(120, 80, 40),
        label="Couleur : Coiffure",
    ).run()

    if new_color is not None:
        # L'utilisateur a confirmé → new_color = tuple (R, G, B)
        self._hair_color = new_color
    # Si new_color est None → l'utilisateur a annulé, on garde l'ancienne couleur

PALETTE :
    32 couleurs prédéfinies en 4 lignes × 8 colonnes :
      - Ligne 0 : Naturels (noir → blanc)
      - Ligne 1 : Rouges et roux
      - Ligne 2 : Roses et violets
      - Ligne 3 : Bleus et verts
"""
from __future__ import annotations

import pygame

from code.client.config import LOGIN_MENU_SETTINGS

# ---------------------------------------------------------------------------
# Palette de 32 couleurs (4 lignes × 8 colonnes)
# ---------------------------------------------------------------------------
COLOR_PALETTE: list[tuple[int, int, int]] = [
    # Ligne 0 — Naturels (du noir profond au blanc)
    ( 20,  14,  12), ( 55,  34,  18), (100,  60,  30), (135,  90,  45),
    (170, 125,  70), (205, 170, 110), (230, 205, 155), (245, 235, 210),
    # Ligne 1 — Rouges et roux
    (160,  25,  25), (215,  50,  50), (185,  75,  35), (215, 110,  55),
    (200,  55,  30), (225,  95,  60), (235, 140,  90), (245, 175, 125),
    # Ligne 2 — Roses et violets
    (195,  45, 110), (230,  90, 155), (240, 155, 195), (140,  40, 170),
    (180,  75, 205), (215, 130, 230), (155,  90, 195), (195, 155, 230),
    # Ligne 3 — Bleus et verts
    ( 25,  55, 155), ( 40, 100, 210), ( 80, 155, 225), ( 35, 155, 175),
    ( 30, 120,  90), ( 55, 175,  95), (100, 205, 145), ( 35,  90,  75),
]

_COLS = 8   # colonnes dans la grille
_ROWS = 4   # lignes dans la grille


class ColorPickerMenu:
    """
    Panneau de sélection de couleur affiché en overlay.

    Le fond du menu parent est capturé dans screen.imagescreen (mis à jour
    après chaque screen.update()), copié ici et affiché en arrière-plan
    pendant toute la durée du picker.
    """

    # ── Dimensions de la grille ──────────────────────────────────────────
    SWATCH_SIZE = 40    # côté d'un carré de couleur (px)
    SWATCH_GAP  = 6     # espace entre les carrés (px)

    # ── Couleurs de l'interface ──────────────────────────────────────────
    COLOR_PANEL_BG      = (18,  20,  32)
    COLOR_PANEL_BORDER  = (60,  80, 140)
    COLOR_TITLE         = (200, 215, 255)
    COLOR_BTN_CONFIRM   = ( 30, 120, 220)
    COLOR_BTN_CONFIRM_H = ( 55, 150, 255)
    COLOR_BTN_CANCEL    = ( 45,  45,  65)
    COLOR_BTN_CANCEL_H  = ( 70,  70,  95)
    COLOR_SWATCH_BORDER = ( 40,  45,  65)
    COLOR_SWATCH_SEL    = (255, 255, 255)   # bordure carré sélectionné
    COLOR_SWATCH_HOVER  = (180, 200, 240)   # bordure carré survolé

    # ── Espacement interne du panneau ────────────────────────────────────
    PADDING = 24

    def __init__(
        self,
        screen,
        initial_color: tuple[int, int, int],
        label: str = "Couleur",
    ) -> None:
        """
        Paramètres
        ----------
        screen        : objet Screen du jeu (accès à display + imagescreen)
        initial_color : couleur sélectionnée au départ (affichée par défaut)
        label         : titre du panneau (ex: "Couleur : Coiffure")
        """
        self.screen          = screen
        self.display         = screen.get_display()
        self._label          = label
        self._selected_color = tuple(initial_color)   # couleur en cours de sélection
        self._clock          = pygame.time.Clock()

        # Fond gelé = dernier frame visible du menu parent.
        # screen.imagescreen est mis à jour par screen.update() à chaque frame.
        raw_bg = getattr(screen, "imagescreen", None)
        self._background: pygame.Surface | None = raw_bg.copy() if raw_bg else None

        # Charger les polices (police Pokémon si disponible, sinon Arial)
        font_path = LOGIN_MENU_SETTINGS.get("font")
        try:
            self._font_title = pygame.font.Font(font_path, 22)
            self._font       = pygame.font.Font(font_path, 16)
        except Exception:
            self._font_title = pygame.font.SysFont("arial", 22, bold=True)
            self._font       = pygame.font.SysFont("arial", 16)

        # Calculer la mise en page (fait une seule fois)
        self._build_layout()

    # ===================================================================
    # Mise en page — calculée une fois dans __init__
    # ===================================================================

    def _build_layout(self) -> None:
        """
        Calcule et stocke les Rect de chaque élément du panneau.

        On utilise un curseur vertical `y` pour empiler les éléments
        proprement sans calculs manuels de position.
        """
        p  = self.PADDING
        dw = self.display.get_width()
        dh = self.display.get_height()

        # Taille totale de la grille de couleurs
        grid_w = _COLS * self.SWATCH_SIZE + (_COLS - 1) * self.SWATCH_GAP  # 362 px
        grid_h = _ROWS * self.SWATCH_SIZE + (_ROWS - 1) * self.SWATCH_GAP  # 178 px

        # Taille du panneau = grille + padding + autres éléments
        panel_w = grid_w + p * 2
        panel_h = (
            p          # marge haute
            + 36       # titre
            + 14       # espace
            + 50       # barre aperçu couleur
            + 18       # espace
            + grid_h   # grille
            + 20       # espace
            + 48       # boutons
            + p        # marge basse
        )

        # Panneau centré à l'écran
        self._panel = pygame.Rect(
            dw // 2 - panel_w // 2,
            dh // 2 - panel_h // 2,
            panel_w, panel_h,
        )

        # Curseur vertical absolu pour positionner chaque élément
        y = self._panel.y + p
        x = self._panel.x + p       # bord gauche du contenu

        # Titre
        self._title_center = (self._panel.centerx, y + 18)
        y += 36 + 14

        # Barre d'aperçu de la couleur sélectionnée
        self._preview_rect = pygame.Rect(x, y, panel_w - p * 2, 50)
        y += 50 + 18

        # Carrés de couleur (un Rect par entrée de palette)
        self._swatch_rects: list[pygame.Rect] = []
        for i in range(len(COLOR_PALETTE)):
            col = i % _COLS
            row = i // _COLS
            sx  = x + col * (self.SWATCH_SIZE + self.SWATCH_GAP)
            sy  = y + row * (self.SWATCH_SIZE + self.SWATCH_GAP)
            self._swatch_rects.append(pygame.Rect(sx, sy, self.SWATCH_SIZE, self.SWATCH_SIZE))
        y += grid_h + 20

        # Boutons Annuler / Confirmer côte à côte
        btn_w = (panel_w - p * 2 - 12) // 2
        self._btn_cancel  = pygame.Rect(x,              y, btn_w, 48)
        self._btn_confirm = pygame.Rect(x + btn_w + 12, y, btn_w, 48)

    # ===================================================================
    # API publique
    # ===================================================================

    def run(self) -> tuple[int, int, int] | None:
        """
        Lance la boucle du sélecteur de couleur.

        Retourne :
          - tuple (R, G, B)  → l'utilisateur a cliqué "Confirmer"
          - None             → l'utilisateur a annulé (Echap ou "Annuler")
        """
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos

                    # Clic sur un carré → sélection prévisuelle (pas encore confirmé)
                    for i, rect in enumerate(self._swatch_rects):
                        if rect.collidepoint(pos):
                            self._selected_color = COLOR_PALETTE[i]
                            break

                    # Bouton Confirmer → on retourne la couleur choisie
                    if self._btn_confirm.collidepoint(pos):
                        return self._selected_color

                    # Bouton Annuler → on retourne None (pas de changement)
                    if self._btn_cancel.collidepoint(pos):
                        return None

            self._draw()
            self.screen.update()
            self._clock.tick(60)

    # ===================================================================
    # Rendu interne
    # ===================================================================

    def _draw(self) -> None:
        """Dessine l'intégralité du picker à chaque frame."""
        # 1. Fond gelé du menu parent
        if self._background is not None:
            self.display.blit(self._background, (0, 0))
        else:
            self.display.fill((8, 10, 18))

        # 2. Couche semi-transparente pour assombrir l'arrière-plan
        overlay = pygame.Surface(self.display.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.display.blit(overlay, (0, 0))

        # 3. Panneau central
        pygame.draw.rect(self.display, self.COLOR_PANEL_BG,     self._panel, border_radius=10)
        pygame.draw.rect(self.display, self.COLOR_PANEL_BORDER, self._panel, width=2, border_radius=10)

        # 4. Titre
        title = self._font_title.render(self._label, True, self.COLOR_TITLE)
        self.display.blit(title, title.get_rect(center=self._title_center))

        # 5. Barre d'aperçu (couleur sélectionnée en grand)
        self._draw_preview()

        # 6. Grille de couleurs
        self._draw_palette()

        # 7. Boutons
        self._draw_buttons()

    def _draw_preview(self) -> None:
        """Barre colorée montrant la couleur actuellement pointée."""
        r, g, b = self._selected_color

        # Fond de la barre avec la couleur choisie
        pygame.draw.rect(self.display, self._selected_color, self._preview_rect, border_radius=6)
        pygame.draw.rect(self.display, self.COLOR_PANEL_BORDER, self._preview_rect, width=1, border_radius=6)

        # Code hexadécimal de la couleur, en blanc ou noir selon le contraste
        hex_text = f"#{r:02X}{g:02X}{b:02X}"
        text_color = _contrast_color(self._selected_color)
        hex_surf = self._font.render(hex_text, True, text_color)
        self.display.blit(hex_surf, hex_surf.get_rect(center=self._preview_rect.center))

    def _draw_palette(self) -> None:
        """Dessine les 32 carrés de couleur avec indicateur de sélection/survol."""
        mouse_pos = pygame.mouse.get_pos()

        for rect, color in zip(self._swatch_rects, COLOR_PALETTE):
            # Fond coloré
            pygame.draw.rect(self.display, color, rect, border_radius=4)

            # Bordure : blanche (sélectionné), bleu clair (survolé), gris (neutre)
            if color == self._selected_color:
                pygame.draw.rect(self.display, self.COLOR_SWATCH_SEL,   rect, width=3, border_radius=4)
            elif rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.display, self.COLOR_SWATCH_HOVER, rect, width=2, border_radius=4)
            else:
                pygame.draw.rect(self.display, self.COLOR_SWATCH_BORDER, rect, width=1, border_radius=4)

    def _draw_button(
        self,
        rect: pygame.Rect,
        color: tuple,
        color_hovered: tuple,
        text: str,
        text_color: tuple,
        mouse_pos: tuple,
    ) -> None:
        hov   = rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.display, color_hovered if hov else color, rect, border_radius=6)
        label = self._font.render(text, True, text_color)
        self.display.blit(label, label.get_rect(center=rect.center))

    def _draw_buttons(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        self._draw_button(self._btn_cancel,  self.COLOR_BTN_CANCEL,  self.COLOR_BTN_CANCEL_H,  "Annuler",   (200, 200, 215), mouse_pos)
        self._draw_button(self._btn_confirm, self.COLOR_BTN_CONFIRM, self.COLOR_BTN_CONFIRM_H, "Confirmer", (255, 255, 255), mouse_pos)


# ---------------------------------------------------------------------------
# Utilitaire
# ---------------------------------------------------------------------------

def _contrast_color(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    """
    Retourne blanc ou noir selon la luminosité perçue du fond.
    Garantit que le texte reste lisible quelle que soit la couleur.

    Formule de luminance ITU-R BT.709 :
        L = 0.2126·R + 0.7152·G + 0.0722·B
    """
    luminance = 0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]
    return (255, 255, 255) if luminance < 128 else (0, 0, 0)
