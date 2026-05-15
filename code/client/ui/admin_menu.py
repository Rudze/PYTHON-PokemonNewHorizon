"""
admin_menu.py — Menu admin accessible depuis le Motismart.
Boutons : Objets, Soigner équipe, +100 P$, +1 Niveau, Donner Pokémon.
"""
from __future__ import annotations

import pygame

from code.shared.config.items import ITEMS

_CATEGORY_TO_POCKET: dict[str, str] = {
    "medicine":  "items",
    "pokeball":  "pokeballs",
    "key":       "key_items",
    "tm_hm":     "tm_hm",
    "berry":     "items",
    "misc":      "items",
}

_PANEL_W  = 240
_BTN_H    = 44
_BTN_GAP  = 10
_MARGIN   = 16
_HEADER_H = 46

_ITEM_W   = 280
_ITEM_ROW = 38
_GIVE_W   = 70
_GIVE_H   = 26

_POKE_PANEL_W = 260

_DIGIT_KEYS = {
    pygame.K_0: "0", pygame.K_1: "1", pygame.K_2: "2",
    pygame.K_3: "3", pygame.K_4: "4", pygame.K_5: "5",
    pygame.K_6: "6", pygame.K_7: "7", pygame.K_8: "8", pygame.K_9: "9",
    pygame.K_KP0: "0", pygame.K_KP1: "1", pygame.K_KP2: "2",
    pygame.K_KP3: "3", pygame.K_KP4: "4", pygame.K_KP5: "5",
    pygame.K_KP6: "6", pygame.K_KP7: "7", pygame.K_KP8: "8", pygame.K_KP9: "9",
}


class AdminMenu:
    def __init__(self, screen, player, keylistener=None) -> None:
        self.screen      = screen
        self.player      = player
        self._keylistener = keylistener
        self.active      = False

        self._show_items       = False
        self._show_give_pkmn   = False
        self._scroll           = 0
        self._max_vis          = 0

        # Champs texte pour le don de Pokémon
        self._dex_input:   str = ""   # numéro Pokédex
        self._lvl_input:   str = ""   # niveau
        self._active_field: str = "dex"   # "dex" | "lvl"
        self._give_msg:    str = ""   # message de résultat (succès / erreur)

        self._font_title: pygame.font.Font | None = None
        self._font:       pygame.font.Font | None = None
        self._font_btn:   pygame.font.Font | None = None
        self._built = False

        self._items_list: list[tuple[str, dict]] = []
        self._item_btns:  list[tuple[pygame.Rect, str, str]] = []

    # ------------------------------------------------------------------

    def toggle(self) -> None:
        self.active = not self.active
        if not self.active:
            self._show_items     = False
            self._show_give_pkmn = False
            self._give_msg       = ""
            self._scroll         = 0

    # ------------------------------------------------------------------

    def update(self, mouse_click: tuple | None = None) -> None:
        if not self.active:
            return
        if not self._built:
            self._build()
        if self._show_give_pkmn:
            self._handle_text_input()
        self._draw(mouse_click)

    # ------------------------------------------------------------------

    def _build(self) -> None:
        try:
            self._font_title = pygame.font.SysFont("segoeui", 16, bold=True)
            self._font       = pygame.font.SysFont("segoeui", 14)
            self._font_btn   = pygame.font.SysFont("segoeui", 13, bold=True)
        except Exception:
            f = pygame.font.Font(None, 16)
            self._font_title = self._font = self._font_btn = f
        self._items_list = list(ITEMS.items())
        self._built = True

    # ------------------------------------------------------------------

    def _draw(self, mouse_click: tuple | None) -> None:
        W, H   = self.screen.get_size()
        disp   = self.screen.get_display()
        mx, my = pygame.mouse.get_pos()

        # ── Panneau principal ─────────────────────────────────────────
        btn_defs = [
            ("Objets",            self._on_items),
            ("Soigner équipe",    self._on_heal),
            ("+100 P$",           self._on_money),
            ("+1 Niveau (1er)",   self._on_level_up),
            ("Donner Pokémon",    self._on_toggle_give_pkmn),
        ]
        nb = len(btn_defs)
        panel_h = _HEADER_H + nb * (_BTN_H + _BTN_GAP) + _BTN_GAP
        px = W - _PANEL_W - _MARGIN
        py = _MARGIN

        bg = pygame.Surface((_PANEL_W, panel_h), pygame.SRCALPHA)
        bg.fill((15, 15, 35, 230))
        disp.blit(bg, (px, py))
        pygame.draw.rect(disp, (90, 90, 200), (px, py, _PANEL_W, panel_h), 2, border_radius=6)

        if self._font_title:
            t = self._font_title.render("Menu Admin", True, (255, 220, 60))
            disp.blit(t, (px + 10, py + 10))
        pygame.draw.line(disp, (90, 90, 200),
                         (px + 4, py + _HEADER_H - 4),
                         (px + _PANEL_W - 4, py + _HEADER_H - 4))

        main_btns: list[tuple[pygame.Rect, object]] = []
        for i, (label, cb) in enumerate(btn_defs):
            bx = px + _BTN_GAP
            by = py + _HEADER_H + i * (_BTN_H + _BTN_GAP) + _BTN_GAP
            br = pygame.Rect(bx, by, _PANEL_W - _BTN_GAP * 2, _BTN_H)
            is_active = (label == "Objets" and self._show_items) or \
                        (label == "Donner Pokémon" and self._show_give_pkmn)
            hov   = br.collidepoint(mx, my)
            color = (60, 100, 200) if is_active else ((50, 160, 50) if hov else (35, 35, 80))
            pygame.draw.rect(disp, color, br, border_radius=6)
            pygame.draw.rect(disp, (100, 100, 220), br, 1, border_radius=6)
            if self._font_btn:
                lt = self._font_btn.render(label, True, (255, 255, 255))
                disp.blit(lt, lt.get_rect(center=br.center))
            main_btns.append((br, cb))

        # ── Sous-panneau items ────────────────────────────────────────
        if self._show_items:
            self._draw_items_panel(disp, H, px, _MARGIN, mx, my)

        # ── Sous-panneau don de Pokémon ────────────────────────────────
        if self._show_give_pkmn:
            self._draw_give_pkmn_panel(disp, px, py, mx, my, mouse_click)

        # ── Clics boutons principaux ──────────────────────────────────
        if mouse_click:
            for br, cb in main_btns:
                if br.collidepoint(mouse_click):
                    cb()
                    return
            if self._show_items:
                for gbr, item_id, pocket in self._item_btns:
                    if gbr.collidepoint(mouse_click):
                        self.player.inv.add_item_with_slot(item_id, pocket, 1)
                        return

    # ------------------------------------------------------------------
    # Sous-panneau items
    # ------------------------------------------------------------------

    def _draw_items_panel(self, disp, H, px, sy, mx, my) -> None:
        avail_h       = H - _MARGIN * 2
        self._max_vis = max(1, (avail_h - _HEADER_H - 8) // _ITEM_ROW)
        sub_h         = _HEADER_H + min(len(self._items_list), self._max_vis) * _ITEM_ROW + 8
        sx = px - _ITEM_W - 8

        sbg = pygame.Surface((_ITEM_W, sub_h), pygame.SRCALPHA)
        sbg.fill((15, 15, 35, 230))
        disp.blit(sbg, (sx, sy))
        pygame.draw.rect(disp, (90, 90, 200), (sx, sy, _ITEM_W, sub_h), 2, border_radius=6)

        if self._font_title:
            t = self._font_title.render("Items", True, (255, 220, 60))
            disp.blit(t, (sx + 10, sy + 10))
        pygame.draw.line(disp, (90, 90, 200),
                         (sx + 4, sy + _HEADER_H - 4),
                         (sx + _ITEM_W - 4, sy + _HEADER_H - 4))

        self._item_btns = []
        for idx, (item_id, defn) in enumerate(
            self._items_list[self._scroll: self._scroll + self._max_vis]
        ):
            ry = sy + _HEADER_H + idx * _ITEM_ROW
            if idx % 2 == 0:
                stripe = pygame.Surface((_ITEM_W, _ITEM_ROW), pygame.SRCALPHA)
                stripe.fill((255, 255, 255, 12))
                disp.blit(stripe, (sx, ry))
            if self._font:
                nt = self._font.render(defn.get("name_fr", item_id), True, (210, 210, 210))
                disp.blit(nt, (sx + 8, ry + (_ITEM_ROW - nt.get_height()) // 2))
            bx2 = sx + _ITEM_W - _GIVE_W - 8
            by2 = ry + (_ITEM_ROW - _GIVE_H) // 2
            gbr = pygame.Rect(bx2, by2, _GIVE_W, _GIVE_H)
            pocket = _CATEGORY_TO_POCKET.get(defn.get("category", "misc"), "items")
            pygame.draw.rect(disp, (60,160,60) if gbr.collidepoint(mx,my) else (35,105,35),
                             gbr, border_radius=4)
            if self._font_btn:
                gt = self._font_btn.render("Donner", True, (255, 255, 255))
                disp.blit(gt, gt.get_rect(center=gbr.center))
            self._item_btns.append((gbr, item_id, pocket))

        total = len(self._items_list)
        if total > self._max_vis:
            bar_h  = sub_h - _HEADER_H - 8
            ind_y  = sy + _HEADER_H + 4 + int(self._scroll / total * bar_h)
            ind_h  = max(20, int(self._max_vis / total * bar_h))
            pygame.draw.rect(disp, (90, 90, 200),
                             (sx + _ITEM_W - 5, ind_y, 3, ind_h), border_radius=2)

    # ------------------------------------------------------------------
    # Sous-panneau don de Pokémon
    # ------------------------------------------------------------------

    def _draw_give_pkmn_panel(self, disp, px, py, mx, my,
                               mouse_click: tuple | None) -> None:
        W = _POKE_PANEL_W
        sx = px - W - 8

        # Hauteur : titre + 2 champs + bouton + message
        FIELD_H  = 36
        LABEL_H  = 22
        BTN_H    = 40
        MSG_H    = 24
        pad      = 12
        panel_h  = _HEADER_H + (LABEL_H + FIELD_H + 8) * 2 + BTN_H + MSG_H + pad * 2 + 8

        bg = pygame.Surface((W, panel_h), pygame.SRCALPHA)
        bg.fill((15, 15, 35, 230))
        disp.blit(bg, (sx, py))
        pygame.draw.rect(disp, (90, 90, 200), (sx, py, W, panel_h), 2, border_radius=6)

        if self._font_title:
            t = self._font_title.render("Donner Pokémon", True, (255, 220, 60))
            disp.blit(t, (sx + pad, py + 10))
        pygame.draw.line(disp, (90, 90, 200),
                         (sx + 4, py + _HEADER_H - 4),
                         (sx + W - 4, py + _HEADER_H - 4))

        cy = py + _HEADER_H + pad

        # Champ Pokédex
        cy = self._draw_field(disp, sx, cy, W, pad, LABEL_H, FIELD_H,
                              "N° Pokédex :", self._dex_input, "dex", mx, my, mouse_click)
        cy += 8

        # Champ Niveau
        cy = self._draw_field(disp, sx, cy, W, pad, LABEL_H, FIELD_H,
                              "Niveau :", self._lvl_input, "lvl", mx, my, mouse_click)
        cy += pad

        # Bouton Donner
        bw = W - pad * 2
        br = pygame.Rect(sx + pad, cy, bw, BTN_H)
        hov = br.collidepoint(mx, my)
        pygame.draw.rect(disp, (50, 160, 50) if hov else (30, 110, 30), br, border_radius=6)
        if self._font_btn:
            lt = self._font_btn.render("Donner", True, (255, 255, 255))
            disp.blit(lt, lt.get_rect(center=br.center))
        cy += BTN_H + 8

        # Message résultat
        if self._give_msg and self._font:
            is_ok = self._give_msg.startswith("✓")
            col   = (80, 220, 80) if is_ok else (220, 80, 80)
            mt    = self._font.render(self._give_msg[:36], True, col)
            disp.blit(mt, (sx + pad, cy))

        # Clic bouton Donner
        if mouse_click and br.collidepoint(mouse_click):
            self._on_give_pokemon()

    def _draw_field(self, disp, sx, cy, W, pad, label_h, field_h,
                    label: str, value: str, field_id: str,
                    mx, my, mouse_click) -> int:
        if self._font:
            lt = self._font.render(label, True, (190, 190, 210))
            disp.blit(lt, (sx + pad, cy))
        cy += label_h

        field_rect = pygame.Rect(sx + pad, cy, W - pad * 2, field_h)
        active = self._active_field == field_id
        pygame.draw.rect(disp, (30, 30, 60) if active else (20, 20, 45), field_rect, border_radius=4)
        pygame.draw.rect(disp, (130, 130, 255) if active else (70, 70, 130), field_rect, 2, border_radius=4)

        display = value + ("|" if active else "")
        if self._font_btn:
            vt = self._font_btn.render(display, True, (255, 255, 255))
            disp.blit(vt, (field_rect.x + 8, field_rect.y + (field_h - vt.get_height()) // 2))

        if mouse_click and field_rect.collidepoint(mouse_click):
            self._active_field = field_id

        return cy + field_h

    # ------------------------------------------------------------------
    # Saisie clavier (digits + backspace + entrée)
    # ------------------------------------------------------------------

    def _handle_text_input(self) -> None:
        if not self._keylistener:
            return

        for key, char in _DIGIT_KEYS.items():
            if self._keylistener.key_pressed(key):
                self._keylistener.remove_key(key)
                if self._active_field == "dex" and len(self._dex_input) < 4:
                    self._dex_input += char
                elif self._active_field == "lvl" and len(self._lvl_input) < 3:
                    self._lvl_input += char
                break

        if self._keylistener.key_pressed(pygame.K_BACKSPACE):
            self._keylistener.remove_key(pygame.K_BACKSPACE)
            if self._active_field == "dex":
                self._dex_input = self._dex_input[:-1]
            else:
                self._lvl_input = self._lvl_input[:-1]

        for enter in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._keylistener.key_pressed(enter):
                self._keylistener.remove_key(enter)
                self._on_give_pokemon()
                break

    # ------------------------------------------------------------------
    # Callbacks boutons
    # ------------------------------------------------------------------

    def _on_items(self) -> None:
        self._show_items     = not self._show_items
        self._show_give_pkmn = False
        self._scroll         = 0

    def _on_heal(self) -> None:
        self.player.inv.heal_party()

    def _on_money(self) -> None:
        self.player.inv.add_money(100)

    def _on_level_up(self) -> None:
        party = self.player.inv.party
        if not party:
            return
        pkmn = party[0]
        if pkmn.level >= 100:
            return
        pkmn.xp = pkmn._calc_xp_for_level(pkmn.level + 1, pkmn.experienceType)
        learned, pending = pkmn.check_level_ups()
        pkmn.newly_learned.extend(learned)
        pkmn.pending_moves.extend(pending)
        self.player.inv.sync_party()

    def _on_toggle_give_pkmn(self) -> None:
        self._show_give_pkmn = not self._show_give_pkmn
        self._show_items     = False
        if self._show_give_pkmn:
            self._dex_input    = ""
            self._lvl_input    = ""
            self._give_msg     = ""
            self._active_field = "dex"

    def _on_give_pokemon(self) -> None:
        from code.shared.models.pokemon import Pokemon
        try:
            dex_num = int(self._dex_input)
            level   = max(1, min(100, int(self._lvl_input or "5")))
        except ValueError:
            self._give_msg = "✗ Numéro / niveau invalide"
            return
        try:
            pkmn   = Pokemon.create_from_id(dex_num, level)
            result = self.player.inv.receive_pokemon(pkmn)
            name   = pkmn.dbSymbol.replace("_", " ").capitalize()
            dest   = "équipe" if result == "party" else "PC"
            self._give_msg = f"✓ {name} Nv.{level} → {dest}"
            self._dex_input = ""
            self._lvl_input = ""
        except Exception as exc:
            self._give_msg = f"✗ Erreur : {exc}"[:36]

    def handle_scroll(self, delta: int) -> None:
        if not self._show_items:
            return
        max_s = max(0, len(self._items_list) - self._max_vis)
        self._scroll = max(0, min(self._scroll + delta, max_s))
