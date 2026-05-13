"""BattleScreen — panel dimensionné sur le background, UI assets."""
from __future__ import annotations
import math
import random
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

# ---------------------------------------------------------------------------
# Table d'efficacité des types (Gen 6+)
# Clé externe = type de l'attaque, clé interne = type du défenseur, valeur = multiplicateur
# ---------------------------------------------------------------------------
_TYPE_CHART: dict[str, dict[str, float]] = {
    "normal":   {"rock": 0.5, "ghost": 0.0, "steel": 0.5},
    "fire":     {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "dragon": 0.5, "steel": 2.0},
    "water":    {"fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0, "dragon": 0.5},
    "electric": {"water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0.0, "flying": 2.0, "dragon": 0.5},
    "grass":    {"fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5, "rock": 2.0, "dragon": 0.5, "steel": 0.5},
    "ice":      {"water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0, "steel": 0.5},
    "fighting": {"normal": 2.0, "ice": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2.0, "ghost": 0.0, "dark": 2.0, "steel": 2.0, "fairy": 0.5},
    "poison":   {"grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0, "fairy": 2.0},
    "ground":   {"fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
    "flying":   {"electric": 0.5, "grass": 2.0, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
    "psychic":  {"fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
    "bug":      {"fire": 0.5, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
    "rock":     {"fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
    "ghost":    {"normal": 0.0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
    "dragon":   {"dragon": 2.0, "steel": 0.5, "fairy": 0.0},
    "dark":     {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
    "steel":    {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2.0, "rock": 2.0, "steel": 0.5, "fairy": 2.0},
    "fairy":    {"fire": 0.5, "fighting": 2.0, "poison": 0.5, "dragon": 2.0, "dark": 2.0, "steel": 0.5},
}


def _type_effectiveness(move_type: str, defender_types: list[str]) -> float:
    row = _TYPE_CHART.get(move_type, {})
    mult = 1.0
    for t in defender_types:
        mult *= row.get(t, 1.0)
    return mult


def _calc_damage(attacker, move, defender) -> tuple[int, float, bool]:
    """Formule officielle Gen 5. Retourne (dégâts, multiplicateur_type, coup_critique)."""
    power = move.power or 0
    if not power or move.category == "status":
        return 0, 1.0, False

    if move.category == "special":
        A, D = attacker.ats, defender.dfs
    else:
        A, D = attacker.atk, defender.dfe

    D = max(D, 1)
    base = math.floor((math.floor(2 * attacker.level / 5 + 2) * power * A / D) / 50) + 2

    if move.type in attacker.type:
        base = math.floor(base * 1.5)

    eff = _type_effectiveness(move.type, defender.type)
    base = math.floor(base * eff)

    is_crit = random.randint(1, 16) == 1
    if is_crit:
        base = math.floor(base * 1.5)

    base = math.floor(base * random.randint(85, 100) / 100)
    return (max(1, base) if eff > 0 else 0), eff, is_crit


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

    def __init__(self, screen, wild_data: dict, player_pokemon=None,
                 wild_pokemon=None, zone: str = None) -> None:
        self._screen         = screen
        self._wild           = wild_data
        self._wild_pokemon   = wild_pokemon      # objet Pokemon complet
        self._player_pokemon = player_pokemon
        self._active         = True
        self._state          = "TEXT"   # TEXT → MENU → MOVE_SELECT → PLAYER_ATTACK → …
        self._move_idx       = 0
        self._intro_progress = 0.0
        self._last_tick      = time.time()
        self._pending_enemy_attack = False  # flag pour lancer la contre-attaque

        # Animation barre EXP
        self._exp_displayed_ratio: float                     = 0.0
        self._exp_anim_segments:   list[tuple[float, float]] = []
        self._exp_anim_seg_idx:    int                       = 0
        self._exp_anim_speed:      float                     = 0.4  # ratio/seconde
        if player_pokemon:
            e, n = player_pokemon.xp_progress()
            self._exp_displayed_ratio = e / n if n else 0.0

        # Résultat du combat : "won" | "fled" | "lost" | None
        self._outcome: str | None = None

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
        ename = (wild_pokemon.dbSymbol.capitalize() if wild_pokemon
                 else wild_data.get("name", "???").capitalize())
        pname = player_pokemon.dbSymbol.capitalize() if player_pokemon else "?"
        self._text_box = TextBox(
            self._cmd_rect,
            bg_surf=self._cmd_bg,
            font=self._f_body,
            text_color=_TEXT,
        )
        self._text_box.set_messages([
            f"Un {ename} sauvage apparaît !",
            f"Que va faire {pname} ?",
        ])

        # --- Spritesheet attaques ---
        self._btn_sheet = _load_raw(BATTLE_UI["fight_buttons"])

        # --- Sprites Pokémon ---
        pid   = wild_data["pokemon_id"]
        shiny = wild_data.get("shiny", False)
        self._wild_sprite   = _load_sprite(pid, shiny, front=True)
        self._player_sprite = _load_sprite(player_pokemon.id, False, front=False) if player_pokemon else None

        # HP depuis l'objet Pokemon si disponible, sinon fallback dict
        if wild_pokemon:
            self._wild_hp_max = wild_pokemon.maxhp
            self._wild_hp     = wild_pokemon.hp
        else:
            hp_max            = wild_data.get("hp_max", 100)
            self._wild_hp_max = hp_max
            self._wild_hp     = hp_max

        # Animation barres HP
        self._hp_anim_speed:          float = 0.7   # ratio/seconde
        self._player_hp_displayed:    float = (player_pokemon.hp / player_pokemon.maxhp if player_pokemon and player_pokemon.maxhp else 0.0)
        self._wild_hp_displayed:      float = (self._wild_hp / self._wild_hp_max if self._wild_hp_max else 0.0)

    # ------------------------------------------------------------------
    def handle_input(self, keylistener, controller, mouse_pos=None, mouse_click=None) -> None:
        if not self._active or self._intro_progress < 1.0:
            return
        up     = controller.get_key("up")
        down   = controller.get_key("down")
        action = controller.get_key("action")

        hover = self._to_panel(mouse_pos)
        click = self._to_panel(mouse_click)

        if self._state in ("TEXT", "PLAYER_ATTACK", "ENEMY_ATTACK",
                           "WILD_FAINTED", "PLAYER_FAINTED"):
            if keylistener.key_pressed(action) or click:
                self._text_box.action()
                if self._text_box.done:
                    self._on_textbox_done()
                if keylistener.key_pressed(action):
                    keylistener.remove_key(action)

        elif self._state == "MENU":
            rects = self._get_cmd_rects()
            if hover:
                for i, r in enumerate(rects):
                    if r.collidepoint(hover) and i != self._cmd_idx:
                        self._cmd_idx        = i
                        self._cmd_anim_frame = 1
            if click:
                for i, r in enumerate(rects):
                    if r.collidepoint(click):
                        self._cmd_idx = i
                        self._confirm()
            if keylistener.key_pressed(up):
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
            if hover:
                for i, r in enumerate(rects):
                    if r.collidepoint(hover):
                        self._move_idx = i
            if click:
                for i, r in enumerate(rects):
                    if r.collidepoint(click):
                        self._move_idx = i
                        self._use_player_move()
            if keylistener.key_pressed(up):
                self._move_idx = (self._move_idx - 1) % n
                keylistener.remove_key(up)
            elif keylistener.key_pressed(down):
                self._move_idx = (self._move_idx + 1) % n
                keylistener.remove_key(down)
            elif keylistener.key_pressed(action):
                self._use_player_move()
                keylistener.remove_key(action)

    # ------------------------------------------------------------------
    def _confirm(self) -> None:
        if   self._cmd_idx == 0: self._state = "MOVE_SELECT"; self._move_idx = 0
        elif self._cmd_idx == 3:
            self._outcome = "fled"
            self._active  = False
        # Party (1) et Bag (2) : TODO

    # ------------------------------------------------------------------
    def _use_player_move(self) -> None:
        """Exécute l'attaque du joueur et prépare les messages."""
        if not self._player_pokemon or not self._wild_pokemon:
            return
        moves = self._player_pokemon.moves
        if not moves:
            return
        move = moves[self._move_idx]

        # Vérification PP
        if move.pp <= 0:
            self._text_box.set_messages(["Plus de PP pour cette attaque !"])
            self._state = "PLAYER_ATTACK"
            self._pending_enemy_attack = False
            return

        move.pp -= 1

        # Vérification précision
        acc = move.accuracy or 100
        hit = random.randint(1, 100) <= acc

        pname = self._player_pokemon.dbSymbol.capitalize()
        ename = self._wild_pokemon.dbSymbol.capitalize()
        mname = move.dbSymbol.replace("-", " ").replace("_", " ").title()

        if not hit:
            msgs = [f"{pname} utilise {mname} !", f"L'attaque échoue !"]
            self._pending_enemy_attack = True
        else:
            dmg, eff, crit = _calc_damage(self._player_pokemon, move, self._wild_pokemon)
            self._wild_pokemon.hp = max(0, self._wild_pokemon.hp - dmg)
            self._wild_hp         = self._wild_pokemon.hp

            msgs = [f"{pname} utilise {mname} !"]
            if crit:
                msgs.append("Coup critique !")
            if eff == 0:
                msgs.append("Ça n'affecte pas l'ennemi…")
            elif eff >= 2:
                msgs.append("C'est super efficace !")
            elif eff < 1:
                msgs.append("Ce n'est pas très efficace…")
            if dmg > 0:
                msgs.append(f"{ename} perd {dmg} PV !")

            self._pending_enemy_attack = (self._wild_pokemon.hp > 0)

        self._text_box.set_messages(msgs)
        self._state = "PLAYER_ATTACK"

    # ------------------------------------------------------------------
    def _enemy_counter_attack(self) -> None:
        """L'ennemi choisit et exécute une attaque aléatoire."""
        if not self._wild_pokemon or not self._player_pokemon:
            self._state = "MENU"
            return
        moves = [m for m in self._wild_pokemon.moves if m.pp > 0]
        if not moves:
            # L'ennemi n'a plus de PP → Lutte
            from code.entities.move import Move
            moves = [Move({"dbSymbol": "struggle", "type": "normal",
                           "power": 50, "accuracy": 100, "pp": 1,
                           "maxpp": 1, "category": "physical", "priority": 0})]
        move = random.choice(moves)
        if move.pp is not None:
            move.pp = max(0, move.pp - 1)

        ename = self._wild_pokemon.dbSymbol.capitalize()
        pname = self._player_pokemon.dbSymbol.capitalize()
        mname = move.dbSymbol.replace("-", " ").replace("_", " ").title()

        acc = move.accuracy or 100
        hit = random.randint(1, 100) <= acc

        if not hit:
            msgs = [f"Le {ename} ennemi utilise {mname} !", "L'attaque échoue !"]
        else:
            dmg, eff, crit = _calc_damage(self._wild_pokemon, move, self._player_pokemon)
            self._player_pokemon.hp = max(0, self._player_pokemon.hp - dmg)

            msgs = [f"Le {ename} ennemi utilise {mname} !"]
            if crit:
                msgs.append("Coup critique !")
            if eff == 0:
                msgs.append("Ça n'affecte pas…")
            elif eff >= 2:
                msgs.append("C'est super efficace !")
            elif eff < 1:
                msgs.append("Ce n'est pas très efficace…")
            if dmg > 0:
                msgs.append(f"{pname} perd {dmg} PV !")

        self._text_box.set_messages(msgs)
        self._state = "ENEMY_ATTACK"

    # ------------------------------------------------------------------
    def _on_textbox_done(self) -> None:
        """Transition d'état après confirmation du TextBox."""
        if self._state == "TEXT":
            self._state = "MENU"

        elif self._state == "PLAYER_ATTACK":
            if self._wild_pokemon and self._wild_pokemon.hp <= 0:
                ename   = self._wild_pokemon.dbSymbol.capitalize()
                xp_gain = self._calc_xp_gain()
                pname   = self._player_pokemon.dbSymbol.capitalize() if self._player_pokemon else "?"
                msgs    = [f"{ename} ennemi est mis KO !"]

                if xp_gain > 0 and self._player_pokemon:
                    # Ratio avant gain (pour lancer l'animation en fond)
                    e_b, n_b = self._player_pokemon.xp_progress()
                    ratio_before = e_b / n_b if n_b else 0.0
                    old_level = self._player_pokemon.level

                    self._player_pokemon.xp += xp_gain
                    learned = self._player_pokemon.check_level_ups()
                    levels_gained = self._player_pokemon.level - old_level

                    e_a, n_a = self._player_pokemon.xp_progress()
                    ratio_after = e_a / n_a if n_a else 0.0

                    # Segments d'animation (un par niveau franchi)
                    if levels_gained == 0:
                        segs: list[tuple[float, float]] = [(ratio_before, ratio_after)]
                    else:
                        segs = [(ratio_before, 1.0)]
                        for _ in range(levels_gained - 1):
                            segs.append((0.0, 1.0))
                        segs.append((0.0, ratio_after))
                    self._exp_anim_segments   = segs
                    self._exp_anim_seg_idx    = 0
                    self._exp_displayed_ratio = segs[0][0]

                    msgs.append(f"{pname} gagne {xp_gain} points d'EXP !")
                    if levels_gained > 0:
                        msgs.append(f"{pname} monte au niveau {self._player_pokemon.level} !")
                    for move_name in learned:
                        display = move_name.replace("-", " ").replace("_", " ").title()
                        msgs.append(f"{pname} apprend {display} !")

                self._text_box.set_messages(msgs)
                self._state = "WILD_FAINTED"

            elif self._pending_enemy_attack:
                self._enemy_counter_attack()
            else:
                self._state = "MENU"

        elif self._state == "ENEMY_ATTACK":
            if self._player_pokemon and self._player_pokemon.hp <= 0:
                pname = self._player_pokemon.dbSymbol.capitalize()
                self._text_box.set_messages([f"{pname} est mis KO !"])
                self._state = "PLAYER_FAINTED"
            else:
                self._state = "MENU"

        elif self._state == "WILD_FAINTED":
            self._outcome = "won"
            self._active  = False
        elif self._state == "PLAYER_FAINTED":
            self._outcome = "lost"
            self._active  = False

    # ------------------------------------------------------------------
    def _calc_xp_gain(self) -> int:
        if not self._wild_pokemon or not self._player_pokemon:
            return 0
        base_exp = getattr(self._wild_pokemon, "baseExperience", 100) or 100
        return max(1, math.floor(base_exp * self._wild_pokemon.level / 7))

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

        # Animation EXP — tourne en fond quel que soit l'état
        if self._exp_anim_segments:
            _, seg_end = self._exp_anim_segments[self._exp_anim_seg_idx]
            self._exp_displayed_ratio = min(
                seg_end, self._exp_displayed_ratio + self._exp_anim_speed * dt
            )
            if self._exp_displayed_ratio >= seg_end:
                self._exp_anim_seg_idx += 1
                if self._exp_anim_seg_idx >= len(self._exp_anim_segments):
                    self._exp_anim_segments = []
                else:
                    self._exp_displayed_ratio = \
                        self._exp_anim_segments[self._exp_anim_seg_idx][0]

        # Animation barres HP — descente progressive
        if self._player_pokemon and self._player_pokemon.maxhp:
            target = self._player_pokemon.hp / self._player_pokemon.maxhp
            if self._player_hp_displayed > target:
                self._player_hp_displayed = max(target, self._player_hp_displayed - self._hp_anim_speed * dt)
            else:
                self._player_hp_displayed = min(target, self._player_hp_displayed + self._hp_anim_speed * dt)

        if self._wild_hp_max:
            hp_cur = self._wild_pokemon.hp if self._wild_pokemon else self._wild_hp
            target = hp_cur / self._wild_hp_max
            if self._wild_hp_displayed > target:
                self._wild_hp_displayed = max(target, self._wild_hp_displayed - self._hp_anim_speed * dt)
            else:
                self._wild_hp_displayed = min(target, self._wild_hp_displayed + self._hp_anim_speed * dt)

        if self._state in ("TEXT", "PLAYER_ATTACK", "ENEMY_ATTACK",
                           "WILD_FAINTED", "PLAYER_FAINTED"):
            self._text_box.update()

        elif self._state == "MENU":
            if now - self._cmd_anim_tick >= _CMD_ANIM_FPS:
                self._cmd_anim_tick  = now
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

        if self._state in ("TEXT", "PLAYER_ATTACK", "ENEMY_ATTACK",
                           "WILD_FAINTED", "PLAYER_FAINTED"):
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
        if self._wild_pokemon:
            name  = self._wild_pokemon.dbSymbol.capitalize()
            level = self._wild_pokemon.level
        else:
            name  = self._wild.get("name", "???").capitalize()
            level = self._wild.get("level", "?")
        name_h = self._f_title.get_height()
        name_y = by + (bar_y - by - name_h) // 2
        surf.blit(self._f_title.render(name, True, _TEXT), (bx + 10, name_y))

        lv = self._f_small.render(f"Nv.{level}", True, _TEXT_DIM)
        surf.blit(lv, (bx + bw - lv.get_width() - 8, name_y))

        ratio = min(1.0, max(0.0, self._wild_hp_displayed))
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

        ratio = min(1.0, max(0.0, self._player_hp_displayed))
        pygame.draw.rect(surf, _HP_BG, (bar_x, bar_y, bar_w, 6))
        color = _HP_OK if ratio >= 0.5 else (_HP_MED if ratio >= 0.25 else _HP_LOW)
        pygame.draw.rect(surf, color, (bar_x, bar_y, int(bar_w * ratio), 6))

        # Barre EXP — animée via _exp_displayed_ratio
        exp_x, exp_y, exp_w = r.x + 89, r.y + int(bh * 0.75), bw - 148
        exp_ratio = min(1.0, max(0.0, self._exp_displayed_ratio))
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
    def outcome(self) -> str | None:
        return self._outcome

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
