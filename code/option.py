from __future__ import annotations

import pygame

from controller import Controller
from inventory_manager import (
    POCKET_ITEMS, POCKET_POKEBALLS, POCKET_TM_HM, POCKET_KEY_ITEMS
)
from keylistener import KeyListener
from map import Map
from player import Player
from pokemon import Pokemon
from save import Save
from screen import Screen
from tool import Tool
from dialogue import Dialogue

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
C_PANEL     = (18, 30, 45)
C_PANEL_BD  = (55, 95, 135)
C_BTN       = (32, 65, 105)
C_BTN_HOV   = (50, 95, 145)
C_BTN_ACT   = (28, 105, 72)
C_BTN_ACT_H = (40, 140, 95)
C_BTN_RED    = (130, 35, 35)
C_BTN_RED_H  = (170, 55, 55)
C_BTN_SYNC   = (130, 90, 15)
C_BTN_SYNC_H = (170, 120, 20)
C_TEXT      = (220, 235, 248)
C_TEXT_DIM  = (110, 135, 158)
C_HP_OK     = (55, 195, 75)
C_HP_WARN   = (215, 155, 35)
C_HP_CRIT   = (215, 55, 55)
C_SLOT_BG   = (25, 42, 62)
C_SLOT_BD   = (48, 78, 108)
C_SLOT_EMPTY_BG = (13, 22, 33)

POCKET_LABELS = {
    POCKET_ITEMS:     "Objets",
    POCKET_POKEBALLS: "Poké Balls",
    POCKET_TM_HM:     "CT / CS",
    POCKET_KEY_ITEMS:  "Objets clés",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _draw_panel(surf: pygame.Surface, rect: pygame.Rect,
                bg=C_PANEL, border=C_PANEL_BD, radius=8, bd=2) -> None:
    pygame.draw.rect(surf, border, rect, border_radius=radius)
    pygame.draw.rect(surf, bg, rect.inflate(-bd * 2, -bd * 2), border_radius=max(0, radius - bd))


class _Btn:
    """Lightweight clickable button."""

    def __init__(self, rect: pygame.Rect, label: str,
                 color=C_BTN, hover=C_BTN_HOV) -> None:
        self.rect   = rect
        self.label  = label
        self.color  = color
        self.hover  = hover

    def draw(self, surf: pygame.Surface, font: pygame.font.Font,
             mouse: tuple[int, int], active: bool = False) -> None:
        c = C_BTN_ACT if active else (self.hover if self.rect.collidepoint(mouse) else self.color)
        _draw_panel(surf, self.rect, bg=c, border=C_PANEL_BD, radius=6)
        txt = font.render(self.label, True, C_TEXT)
        surf.blit(txt, txt.get_rect(center=self.rect.center))

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


# ---------------------------------------------------------------------------
# Option — menu hub
# ---------------------------------------------------------------------------

class Option:
    """
    Menu Échap — hub visuel pour Sac, Équipe et PC.

    game.py doit passer mouse_click à update() :
        self.option.update(self.mouse_click)
        self.mouse_click = None
    """

    _VIEWS = ("bag", "party", "pc")

    def __init__(self, screen: Screen, controller: Controller, map: Map,
                 language: str, save: Save, keylistener: KeyListener,
                 dialogue: Dialogue) -> None:
        self.screen     = screen
        self.controller = controller
        self.map        = map
        self.language   = language
        self.save       = save
        self.player: Player = map.player
        self.keylistener    = keylistener
        self.dialogue       = dialogue

        self.initialization = False
        self.image_background: pygame.Surface | None = None
        self.active_view: str | None = None

        # fonts — created in _initialize()
        self._ft: dict[str, pygame.font.Font] = {}

        # geometry — updated in _initialize()
        self._panel  = pygame.Rect(0, 0, 0, 0)
        self._content = pygame.Rect(0, 0, 0, 0)

        # button registries
        self._nav:    dict[str, _Btn] = {}
        self._action: dict[str, _Btn] = {}
        self._close_btn: _Btn | None  = None

        # dynamic per-view click targets (rebuilt each draw)
        self._bag_plus:    list[tuple[str, str, pygame.Rect]] = []
        self._bag_quick:   list[tuple[str, str, pygame.Rect]] = []
        self._party_heal:  pygame.Rect | None = None
        self._capture_btn: _Btn | None = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def update(self, mouse_click: tuple[int, int] | None = None) -> None:
        if not self.initialization:
            self._initialize()
            self.initialization = True

        self._draw()

        if mouse_click:
            self._handle_click(mouse_click)

        self._check_end()

    def check_inputs(self) -> None:
        if self.keylistener.key_pressed(self.controller.get_key("action")):
            self.save.save()
            self.keylistener.remove_key(self.controller.get_key("action"))

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        self.image_background = Tool.blur(self.screen.image_screen(), 2)

        W, H = self.screen.get_size()
        PAD = 36
        self._panel   = pygame.Rect(PAD, PAD, W - PAD * 2, H - PAD * 2)
        self._content = pygame.Rect(
            self._panel.x + 12,
            self._panel.y + 68,
            self._panel.width - 24,
            self._panel.height - 80,
        )

        try:
            self._ft["title"] = pygame.font.SysFont("segoeui", 20, bold=True)
            self._ft["body"]  = pygame.font.SysFont("segoeui", 16)
            self._ft["small"] = pygame.font.SysFont("segoeui", 13)
        except Exception:
            f = pygame.font.Font(None, 20)
            self._ft = {"title": f, "body": f, "small": f}

        self._build_buttons()

    def _build_buttons(self) -> None:
        px, py = self._panel.x, self._panel.y
        pw = self._panel.width

        # Nav
        nav_defs = [("bag", "SAC"), ("party", "ÉQUIPE"), ("pc", "PC")]
        bw, bh, gap = 120, 36, 8
        bx = px + 12
        for key, label in nav_defs:
            self._nav[key] = _Btn(pygame.Rect(bx, py + 16, bw, bh), label)
            bx += bw + gap

        # Actions (right side) — SOIGNER | SAUVEGARDER | FORCE SYNC
        ax = px + pw - 380
        ay = py + 16
        self._action["heal"] = _Btn(
            pygame.Rect(ax, ay, 110, bh), "SOIGNER", C_BTN_ACT, C_BTN_ACT_H
        )
        self._action["save"] = _Btn(
            pygame.Rect(ax + 118, ay, 120, bh), "SAUVEGARDER"
        )
        self._action["sync"] = _Btn(
            pygame.Rect(ax + 248, ay, 120, bh), "FORCE SYNC", C_BTN_SYNC, C_BTN_SYNC_H
        )

        # Close ✕
        self._close_btn = _Btn(
            pygame.Rect(px + pw - 32, py + 6, 26, 26), "✕", (90, 28, 28), (150, 48, 48)
        )

    # ------------------------------------------------------------------
    # Main draw dispatcher
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        disp  = self.screen.get_display()
        W, H  = self.screen.get_size()
        mouse = pygame.mouse.get_pos()

        # Blurred BG + overlay
        disp.blit(self.image_background, (0, 0))
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        disp.blit(ov, (0, 0))

        # Panel
        _draw_panel(disp, self._panel, radius=10)

        # Buttons
        for key, btn in self._nav.items():
            btn.draw(disp, self._ft["title"], mouse, active=(self.active_view == key))
        for btn in self._action.values():
            btn.draw(disp, self._ft["body"], mouse)
        if self._close_btn:
            self._close_btn.draw(disp, self._ft["body"], mouse)

        # Separator line under nav
        sep_y = self._panel.y + 60
        pygame.draw.line(disp, C_PANEL_BD,
                         (self._panel.x + 12, sep_y),
                         (self._panel.right - 12, sep_y), 1)

        # Content
        view = self.active_view
        if view == "bag":
            self._draw_bag(disp, mouse)
        elif view == "party":
            self._draw_party(disp, mouse)
        elif view == "pc":
            self._draw_pc(disp, mouse)
        else:
            self._draw_hub(disp)

    # ------------------------------------------------------------------
    # Hub (home screen)
    # ------------------------------------------------------------------

    def _draw_hub(self, surf: pygame.Surface) -> None:
        inv = self.player.inv
        cr  = self._content
        ft  = self._ft

        api_ok   = inv.api_client is not None and inv.account_id is not None
        api_lbl  = f"API connectée  (account_id={inv.account_id})" if api_ok else "API non configurée — mode local"
        api_col  = (60, 200, 80) if api_ok else (215, 100, 35)

        pc_count = sum(1 for b in inv.pc.boxes.values() for p in b if p is not None)

        lines: list[tuple[str, str, tuple]] = [
            ("Menu Principal", "title", C_TEXT),
            ("", "body", C_TEXT),
            (f"Pokémon en équipe : {len(inv.party)} / 6", "body", C_TEXT),
            (f"Pokémon au PC     : {pc_count}", "body", C_TEXT),
            (f"Pokédollars       : {self.player.pokedollars} ₽", "body", C_TEXT),
            ("", "body", C_TEXT),
            (api_lbl, "small", api_col),
            ("", "body", C_TEXT),
            ("Clique sur SAC, ÉQUIPE ou PC pour ouvrir la vue correspondante.", "small", C_TEXT_DIM),
            ("SOIGNER      — restaure tous les PV de l'équipe.", "small", C_TEXT_DIM),
            ("SAUVEGARDER  — sauvegarde locale + envoi API.", "small", C_TEXT_DIM),
            ("FORCE SYNC   — vide l'inventaire local et recharge depuis l'API.", "small", C_TEXT_DIM),
            ("", "body", C_TEXT),
            ("ÉCHAP / ✕    — fermer ce menu.", "small", C_TEXT_DIM),
        ]
        y = cr.y + 14
        for text, size, color in lines:
            t = ft[size].render(text, True, color)
            surf.blit(t, (cr.x + 20, y))
            y += ft[size].get_height() + 6

    # ------------------------------------------------------------------
    # Bag view
    # ------------------------------------------------------------------

    def _draw_bag(self, surf: pygame.Surface, mouse: tuple[int, int]) -> None:
        cr  = self._content
        inv = self.player.inv
        ft  = self._ft

        self._bag_plus.clear()
        self._bag_quick.clear()

        pockets = list(POCKET_LABELS.items())
        half = len(pockets) // 2
        col_w = (cr.width - 20) // 2

        for idx, (pocket, label) in enumerate(pockets):
            col = idx % 2
            row = idx // 2
            cx = cr.x + 10 + col * col_w
            cy = cr.y + 10 + row * 160

            # Pocket header
            h = ft["title"].render(label, True, C_TEXT)
            surf.blit(h, (cx, cy))
            pygame.draw.line(surf, C_PANEL_BD, (cx, cy + 24), (cx + col_w - 16, cy + 24), 1)

            items = inv.bag.pockets.get(pocket, [])
            iy = cy + 30

            if not items:
                t = ft["small"].render("— vide —", True, C_TEXT_DIM)
                surf.blit(t, (cx + 10, iy))
                iy += 20

            for item in items:
                row_txt = f"{item.item_db_symbol}  ×{item.quantity}"
                t = ft["small"].render(row_txt, True, C_TEXT)
                surf.blit(t, (cx + 8, iy + 2))

                # [+] button
                plus = pygame.Rect(cx + col_w - 30, iy, 22, 22)
                pc = C_BTN_HOV if plus.collidepoint(mouse) else C_BTN
                _draw_panel(surf, plus, bg=pc, border=C_PANEL_BD, radius=4, bd=1)
                pt = ft["small"].render("+", True, C_TEXT)
                surf.blit(pt, pt.get_rect(center=plus.center))
                self._bag_plus.append((item.item_db_symbol, pocket, plus))
                iy += 24

        # Quick-add row at bottom
        qa_y = cr.bottom - 44
        quick = [
            ("potion",    POCKET_ITEMS,     "+5 Potion"),
            ("poke_ball", POCKET_POKEBALLS, "+10 Poké Ball"),
            ("tm01",      POCKET_TM_HM,    "+1 CT01"),
        ]
        bx = cr.x + 10
        for sym, pocket, lbl in quick:
            r = pygame.Rect(bx, qa_y, 150, 32)
            c = C_BTN_HOV if r.collidepoint(mouse) else C_BTN
            _draw_panel(surf, r, bg=c, border=C_PANEL_BD, radius=6)
            t = ft["small"].render(lbl, True, C_TEXT)
            surf.blit(t, t.get_rect(center=r.center))
            self._bag_quick.append((sym, pocket, r))
            bx += 158

    # ------------------------------------------------------------------
    # Party view
    # ------------------------------------------------------------------

    def _draw_party(self, surf: pygame.Surface, mouse: tuple[int, int]) -> None:
        cr  = self._content
        inv = self.player.inv
        ft  = self._ft

        cols, rows = 3, 2
        gap   = 12
        card_w = (cr.width  - gap * (cols + 1)) // cols
        card_h = (cr.height - gap * (rows + 1) - 50) // rows

        for i in range(6):
            col = i % cols
            row = i // cols
            sx = cr.x + gap + col * (card_w + gap)
            sy = cr.y + gap + row * (card_h + gap)
            card = pygame.Rect(sx, sy, card_w, card_h)

            if i < len(inv.party):
                poke = inv.party[i]
                _draw_panel(surf, card, bg=C_SLOT_BG, border=C_SLOT_BD, radius=8)

                # Name + level
                nt = ft["body"].render(
                    f"#{i+1}  {poke.dbSymbol.capitalize()}  Nv.{poke.level}", True, C_TEXT
                )
                surf.blit(nt, (sx + 8, sy + 8))

                # HP bar
                ratio = max(0.0, poke.hp / poke.maxhp) if poke.maxhp else 0
                bar_bg  = pygame.Rect(sx + 8, sy + 34, card_w - 16, 10)
                bar_fill = pygame.Rect(sx + 8, sy + 34, int((card_w - 16) * ratio), 10)
                pygame.draw.rect(surf, (15, 15, 15), bar_bg,  border_radius=3)
                hp_col = C_HP_OK if ratio > 0.5 else (C_HP_WARN if ratio > 0.2 else C_HP_CRIT)
                pygame.draw.rect(surf, hp_col, bar_fill, border_radius=3)

                hp_t = ft["small"].render(f"PV {poke.hp}/{poke.maxhp}", True, C_TEXT_DIM)
                surf.blit(hp_t, (sx + 8, sy + 48))

                # Status + types
                st_lbl = poke.status if poke.status else "OK"
                st_col = (215, 115, 35) if poke.status else C_HP_OK
                st_t   = ft["small"].render(st_lbl, True, st_col)
                surf.blit(st_t, (sx + 8, sy + card_h - 22))

                ty_str = " / ".join(t.replace("__undef__", "") for t in poke.type if t != "__undef__")
                ty_t = ft["small"].render(ty_str, True, C_TEXT_DIM)
                surf.blit(ty_t, (sx + card_w - ty_t.get_width() - 8, sy + card_h - 22))

            else:
                _draw_panel(surf, card, bg=C_SLOT_EMPTY_BG, border=C_SLOT_BD, radius=8)
                et = ft["small"].render("— vide —", True, C_TEXT_DIM)
                surf.blit(et, et.get_rect(center=card.center))

        # Heal button at bottom
        hbr = pygame.Rect(cr.x + 10, cr.bottom - 42, 180, 32)
        hc  = C_BTN_ACT_H if hbr.collidepoint(mouse) else C_BTN_ACT
        _draw_panel(surf, hbr, bg=hc, border=C_PANEL_BD, radius=6)
        ht = ft["body"].render("SOIGNER TOUT", True, C_TEXT)
        surf.blit(ht, ht.get_rect(center=hbr.center))
        self._party_heal = hbr

    # ------------------------------------------------------------------
    # PC view
    # ------------------------------------------------------------------

    def _draw_pc(self, surf: pygame.Surface, mouse: tuple[int, int]) -> None:
        cr  = self._content
        inv = self.player.inv
        ft  = self._ft

        box = inv.pc.boxes.get(0, [None] * 30)

        # Title
        title_t = ft["title"].render("PC — Boîte 1", True, C_TEXT)
        surf.blit(title_t, (cr.x + 10, cr.y + 8))

        # Grid 5 × 6
        cols, rows  = 5, 6
        gap  = 6
        grid_top = cr.y + 36
        grid_h   = cr.height - 90
        cell_w = (cr.width - 20 - gap * (cols - 1)) // cols
        cell_h = (grid_h   - gap * (rows - 1)) // rows

        for slot in range(min(cols * rows, 30)):
            col = slot % cols
            row = slot // cols
            cx  = cr.x + 10 + col * (cell_w + gap)
            cy  = grid_top  + row * (cell_h + gap)
            cell = pygame.Rect(cx, cy, cell_w, cell_h)

            occupied = slot < len(box) and box[slot] is not None
            bg = C_SLOT_BG if occupied else C_SLOT_EMPTY_BG
            bd = C_SLOT_BD if occupied else (38, 58, 78)
            _draw_panel(surf, cell, bg=bg, border=bd, radius=6)

            if occupied:
                poke = box[slot]
                name = poke.dbSymbol[:9].capitalize()
                nt   = ft["small"].render(name, True, C_TEXT)
                surf.blit(nt, nt.get_rect(centerx=cell.centerx, y=cell.y + 4))
                lvl  = ft["small"].render(f"Nv{poke.level}", True, C_TEXT_DIM)
                surf.blit(lvl, lvl.get_rect(centerx=cell.centerx, y=cell.y + cell_h - 18))
            else:
                dot = ft["small"].render("·", True, (40, 60, 80))
                surf.blit(dot, dot.get_rect(center=cell.center))

        # [CAPTURER] button
        cap_r = pygame.Rect(cr.x + 10, cr.bottom - 42, 220, 32)
        if self._capture_btn is None:
            self._capture_btn = _Btn(cap_r, "CAPTURER Pikachu nv.10", C_BTN_RED, C_BTN_RED_H)
        else:
            self._capture_btn.rect = cap_r
        self._capture_btn.draw(surf, ft["body"], mouse)

        # PC stats
        total = sum(
            1 for bx in inv.pc.boxes.values()
            for p in bx if p is not None
        )
        stats_t = ft["small"].render(f"Pokémon stockés : {total}", True, C_TEXT_DIM)
        surf.blit(stats_t, (cap_r.right + 16, cap_r.centery - stats_t.get_height() // 2))

    # ------------------------------------------------------------------
    # Click routing
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> None:
        inv = self.player.inv

        if self._close_btn and self._close_btn.hit(pos):
            self._close_menu()
            return

        for key, btn in self._nav.items():
            if btn.hit(pos):
                self.active_view = key if self.active_view != key else None
                return

        if self._action["heal"].hit(pos):
            inv.heal_party()
            print("[GUI] Équipe soignée")
            return

        if self._action["save"].hit(pos):
            self.save.save()
            inv.save_all()
            print("[GUI] Sauvegarde effectuée")
            return

        if self._action["sync"].hit(pos):
            print("[GUI] FORCE SYNC demandé...")
            ok = inv.reload_from_api()
            if ok:
                print("[GUI] FORCE SYNC : inventaire rechargé depuis l'API avec succès.")
            else:
                print("[GUI] FORCE SYNC : échec (API indisponible ou pas de client configuré).")
            return

        if self.active_view == "bag":
            self._click_bag(pos, inv)

        elif self.active_view == "party":
            if self._party_heal and self._party_heal.collidepoint(pos):
                inv.heal_party()
                print("[GUI] Équipe soignée")

        elif self.active_view == "pc":
            if self._capture_btn and self._capture_btn.hit(pos):
                poke = Pokemon.create_pokemon("Pikachu", 10)
                dest = inv.receive_pokemon(poke)
                print(f"[GUI] Capture Pikachu nv.10 → {dest}")

    def _click_bag(self, pos, inv) -> None:
        # [+] buttons on individual items
        for sym, pocket, rect in self._bag_plus:
            if rect.collidepoint(pos):
                qty = 10 if pocket == POCKET_POKEBALLS else 5
                inv.add_item(sym, pocket, qty)
                print(f"[GUI] +{qty}× {sym} ({pocket})")
                return

        # Quick-add buttons
        for sym, pocket, rect in self._bag_quick:
            if rect.collidepoint(pos):
                qty = 10 if pocket == POCKET_POKEBALLS else 1
                inv.add_item(sym, pocket, qty)
                print(f"[GUI] Quick-add {qty}× {sym} ({pocket})")
                return

    # ------------------------------------------------------------------
    # Menu close / end check
    # ------------------------------------------------------------------

    def _close_menu(self) -> None:
        self.initialization = False
        self.active_view    = None
        self.player.menu_option = False

    def _check_end(self) -> None:
        if self.dialogue.active:
            return
        if self.keylistener.key_pressed(self.controller.get_key("quit")):
            self.keylistener.remove_key(self.controller.get_key("quit"))
            self._close_menu()
