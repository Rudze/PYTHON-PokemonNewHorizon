"""BattleScreen — panel dimensionné sur le background, UI assets."""
from __future__ import annotations
import time
import pygame
from PIL import Image
from code.config import SPRITES_BATTLE_DIR, BATTLE_ZONE, BATTLE_UI, MOVE_TYPE_ROW, FONTS_DIR
from code.ui.components.text_box import TextBox

# Boutons de commande : fight=0, party=1, bag=2, run=3
_CMD_LABELS  = ["FIGHT", "PARTY", "BAG", "RUN"]
_CMD_FRAMES  = 10   # 1 idle + 9 animation
_CMD_CELL_W  = 138
_CMD_CELL_H  = 44
_CMD_ANIM_FPS = 0.06   # secondes par frame d'animation

# Boutons d'attaque
_BTN_CELL_W = 243
_BTN_CELL_H = 44


def _mk_font(size: int) -> pygame.font.Font:
    try:    return pygame.font.Font(str(FONTS_DIR / "pokemon2.ttf"), size)
    except: return pygame.font.SysFont("arial", size)


_TEXT      = (255, 255, 255)
_TEXT_DIM  = (180, 180, 180)
_TEXT_BTN  = (255, 255, 255)
_HP_BG     = (80,  80,  80)
_HP_OK     = (56,  200, 72)
_HP_MED    = (220, 180, 40)
_HP_LOW    = (220, 60,  60)
_EXP_COLOR = (80,  140, 220)


class BattleScreen:

    def __init__(self, screen, wild_data: dict, player_pokemon=None, zone: str = None) -> None:
        self._screen         = screen
        self._wild           = wild_data
        self._player_pokemon = player_pokemon
        self._active         = True
        self._state          = "TEXT"   # TEXT → MENU → MOVE_SELECT
        self._move_idx       = 0
        self._intro_progress = 0.0
        self._last_tick      = time.time()

        sw, sh = screen.get_size()

        # --- Dimensions panel calées sur le background ---
        zone_cfg = BATTLE_ZONE.get(zone or "") or BATTLE_ZONE["default"]
        bg_path  = zone_cfg["background"]
        self._pw, self._ph = _panel_size_from_bg(bg_path, int(sw * 0.68), int(sh * 0.68))
        self._px = (sw - self._pw) // 2
        self._py = (sh - self._ph) // 2

        self._panel = pygame.Surface((self._pw, self._ph), pygame.SRCALPHA)

        self._f_title = _mk_font(14)
        self._f_body  = _mk_font(13)
        self._f_small = _mk_font(10)

        self._bg_surf = _load_battleback(bg_path, self._pw, self._ph)

        # --- Boîte ennemi (haut gauche) ---
        eb_w = int(self._pw * 0.40)
        self._enemy_box = _load_ui(BATTLE_UI["enemy_box"], (eb_w, int(eb_w * 0.20)))

        # --- Boutons de commande (bas gauche, stacked au-dessus de la player box) ---
        self._cb_w     = int(self._pw * 0.23)
        self._cb_h     = int(_CMD_CELL_H * self._cb_w / _CMD_CELL_W)
        self._cb_gap   = 4
        self._cb_sheet = _load_raw(BATTLE_UI["command_buttons"])
        # Navigation commande : index linéaire 0-3
        self._cmd_idx        = 0
        self._cmd_anim_frame = 1          # frame courante (1-9)
        self._cmd_anim_tick  = time.time()

        # --- Boîte joueur (bas gauche absolu) ---
        pb_w = int(self._pw * 0.42)
        pb_h = int(pb_w * 0.295)
        self._pb_h       = pb_h
        self._player_box = _load_ui(BATTLE_UI["player_box"], (pb_w, pb_h))
        self._player_box_rect = pygame.Rect(8, self._ph - pb_h - 8, pb_w, pb_h)

        # --- Zone texte / overlay (bas droit — TEXT state) ---
        cmd_x = int(self._pw * 0.47)
        cmd_w = self._pw - cmd_x - 6
        cmd_h = int(self._ph * 0.26)
        cmd_y = self._ph - cmd_h - 6
        self._cmd_rect = pygame.Rect(cmd_x, cmd_y, cmd_w, cmd_h)
        self._cmd_bg   = _load_ui(BATTLE_UI["overlay_message"], (cmd_w, cmd_h))

        # --- TextBox (état TEXT) ---
        pname = player_pokemon.dbSymbol.upper() if player_pokemon else "?"
        self._text_box = TextBox(
            self._cmd_rect,
            bg_surf=self._cmd_bg,
            font=self._f_body,
            text_color=_TEXT,
        )
        self._text_box.set_messages([f"Que va faire {pname} ?"])

        # --- Spritesheet attaques ---
        self._btn_sheet = _load_raw(BATTLE_UI["fight_buttons"])

        # --- Sprites Pokémon ---
        pid   = wild_data["pokemon_id"]
        shiny = wild_data.get("shiny", False)
        self._wild_sprite   = _load_sprite(pid, shiny, front=True)
        self._player_sprite = _load_sprite(player_pokemon.id, False, front=False) if player_pokemon else None

        hp_max            = wild_data.get("hp_max", 100)
        self._wild_hp_max = hp_max
        self._wild_hp     = hp_max

    # ------------------------------------------------------------------
    def handle_input(self, keylistener, controller, mouse_pos=None, mouse_click=None) -> None:
        if not self._active or self._intro_progress < 1.0:
            return
        up     = controller.get_key("up")
        down   = controller.get_key("down")
        action = controller.get_key("action")

        # Coordonnées souris converties en repère panel
        hover = self._to_panel(mouse_pos)
        click = self._to_panel(mouse_click)

        if self._state == "TEXT":
            # Touche E OU clic n'importe où dans la fenêtre
            if keylistener.key_pressed(action) or click:
                self._text_box.action()
                if self._text_box.done:
                    self._state = "MENU"
                if keylistener.key_pressed(action):
                    keylistener.remove_key(action)

        elif self._state == "MENU":
            rects = self._get_cmd_rects()
            # Survol → sélectionne + lance l'animation
            if hover:
                for i, r in enumerate(rects):
                    if r.collidepoint(hover) and i != self._cmd_idx:
                        self._cmd_idx        = i
                        self._cmd_anim_frame = 1
            # Clic sur un bouton → confirme
            if click:
                for i, r in enumerate(rects):
                    if r.collidepoint(click):
                        self._cmd_idx = i
                        self._confirm()
            # Clavier
            if   keylistener.key_pressed(up):
                self._cmd_idx = (self._cmd_idx - 1) % 4
                self._cmd_anim_frame = 1
                keylistener.remove_key(up)
            elif keylistener.key_pressed(down):
                self._cmd_idx = (self._cmd_idx + 1) % 4
                self._cmd_anim_frame = 1
                keylistener.remove_key(down)
            elif keylistener.key_pressed(action):
                self._confirm()
                keylistener.remove_key(action)

        elif self._state == "MOVE_SELECT":
            moves = self._player_pokemon.moves if self._player_pokemon else []
            n = len(moves)
            if n == 0:
                return
            rects = self._get_move_rects(n)
            # Survol → sélectionne
            if hover:
                for i, r in enumerate(rects):
                    if r.collidepoint(hover):
                        self._move_idx = i
            # Clic → TODO utiliser l'attaque
            if click:
                for i, r in enumerate(rects):
                    if r.collidepoint(click):
                        self._move_idx = i
                        # TODO: déclencher l'attaque
            # Clavier
            if   keylistener.key_pressed(up):     self._move_idx = (self._move_idx - 1) % n; keylistener.remove_key(up)
            elif keylistener.key_pressed(down):   self._move_idx = (self._move_idx + 1) % n; keylistener.remove_key(down)
            elif keylistener.key_pressed(action): keylistener.remove_key(action)  # TODO: utiliser l'attaque

    def _confirm(self) -> None:
        if   self._cmd_idx == 0: self._state = "MOVE_SELECT"; self._move_idx = 0  # Fight
        elif self._cmd_idx == 3: self._active = False                               # Run
        # Party (1) et Bag (2) : TODO

    # ------------------------------------------------------------------
    # Helpers souris / rects
    # ------------------------------------------------------------------

    def _to_panel(self, screen_pos) -> tuple | None:
        """Convertit une position écran en coordonnées locales du panel."""
        if screen_pos is None:
            return None
        return (screen_pos[0] - self._px, screen_pos[1] - self._py)

    def _get_cmd_rects(self) -> list[pygame.Rect]:
        """Rects des 4 boutons de commande (repère panel)."""
        btn_x = self._pw - self._cb_w - 6
        return [
            pygame.Rect(
                btn_x,
                self._ph - 6 - (4 - i) * self._cb_h - (4 - i - 1) * self._cb_gap,
                self._cb_w, self._cb_h,
            )
            for i in range(4)
        ]

    def _get_move_rects(self, n: int) -> list[pygame.Rect]:
        """Rects des n boutons d'attaque (repère panel)."""
        btn_x = int(self._pw * 0.54)
        btn_w = self._pw - btn_x - 6
        btn_h = int(_BTN_CELL_H * btn_w / _BTN_CELL_W)
        gap   = 4
        return [
            pygame.Rect(
                btn_x,
                self._ph - 6 - (n - i) * btn_h - (n - i - 1) * gap,
                btn_w, btn_h,
            )
            for i in range(n)
        ]

    # ------------------------------------------------------------------
    def update(self) -> None:
        now = time.time()
        dt  = now - self._last_tick
        self._last_tick = now

        if self._intro_progress < 1.0:
            self._intro_progress = min(1.0, self._intro_progress + 0.05)
            return

        # Avance les animations GIF des sprites
        if self._wild_sprite:
            self._wild_sprite.update(dt)
        if self._player_sprite:
            self._player_sprite.update(dt)

        if self._state == "TEXT":
            self._text_box.update()

        elif self._state == "MENU":
            if now - self._cmd_anim_tick >= _CMD_ANIM_FPS:
                self._cmd_anim_tick  = now
                # Cycle frames 1→9→1→...
                self._cmd_anim_frame = (self._cmd_anim_frame % 9) + 1

    # ------------------------------------------------------------------
    def draw(self, display: pygame.Surface) -> None:
        if not self._active:
            return

        overlay = pygame.Surface(display.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        display.blit(overlay, (0, 0))

        p = self._panel
        p.fill((0, 0, 0, 0))

        if self._bg_surf:
            p.blit(self._bg_surf, (0, 0))

        self._draw_sprites(p)
        self._draw_enemy_box(p)
        self._draw_player_box(p)

        if self._state == "TEXT":
            self._text_box.draw(p)
        elif self._state == "MENU":
            self._draw_cmd_buttons(p)
        elif self._state == "MOVE_SELECT":
            self._draw_moves(p)

        reveal_h = int(self._ph * self._intro_progress)
        if reveal_h > 0:
            display.blit(p, (self._px, self._py), (0, 0, self._pw, reveal_h))

    # ------------------------------------------------------------------
    def _draw_sprites(self, surf: pygame.Surface) -> None:
        if self._wild_sprite:
            frame = self._wild_sprite.current_frame()
            if frame:
                ws = pygame.transform.scale(frame, (
                    int(self._wild_sprite.get_width()  * 2.7),
                    int(self._wild_sprite.get_height() * 2.7),
                ))
                surf.blit(ws, (int(self._pw * 0.70) - ws.get_width() // 2, int(self._ph * 0.25)))

        if self._player_sprite:
            frame = self._player_sprite.current_frame()
            if frame:
                ps = pygame.transform.scale(frame, (
                    int(self._player_sprite.get_width()  * 2.7),
                    int(self._player_sprite.get_height() * 2.7),
                ))
                surf.blit(ps, (int(self._pw * 0.20) - ps.get_width() // 2, int(self._ph * 0.55)))

    # ------------------------------------------------------------------
    def _draw_enemy_box(self, surf: pygame.Surface) -> None:
        if not self._enemy_box:
            return
        bx, by = 8, 8
        bw, bh = self._enemy_box.get_size()
        surf.blit(self._enemy_box, (bx, by))

        bar_x, bar_y, bar_w = bx + 22, by + int(bh * 0.70), bw - 73

        # Nom centré verticalement entre le haut de la boîte et la barre HP
        name = self._wild.get("name", "???").capitalize()
        name_h = self._f_title.get_height()
        name_y = by + (bar_y - by - name_h) // 2
        surf.blit(self._f_title.render(name, True, _TEXT), (bx + 10, name_y))

        lv = self._f_small.render(f"Nv.{self._wild['level']}", True, _TEXT_DIM)
        surf.blit(lv, (bx + bw - lv.get_width() - 8, name_y))

        ratio = self._wild_hp / self._wild_hp_max if self._wild_hp_max else 0
        pygame.draw.rect(surf, _HP_BG, (bar_x, bar_y, bar_w, 6))
        color = _HP_OK if ratio >= 0.5 else (_HP_MED if ratio >= 0.25 else _HP_LOW)
        pygame.draw.rect(surf, color, (bar_x, bar_y, int(bar_w * ratio), 6))

    # ------------------------------------------------------------------
    def _draw_player_box(self, surf: pygame.Surface) -> None:
        if not self._player_box or not self._player_pokemon:
            return
        r       = self._player_box_rect
        bw, bh  = r.width, r.height
        surf.blit(self._player_box, r.topleft)

        pp = self._player_pokemon

        # Barre HP — position indépendante
        bar_x, bar_y, bar_w = r.x + 7, r.y + int(bh * 0.51), bw - 65

        # Nom centré verticalement entre le haut de la boîte et la barre HP
        name = pp.dbSymbol.capitalize()
        name_h = self._f_title.get_height()
        name_y = r.y + (bar_y - r.y - name_h) // 2
        surf.blit(self._f_title.render(name, True, _TEXT), (r.x + 10, name_y))

        lv = self._f_small.render(f"Nv.{pp.level}", True, _TEXT_DIM)
        surf.blit(lv, (r.x + bw - lv.get_width() - 8, name_y))

        hp_txt = self._f_small.render(f"{pp.hp}/{pp.maxhp}", True, _TEXT)
        surf.blit(hp_txt, (r.x + bw - hp_txt.get_width() - 8, r.y + int(bh * 0.44)))

        ratio = pp.hp / pp.maxhp if pp.maxhp else 0
        pygame.draw.rect(surf, _HP_BG, (bar_x, bar_y, bar_w, 6))
        color = _HP_OK if ratio >= 0.5 else (_HP_MED if ratio >= 0.25 else _HP_LOW)
        pygame.draw.rect(surf, color, (bar_x, bar_y, int(bar_w * ratio), 6))

        # Barre EXP — position entièrement indépendante
        exp_x, exp_y, exp_w = r.x + 89, r.y + int(bh * 0.75), bw - 148
        exp_ratio = (pp.xp / pp.xp_to_next_level) if pp.xp_to_next_level else 0
        pygame.draw.rect(surf, _HP_BG,     (exp_x, exp_y, exp_w, 4))
        pygame.draw.rect(surf, _EXP_COLOR, (exp_x, exp_y, int(exp_w * exp_ratio), 4))

    # ------------------------------------------------------------------
    def _draw_cmd_buttons(self, surf: pygame.Surface) -> None:
        """4 boutons fight/party/bag/run empilés bas-droit."""
        if not self._cb_sheet:
            return

        btn_x   = self._pw - self._cb_w - 6
        sheet_w = self._cb_sheet.get_width()
        sheet_h = self._cb_sheet.get_height()

        for i in range(4):
            # Run (i=3) tout en bas, Fight (i=0) en haut de la pile
            by = self._ph - 6 - (4 - i) * self._cb_h - (4 - i - 1) * self._cb_gap

            frame = self._cmd_anim_frame if i == self._cmd_idx else 0
            src_x = min(frame * _CMD_CELL_W, sheet_w - _CMD_CELL_W)
            src_y = min(i     * _CMD_CELL_H, sheet_h - _CMD_CELL_H)

            cell   = self._cb_sheet.subsurface(pygame.Rect(src_x, src_y, _CMD_CELL_W, _CMD_CELL_H))
            scaled = pygame.transform.scale(cell, (self._cb_w, self._cb_h))
            surf.blit(scaled, (btn_x, by))

    # ------------------------------------------------------------------
    def _draw_moves(self, surf: pygame.Surface) -> None:
        if not self._btn_sheet or not self._player_pokemon:
            return
        moves = self._player_pokemon.moves
        if not moves:
            return

        btn_x = int(self._pw * 0.54)
        btn_w = self._pw - btn_x - 6
        btn_h = int(_BTN_CELL_H * btn_w / _BTN_CELL_W)
        gap   = 4
        n     = len(moves)

        for i, move in enumerate(moves):
            by = self._ph - 6 - (n - i) * btn_h - (n - i - 1) * gap

            selected = (i == self._move_idx)
            row   = MOVE_TYPE_ROW.get(move.type, 0)
            src_x = _BTN_CELL_W if selected else 0
            src_y = row * _BTN_CELL_H

            cell   = self._btn_sheet.subsurface(pygame.Rect(src_x, src_y, _BTN_CELL_W, _BTN_CELL_H))
            scaled = pygame.transform.scale(cell, (btn_w, btn_h))
            surf.blit(scaled, (btn_x, by))

            name = move.dbSymbol.replace("_", " ").title()
            surf.blit(self._f_body.render(name, True, _TEXT_BTN),
                      (btn_x + 28, by + btn_h // 2 - 8))
            pp_txt = self._f_small.render(f"{move.pp}/{move.maxpp}", True, _TEXT_BTN)
            surf.blit(pp_txt, (btn_x + btn_w - pp_txt.get_width() - 8, by + btn_h // 2 - 6))

    # ------------------------------------------------------------------
    @property
    def active(self) -> bool:
        return self._active


# ---------------------------------------------------------------------------
# Sprite animé GIF
# ---------------------------------------------------------------------------

class AnimatedGif:
    """Charge un GIF animé via Pillow et expose la frame courante comme Surface pygame."""

    def __init__(self, path) -> None:
        self._frames: list[pygame.Surface] = []
        self._delays: list[float] = []   # durée en secondes par frame
        self._frame_idx = 0
        self._elapsed   = 0.0
        self._load(path)

    def _load(self, path) -> None:
        img = Image.open(str(path))
        try:
            while True:
                frame = img.convert("RGBA")
                data  = frame.tobytes()
                w, h  = frame.size
                surf  = pygame.image.fromstring(data, (w, h), "RGBA").convert_alpha()
                self._frames.append(surf)
                # duration en ms dans les métadonnées GIF, défaut 100 ms
                delay = img.info.get("duration", 100) / 1000.0
                self._delays.append(max(delay, 0.05))
                img.seek(img.tell() + 1)
        except EOFError:
            pass

    @property
    def valid(self) -> bool:
        return bool(self._frames)

    def get_size(self) -> tuple[int, int]:
        return self._frames[0].get_size() if self._frames else (0, 0)

    def get_width(self)  -> int: return self.get_size()[0]
    def get_height(self) -> int: return self.get_size()[1]

    def update(self, dt: float) -> None:
        if len(self._frames) <= 1:
            return
        self._elapsed += dt
        while self._elapsed >= self._delays[self._frame_idx]:
            self._elapsed  -= self._delays[self._frame_idx]
            self._frame_idx = (self._frame_idx + 1) % len(self._frames)

    def current_frame(self) -> pygame.Surface | None:
        return self._frames[self._frame_idx] if self._frames else None


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _panel_size_from_bg(path, max_w: int, max_h: int) -> tuple[int, int]:
    try:
        img = pygame.image.load(str(path))
        bw, bh = img.get_size()
        scale  = min(max_w / bw, max_h / bh)
        return int(bw * scale), int(bh * scale)
    except:
        return max_w, max_h

def _load_battleback(path, target_w: int, target_h: int) -> pygame.Surface | None:
    try:
        img = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.scale(img, (target_w, target_h))
    except: return None

def _load_ui(path, size: tuple) -> pygame.Surface | None:
    try: return pygame.transform.scale(pygame.image.load(str(path)).convert_alpha(), size)
    except: return None

def _load_raw(path) -> pygame.Surface | None:
    try: return pygame.image.load(str(path)).convert_alpha()
    except: return None

def _load_sprite(pokemon_id: int, shiny: bool, front: bool) -> AnimatedGif | None:
    suffix = "s" if shiny else "n"
    view   = "front" if front else "back"
    for name in [f"{pokemon_id}-{view}-{suffix}.gif", f"{pokemon_id}-{view}-{suffix}-m.gif"]:
        path = SPRITES_BATTLE_DIR / name
        if path.exists():
            try:
                gif = AnimatedGif(path)
                if gif.valid:
                    return gif
            except Exception:
                pass
    return None
