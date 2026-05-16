"""BattleScreen — panel dimensionné sur le background, UI assets.

Renderer pur : toute la logique de combat est déléguée à BattleManager.
"""
from __future__ import annotations
import time
import pygame
from PIL import Image
from code.client.config import (SPRITES_BATTLE_DIR, BATTLE_ZONE, BATTLE_UI,
                                MOVE_TYPE_ROW, FONTS_DIR, BATTLE_INTERFACES_DIR)
from code.client.ui.components.text_box import TextBox
from code.server.battle.battle_manager import BattleManager

# Boutons de commande : fight=0, party=1, bag=2, run=3
_CMD_LABELS  = ["FIGHT", "PARTY", "BAG", "RUN"]
_CMD_FRAMES  = 10   # 1 idle + 9 animation
_CMD_CELL_W  = 138
_CMD_CELL_H  = 44
_CMD_ANIM_FPS = 0.06   # secondes par frame d'animation

# Boutons d'attaque
_BTN_CELL_W = 243
_BTN_CELL_H = 44

_TEXT      = (255, 255, 255)
_TEXT_DIM  = (180, 180, 180)
_TEXT_BTN  = (255, 255, 255)
_HP_BG     = (80,  80,  80)
_HP_OK     = (56,  200, 72)
_HP_MED    = (220, 180, 40)
_HP_LOW    = (220, 60,  60)
_EXP_COLOR = (80,  140, 220)


def _mk_font(size: int) -> pygame.font.Font:
    try:    return pygame.font.Font(str(FONTS_DIR / "pokemon2.ttf"), size)
    except: return pygame.font.SysFont("arial", size)


# Taux de capture par type de Pokéball
_BALL_RATES: dict[str, float] = {
    "poke_ball":   1.0,
    "super_ball":  1.5,
    "hyper_ball":  2.0,
    "master_ball": 255.0,
}
# Bonus de statut pour le calcul de capture
_STATUS_CATCH_BONUS: dict[str, float] = {
    "SLP": 2.0, "FRZ": 2.0,
    "PAR": 1.5, "BRN": 1.5, "PSN": 1.5, "TOX": 1.5,
}


def _catch_probability(poke, ball_rate: float) -> float:
    """Probabilité de capture [0..1] — formule Gen 3 simplifiée."""
    import random as _r
    catch_rate  = getattr(poke, "catchRate", 45) or 45
    hp_ratio    = poke.hp / max(poke.maxhp, 1)
    status_mult = _STATUS_CATCH_BONUS.get(getattr(poke, "status", ""), 1.0)
    a = (3 - 2 * hp_ratio) * catch_rate * ball_rate * status_mult / 3
    return min(1.0, a / 255.0)


class BattleScreen:

    def __init__(self, screen, wild_data: dict, player_pokemon=None,
                 wild_pokemon=None, zone: str = None,
                 player_inv=None) -> None:
        self._screen         = screen
        self._wild           = wild_data
        self._wild_pokemon   = wild_pokemon
        self._player_pokemon = player_pokemon
        self._player_inv     = player_inv   # InventoryManager — pour les Pokéballs
        self._active         = True
        self._state          = "TEXT"
        self._move_idx       = 0
        self._intro_progress = 0.0
        self._last_tick      = time.time()
        self._pending_enemy_attack = False

        # ── BattleManager (logique pure) ──────────────────────────────────
        self._manager = BattleManager(player_pokemon, wild_pokemon)

        # Animation barre EXP
        self._exp_displayed_ratio: float                     = 0.0
        self._exp_anim_segments:   list[tuple[float, float]] = []
        self._exp_anim_seg_idx:    int                       = 0
        self._exp_anim_speed:      float                     = 0.4
        if player_pokemon:
            e, n = player_pokemon.xp_progress()
            self._exp_displayed_ratio = e / n if n else 0.0

        self._outcome: str | None = None

        # Icônes de statut
        self._status_icons: dict[str, pygame.Surface | None] = {}
        _st = _load_raw(BATTLE_INTERFACES_DIR / "battleStatuses.png")
        if _st:
            _sw2 = _st.get_width()
            for _r, _k in enumerate(["SLP", "PSN", "BRN", "PAR", "FRZ"]):
                self._status_icons[_k] = _st.subsurface(pygame.Rect(0, _r * 16, _sw2, 16))
            self._status_icons["TOX"] = self._status_icons.get("PSN")

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

        # --- Boutons de commande (bas droit) ---
        self._cb_w     = int(self._pw * 0.23)
        self._cb_h     = int(_CMD_CELL_H * self._cb_w / _CMD_CELL_W)
        self._cb_gap   = 4
        self._cb_sheet = _load_raw(BATTLE_UI["command_buttons"])
        self._cmd_idx        = 0
        self._cmd_anim_frame = 1
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
        else:
            self._wild_hp_max = wild_data.get("hp_max", 100)

        # Animation barres HP
        self._hp_anim_speed:          float = 0.7
        self._player_hp_displayed:    float = (player_pokemon.hp / player_pokemon.maxhp if player_pokemon and player_pokemon.maxhp else 0.0)
        wild_hp_cur = wild_pokemon.hp if wild_pokemon else self._wild_hp_max
        self._wild_hp_displayed:      float = (wild_hp_cur / self._wild_hp_max if self._wild_hp_max else 0.0)

    # ------------------------------------------------------------------
    def handle_input(self, keylistener, controller, mouse_pos=None, mouse_click=None) -> None:
        if not self._active or self._intro_progress < 1.0:
            return
        up     = controller.get_key("up")
        down   = controller.get_key("down")
        action = controller.get_key("action")
        quit   = controller.get_key("quit")

        hover = self._to_panel(mouse_pos)
        click = self._to_panel(mouse_click)

        if self._state in ("TEXT", "PLAYER_ATTACK", "ENEMY_ATTACK",
                           "WILD_FAINTED", "WILD_CAUGHT", "PLAYER_FAINTED", "END_OF_TURN"):
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
            elif keylistener.key_pressed(quit):
                self._state = "MENU"
                keylistener.remove_key(quit)

    # ------------------------------------------------------------------
    def _confirm(self) -> None:
        if self._cmd_idx == 0:
            # Si charge ou verrou en cours → auto-exécuter le move
            auto_sym = self._manager.auto_move_sym
            if auto_sym and self._player_pokemon:
                for i, m in enumerate(self._player_pokemon.moves):
                    if m.dbSymbol.lower().replace("_", "-") == auto_sym:
                        self._move_idx = i
                        self._use_player_move()
                        return
                self._manager.clear_auto_move()
            self._state = "MOVE_SELECT"
            self._move_idx = 0
        elif self._cmd_idx == 2:   # BAG → tenter une capture
            self._try_catch()
        elif self._cmd_idx == 3:
            self._manager.end_battle("fled")
            self._outcome = "fled"
            self._active  = False

    # ------------------------------------------------------------------
    def _use_player_move(self) -> None:
        """Délègue l'exécution du move au manager, met à jour le state machine."""
        if not self._player_pokemon or not self._wild_pokemon:
            return

        msgs, pending = self._manager.player_use_move(self._move_idx)

        # Synchroniser le sprite si Transform a eu lieu
        self._sync_transform_sprite()

        self._pending_enemy_attack = pending
        self._text_box.set_messages(msgs)
        self._state = "PLAYER_ATTACK"

    # ------------------------------------------------------------------
    def _enemy_counter_attack(self) -> None:
        """Délègue la contre-attaque au manager, met à jour le state machine."""
        if not self._wild_pokemon or not self._player_pokemon:
            self._state = "MENU"
            return

        msgs = self._manager.enemy_act()

        # Synchroniser le sprite si Transform a eu lieu (wild)
        self._sync_transform_sprite()

        self._text_box.set_messages(msgs)
        self._state = "ENEMY_ATTACK"

    # ------------------------------------------------------------------
    def _sync_transform_sprite(self) -> None:
        """Met à jour le sprite joueur si une transformation vient de se produire."""
        if self._manager.is_transformed:
            backup = self._manager.get_transform_backup()
            if backup is not None and "sprite" not in backup:
                # Première détection : charger le sprite dos du Pokémon cloné
                if self._wild_pokemon:
                    new_spr = _load_sprite(getattr(self._wild_pokemon, "id", 0),
                                           shiny=False, front=False)
                    if new_spr:
                        self._manager.set_transform_sprite_backup(self._player_sprite)
                        self._player_sprite = new_spr

    def _restore_transform_sprite(self) -> None:
        """Restaure le sprite joueur après la fin du combat."""
        backup = self._manager.get_transform_backup()
        if backup and "sprite" in backup:
            self._player_sprite = backup["sprite"]

    # ------------------------------------------------------------------
    def _try_catch(self) -> None:
        """Tente de capturer le Pokémon sauvage avec la meilleure Pokéball disponible."""
        import random as _random

        if not self._wild_pokemon:
            self._text_box.set_messages(["Pas de Pokémon cible !"])
            self._state = "TEXT"
            return

        # Cherche la meilleure Pokéball dans l'inventaire
        inv  = self._player_inv
        ball_sym  = None
        ball_rate = 0.0

        if inv and hasattr(inv, "bag"):
            balls = inv.bag.pockets.get("pokeballs", [])
            # Priorité : master > hyper > super > poke
            for sym in ("master_ball", "hyper_ball", "super_ball", "poke_ball"):
                for item in balls:
                    if item.item_db_symbol == sym and item.quantity > 0:
                        ball_sym  = sym
                        ball_rate = _BALL_RATES[sym]
                        break
                if ball_sym:
                    break

        if not ball_sym:
            self._text_box.set_messages(["Pas de Pokeball disponible !"])
            self._state = "TEXT"
            return

        # Retire une Pokéball de l'inventaire
        inv.bag.remove(ball_sym, "pokeballs", 1)

        poke  = self._wild_pokemon
        wname = poke.dbSymbol.capitalize()
        msgs  = [f"Lance une {ball_sym.replace('_', ' ').title()} !"]

        prob = _catch_probability(poke, ball_rate)
        if ball_rate >= 255 or _random.random() < prob:
            # Capturé !
            msgs.append(f"{wname} est capturé !")
            self._text_box.set_messages(msgs)
            self._state = "WILD_CAUGHT"
        else:
            msgs.append(f"Oh ! {wname} s'est échappé !")
            self._text_box.set_messages(msgs)
            self._state          = "TEXT"
            self._pending_enemy_attack = True   # l'ennemi contre-attaque

    # ------------------------------------------------------------------
    def _end_battle(self, outcome: str) -> None:
        """Fin de combat : restaure les transformations, met à jour l'état."""
        self._restore_transform_sprite()
        self._manager.end_battle(outcome)
        self._outcome = outcome
        self._active  = False

    # ------------------------------------------------------------------
    def _on_textbox_done(self) -> None:
        """Transition d'état après confirmation du TextBox."""
        if self._state == "TEXT":
            self._state = "MENU"

        elif self._state == "PLAYER_ATTACK":
            if self._wild_pokemon and self._wild_pokemon.hp <= 0:
                ename   = self._wild_pokemon.dbSymbol.capitalize()
                pname   = self._player_pokemon.dbSymbol.capitalize() if self._player_pokemon else "?"
                msgs    = [f"{ename} ennemi est mis KO !"]

                # Calcul XP + animation — fait par le manager
                xp_gain = self._manager.calc_xp_gain()
                if xp_gain > 0 and self._player_pokemon:
                    e_b, n_b = self._player_pokemon.xp_progress()
                    ratio_before = e_b / n_b if n_b else 0.0
                    old_level = self._player_pokemon.level

                    xp_msgs = self._manager.on_wild_fainted()

                    e_a, n_a = self._player_pokemon.xp_progress()
                    ratio_after = e_a / n_a if n_a else 0.0
                    levels_gained = self._player_pokemon.level - old_level

                    # Segments d'animation EXP (un par niveau franchi)
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

                    msgs.extend(xp_msgs)

                self._text_box.set_messages(msgs)
                self._state = "WILD_FAINTED"

            elif self._player_pokemon and self._player_pokemon.hp <= 0:
                pname = self._player_pokemon.dbSymbol.capitalize()
                self._text_box.set_messages([f"{pname} est mis KO !"])
                self._state = "PLAYER_FAINTED"
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
                eot = self._manager.collect_end_of_turn()
                if eot:
                    self._text_box.set_messages(eot)
                    self._state = "END_OF_TURN"
                else:
                    self._state = "MENU"

        elif self._state == "END_OF_TURN":
            if self._player_pokemon and self._player_pokemon.hp <= 0:
                pname = self._player_pokemon.dbSymbol.capitalize()
                self._text_box.set_messages([f"{pname} est mis KO !"])
                self._state = "PLAYER_FAINTED"
            elif self._wild_pokemon and self._wild_pokemon.hp <= 0:
                self._state = "MENU"
            else:
                self._state = "MENU"

        elif self._state == "WILD_FAINTED":
            self._end_battle("won")
        elif self._state == "WILD_CAUGHT":
            self._end_battle("caught")
        elif self._state == "PLAYER_FAINTED":
            self._end_battle("lost")

        # Vérifier si le manager a terminé le combat (ex: fuite via move)
        mgr_outcome = self._manager.get_outcome()
        if mgr_outcome and self._active:
            self._restore_transform_sprite()
            self._outcome = mgr_outcome
            self._active  = False

    # ------------------------------------------------------------------
    # Helpers souris / rects
    # ------------------------------------------------------------------

    def _to_panel(self, screen_pos) -> tuple | None:
        if screen_pos is None:
            return None
        return (screen_pos[0] - self._px, screen_pos[1] - self._py)

    def _get_cmd_rects(self) -> list[pygame.Rect]:
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

        # Animation EXP
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

        # Animation barres HP
        if self._player_pokemon and self._player_pokemon.maxhp:
            target = self._player_pokemon.hp / self._player_pokemon.maxhp
            if self._player_hp_displayed > target:
                self._player_hp_displayed = max(target, self._player_hp_displayed - self._hp_anim_speed * dt)
            else:
                self._player_hp_displayed = min(target, self._player_hp_displayed + self._hp_anim_speed * dt)

        if self._wild_hp_max:
            hp_cur = self._wild_pokemon.hp if self._wild_pokemon else 0
            target = hp_cur / self._wild_hp_max
            if self._wild_hp_displayed > target:
                self._wild_hp_displayed = max(target, self._wild_hp_displayed - self._hp_anim_speed * dt)
            else:
                self._wild_hp_displayed = min(target, self._wild_hp_displayed + self._hp_anim_speed * dt)

        if self._state in ("TEXT", "PLAYER_ATTACK", "ENEMY_ATTACK",
                           "WILD_FAINTED", "WILD_CAUGHT", "PLAYER_FAINTED", "END_OF_TURN"):
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
                           "WILD_FAINTED", "WILD_CAUGHT", "PLAYER_FAINTED", "END_OF_TURN"):
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

        if self._wild_pokemon:
            self._draw_status_icon(surf, self._wild_pokemon.status,
                                   bx + 4, bar_y - 18)

    # ------------------------------------------------------------------
    def _draw_player_box(self, surf: pygame.Surface) -> None:
        if not self._player_box or not self._player_pokemon:
            return
        r       = self._player_box_rect
        bw, bh  = r.width, r.height
        surf.blit(self._player_box, r.topleft)

        pp = self._player_pokemon

        bar_x, bar_y, bar_w = r.x + 7, r.y + int(bh * 0.51), bw - 65

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

        if pp:
            self._draw_status_icon(surf, pp.status, r.x + 4, bar_y - 18)

        exp_x, exp_y, exp_w = r.x + 89, r.y + int(bh * 0.75), bw - 148
        exp_ratio = min(1.0, max(0.0, self._exp_displayed_ratio))
        pygame.draw.rect(surf, _HP_BG,     (exp_x, exp_y, exp_w, 4))
        pygame.draw.rect(surf, _EXP_COLOR, (exp_x, exp_y, int(exp_w * exp_ratio), 4))

    # ------------------------------------------------------------------
    def _draw_status_icon(self, surf: pygame.Surface, status: str,
                          x: int, y: int) -> None:
        if not status:
            return
        icon = self._status_icons.get(status)
        if icon:
            surf.blit(icon, (x, y))

    # ------------------------------------------------------------------
    def _draw_cmd_buttons(self, surf: pygame.Surface) -> None:
        if not self._cb_sheet:
            return

        btn_x   = self._pw - self._cb_w - 6
        sheet_w = self._cb_sheet.get_width()
        sheet_h = self._cb_sheet.get_height()

        for i in range(4):
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

from code.client.ui.animated_gif import AnimatedGif  # noqa: E402


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
