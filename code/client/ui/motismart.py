from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pygame

from code.client.config import MOTISMART_UI
from code.client.core.controller import Controller
from code.client.core.keylistener import KeyListener
from code.client.core.screen import Screen
from code.server.managers.save_manager import Save
from code.client.ui.admin_menu import AdminMenu


def _load(path, size: tuple | None = None) -> pygame.Surface | None:
    try:
        img = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.scale(img, size) if size else img
    except Exception as e:
        print(f"[Motismart] Impossible de charger {path} : {e}")
        return None


@dataclass
class _App:
    label:    str
    icon:     pygame.Surface | None
    on_click: Callable


# Grille d'apps : 3 colonnes × 5 lignes = 15 cellules
_GRID_COLS       = 3
_GRID_ROWS       = 5
_GRID_PAD_LEFT   = 0.13   # % de la largeur du téléphone
_GRID_PAD_RIGHT  = 0.13
_GRID_PAD_TOP    = 0.22   # % de la hauteur du téléphone
_GRID_PAD_BOTTOM = 0.14
_GRID_GAP        = 6      # px entre cellules

# Couleur des cellules vides
_CELL_BG  = (255, 255, 255, 18)   # blanc très transparent
_CELL_BD  = (200, 200, 255, 60)   # contour légèrement visible


class Motismart:
    """
    Menu téléphone — touche X.
    Bas-gauche, animation slide-up à l'ouverture, slide-down à la fermeture.
    Contient une grille 3×5 pour les icônes d'applications.
    """

    _HEIGHT_RATIO  = 0.50
    _HEIGHT_MULT   = 1.30
    _X_MARGIN      = 16
    _X_SHIFT       = 48
    _Y_MARGIN      = 8
    _OPEN_SPEED    = 1400.0
    _CLOSE_SPEED   = 2200.0

    def __init__(
        self,
        screen: Screen,
        controller: Controller,
        keylistener: KeyListener,
        save: Save,
        player,
    ) -> None:
        self.screen      = screen
        self.controller  = controller
        self.keylistener = keylistener
        self.save        = save
        self.player      = player

        self._ready     = False
        self._bg_surf:  pygame.Surface | None = None
        self._bg_w      = 0
        self._bg_h      = 0
        self._draw_x    = 0
        self._target_y  = 0.0
        self._screen_h  = 0
        self._anim_y    = 0.0
        self._opening   = False
        self._closing   = False
        self._last_tick = 0.0

        # Grille d'apps
        self._apps: list[_App | None] = [None] * (_GRID_COLS * _GRID_ROWS)

        # Menu admin (app cell 0)
        self._admin_menu = AdminMenu(screen, player, keylistener)
        self._apps[0] = _App("Admin", None, self._admin_menu.toggle)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def update(self, mouse_click: tuple | None = None) -> None:
        now = time.time()
        dt  = now - self._last_tick if self._last_tick else 0.0
        self._last_tick = now

        if not self._ready:
            self._build()
            return

        self._update_anim(dt)
        self._draw()

        # Menus d'apps (dessinés par-dessus le téléphone)
        if self._admin_menu.active:
            self._admin_menu.update(mouse_click)
            mouse_click = None   # consommé par le menu admin

        if not self._closing:
            self._handle_input(mouse_click)

    def check_inputs(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        W, H = self.screen.get_size()
        self._screen_h = H

        bg_h = min(
            int(H * self._HEIGHT_RATIO * self._HEIGHT_MULT),
            H - self._Y_MARGIN * 2,
        )
        self._bg_h = bg_h

        raw = _load(MOTISMART_UI["bg"])
        if raw:
            bg_w          = int(bg_h * raw.get_width() / raw.get_height())
            self._bg_surf = pygame.transform.scale(raw, (bg_w, bg_h))
        else:
            bg_w = int(bg_h * 0.45)
        self._bg_w = bg_w

        self._draw_x   = self._X_MARGIN + self._X_SHIFT
        self._target_y = float(H - bg_h - self._Y_MARGIN)
        self._anim_y   = float(H + bg_h)
        self._opening  = True
        self._closing  = False
        self._ready    = True

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def _update_anim(self, dt: float) -> None:
        if self._opening:
            self._anim_y -= self._OPEN_SPEED * dt
            if self._anim_y <= self._target_y:
                self._anim_y  = self._target_y
                self._opening = False
        elif self._closing:
            self._anim_y += self._CLOSE_SPEED * dt
            if self._anim_y >= float(self._screen_h + self._bg_h):
                self._do_close()

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        disp   = self.screen.get_display()
        phone_x = self._draw_x
        phone_y = int(self._anim_y)

        if self._bg_surf:
            disp.blit(self._bg_surf, (phone_x, phone_y))

        self._draw_grid(disp, phone_x, phone_y)

    def _draw_grid(self, disp: pygame.Surface, phone_x: int, phone_y: int) -> None:
        bw, bh = self._bg_w, self._bg_h
        gx = phone_x + int(bw * _GRID_PAD_LEFT)
        gy = phone_y + int(bh * _GRID_PAD_TOP)
        gw = bw - int(bw * _GRID_PAD_LEFT) - int(bw * _GRID_PAD_RIGHT)
        gh = bh - int(bh * _GRID_PAD_TOP)  - int(bh * _GRID_PAD_BOTTOM)

        cell_w = (gw - _GRID_GAP * (_GRID_COLS - 1)) // _GRID_COLS
        cell_h = (gh - _GRID_GAP * (_GRID_ROWS - 1)) // _GRID_ROWS

        for row in range(_GRID_ROWS):
            for col in range(_GRID_COLS):
                idx = row * _GRID_COLS + col
                cx  = gx + col * (cell_w + _GRID_GAP)
                cy  = gy + row * (cell_h + _GRID_GAP)

                # Fond de cellule
                cell_surf = pygame.Surface((cell_w, cell_h), pygame.SRCALPHA)
                cell_surf.fill(_CELL_BG)
                pygame.draw.rect(cell_surf, _CELL_BD, (0, 0, cell_w, cell_h), 1, border_radius=6)
                disp.blit(cell_surf, (cx, cy))

                app = self._apps[idx]
                if app is None:
                    continue

                # Icône de l'app
                if app.icon:
                    icon_size = min(cell_w, cell_h) - 8
                    icon = pygame.transform.smoothscale(app.icon, (icon_size, icon_size))
                    disp.blit(icon, icon.get_rect(center=(cx + cell_w // 2, cy + cell_h // 2 - 6)))
                else:
                    # Placeholder coloré si pas d'icône
                    r = pygame.Rect(cx + 4, cy + 4, cell_w - 8, cell_h - 8 - 14)
                    pygame.draw.rect(disp, (80, 120, 200), r, border_radius=4)

                # Label
                try:
                    font = pygame.font.SysFont("segoeui", max(8, cell_h // 5))
                    lbl  = font.render(app.label, True, (240, 240, 240))
                    lx   = cx + (cell_w - lbl.get_width()) // 2
                    ly   = cy + cell_h - lbl.get_height() - 3
                    disp.blit(lbl, (lx, ly))
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------

    def _handle_input(self, mouse_click: tuple | None) -> None:
        quit_key  = self.controller.get_key("quit")
        phone_key = self.controller.get_key("phone")

        # Échap : ferme l'admin en premier, puis le téléphone
        if self.keylistener.key_pressed(quit_key):
            self.keylistener.remove_key(quit_key)
            if self._admin_menu.active:
                self._admin_menu.active = False
            else:
                self._closing = True
            return

        if self.keylistener.key_pressed(phone_key):
            self.keylistener.remove_key(phone_key)
            self._closing = True
            return

        # Clic sur une cellule de la grille
        if mouse_click:
            self._handle_grid_click(mouse_click)

    def _handle_grid_click(self, pos: tuple) -> None:
        bw, bh  = self._bg_w, self._bg_h
        phone_x = self._draw_x
        phone_y = int(self._anim_y)

        gx = phone_x + int(bw * _GRID_PAD_LEFT)
        gy = phone_y + int(bh * _GRID_PAD_TOP)
        gw = bw - int(bw * _GRID_PAD_LEFT) - int(bw * _GRID_PAD_RIGHT)
        gh = bh - int(bh * _GRID_PAD_TOP)  - int(bh * _GRID_PAD_BOTTOM)

        cell_w = (gw - _GRID_GAP * (_GRID_COLS - 1)) // _GRID_COLS
        cell_h = (gh - _GRID_GAP * (_GRID_ROWS - 1)) // _GRID_ROWS

        mx, my = pos
        if not (gx <= mx < gx + gw and gy <= my < gy + gh):
            return

        col = (mx - gx) // (cell_w + _GRID_GAP)
        row = (my - gy) // (cell_h + _GRID_GAP)
        col = max(0, min(col, _GRID_COLS - 1))
        row = max(0, min(row, _GRID_ROWS - 1))
        idx = row * _GRID_COLS + col

        # Vérifier que le clic est bien dans la cellule (pas dans le gap)
        cx = gx + col * (cell_w + _GRID_GAP)
        cy = gy + row * (cell_h + _GRID_GAP)
        if not (cx <= mx < cx + cell_w and cy <= my < cy + cell_h):
            return

        if 0 <= idx < len(self._apps) and self._apps[idx] is not None:
            self._apps[idx].on_click()

    def _do_close(self) -> None:
        if self._admin_menu.active:
            self._admin_menu.active = False
        self.player.menu_option = False
        self.player.can_move    = True
        self._ready             = False
        self._closing           = False
        self._opening           = False
        self._last_tick         = 0.0
