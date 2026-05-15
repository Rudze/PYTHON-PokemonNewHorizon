"""
move_learn_menu.py — Menu de remplacement d'attaque (overworld).

Deux états :
  CONFIRM : dialogue oui/non — le Pokémon peut-il apprendre l'attaque ?
  SELECT  : sélection de l'attaque à remplacer parmi les 4 actuelles.

Taille : plein écran (même emprise que le battle screen).
Fond blanc opaque.
"""
from __future__ import annotations

import pygame

from code.shared.models.move import Move

# Palette
_WHITE   = (255, 255, 255)
_DARK    = ( 20,  20,  35)
_GREY    = (130, 130, 145)
_BLUE    = ( 55, 100, 210)
_BLUE_LT = (210, 225, 255)
_GREEN   = ( 40, 170,  60)
_RED     = (190,  40,  40)
_HOVER_G = ( 55, 200,  80)
_HOVER_R = (220,  55,  55)
_CARD_BG = (240, 245, 255)
_CARD_BD = (150, 175, 220)
_CARD_HV = (200, 215, 255)


class MoveLearnMenu:
    """
    Appelé depuis game.py chaque frame tant que `active` est True.
    Renvoie None pendant son exécution, puis "done" ou "cancel" une fois terminé.
    """

    _CONFIRM = "confirm"
    _SELECT  = "select"

    def __init__(self, screen, pokemon, new_move_name: str) -> None:
        self.screen        = screen
        self.pokemon       = pokemon
        self.new_move_name = new_move_name
        self.active        = True
        self._state        = self._CONFIRM
        self._result: str | None = None

        try:
            self._new_move: Move | None = Move.createMove(new_move_name)
        except Exception:
            self._new_move = None

        self._font_h:  pygame.font.Font | None = None
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None
        self._built = False

    # ------------------------------------------------------------------

    def update(self, mouse_click: tuple | None) -> str | None:
        """Dessine + traite les clics. Retourne None, 'done' ou 'cancel'."""
        if not self.active:
            return self._result
        if not self._built:
            self._build()
        self._draw(mouse_click)
        return None if self.active else self._result

    # ------------------------------------------------------------------

    def _build(self) -> None:
        try:
            self._font_h  = pygame.font.SysFont("segoeui", 24, bold=True)
            self._font    = pygame.font.SysFont("segoeui", 17)
            self._font_sm = pygame.font.SysFont("segoeui", 13)
        except Exception:
            f = pygame.font.Font(None, 18)
            self._font_h = self._font = self._font_sm = f
        self._built = True

    def _draw(self, mouse_click: tuple | None) -> None:
        W, H = self.screen.get_size()
        disp = self.screen.get_display()

        disp.fill(_WHITE)

        if self._state == self._CONFIRM:
            self._draw_confirm(disp, W, H, mouse_click)
        else:
            self._draw_select(disp, W, H, mouse_click)

    # ── État CONFIRM ────────────────────────────────────────────────────

    def _draw_confirm(self, disp, W, H, mouse_click) -> None:
        mx, my = pygame.mouse.get_pos()
        pname  = self.pokemon.dbSymbol.replace("_", " ").capitalize()
        mname  = self.new_move_name.replace("_", " ").capitalize()

        cy = H // 2 - 80
        self._blit_center(disp, self._font_h, f"{pname} peut apprendre", _DARK, W, cy)
        self._blit_center(disp, self._font_h, mname + " !", _BLUE, W, cy + 34)
        self._blit_center(disp, self._font, "Voulez-vous apprendre cette attaque ?", _GREY, W, cy + 85)

        bw, bh = 140, 48
        gap    = 24
        yes_r  = pygame.Rect(W // 2 - bw - gap // 2, cy + 135, bw, bh)
        no_r   = pygame.Rect(W // 2 + gap // 2,       cy + 135, bw, bh)

        pygame.draw.rect(disp, _HOVER_G if yes_r.collidepoint(mx, my) else _GREEN, yes_r, border_radius=10)
        pygame.draw.rect(disp, _HOVER_R if no_r.collidepoint(mx, my)  else _RED,   no_r,  border_radius=10)
        self._blit_center(disp, self._font, "OUI", _WHITE, yes_r.centerx, yes_r.centery, center_x=False)
        self._blit_center(disp, self._font, "NON", _WHITE, no_r.centerx,  no_r.centery,  center_x=False)

        if mouse_click:
            if yes_r.collidepoint(mouse_click):
                self._state = self._SELECT
            elif no_r.collidepoint(mouse_click):
                self._finish("cancel")

    # ── État SELECT ─────────────────────────────────────────────────────

    def _draw_select(self, disp, W, H, mouse_click) -> None:
        mx, my = pygame.mouse.get_pos()

        self._blit_center(disp, self._font_h, "Quelle attaque remplacer ?", _DARK, W, 40)

        # ── Carte nouvelle attaque (gauche) ─────────────────────────────
        CARD_W = int(W * 0.36)
        CARD_H = 200
        nx = int(W * 0.05)
        ny = int(H * 0.20)
        self._draw_move_card(disp, nx, ny, CARD_W, CARD_H,
                             self._new_move, self.new_move_name,
                             bg=_BLUE_LT, border=_BLUE, label="NOUVELLE ATTAQUE")

        # Flèche vers la droite
        ax = nx + CARD_W + 10
        ay = ny + CARD_H // 2
        self._draw_arrow(disp, ax, ay)

        # ── 4 attaques actuelles (droite) ────────────────────────────────
        SLOT_W = int(W * 0.36)
        SLOT_H = 82
        SLOT_G = 14
        sx     = int(W * 0.55)
        total_h = 4 * SLOT_H + 3 * SLOT_G
        sy     = (H - total_h) // 2

        move_rects: list[pygame.Rect] = []
        for i, mv in enumerate(self.pokemon.moves):
            ry  = sy + i * (SLOT_H + SLOT_G)
            r   = pygame.Rect(sx, ry, SLOT_W, SLOT_H)
            hov = r.collidepoint(mx, my)
            move_rects.append(r)
            self._draw_move_card(disp, r.x, r.y, r.width, r.height, mv, mv.dbSymbol if mv else "???",
                                 bg=_CARD_HV if hov else _CARD_BG, border=_BLUE if hov else _CARD_BD)

        # ── Bouton Annuler ───────────────────────────────────────────────
        cw, ch = 180, 48
        cr = pygame.Rect(W // 2 - cw // 2, H - ch - 24, cw, ch)
        chov = cr.collidepoint(mx, my)
        pygame.draw.rect(disp, (160, 160, 160) if chov else (110, 110, 110), cr, border_radius=10)
        self._blit_center(disp, self._font, "Annuler", _WHITE, cr.centerx, cr.centery, center_x=False)

        # ── Clics ────────────────────────────────────────────────────────
        if mouse_click:
            for i, r in enumerate(move_rects):
                if r.collidepoint(mouse_click) and self._new_move:
                    self.pokemon.moves[i] = self._new_move
                    self._finish("done")
                    return
            if cr.collidepoint(mouse_click):
                self._finish("cancel")

    # ------------------------------------------------------------------

    def _finish(self, result: str) -> None:
        self._result = result
        self.active  = False

    def _draw_move_card(
        self, disp, x, y, w, h,
        move: Move | None, name_sym: str,
        bg, border, label: str = ""
    ) -> None:
        pygame.draw.rect(disp, bg,     (x, y, w, h), border_radius=10)
        pygame.draw.rect(disp, border, (x, y, w, h), 2, border_radius=10)

        pad = 10
        ty  = y + pad

        if label and self._font_sm:
            lt = self._font_sm.render(label, True, border)
            disp.blit(lt, (x + pad, ty))
            ty += lt.get_height() + 4

        display_name = name_sym.replace("_", " ").capitalize()
        if self._font:
            nt = self._font.render(display_name, True, _DARK)
            disp.blit(nt, (x + pad, ty))
            ty += nt.get_height() + 4

        if move and self._font_sm:
            mtype = (move.type or "normal").capitalize()
            pwr   = str(move.power)   if move.power    else "—"
            acc   = f"{move.accuracy}%" if move.accuracy else "—"
            pp    = str(move.pp)      if move.pp       else "—"
            info  = f"Type : {mtype}   Puissance : {pwr}   Précision : {acc}   PP : {pp}"
            it    = self._font_sm.render(info, True, _GREY)
            disp.blit(it, (x + pad, ty))

    def _draw_arrow(self, disp, ax, ay) -> None:
        size = 14
        pts  = [(ax, ay - size), (ax + size * 2, ay), (ax, ay + size)]
        pygame.draw.polygon(disp, _BLUE, pts)

    def _blit_center(self, disp, font, text, color, cx_or_W, cy, center_x=True) -> None:
        if not font:
            return
        surf = font.render(text, True, color)
        if center_x:
            x = cx_or_W // 2 - surf.get_width() // 2
        else:
            x = cx_or_W - surf.get_width() // 2
        disp.blit(surf, (x, cy - surf.get_height() // 2))
