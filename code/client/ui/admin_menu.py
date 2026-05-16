"""
admin_menu.py — Menu admin accessible depuis le Motismart.
Boutons : Objets, Soigner équipe, +100 P$, +1 Niveau, Donner Pokémon.

Formulaire Donner Pokémon :
  - Nom OU N° Pokédex   (lettres + chiffres)
  - Niveau              (1-100)
  - Shiny               (toggle Oui/Non)
  - Genre               (cycle Aléatoire / Mâle / Femelle)
  - OT                  (auto = nom du joueur, éditable)
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

_POKE_PANEL_W = 300

_LETTER_KEYS = {
    pygame.K_a:"a", pygame.K_b:"b", pygame.K_c:"c", pygame.K_d:"d",
    pygame.K_e:"e", pygame.K_f:"f", pygame.K_g:"g", pygame.K_h:"h",
    pygame.K_i:"i", pygame.K_j:"j", pygame.K_k:"k", pygame.K_l:"l",
    pygame.K_m:"m", pygame.K_n:"n", pygame.K_o:"o", pygame.K_p:"p",
    pygame.K_q:"q", pygame.K_r:"r", pygame.K_s:"s", pygame.K_t:"t",
    pygame.K_u:"u", pygame.K_v:"v", pygame.K_w:"w", pygame.K_x:"x",
    pygame.K_y:"y", pygame.K_z:"z",
    pygame.K_MINUS: "-", pygame.K_SPACE: "-",
}
_DIGIT_KEYS = {
    pygame.K_0:"0", pygame.K_1:"1", pygame.K_2:"2", pygame.K_3:"3",
    pygame.K_4:"4", pygame.K_5:"5", pygame.K_6:"6", pygame.K_7:"7",
    pygame.K_8:"8", pygame.K_9:"9",
    pygame.K_KP0:"0", pygame.K_KP1:"1", pygame.K_KP2:"2", pygame.K_KP3:"3",
    pygame.K_KP4:"4", pygame.K_KP5:"5", pygame.K_KP6:"6", pygame.K_KP7:"7",
    pygame.K_KP8:"8", pygame.K_KP9:"9",
}
_GENDER_CYCLE = ["aleatoire", "male", "female"]
_GENDER_LABELS = {"aleatoire": "Aléatoire", "male": "Mâle", "female": "Femelle"}


class AdminMenu:
    def __init__(self, screen, player, keylistener=None) -> None:
        self.screen       = screen
        self.player       = player
        self._keylistener = keylistener
        self.active       = False

        self._show_items     = False
        self._show_give_pkmn = False
        self._scroll         = 0
        self._max_vis        = 0

        # Champs du formulaire "Donner Pokémon"
        self._name_input:   str  = ""        # nom (dbSymbol) OU N° Pokédex
        self._lvl_input:    str  = ""        # niveau 1-100
        self._ot_input:     str  = ""        # original trainer (auto = player.name)
        self._shiny:        bool = False     # shiny toggle
        self._gender_idx:   int  = 0        # index dans _GENDER_CYCLE
        self._active_field: str  = "name"   # "name" | "lvl" | "ot"
        self._give_msg:     str  = ""

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
        bg.fill((72, 72, 72, 230))
        disp.blit(bg, (px, py))
        pygame.draw.rect(disp, (180, 180, 180), (px, py, _PANEL_W, panel_h), 2, border_radius=6)

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
            color = (130, 130, 130) if is_active else ((100, 160, 100) if hov else (85, 85, 85))
            pygame.draw.rect(disp, color, br, border_radius=6)
            pygame.draw.rect(disp, (210, 210, 210), br, 1, border_radius=6)
            if self._font_btn:
                lt = self._font_btn.render(label, True, (255, 255, 255))
                disp.blit(lt, lt.get_rect(center=br.center))
            main_btns.append((br, cb))

        if self._show_items:
            self._draw_items_panel(disp, H, px, _MARGIN, mx, my)

        if self._show_give_pkmn:
            self._draw_give_pkmn_panel(disp, px, py, mx, my, mouse_click)

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
        sbg.fill((72, 72, 72, 230))
        disp.blit(sbg, (sx, sy))
        pygame.draw.rect(disp, (180, 180, 180), (sx, sy, _ITEM_W, sub_h), 2, border_radius=6)

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
            pygame.draw.rect(disp, (180, 180, 180),
                             (sx + _ITEM_W - 5, ind_y, 3, ind_h), border_radius=2)

    # ------------------------------------------------------------------
    # Sous-panneau don de Pokémon
    # ------------------------------------------------------------------

    def _draw_give_pkmn_panel(self, disp, px, py, mx, my,
                               mouse_click: tuple | None) -> None:
        W       = _POKE_PANEL_W
        sx      = px - W - 8
        FIELD_H = 34
        LABEL_H = 20
        BTN_H   = 36
        MSG_H   = 22
        TOG_H   = 34
        pad     = 10

        # Hauteur : titre + 3 champs texte + 2 toggles + bouton + message
        panel_h = (_HEADER_H + pad
                   + (LABEL_H + FIELD_H + 6) * 3   # name, level, ot
                   + (LABEL_H + TOG_H + 6) * 2      # shiny, genre
                   + BTN_H + 8 + MSG_H + pad)

        bg = pygame.Surface((W, panel_h), pygame.SRCALPHA)
        bg.fill((72, 72, 72, 230))
        disp.blit(bg, (sx, py))
        pygame.draw.rect(disp, (180, 180, 180), (sx, py, W, panel_h), 2, border_radius=6)

        if self._font_title:
            t = self._font_title.render("Donner Pokemon", True, (255, 220, 60))
            disp.blit(t, (sx + pad, py + 10))
        pygame.draw.line(disp, (90, 90, 200),
                         (sx + 4, py + _HEADER_H - 4),
                         (sx + W - 4, py + _HEADER_H - 4))

        cy = py + _HEADER_H + pad

        # ── Champ Nom / N° Pokédex ───────────────────────────────────────
        cy = self._text_field(disp, sx, cy, W, pad, LABEL_H, FIELD_H,
                              "Nom ou N Pokedex :", self._name_input,
                              "name", mx, my, mouse_click)
        cy += 6

        # ── Champ Niveau ─────────────────────────────────────────────────
        cy = self._text_field(disp, sx, cy, W, pad, LABEL_H, FIELD_H,
                              "Niveau (1-100) :", self._lvl_input,
                              "lvl", mx, my, mouse_click)
        cy += 6

        # ── Champ OT ─────────────────────────────────────────────────────
        cy = self._text_field(disp, sx, cy, W, pad, LABEL_H, FIELD_H,
                              "OT (Dresseur) :", self._ot_input,
                              "ot", mx, my, mouse_click)
        cy += 6

        # ── Toggle Shiny ─────────────────────────────────────────────────
        if self._font:
            lt = self._font.render("Shiny :", True, (190, 190, 210))
            disp.blit(lt, (sx + pad, cy))
        cy += LABEL_H

        shiny_col = (180, 140, 0) if self._shiny else (50, 50, 80)
        shiny_lbl = "Oui (Shiny)" if self._shiny else "Non"
        shiny_r   = pygame.Rect(sx + pad, cy, W - pad * 2, TOG_H)
        hov_s     = shiny_r.collidepoint(mx, my)
        pygame.draw.rect(disp, (shiny_col[0]+20, shiny_col[1]+20, shiny_col[2]+20)
                         if hov_s else shiny_col, shiny_r, border_radius=5)
        pygame.draw.rect(disp, (200, 180, 50) if self._shiny else (80, 80, 130),
                         shiny_r, 1, border_radius=5)
        if self._font_btn:
            st = self._font_btn.render(shiny_lbl, True,
                                       (255, 230, 50) if self._shiny else (200, 200, 200))
            disp.blit(st, st.get_rect(center=shiny_r.center))
        if mouse_click and shiny_r.collidepoint(mouse_click):
            self._shiny = not self._shiny
        cy += TOG_H + 6

        # ── Cycle Genre ──────────────────────────────────────────────────
        if self._font:
            lt = self._font.render("Genre :", True, (190, 190, 210))
            disp.blit(lt, (sx + pad, cy))
        cy += LABEL_H

        gender_key = _GENDER_CYCLE[self._gender_idx]
        gender_lbl = _GENDER_LABELS[gender_key]
        gender_r   = pygame.Rect(sx + pad, cy, W - pad * 2, TOG_H)
        hov_g      = gender_r.collidepoint(mx, my)
        GCOLS = {"aleatoire": (50,50,80), "male": (30,80,160), "female": (160,50,100)}
        gc = GCOLS[gender_key]
        pygame.draw.rect(disp, (gc[0]+20,gc[1]+20,gc[2]+20) if hov_g else gc,
                         gender_r, border_radius=5)
        pygame.draw.rect(disp, (200,200,200), gender_r, 1, border_radius=5)
        if self._font_btn:
            gt2 = self._font_btn.render(f"< {gender_lbl} >", True, (240, 240, 255))
            disp.blit(gt2, gt2.get_rect(center=gender_r.center))
        if mouse_click and gender_r.collidepoint(mouse_click):
            self._gender_idx = (self._gender_idx + 1) % len(_GENDER_CYCLE)
        cy += TOG_H + 8

        # ── Bouton Donner ────────────────────────────────────────────────
        give_r = pygame.Rect(sx + pad, cy, W - pad * 2, BTN_H)
        hov_b  = give_r.collidepoint(mx, my)
        pygame.draw.rect(disp, (60,180,60) if hov_b else (30,120,30), give_r, border_radius=6)
        pygame.draw.rect(disp, (80,220,80), give_r, 1, border_radius=6)
        if self._font_btn:
            dt = self._font_btn.render("Donner  [Entree]", True, (255, 255, 255))
            disp.blit(dt, dt.get_rect(center=give_r.center))
        cy += BTN_H + 8

        # ── Message résultat ─────────────────────────────────────────────
        if self._give_msg and self._font:
            ok  = self._give_msg.startswith("OK")
            col = (80, 220, 80) if ok else (220, 80, 80)
            mt  = self._font.render(self._give_msg[:42], True, col)
            disp.blit(mt, (sx + pad, cy))

        if mouse_click and give_r.collidepoint(mouse_click):
            self._on_give_pokemon()

    def _text_field(self, disp, sx, cy, W, pad, label_h, field_h,
                    label, value, field_id, mx, my, mouse_click) -> int:
        if self._font:
            lt = self._font.render(label, True, (190, 190, 210))
            disp.blit(lt, (sx + pad, cy))
        cy += label_h

        field_rect = pygame.Rect(sx + pad, cy, W - pad * 2, field_h)
        active = (self._active_field == field_id)
        pygame.draw.rect(disp, (95, 95, 95) if active else (65, 65, 65), field_rect, border_radius=4)
        pygame.draw.rect(disp, (220, 220, 220) if active else (150, 150, 150), field_rect, 2, border_radius=4)

        display = value[-28:] + ("|" if active else "")
        if self._font_btn:
            vt = self._font_btn.render(display, True, (255, 255, 255))
            disp.blit(vt, (field_rect.x + 6, field_rect.y + (field_h - vt.get_height()) // 2))

        if mouse_click and field_rect.collidepoint(mouse_click):
            self._active_field = field_id

        return cy + field_h

    # ------------------------------------------------------------------
    # Saisie clavier
    # ------------------------------------------------------------------

    def _handle_text_input(self) -> None:
        if not self._keylistener:
            return

        kl = self._keylistener
        af = self._active_field

        # Backspace
        if kl.key_pressed(pygame.K_BACKSPACE):
            kl.remove_key(pygame.K_BACKSPACE)
            if af == "name": self._name_input = self._name_input[:-1]
            elif af == "lvl": self._lvl_input = self._lvl_input[:-1]
            elif af == "ot":  self._ot_input  = self._ot_input[:-1]
            return

        # Entrée → donner
        for enter_key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if kl.key_pressed(enter_key):
                kl.remove_key(enter_key)
                self._on_give_pokemon()
                return

        # Tab → champ suivant
        if kl.key_pressed(pygame.K_TAB):
            kl.remove_key(pygame.K_TAB)
            fields = ["name", "lvl", "ot"]
            idx = fields.index(af) if af in fields else 0
            self._active_field = fields[(idx + 1) % len(fields)]
            return

        # Chiffres (tous champs)
        for key, char in _DIGIT_KEYS.items():
            if kl.key_pressed(key):
                kl.remove_key(key)
                if af == "name" and len(self._name_input) < 30:
                    self._name_input += char
                elif af == "lvl" and len(self._lvl_input) < 3:
                    self._lvl_input += char
                elif af == "ot" and len(self._ot_input) < 16:
                    self._ot_input += char
                return

        # Lettres (name + ot)
        if af in ("name", "ot"):
            mods = pygame.key.get_mods()
            shift = bool(mods & pygame.KMOD_SHIFT)
            for key, char in _LETTER_KEYS.items():
                if kl.key_pressed(key):
                    kl.remove_key(key)
                    c = char.upper() if shift else char
                    if af == "name" and len(self._name_input) < 30:
                        self._name_input += c
                    elif af == "ot" and len(self._ot_input) < 16:
                        self._ot_input += c
                    return

    # ------------------------------------------------------------------
    # Callbacks
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
            self._name_input   = ""
            self._lvl_input    = ""
            # Auto-remplir OT avec le nom du joueur
            self._ot_input     = getattr(getattr(self.player, "name", None), "__str__",
                                         lambda: "")() or getattr(self.player, "name", "") or ""
            self._shiny        = False
            self._gender_idx   = 0
            self._give_msg     = ""
            self._active_field = "name"

    def _on_give_pokemon(self) -> None:
        from code.shared.models.pokemon import Pokemon
        import random as _random

        raw = self._name_input.strip()
        if not raw:
            self._give_msg = "Entrez un nom ou N Pokedex"
            return

        try:
            level = max(1, min(100, int(self._lvl_input or "5")))
        except ValueError:
            self._give_msg = "Niveau invalide (1-100)"
            return

        try:
            # Tenter par numéro Pokédex d'abord, sinon par nom
            if raw.isdigit():
                pkmn = Pokemon.create_from_id(int(raw), level)
            else:
                pkmn = Pokemon.create_pokemon(raw.lower(), level)
        except Exception as exc:
            self._give_msg = f"Introuvable : {raw}"
            return

        # Appliquer shiny
        pkmn.shiny = "shiny" if self._shiny else ""

        # Appliquer genre
        gender_key = _GENDER_CYCLE[self._gender_idx]
        if gender_key == "male":
            pkmn.gender = "male"
        elif gender_key == "female":
            pkmn.gender = "female"
        # "aleatoire" → déjà tiré dans __init__, on ne change rien

        # Appliquer OT
        ot = self._ot_input.strip()
        if not ot:
            ot = getattr(self.player, "name", "") or ""
        pkmn.ot = ot

        try:
            result = self.player.inv.receive_pokemon(pkmn)
            name   = pkmn.dbSymbol.replace("_", " ").capitalize()
            shiny_tag = " [S]" if pkmn.shiny else ""
            dest  = "equipe" if result == "party" else "PC"
            self._give_msg = f"OK {name}{shiny_tag} Nv.{level} -> {dest}"
            self._name_input = ""
            self._lvl_input  = ""
        except Exception as exc:
            self._give_msg = f"Erreur : {exc}"

    def handle_scroll(self, delta: int) -> None:
        if not self._show_items:
            return
        max_s = max(0, len(self._items_list) - self._max_vis)
        self._scroll = max(0, min(self._scroll + delta, max_s))
