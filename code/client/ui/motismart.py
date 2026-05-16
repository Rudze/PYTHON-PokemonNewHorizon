from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pygame

from code.client.config import MOTISMART_UI, SPRITES_BATTLE_DIR, FONTS_DIR
from code.client.core.controller import Controller
from code.client.core.keylistener import KeyListener
from code.client.core.screen import Screen
from code.server.managers.save_manager import Save
from code.client.ui.admin_menu import AdminMenu
from code.client.ui.animated_gif import AnimatedGif

_FONT_PATH = str(FONTS_DIR / "pokemon.ttf")

_TYPE_COLORS: dict[str, tuple] = {
    "normal": (168, 167, 122), "fire": (238, 129, 48),  "water": (99, 144, 240),
    "electric": (247, 208, 44), "grass": (122, 199, 76), "ice": (150, 217, 214),
    "fighting": (194, 46, 40), "poison": (163, 62, 161), "ground": (226, 191, 101),
    "flying": (169, 143, 243), "psychic": (249, 85, 135), "bug": (166, 185, 26),
    "rock": (182, 161, 100), "ghost": (115, 87, 151),   "dragon": (111, 53, 252),
    "dark": (112, 87, 70),   "steel": (183, 183, 206),  "fairy": (214, 133, 173),
}
_TYPE_FR: dict[str, str] = {
    "normal": "Normal", "fire": "Feu", "water": "Eau", "electric": "Electrik",
    "grass": "Plante", "ice": "Glace", "fighting": "Combat", "poison": "Poison",
    "ground": "Sol", "flying": "Vol", "psychic": "Psy", "bug": "Insecte",
    "rock": "Roche", "ghost": "Spectre", "dragon": "Dragon", "dark": "Tenebres",
    "steel": "Acier", "fairy": "Fee",
}


def _make_font(size: int) -> pygame.font.Font:
    try:
        return pygame.font.Font(_FONT_PATH, size)
    except Exception:
        return pygame.font.SysFont("arial", size)


_CAT_FR = {"physical": "Physique", "special": "Speciale", "status": "Statut"}

def _priority_fr(p: int) -> str:
    if p == 0:  return "Normale"
    if p > 0:   return f"Priorite +{p}"
    return f"Retard {p}"

_MOVE_DB: dict = {}   # dbSymbol → entry depuis move_data.json

def _get_move_db() -> dict:
    global _MOVE_DB
    if _MOVE_DB:
        return _MOVE_DB
    try:
        import json as _j
        from code.shared.config import JSON_DIR as _jd
        raw = _j.load(open(str(_jd / "move_data.json")))
        _MOVE_DB = {v["name"]: v for v in raw.values()}
    except Exception:
        pass
    return _MOVE_DB


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
# Marges exactes mesurées dans bg.png (300×432, zone écran 234×342) :
#   left/right : 33px → 33/300 ≈ 0.110
#   top/bottom : 45px → 45/432 ≈ 0.104
_GRID_PAD_LEFT   = 0.110
_GRID_PAD_RIGHT  = 0.110
_GRID_PAD_TOP    = 0.104
_GRID_PAD_BOTTOM = 0.104
_GRID_GAP        = 4      # px entre cellules
_GRID_X_OFFSET   = -4     # décalage horizontal de la grille app (px, négatif = gauche)
_STATS_X_OFFSET  = -6     # idem pour la page stats (cumulatif : -4 + -2)
_STATS_Y_OFFSET  =  1     # décalage vertical page stats (px vers le bas)

# Couleur des cellules vides
_CELL_BG  = (110, 110, 110, 55)   # gris semi-transparent
_CELL_BD  = (200, 200, 200, 80)   # contour gris clair


class Motismart:
    """
    Menu téléphone — touche X.
    Bas-gauche, animation slide-up à l'ouverture, slide-down à la fermeture.
    Contient une grille 3×5 pour les icônes d'applications.
    """

    _HEIGHT_RATIO  = 0.50
    _HEIGHT_MULT   = 1.30
    _X_MARGIN      = 16
    _X_SHIFT       = 16
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

        # Page stats Pokémon (None = pas affichée)
        self._poke_stats_page: _PokemonStatsPage | None = None

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

        # Page stats Pokémon — dessinée par-dessus la grille
        if self._poke_stats_page is not None:
            close = self._poke_stats_page.draw(
                self.screen.get_display(),
                self._draw_x, int(self._anim_y),
                self._bg_w, self._bg_h,
                dt, mouse_click,
            )
            if close:
                self._poke_stats_page = None
            # Les touches téléphone/Échap ferment le téléphone même avec la page ouverte
            if not self._closing:
                self._handle_input(None)   # None = pas de clic grille
            return

        # Menus d'apps (dessinés par-dessus le téléphone)
        if self._admin_menu.active:
            self._admin_menu.update(mouse_click)
            mouse_click = None   # consommé par le menu admin

        if not self._closing:
            self._handle_input(mouse_click)

    def check_inputs(self) -> None:
        pass

    def open_pokemon_stats(self, pkmn) -> None:
        """Ouvre le Motismart sur la page stats du Pokémon donné."""
        if not self._ready:
            self._build()
        self._poke_stats_page = _PokemonStatsPage(pkmn)

    def force_close(self) -> None:
        """Ferme immédiatement le Motismart sans animation."""
        self._do_close()

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
        gx = phone_x + int(bw * _GRID_PAD_LEFT) + _GRID_X_OFFSET
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
                    # Placeholder gris si pas d'icône
                    r = pygame.Rect(cx + 4, cy + 4, cell_w - 8, cell_h - 8 - 14)
                    pygame.draw.rect(disp, (110, 110, 110), r, border_radius=4)

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

        gx = phone_x + int(bw * _GRID_PAD_LEFT) + _GRID_X_OFFSET
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
        self._poke_stats_page   = None
        self.player.menu_option = False
        self.player.can_move    = True
        self._ready             = False
        self._closing           = False
        self._opening           = False
        self._last_tick         = 0.0


# ---------------------------------------------------------------------------
# Page stats Pokémon intégrée au Motismart
# ---------------------------------------------------------------------------

class _PokemonStatsPage:
    """
    S'affiche par-dessus la grille Motismart.
    Retourne True dans draw() quand le joueur clique sur le bouton X.
    5 onglets : Identite / Stats / EV / IV / Attaques.
    Sprite GIF anime en haut.
    """

    _TABS    = ["Id", "Stats", "EV", "IV", "Atk"]
    _TAB_H   = 34
    _CLOSE_W = 32

    def __init__(self, pkmn) -> None:
        self.pkmn  = pkmn
        self._page = 0
        self._gif: AnimatedGif | None = None
        self._fonts_ready = False
        self._f_hdr:   pygame.font.Font | None = None   # nom + niveau (grand)
        self._f_title: pygame.font.Font | None = None   # labels contenu
        self._f_val:   pygame.font.Font | None = None   # valeurs contenu
        self._f_tab:   pygame.font.Font | None = None   # onglets
        self._f_small: pygame.font.Font | None = None   # badges / tooltip
        self._hover_mv = None   # Move survolé pour le tooltip
        self._load_gif()

    # ------------------------------------------------------------------ GIF

    def _load_gif(self) -> None:
        pid   = getattr(self.pkmn, "id", None)
        shiny = bool(getattr(self.pkmn, "shiny", ""))
        if pid is None:
            return
        suffix = "s" if shiny else "n"
        for fname in (f"{pid}-front-{suffix}.gif", f"{pid}-front-n.gif"):
            path = SPRITES_BATTLE_DIR / fname
            if path.exists():
                gif = AnimatedGif(path)
                if gif.valid:
                    self._gif = gif
                    return

    # ---------------------------------------------------------------- Fonts

    def _build_fonts(self) -> None:
        if self._fonts_ready:
            return
        self._f_hdr   = _make_font(18)   # nom + niveau dans le header
        self._f_title = _make_font(16)   # labels des lignes de contenu
        self._f_val   = _make_font(16)   # valeurs des lignes de contenu
        self._f_tab   = _make_font(14)   # texte des onglets
        self._f_small = _make_font(13)   # badges de type + tooltip
        self._fonts_ready = True

    # ----------------------------------------------------------------- Draw

    def draw(
        self,
        disp: pygame.Surface,
        phone_x: int, phone_y: int,
        phone_w: int, phone_h: int,
        dt: float,
        mouse_click: tuple | None,
        mouse_pos: tuple | None = None,
    ) -> bool:
        """Retourne True si la page doit se fermer."""
        self._build_fonts()

        # Avance l'animation GIF
        if self._gif:
            self._gif.update(dt)

        # Zone de contenu (intérieur de l'écran du téléphone)
        pad_l = int(phone_w * _GRID_PAD_LEFT)
        pad_r = int(phone_w * _GRID_PAD_RIGHT)
        pad_t = int(phone_h * _GRID_PAD_TOP)
        pad_b = int(phone_h * _GRID_PAD_BOTTOM)

        cx = phone_x + pad_l + _STATS_X_OFFSET
        cy = phone_y + pad_t + _STATS_Y_OFFSET
        cw = phone_w - pad_l - pad_r
        ch = phone_h - pad_t - pad_b

        # Fond opaque par-dessus la grille
        bg = pygame.Surface((cw, ch), pygame.SRCALPHA)
        bg.fill((72, 72, 72, 255))
        disp.blit(bg, (cx, cy))
        pygame.draw.rect(disp, (180, 180, 180), (cx, cy, cw, ch), 1, border_radius=6)

        # Bouton X (haut-droite)
        close_rect = pygame.Rect(cx + cw - self._CLOSE_W - 2, cy + 2,
                                 self._CLOSE_W, self._CLOSE_W)
        pygame.draw.rect(disp, (160, 50, 50), close_rect, border_radius=4)
        if self._f_tab:
            xt = self._f_tab.render("X", True, (255, 255, 255))
            disp.blit(xt, xt.get_rect(center=close_rect.center))

        if mouse_click and close_rect.collidepoint(mouse_click):
            return True   # fermer

        # Onglets
        tabs_y  = cy + 2
        tab_w   = (cw - self._CLOSE_W - 6) // len(self._TABS)
        for i, name in enumerate(self._TABS):
            tx = cx + i * tab_w
            active = (i == self._page)
            ts = pygame.Surface((tab_w, self._TAB_H), pygame.SRCALPHA)
            ts.fill((110, 110, 110, 240) if active else (65, 65, 65, 200))
            disp.blit(ts, (tx, tabs_y))
            pygame.draw.rect(disp, (220, 220, 220) if active else (140, 140, 140),
                             (tx, tabs_y, tab_w, self._TAB_H), 1, border_radius=3)
            if self._f_tab:
                tt = self._f_tab.render(name, True,
                                        (255, 255, 255) if active else (180, 180, 180))
                disp.blit(tt, tt.get_rect(center=(tx + tab_w // 2,
                                                   tabs_y + self._TAB_H // 2)))
            if mouse_click and pygame.Rect(tx, tabs_y, tab_w, self._TAB_H).collidepoint(mouse_click):
                self._page = i

        content_y = tabs_y + self._TAB_H + 6

        # Sprite animé (haut de la zone de contenu)
        sprite_h = min(110, ch // 3)
        if self._gif:
            frame = self._gif.current_frame()
            if frame:
                sw, sh = frame.get_size()
                scale  = min(sprite_h / max(sh, 1), (cw // 2) / max(sw, 1))
                nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
                scaled = pygame.transform.smoothscale(frame, (nw, nh))
                disp.blit(scaled, scaled.get_rect(center=(cx + cw // 4,
                                                           content_y + sprite_h // 2)))

        # Level + types à droite du sprite
        rx = cx + cw // 2
        ry = content_y + 4
        name  = getattr(self.pkmn, "dbSymbol", "???").replace("_", " ").capitalize()
        level = getattr(self.pkmn, "level", 1)
        if self._f_hdr:
            nt = self._f_hdr.render(name, True, (255, 255, 255))
            disp.blit(nt, (rx, ry));  ry += nt.get_height() + 3
            lt = self._f_hdr.render(f"Nv. {level}", True, (255, 255, 255))
            disp.blit(lt, (rx, ry));  ry += lt.get_height() + 6

        for t in getattr(self.pkmn, "type", []):
            col    = _TYPE_COLORS.get(t.lower(), (100, 100, 100))
            fr_t   = _TYPE_FR.get(t.lower(), t.capitalize())
            tw, th = 82, 22
            ts = pygame.Surface((tw, th), pygame.SRCALPHA)
            ts.fill((*col, 210))
            disp.blit(ts, (rx, ry))
            pygame.draw.rect(disp, (0, 0, 0, 60), (rx, ry, tw, th), 1, border_radius=5)
            if self._f_small:
                tt = self._f_small.render(fr_t, True, (255, 255, 255))
                disp.blit(tt, tt.get_rect(center=(rx + tw // 2, ry + th // 2)))
            ry += th + 5

        # Statut
        status = getattr(self.pkmn, "status", "")
        if status and self._f_small:
            SC = {"PSN":(163,62,161),"TOX":(163,62,161),"BRN":(238,129,48),
                  "PAR":(247,208,44),"SLP":(130,130,150),"FRZ":(150,217,214)}
            st = self._f_small.render(status, True, SC.get(status, (200,200,200)))
            disp.blit(st, (rx, ry))

        # Séparateur
        sep_y = content_y + sprite_h + 4
        pygame.draw.line(disp, (50, 50, 100), (cx + 4, sep_y), (cx + cw - 4, sep_y))
        page_y = sep_y + 5

        pages = [self._pg_identity, self._pg_stats, self._pg_ev, self._pg_iv]
        if self._page < 4:
            pages[self._page](disp, cx + 4, page_y, cw - 8)
        else:
            self._pg_moves(disp, cx + 4, page_y, cw - 8,
                           mouse_pos or pygame.mouse.get_pos(), disp, cx, cy)

        return False

    # ---------------------------------------------------------------- Helpers

    def _row(self, disp, x, y, w, label, value, col=(255, 255, 255)):
        h = 0
        if self._f_title:
            lt = self._f_title.render(label, True, (255, 255, 255))
            disp.blit(lt, (x, y));  h = lt.get_height() + 2
        if self._f_val:
            vt = self._f_val.render(str(value), True, col)
            disp.blit(vt, (x + w - vt.get_width(), y))
        return h or 14

    def _bar_row(self, disp, x, y, w, label, val, max_val, col_bar=(80,160,255)):
        h = self._row(disp, x, y, w, label, val)
        bw = w;  bh = 9
        pygame.draw.rect(disp, (50, 50, 50), (x, y + h, bw, bh), border_radius=4)
        ratio = min(1.0, val / max(max_val, 1))
        if ratio > 0:
            pygame.draw.rect(disp, col_bar, (x, y + h, int(bw * ratio), bh), border_radius=4)
        return h + bh + 6

    # ------------------------------------------------------------------ Pages

    def _pg_identity(self, disp, x, y, w):
        p = self.pkmn
        xp_cur, xp_need = p.xp_progress() if hasattr(p, "xp_progress") else (0, 1)
        ability = getattr(p, "ability", None) or "---"
        ability_fr = str(ability).replace("-", " ").replace("_", " ").title()
        for lbl, val in [
            ("N Pokedex",  f"#{getattr(p,'id','?'):03d}" if isinstance(getattr(p,'id',0),int) else f"#{getattr(p,'id','?')}"),
            ("Nom",        getattr(p,"dbSymbol","?").replace("_"," ").capitalize()),
            ("Talent",     ability_fr),
            ("Dresseur",   getattr(p,"ot","") or "---"),
            ("EXP",        f"{getattr(p,'xp',0):,}".replace(","," ")),
            ("EXP (niv.)", f"{xp_cur:,}".replace(","," ")),
            ("Prochain",   f"{xp_need:,}".replace(","," ")),
        ]:
            y += self._row(disp, x, y, w, lbl, val)

    def _pg_stats(self, disp, x, y, w):
        p = self.pkmn
        hp, mhp = max(0,getattr(p,"hp",0)), max(1,getattr(p,"maxhp",1))
        y += self._bar_row(disp, x, y, w, f"PV  {hp}/{mhp}", hp, mhp,
                           col_bar=(50,200,70) if hp/mhp>0.5 else (230,180,30) if hp/mhp>0.2 else (220,50,50))
        hap = int(getattr(p,"happiness",0)/255*100)
        y += self._bar_row(disp, x, y, w, f"Bonheur  {hap}%", hap, 100, col_bar=(200,150,200))
        for lbl, attr in [("Attaque","atk"),("Defense","dfe"),
                           ("Atk Spe","ats"),("Def Spe","dfs"),("Vitesse","spd")]:
            y += self._row(disp, x, y, w, lbl, getattr(p, attr, "?"))

    def _pg_ev(self, disp, x, y, w):
        evs = getattr(self.pkmn,"trained_evs",{"hp":0,"atk":0,"dfe":0,"ats":0,"dfs":0,"spd":0})
        total = sum(evs.values())
        for lbl, k in [("PV","hp"),("Attaque","atk"),("Defense","dfe"),
                        ("Atk Spe","ats"),("Def Spe","dfs"),("Vitesse","spd")]:
            y += self._bar_row(disp, x, y, w, f"{lbl}  {evs.get(k,0)}", evs.get(k,0), 252,
                               col_bar=(100,200,100))
        if self._f_title:
            tt = self._f_title.render(f"Total : {total} / 510", True, (255, 255, 255))
            disp.blit(tt, (x, y))

    def _pg_iv(self, disp, x, y, w):
        ivs = getattr(self.pkmn,"ivs",{})
        for lbl, k in [("PV","hp"),("Attaque","atk"),("Defense","dfe"),
                        ("Atk Spe","ats"),("Def Spe","dfs"),("Vitesse","spd")]:
            v = ivs.get(k, 0)
            col = (100,220,100) if v==31 else (220,100,100) if v==0 else (150,180,255)
            y += self._bar_row(disp, x, y, w, f"{lbl}  {v}", v, 31,
                               col_bar=col)

    def _pg_moves(self, disp, x, y, w, mouse_pos, full_disp, panel_cx, panel_cy):
        pkmn  = self.pkmn
        moves = getattr(pkmn, "moves", [])
        db    = _get_move_db()

        if not moves:
            if self._f_val:
                t = self._f_val.render("Aucune attaque", True, (150, 150, 180))
                disp.blit(t, (x, y))
            return

        hovered_mv = None
        hovered_rect = None

        for mv in moves:
            sym   = getattr(mv, "dbSymbol", "???")
            entry = db.get(sym, {})
            name  = entry.get("name_fr") or sym.replace("-"," ").replace("_"," ").title()
            mtyp  = getattr(mv, "type", entry.get("type","normal"))
            cat   = getattr(mv, "category", entry.get("damage_class","physical"))
            pwr   = getattr(mv, "power",    entry.get("power", 0)) or "-"
            acc   = getattr(mv, "accuracy", entry.get("accuracy",100)) or "-"
            pp    = getattr(mv, "pp", entry.get("pp", 0))
            mxpp  = getattr(mv, "maxpp", pp)

            mh = 46
            card_rect = pygame.Rect(x, y, w, mh)
            tc = _TYPE_COLORS.get(mtyp.lower(), (80, 80, 80))

            # Fond de carte (surbrillance si survolée)
            hov = card_rect.collidepoint(mouse_pos)
            alpha = 90 if hov else 50
            ms = pygame.Surface((w, mh), pygame.SRCALPHA)
            ms.fill((*tc, alpha))
            disp.blit(ms, (x, y))
            pygame.draw.rect(disp, (*tc, 150 if hov else 100),
                             (x, y, w, mh), 2 if hov else 1, border_radius=5)

            if hov:
                hovered_mv   = mv
                hovered_rect = card_rect

            # Nom de l'attaque
            if self._f_title:
                nt = self._f_title.render(name[:20], True, (255, 255, 255))
                disp.blit(nt, (x + 5, y + 4))

            if self._f_small:
                # Badge type
                fr_t = _TYPE_FR.get(mtyp.lower(), mtyp.capitalize())
                tw2, th2 = 62, 17
                ts2 = pygame.Surface((tw2, th2), pygame.SRCALPHA)
                ts2.fill((*tc, 210))
                disp.blit(ts2, (x + 5, y + mh - th2 - 5))
                pygame.draw.rect(disp, (0,0,0,60),(x+5, y+mh-th2-5, tw2, th2),1,border_radius=3)
                tt2 = self._f_small.render(fr_t, True, (255, 255, 255))
                disp.blit(tt2, tt2.get_rect(center=(x+5+tw2//2, y+mh-th2-5+th2//2)))

                # Catégorie
                cat_fr = _CAT_FR.get(cat, cat.capitalize() if cat else "?")
                ct = self._f_small.render(cat_fr, True, (255, 255, 255))
                disp.blit(ct, (x + 5 + tw2 + 6, y + mh - ct.get_height() - 7))

                # PP
                pp_t = self._f_small.render(f"PP {pp}/{mxpp}", True, (255, 255, 255))
                disp.blit(pp_t, (x + w - pp_t.get_width() - 4, y + mh - pp_t.get_height() - 6))

            y += mh + 3

        # ── Tooltip au survol ──────────────────────────────────────────────
        if hovered_mv is not None:
            self._draw_move_tooltip(full_disp, hovered_mv, hovered_rect,
                                    panel_cx, panel_cy)

    def _draw_move_tooltip(self, disp, mv, card_rect, panel_cx, panel_cy):
        """Tooltip détaillé affiché à droite du panneau quand on survole une attaque."""
        db    = _get_move_db()
        sym   = getattr(mv, "dbSymbol", "???")
        entry = db.get(sym, {})

        name_fr = entry.get("name_fr") or sym.replace("-"," ").replace("_"," ").title()
        mtyp    = getattr(mv,"type",  entry.get("type","normal"))
        cat     = getattr(mv,"category", entry.get("damage_class","physical"))
        pwr     = getattr(mv,"power",    entry.get("power",0)) or "-"
        acc     = getattr(mv,"accuracy", entry.get("accuracy",100)) or "-"
        pp      = getattr(mv,"pp",    entry.get("pp",0))
        mxpp    = getattr(mv,"maxpp", pp)
        prio    = getattr(mv,"priority", entry.get("priority",0))
        chance  = entry.get("effect_chance", None)
        effect  = entry.get("effect", "")

        tc = _TYPE_COLORS.get(mtyp.lower(), (60, 60, 80))

        lines = [
            ("", name_fr, (255, 255, 255)),
            ("Type",     _TYPE_FR.get(mtyp.lower(), mtyp.capitalize()), (255, 255, 255)),
            ("Categorie", _CAT_FR.get(cat, cat), (255, 255, 255)),
            ("Puissance", str(pwr),               (255, 255, 255)),
            ("Precision", f"{acc}%"  if acc != "-" else "-", (255, 255, 255)),
            ("PP",        f"{pp}/{mxpp}",          (255, 255, 255)),
            ("Priorite",  _priority_fr(prio),      (255, 255, 255)),
        ]
        if chance:
            lines.append(("Chance", f"{chance}%", (255, 255, 255)))
        if effect:
            lines.append(("", effect, (255, 255, 255)))

        f = self._f_small
        if not f:
            return

        # Calcul dimensions du tooltip
        pad   = 8
        lh    = f.get_height() + 3
        tw    = 180
        th    = pad * 2 + len(lines) * lh

        # Positionner à droite du panneau phone (ou à gauche si pas de place)
        W, H = disp.get_size()
        tx   = panel_cx + 10   # légèrement à l'intérieur du bord droit
        ty   = max(4, min(card_rect.top, H - th - 4))
        if tx + tw > W - 4:
            tx = panel_cx - tw - 6

        # Fond
        bg = pygame.Surface((tw, th), pygame.SRCALPHA)
        bg.fill((70, 70, 70, 245))
        disp.blit(bg, (tx, ty))
        pygame.draw.rect(disp, (*tc, 200), (tx, ty, tw, th), 2, border_radius=6)

        iy = ty + pad
        for label, val, col in lines:
            if label:
                lt = f.render(f"{label}: {val}", True, col)
            else:
                lt = f.render(val[:26], True, col)
            disp.blit(lt, (tx + pad, iy))
            iy += lh
