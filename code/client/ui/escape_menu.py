from __future__ import annotations

import pygame

from code.client.config import BATTLE_UI
from code.client.core.controller import Controller
from code.client.core.keylistener import KeyListener
from code.client.core.screen import Screen
from code.client.ui.components.text_box import TextBox

_CHOICES = ["Continuer", "Se déconnecter", "Quitter"]

_C_SELECTED   = (255, 255, 255)
_C_UNSELECTED = (160, 160, 180)


class EscapeMenu:
    """
    Menu Échap — bulle de dialogue + choix en bas-à-droite de la bulle.
    Pas de fond noir. Bloque les déplacements du joueur.
    Navigation : haut/bas + E, Échap = Continuer.
    """

    RESULT_CONTINUE   = "continuer"
    RESULT_DISCONNECT = "deconnecter"
    RESULT_QUIT       = "quitter"

    def __init__(
        self,
        screen: Screen,
        controller: Controller,
        keylistener: KeyListener,
    ) -> None:
        self.screen      = screen
        self.controller  = controller
        self.keylistener = keylistener

        self.active  = False
        self.result: str | None = None

        self._built    = False
        self._textbox: TextBox | None        = None
        self._font:    pygame.font.Font | None = None
        self._selected = 0

        self._choice_right = 0   # ancrage droite des choix
        self._choice_y0    = 0
        self._line_h       = 0

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def open(self) -> None:
        self.active    = True
        self.result    = None
        self._selected = 0
        if not self._built:
            self._build()
        self._textbox.set_messages(["Que souhaitez-vous faire ?"])

    def update(self, mouse_click: tuple | None = None) -> None:
        if not self.active:
            return
        self._textbox.update()
        self._draw()
        self._handle_input(mouse_click)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        W, H = self.screen.get_size()

        try:
            self._font = pygame.font.SysFont("segoeui", 22)
        except Exception:
            self._font = pygame.font.Font(None, 26)

        # Bulle de dialogue (même style que dialogue in-world)
        tw = int(W * 0.68)
        th = int(H * 0.18)
        tx = (W - tw) // 2
        ty = H - th - 16

        try:
            bg = pygame.transform.scale(
                pygame.image.load(str(BATTLE_UI["overlay_message"])).convert_alpha(),
                (tw, th),
            )
        except Exception:
            bg = None

        self._textbox = TextBox(
            pygame.Rect(tx, ty, tw, th),
            bg_surf=bg,
            text_color=(255, 255, 255),
        )

        # Choix — bas-à-droite de la bulle, juste au-dessus d'elle
        self._line_h       = self._font.get_height() + 6
        total_h            = len(_CHOICES) * self._line_h
        self._choice_right = tx + tw - 24          # ancre droite = bord droit textbox
        self._choice_y0    = ty - total_h - 12     # juste au-dessus de la bulle

        self._built = True

    # ------------------------------------------------------------------
    # Rendu — pas d'overlay, monde visible derrière
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        disp = self.screen.get_display()

        self._textbox.draw(disp)

        for i, label in enumerate(_CHOICES):
            if i == self._selected:
                text  = f"▶  {label}"
                color = _C_SELECTED
            else:
                text  = f"    {label}"
                color = _C_UNSELECTED

            surf = self._font.render(text, True, color)
            # Alignement à droite sur self._choice_right
            x = self._choice_right - surf.get_width()
            y = self._choice_y0 + i * self._line_h
            disp.blit(surf, (x, y))

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    def _handle_input(self, mouse_click: tuple | None) -> None:
        up_key     = self.controller.get_key("up")
        down_key   = self.controller.get_key("down")
        action_key = self.controller.get_key("action")
        quit_key   = self.controller.get_key("quit")

        if self.keylistener.key_pressed(quit_key):
            self.keylistener.remove_key(quit_key)
            self._confirm(0)
            return

        if self.keylistener.key_pressed(up_key):
            self._selected = (self._selected - 1) % len(_CHOICES)
            self.keylistener.remove_key(up_key)
        elif self.keylistener.key_pressed(down_key):
            self._selected = (self._selected + 1) % len(_CHOICES)
            self.keylistener.remove_key(down_key)
        elif self.keylistener.key_pressed(action_key):
            self.keylistener.remove_key(action_key)
            self._confirm(self._selected)

        if mouse_click:
            for i in range(len(_CHOICES)):
                y    = self._choice_y0 + i * self._line_h
                text = f"▶  {_CHOICES[i]}" if i == self._selected else f"    {_CHOICES[i]}"
                w    = self._font.size(text)[0]
                x    = self._choice_right - w
                if pygame.Rect(x, y, w, self._line_h).collidepoint(mouse_click):
                    self._confirm(i)
                    return

    def _confirm(self, index: int) -> None:
        results = [self.RESULT_CONTINUE, self.RESULT_DISCONNECT, self.RESULT_QUIT]
        self.result = results[index]
        self.active = False
