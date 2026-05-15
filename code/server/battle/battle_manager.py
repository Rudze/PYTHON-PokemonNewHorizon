"""BattleManager — contient toute la logique de combat, sans aucun rendu."""
from __future__ import annotations
import math
import random

from code.server.battle.type_chart import type_effectiveness
from code.server.battle.status import can_inflict_status, STATUS_INFLICT_MSG
from code.server.battle.move_effects import lookup_effect
from code.server.battle.calc import calc_damage, stage_mult


class BattleManager:
    """
    Gère l'intégralité de la logique d'un combat sauvage.

    Interface publique :
        player_use_move(move_idx)  -> (msgs, pending_enemy)
        enemy_act()                -> msgs
        collect_end_of_turn()      -> msgs
        on_wild_fainted()          -> msgs   (XP, niveaux, moves appris)
        get_outcome()              -> str | None
        player_pokemon             (property)
        wild_pokemon               (property)
    """

    def __init__(self, player_pokemon, wild_pokemon) -> None:
        self._player_pokemon = player_pokemon
        self._wild_pokemon   = wild_pokemon
        self._outcome: str | None = None

        # ── États de combat volatils ──────────────────────────────────────
        self._player_sleep_ctr:   int  = 0
        self._wild_sleep_ctr:     int  = 0
        self._player_tox:         int  = 0
        self._wild_tox:           int  = 0
        self._player_confused:    int  = 0
        self._wild_confused:      int  = 0
        self._player_recharging:  bool = False
        self._wild_recharging:    bool = False
        _s0 = lambda: {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        self._player_stages: dict[str, int] = _s0()
        self._wild_stages:   dict[str, int] = _s0()

        # ── Mécaniques multi-tours ────────────────────────────────────────
        self._player_charging: str | None   = None
        self._wild_charging:   str | None   = None
        self._player_locked:   tuple | None = None
        self._wild_locked:     tuple | None = None
        self._player_trapped:  int          = 0
        self._wild_trapped:    int          = 0

        # ── Effets de terrain / protection ───────────────────────────────
        self._player_leech_seeded: bool = False
        self._wild_leech_seeded:   bool = False
        self._player_reflect:  int = 0
        self._wild_reflect:    int = 0
        self._player_screen:   int = 0
        self._wild_screen:     int = 0
        self._player_mist:     int = 0
        self._wild_mist:       int = 0

        # ── Désactivation / suivi dernier move ────────────────────────────
        self._player_disabled: tuple | None = None
        self._wild_disabled:   tuple | None = None
        self._last_player_move  = None
        self._last_wild_move    = None

        # ── Mécaniques spéciales ──────────────────────────────────────────
        self._last_phys_to_player: int  = 0
        self._last_phys_to_wild:   int  = 0
        self._player_rage:         bool = False
        self._wild_rage:           bool = False
        self._player_focus_energy: bool = False
        self._wild_focus_energy:   bool = False
        self._player_bide:         tuple | None = None
        self._wild_bide:           tuple | None = None
        self._player_transformed:  dict | None = None

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def player_pokemon(self):
        return self._player_pokemon

    @property
    def wild_pokemon(self):
        return self._wild_pokemon

    def get_outcome(self) -> str | None:
        return self._outcome

    # ── Accesseurs état multi-tours (lecture seule pour le renderer) ──────

    @property
    def auto_move_sym(self) -> str | None:
        """Sym du move en cours de charge/verrou/bide, pour auto-exécution."""
        return (
            self._player_charging or
            (self._player_locked[0] if self._player_locked else None) or
            ("bide" if self._player_bide else None)
        )

    def clear_auto_move(self) -> None:
        """Annule l'état de charge/verrou (si le move est introuvable)."""
        self._player_charging = None
        self._player_locked   = None
        self._player_bide     = None

    @property
    def is_transformed(self) -> bool:
        """Vrai si le joueur est actuellement transformé."""
        return self._player_transformed is not None

    def get_transform_backup(self) -> dict | None:
        """Retourne le dict de backup de la transformation (pour le renderer)."""
        return self._player_transformed

    def set_transform_sprite_backup(self, sprite) -> None:
        """Sauvegarde le sprite original dans le dict de transformation."""
        if self._player_transformed is not None:
            self._player_transformed["sprite"] = sprite

    # ── API publique ──────────────────────────────────────────────────────

    def player_use_move(self, move_idx: int) -> tuple[list[str], bool]:
        """
        Exécute le move du joueur à l'index donné.
        Retourne (messages, pending_enemy_attack).
        """
        if not self._player_pokemon or not self._wild_pokemon:
            return [], False

        moves = self._player_pokemon.moves
        if not moves:
            return [], False

        move     = moves[move_idx]
        move_sym = move.dbSymbol.lower().replace("_", "-")

        # Pas de déduction de PP sur les tours auto (charge / verrou / bide)
        is_auto = (
            self._player_charging == move_sym or
            (self._player_locked is not None and self._player_locked[0] == move_sym) or
            (self._player_bide   is not None and move_sym == "bide")
        )
        if not is_auto:
            # Désactivation
            if self._player_disabled:
                dis_sym, _ = self._player_disabled
                if dis_sym == move_sym:
                    mname_dis = move.dbSymbol.replace("-", " ").replace("_", " ").title()
                    return [f"{mname_dis} est désactivée !"], True
            if move.pp <= 0:
                return ["Plus de PP pour cette attaque !"], False
            move.pp -= 1

        self._last_player_move = move

        can_act, status_msgs = self.check_can_act(is_player=True)
        if not can_act:
            return status_msgs, True

        msgs = status_msgs + self.execute_move(
            self._player_pokemon, move, self._wild_pokemon,
            attacker_is_player=True,
        )
        if self._player_pokemon.hp <= 0:
            pending = False
        else:
            pending = (self._wild_pokemon.hp > 0)
        return msgs, pending

    def enemy_act(self) -> list[str]:
        """
        Exécute l'action de l'ennemi sauvage.
        Retourne la liste de messages.
        """
        if not self._wild_pokemon or not self._player_pokemon:
            return []

        # Auto-exécution pour charge / verrou / bide
        auto_sym = (
            self._wild_charging or
            (self._wild_locked[0] if self._wild_locked else None) or
            ("bide" if self._wild_bide else None)
        )
        if auto_sym:
            auto_move = next(
                (m for m in self._wild_pokemon.moves
                 if m.dbSymbol.lower().replace("_", "-") == auto_sym),
                None,
            )
            if auto_move:
                can_act, status_msgs = self.check_can_act(is_player=False)
                self._last_wild_move = auto_move
                if not can_act:
                    return status_msgs
                return status_msgs + self.execute_move(
                    self._wild_pokemon, auto_move, self._player_pokemon, False)
            else:
                self._wild_charging = self._wild_locked = self._wild_bide = None

        moves = [m for m in self._wild_pokemon.moves if m.pp > 0]
        if not moves:
            from code.shared.models.move import Move as _Move
            moves = [_Move({"dbSymbol": "struggle", "type": "normal",
                            "power": 50, "accuracy": 100, "pp": 1,
                            "maxpp": 1, "category": "physical", "priority": 0})]
        move = random.choice(moves)
        if move.pp is not None:
            move.pp = max(0, move.pp - 1)
        self._last_wild_move = move

        can_act, status_msgs = self.check_can_act(is_player=False)
        if not can_act:
            return status_msgs

        return status_msgs + self.execute_move(
            self._wild_pokemon, move, self._player_pokemon,
            attacker_is_player=False,
        )

    def collect_end_of_turn(self) -> list[str]:
        """Calcule les dégâts de fin de tour et retourne les messages."""
        msgs = []
        pp  = self._player_pokemon
        wp  = self._wild_pokemon
        pn  = pp.dbSymbol.capitalize() if pp else "?"
        wn  = wp.dbSymbol.capitalize() if wp else "?"

        # ── Statuts (brûlure / poison) ────────────────────────────────────
        for poke, is_pl in [(pp, True), (wp, False)]:
            if not poke or poke.hp <= 0:
                continue
            name = poke.dbSymbol.capitalize()
            pfx  = "" if is_pl else f"Le {name} ennemi "
            if poke.status == "PSN":
                dmg = max(1, poke.maxhp // 8)
                poke.hp = max(0, poke.hp - dmg)
                msgs.append(f"{pfx}{name} est blessé par l'empoisonnement !")
            elif poke.status == "TOX":
                if is_pl: self._player_tox += 1; ctr = self._player_tox
                else:     self._wild_tox   += 1; ctr = self._wild_tox
                dmg = max(1, poke.maxhp * ctr // 16)
                poke.hp = max(0, poke.hp - dmg)
                msgs.append(f"{pfx}{name} est sérieusement blessé par le poison !")
            elif poke.status == "BRN":
                dmg = max(1, poke.maxhp // 8)
                poke.hp = max(0, poke.hp - dmg)
                msgs.append(f"{pfx}{name} est blessé par la brûlure !")

        # ── Vampigraine ────────────────────────────────────────────────────
        if self._wild_leech_seeded and wp and wp.hp > 0:
            dmg = max(1, wp.maxhp // 8)
            wp.hp = max(0, wp.hp - dmg)
            if pp: pp.hp = min(pp.maxhp, pp.hp + dmg)
            msgs.append(f"Le {wn} ennemi perd des PV à cause de la Vampigraine !")
        if self._player_leech_seeded and pp and pp.hp > 0:
            dmg = max(1, pp.maxhp // 8)
            pp.hp = max(0, pp.hp - dmg)
            if wp: wp.hp = min(wp.maxhp, wp.hp + dmg)
            msgs.append(f"{pn} perd des PV à cause de la Vampigraine !")

        # ── Piège (Ligotage, Étreinte…) ────────────────────────────────────
        if self._wild_trapped > 0 and wp and wp.hp > 0:
            self._wild_trapped -= 1
            dmg = max(1, wp.maxhp // 8)
            wp.hp = max(0, wp.hp - dmg)
            msgs.append(f"Le {wn} ennemi est blessé par le piège !")
        if self._player_trapped > 0 and pp and pp.hp > 0:
            self._player_trapped -= 1
            dmg = max(1, pp.maxhp // 8)
            pp.hp = max(0, pp.hp - dmg)
            msgs.append(f"{pn} est blessé par le piège !")

        # ── Décompte écrans / brume ────────────────────────────────────────
        for attr in ("_player_reflect", "_wild_reflect",
                     "_player_screen",  "_wild_screen",
                     "_player_mist",    "_wild_mist"):
            v = getattr(self, attr)
            if v > 0:
                setattr(self, attr, v - 1)

        # ── Désactivation (décompte) ───────────────────────────────────────
        for attr in ("_player_disabled", "_wild_disabled"):
            v = getattr(self, attr)
            if v is not None:
                sym, t = v
                setattr(self, attr, None if t <= 1 else (sym, t - 1))

        return msgs

    def on_wild_fainted(self) -> list[str]:
        """
        Appelé quand le Pokémon sauvage tombe à 0 PV.
        Gère le gain d'XP, la montée de niveau, les moves appris.
        Retourne la liste de messages (sans le message KO lui-même).
        """
        if not self._wild_pokemon or not self._player_pokemon:
            return []

        msgs: list[str] = []
        pname   = self._player_pokemon.dbSymbol.capitalize()
        xp_gain = self.calc_xp_gain()

        if xp_gain > 0:
            old_level = self._player_pokemon.level
            self._player_pokemon.xp += xp_gain
            learned, _pending = self._player_pokemon.check_level_ups()
            levels_gained = self._player_pokemon.level - old_level

            msgs.append(f"{pname} gagne {xp_gain} points d'EXP !")
            if levels_gained > 0:
                msgs.append(f"{pname} monte au niveau {self._player_pokemon.level} !")
            for move_name in learned:
                display = move_name.replace("-", " ").replace("_", " ").title()
                msgs.append(f"{pname} apprend {display} !")

        return msgs

    def end_battle(self, outcome: str) -> None:
        """Point de sortie unique du combat — restaure toujours les transformations."""
        self.restore_transform()
        self._outcome = outcome

    def calc_xp_gain(self) -> int:
        """Calcule les XP gagnés après un KO ennemi."""
        if not self._wild_pokemon or not self._player_pokemon:
            return 0
        base_exp = getattr(self._wild_pokemon, "baseExperience", 100) or 100
        return max(1, math.floor(base_exp * self._wild_pokemon.level / 7))

    # ── Helpers statuts & stades ──────────────────────────────────────────

    def check_can_act(self, is_player: bool) -> tuple[bool, list[str]]:
        """
        Vérifie si un combattant peut agir ce tour.
        Retourne (peut_agir, messages_à_afficher).
        """
        poke = self._player_pokemon if is_player else self._wild_pokemon
        if poke is None:
            return True, []
        name = poke.dbSymbol.capitalize()
        pfx  = "" if is_player else f"Le {name} ennemi "

        # Recharge (Hyper Beam etc.)
        if is_player and self._player_recharging:
            self._player_recharging = False
            return False, [f"{pfx}{name} doit se reposer !"]
        if not is_player and self._wild_recharging:
            self._wild_recharging = False
            return False, [f"{pfx}{name} doit se reposer !"]

        msgs: list[str] = []
        blocked = False
        st = poke.status

        if st == "SLP":
            ctr = self._player_sleep_ctr if is_player else self._wild_sleep_ctr
            ctr -= 1
            if is_player: self._player_sleep_ctr = ctr
            else:          self._wild_sleep_ctr   = ctr
            if ctr <= 0:
                poke.status = ""
                if is_player: self._player_sleep_ctr = 0
                else:          self._wild_sleep_ctr   = 0
                msgs.append(f"{pfx}{name} se réveille !")
            else:
                msgs.append(f"{pfx}{name} est profondément endormi…")
                blocked = True

        elif st == "PAR":
            if random.randint(1, 4) == 1:
                msgs.append(f"{pfx}{name} est complètement paralysé !")
                blocked = True

        elif st == "FRZ":
            if random.randint(1, 5) == 1:
                poke.status = ""
                msgs.append(f"{pfx}{name} se dégèle !")
            else:
                msgs.append(f"{pfx}{name} est gelé !")
                blocked = True

        if blocked:
            return False, msgs

        # Confusion
        ctr = self._player_confused if is_player else self._wild_confused
        if ctr > 0:
            ctr -= 1
            if is_player: self._player_confused = ctr
            else:          self._wild_confused   = ctr
            if ctr <= 0:
                msgs.append(f"{pfx}{name} n'est plus confus !")
            else:
                msgs.append(f"{pfx}{name} est confus !")
                if random.randint(1, 2) == 1:
                    self_dmg = max(1, math.floor(
                        (math.floor(2 * poke.level / 5 + 2) * 40 * poke.atk / max(1, poke.dfe)) / 50
                    ) + 2)
                    self_dmg = math.floor(self_dmg * random.randint(85, 100) / 100)
                    poke.hp = max(0, poke.hp - self_dmg)
                    msgs.append(f"{pfx}{name} se blesse dans sa confusion !")
                    return False, msgs

        return True, msgs

    def apply_status(self, target_poke, status: str, is_target_player: bool,
                     msgs: list[str]) -> None:
        """Inflige un statut si la cible n'en a pas déjà un et n'est pas immunisée."""
        if not target_poke:
            return
        if target_poke.status:
            return
        if not can_inflict_status(status, getattr(target_poke, "type", [])):
            msgs.append("Ça n'a pas d'effet !")
            return
        if status == "any_bpf":
            status = random.choice(["BRN", "PAR", "FRZ"])
        target_poke.status = status
        if status == "SLP":
            turns = random.randint(1, 3)
            if is_target_player:
                self._player_sleep_ctr = turns
            else:
                self._wild_sleep_ctr   = turns
        tname = target_poke.dbSymbol.capitalize()
        pfx   = "" if is_target_player else f"Le {tname} ennemi "
        msgs.append(f"{pfx}{tname} {STATUS_INFLICT_MSG.get(status, '!')}")

    def apply_stage(self, poke, stages: dict[str, int], is_player: bool,
                    msgs: list[str]) -> None:
        """Applique des modifications de stade et génère les messages."""
        # Brume : bloque les baisses de stats
        if any(v < 0 for v in stages.values()):
            if is_player and self._player_mist > 0:
                msgs.append(f"La Brume protège {poke.dbSymbol.capitalize()} !")
                return
            if not is_player and self._wild_mist > 0:
                msgs.append(f"La Brume protège {poke.dbSymbol.capitalize()} !")
                return
        stage_dict = self._player_stages if is_player else self._wild_stages
        name = poke.dbSymbol.capitalize()
        pfx  = "" if is_player else f"Le {name} ennemi "
        _FR = {"atk": "l'Attaque", "def": "la Défense", "spa": "l'Att. Spé.",
               "spd": "la Déf. Spé.", "spe": "la Vitesse",
               "acc": "la Précision", "eva": "l'Esquive"}
        for stat, delta in stages.items():
            old = stage_dict.get(stat, 0)
            new = max(-6, min(6, old + delta))
            stage_dict[stat] = new
            diff = new - old
            if diff == 0:
                msgs.append(f"Le stade de {_FR.get(stat, stat)} de {pfx}{name} ne peut plus changer !")
            elif delta > 0:
                deg = "beaucoup" if abs(delta) >= 2 else ""
                msgs.append(f"{pfx}{name} augmente {deg} {_FR.get(stat, stat)} !")
            else:
                deg = "beaucoup" if abs(delta) >= 2 else ""
                msgs.append(f"{pfx}{name} baisse {deg} {_FR.get(stat, stat)} !")

    def apply_confusion(self, poke, is_player: bool, msgs: list[str]) -> None:
        """Inflige la confusion si le Pokémon n'est pas déjà confus."""
        ctr = self._player_confused if is_player else self._wild_confused
        if ctr > 0:
            return
        turns = random.randint(2, 5)
        if is_player: self._player_confused = turns
        else:          self._wild_confused   = turns
        name = poke.dbSymbol.capitalize()
        pfx  = "" if is_player else f"Le {name} ennemi "
        msgs.append(f"{pfx}{name} est maintenant confus !")

    # ── Mécaniques spéciales ──────────────────────────────────────────────

    def try_special(self, attacker, move, defender,
                    attacker_is_player: bool, effect: dict,
                    msgs: list[str]):
        """
        Gère les attaques à mécanique unique.
        Retourne msgs si le move est traité ici, None pour tomber
        dans la gestion dégâts classique.
        """
        aname = attacker.dbSymbol.capitalize()
        dname = defender.dbSymbol.capitalize()
        apfx  = "" if attacker_is_player else f"Le {aname} ennemi "

        if effect.get("leech_seed"):
            seeded = self._wild_leech_seeded if attacker_is_player else self._player_leech_seeded
            if seeded:
                msgs.append(f"{dname} est déjà ensemencé !")
            else:
                if attacker_is_player: self._wild_leech_seeded   = True
                else:                  self._player_leech_seeded = True
                msgs.append(f"{dname} est ensemencé par une Vampigraine !")
            return msgs

        if effect.get("light_screen"):
            if attacker_is_player: self._player_screen = 5
            else:                  self._wild_screen   = 5
            msgs.append(f"{apfx}{aname} déploie un Écran Lumineux !")
            return msgs

        if effect.get("reflect_move"):
            if attacker_is_player: self._player_reflect = 5
            else:                  self._wild_reflect   = 5
            msgs.append(f"{apfx}{aname} déploie un Miroir !")
            return msgs

        if effect.get("mist_move"):
            if attacker_is_player: self._player_mist = 5
            else:                  self._wild_mist   = 5
            msgs.append(f"{apfx}{aname} se protège avec Brume !")
            return msgs

        if effect.get("focus_energy"):
            if attacker_is_player: self._player_focus_energy = True
            else:                  self._wild_focus_energy   = True
            msgs.append(f"{apfx}{aname} se concentre intensément !")
            return msgs

        if effect.get("end_wild"):
            msgs.append(f"{apfx}{aname} fuit !")
            self.end_battle("fled")
            return msgs

        if effect.get("disable_move"):
            last = self._last_wild_move if attacker_is_player else self._last_player_move
            if last is None:
                msgs.append("L'attaque échoue !")
            else:
                turns = random.randint(1, 8)
                sym   = last.dbSymbol.lower().replace("_", "-")
                if attacker_is_player: self._wild_disabled   = (sym, turns)
                else:                  self._player_disabled = (sym, turns)
                mname2 = last.dbSymbol.replace("-", " ").replace("_", " ").title()
                msgs.append(f"{dname} ne peut plus utiliser {mname2} !")
            return msgs

        if effect.get("mimic"):
            last = self._last_wild_move if attacker_is_player else self._last_player_move
            if last is None:
                msgs.append("L'attaque échoue !")
            else:
                from code.shared.models.move import Move as _M
                new_mv = _M.from_dict(last.to_dict())
                new_mv.pp = min(5, new_mv.maxpp)
                if attacker_is_player and self._player_pokemon:
                    moves = self._player_pokemon.moves
                    # move_idx is not tracked here; replace last used move slot
                    # The caller (battle_screen) knows the move_idx
                    pass
                mname2 = last.dbSymbol.replace("-", " ").replace("_", " ").title()
                msgs.append(f"{apfx}{aname} a appris {mname2} par Imitation !")
            return msgs

        if effect.get("mirror_move"):
            last = self._last_wild_move if attacker_is_player else self._last_player_move
            if last is None:
                msgs.append("L'attaque échoue !")
            else:
                extra = self.execute_move(attacker, last, defender, attacker_is_player)
                msgs.extend(extra[1:])
            return msgs

        if effect.get("metronome"):
            try:
                import json as _j
                from code.shared.config import JSON_DIR as _JD
                from code.shared.models.move import Move as _M2
                pool = _j.load(open(str(_JD / "move_data.json")))
                excl = {"metronome", "struggle", "chatter", "sketch"}
                pool = [v for k, v in pool.items()
                        if v.get("name","").lower() not in excl and k not in excl]
                chosen = random.choice(pool)
                temp = _M2({
                    "dbSymbol":  chosen.get("name", "tackle"),
                    "type":      chosen.get("type", "normal"),
                    "power":     chosen.get("power") or 0,
                    "accuracy":  chosen.get("accuracy") or 100,
                    "pp": 10, "maxpp": 10,
                    "category":  chosen.get("damage_class", "physical"),
                    "priority":  0,
                })
                mname2 = temp.dbSymbol.replace("-", " ").replace("_", " ").title()
                msgs.append(f"→ {mname2} !")
                extra = self.execute_move(attacker, temp, defender, attacker_is_player)
                msgs.extend(extra[1:])
            except Exception:
                msgs.append("L'attaque échoue !")
            return msgs

        if effect.get("transform"):
            self.do_transform(attacker, defender, attacker_is_player, msgs)
            return msgs

        if effect.get("counter"):
            lp = self._last_phys_to_player if attacker_is_player else self._last_phys_to_wild
            if lp <= 0:
                msgs.append("L'attaque échoue !")
            else:
                dmg = lp * 2
                defender.hp = max(0, defender.hp - dmg)
                if attacker_is_player:
                    pass  # wild HP mirror is handled via the pokemon object
                msgs.append(f"{dname} perd {dmg} PV !")
            return msgs

        if effect.get("bide"):
            bide_attr = "_player_bide" if attacker_is_player else "_wild_bide"
            bide_val  = getattr(self, bide_attr)
            if bide_val is None:
                setattr(self, bide_attr, (2, 0))
                msgs.append(f"{apfx}{aname} accumule de l'énergie !")
            else:
                turns, acc = bide_val
                if turns > 1:
                    setattr(self, bide_attr, (turns - 1, acc))
                    msgs.append(f"{apfx}{aname} accumule de l'énergie !")
                else:
                    setattr(self, bide_attr, None)
                    if acc <= 0:
                        msgs.append("L'attaque échoue !")
                    else:
                        release = acc * 2
                        defender.hp = max(0, defender.hp - release)
                        msgs.append(f"{apfx}{aname} libère son énergie !")
                        msgs.append(f"{dname} perd {release} PV !")
            return msgs

        if effect.get("conversion"):
            if attacker.moves:
                new_type = random.choice(attacker.moves).type
                attacker.type = [new_type]
                msgs.append(f"{apfx}{aname} devient de type {new_type.capitalize()} !")
            else:
                msgs.append("L'attaque échoue !")
            return msgs

        return None

    def do_transform(self, attacker, defender, attacker_is_player: bool,
                     msgs: list[str]) -> None:
        """Applique la transformation du Pokémon attaquant."""
        aname = attacker.dbSymbol.capitalize()
        apfx  = "" if attacker_is_player else f"Le {aname} ennemi "

        if attacker_is_player:
            self._player_transformed = {
                "atk":    attacker.atk,
                "dfe":    attacker.dfe,
                "ats":    attacker.ats,
                "dfs":    attacker.dfs,
                "spd":    attacker.spd,
                "type":   list(attacker.type),
                "moves":  list(attacker.moves),
                "stages": dict(self._player_stages),
            }

        attacker.atk  = defender.atk
        attacker.dfe  = defender.dfe
        attacker.ats  = defender.ats
        attacker.dfs  = defender.dfs
        attacker.spd  = defender.spd
        attacker.type = list(defender.type)
        from code.shared.models.move import Move as _M
        attacker.moves = [
            (lambda mv: setattr(mv, "pp", min(5, mv.maxpp)) or mv)(_M.from_dict(m.to_dict()))
            for m in defender.moves
        ]
        if attacker_is_player:
            self._player_stages = dict(self._wild_stages)
        else:
            self._wild_stages = dict(self._player_stages)
        msgs.append(f"{apfx}{aname} se transforme en {defender.dbSymbol.capitalize()} !")

    def restore_transform(self) -> None:
        """Restaure le Pokémon joueur après une transformation."""
        if self._player_transformed and self._player_pokemon:
            d = self._player_transformed
            self._player_pokemon.atk   = d["atk"]
            self._player_pokemon.dfe   = d["dfe"]
            self._player_pokemon.ats   = d["ats"]
            self._player_pokemon.dfs   = d["dfs"]
            self._player_pokemon.spd   = d["spd"]
            self._player_pokemon.type  = d["type"]
            self._player_pokemon.moves = d["moves"]
            self._player_stages        = d["stages"]
            self._player_transformed   = None

    def execute_move(
        self,
        attacker, move, defender,
        attacker_is_player: bool,
    ) -> list[str]:
        """Exécute un move complet. Retourne la liste de messages."""
        aname  = attacker.dbSymbol.capitalize()
        dname  = defender.dbSymbol.capitalize()
        mname  = move.dbSymbol.replace("-", " ").replace("_", " ").title()
        apfx   = "" if attacker_is_player else f"Le {aname} ennemi "
        dpfx   = "Le " + dname + " ennemi " if attacker_is_player else ""
        effect = lookup_effect(move.dbSymbol)
        msgs   = [f"{apfx}{aname} utilise {mname} !"]

        acc = effect.get("acc_override", move.accuracy) or 100
        if not (random.randint(1, 100) <= acc):
            msgs.append("L'attaque échoue !")
            return msgs

        # ── Haze (réinitialise tous les stades) ──────────────────────────
        if effect.get("haze"):
            _s0 = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
            self._player_stages = dict(_s0)
            self._wild_stages   = dict(_s0)
            msgs.append("Tous les changements de statistiques ont été annulés !")
            return msgs

        # ── Mécaniques spéciales (Métronome, Transform, Bide…) ───────────
        sp = self.try_special(attacker, move, defender, attacker_is_player, effect, msgs)
        if sp is not None:
            return sp

        # ── Soin pur ─────────────────────────────────────────────────────
        if "heal" in effect and not effect.get("damage"):
            if effect.get("rest_sleep"):
                attacker.status = ""
                attacker.hp = attacker.maxhp
                if attacker_is_player: self._player_sleep_ctr = 2
                else:                  self._wild_sleep_ctr   = 2
                attacker.status = "SLP"
                msgs.append(f"{apfx}{aname} s'endort et récupère tous ses PV !")
            else:
                old_hp = attacker.hp
                attacker.hp = min(attacker.maxhp, attacker.hp + int(attacker.maxhp * effect["heal"]))
                msgs.append(f"{apfx}{aname} récupère {attacker.hp - old_hp} PV !")
            return msgs

        # ── Statut / stades / confusion purs ─────────────────────────────
        if not effect.get("damage") and (
            "status" in effect or "stages" in effect or "confuse" in effect
        ):
            tgt_is_foe    = (effect.get("target") == "foe")
            target        = defender if tgt_is_foe else attacker
            tgt_is_player = not attacker_is_player if tgt_is_foe else attacker_is_player
            if "status" in effect:
                self.apply_status(target, effect["status"], tgt_is_player, msgs)
            if "stages" in effect:
                self.apply_stage(target, effect["stages"], tgt_is_player, msgs)
            if effect.get("confuse"):
                self.apply_confusion(target, tgt_is_player, msgs)
            return msgs

        # ── Dégâts ───────────────────────────────────────────────────────
        atk_s     = self._player_stages if attacker_is_player else self._wild_stages
        def_s     = self._wild_stages   if attacker_is_player else self._player_stages
        burned    = (attacker.status == "BRN")
        high_crit = effect.get("high_crit", False)

        # ── Deux tours de charge (Vol, Tunnel, Laser-Soleil…) ──────────────
        if effect.get("two_turn"):
            sym     = move.dbSymbol.lower().replace("_", "-")
            ch_attr = "_player_charging" if attacker_is_player else "_wild_charging"
            if getattr(self, ch_attr) != sym:
                setattr(self, ch_attr, sym)
                msgs.append(f"{apfx}{aname} {effect.get('charge_msg','se prépare !')}")
                if "stages" in effect and effect.get("target") == "self":
                    self.apply_stage(attacker, effect["stages"], attacker_is_player, msgs)
                return msgs
            else:
                setattr(self, ch_attr, None)

        # Dream Eater : échoue si la cible n'est pas endormie
        if effect.get("drain_sleep_only") and defender.status != "SLP":
            msgs.append(f"{dpfx}{dname} n'est pas endormi !")
            return msgs

        # OHKO
        if effect.get("ohko"):
            eff = type_effectiveness(move.type, defender.type)
            if eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            else:
                msgs.append("Coup fatal !")
                defender.hp = 0
            return msgs

        # Dégâts fixes
        if "fixed_dmg" in effect:
            eff = type_effectiveness(move.type, defender.type)
            if eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            else:
                dmg = effect["fixed_dmg"]
                defender.hp = max(0, defender.hp - dmg)
                msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Dégâts = niveau
        if effect.get("level_dmg"):
            eff = type_effectiveness(move.type, defender.type)
            if eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            else:
                dmg = attacker.level
                defender.hp = max(0, defender.hp - dmg)
                msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Psyko (dégâts aléatoires 50-150% du niveau)
        if effect.get("psywave"):
            dmg = max(1, int(attacker.level * random.randint(50, 150) / 100))
            defender.hp = max(0, defender.hp - dmg)
            msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Griffe-Acier (demi-PV de la cible)
        if effect.get("half_hp"):
            dmg = max(1, defender.hp // 2)
            defender.hp = max(0, defender.hp - dmg)
            msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Multi-coups
        if effect.get("multi_hit"):
            multi = effect["multi_hit"]
            if multi is True:
                r = random.randint(1, 8)
                num_hits = 2 if r <= 3 else (3 if r <= 6 else (4 if r == 7 else 5))
            else:
                lo, hi = multi
                num_hits = random.randint(lo, hi)
            total_dmg = 0
            first_eff = 1.0
            any_crit  = False
            hit_count = 0
            for h in range(num_hits):
                if defender.hp <= 0:
                    break
                h_dmg, h_eff, h_crit = calc_damage(
                    attacker, move, defender,
                    atk_stage=atk_s.get("atk" if move.category != "special" else "spa", 0),
                    def_stage=def_s.get("def" if move.category != "special" else "spd", 0),
                    burned=burned, high_crit=high_crit,
                )
                defender.hp = max(0, defender.hp - h_dmg)
                total_dmg += h_dmg
                hit_count  += 1
                if h == 0:
                    first_eff = h_eff
                if h_crit:
                    any_crit = True
            if any_crit:  msgs.append("Coup critique !")
            if first_eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            elif first_eff >= 2:
                msgs.append("C'est super efficace !")
            elif first_eff < 1:
                msgs.append("Ce n'est pas très efficace…")
            if total_dmg > 0:
                msgs.append(f"L'attaque a frappé {hit_count} fois !")
                msgs.append(f"{dpfx}{dname} perd {total_dmg} PV au total !")
            if defender.hp > 0 and "status" in effect:
                chance = effect.get("chance", 100)
                if random.randint(1, 100) <= chance:
                    self.apply_status(defender, effect["status"], not attacker_is_player, msgs)
            return msgs

        # Dégâts normaux
        hc  = high_crit or (self._player_focus_energy if attacker_is_player else self._wild_focus_energy)
        dmg, eff, crit = calc_damage(
            attacker, move, defender,
            atk_stage=atk_s.get("atk" if move.category != "special" else "spa", 0),
            def_stage=def_s.get("def" if move.category != "special" else "spd", 0),
            burned=burned, high_crit=hc,
        )
        # ── Réduction Écran Lumineux / Miroir ────────────────────────────
        if eff > 0 and dmg > 0:
            if not attacker_is_player:
                if move.category == "special" and self._player_screen > 0:
                    dmg = max(1, dmg // 2)
                elif move.category == "physical" and self._player_reflect > 0:
                    dmg = max(1, dmg // 2)
            else:
                if move.category == "special" and self._wild_screen > 0:
                    dmg = max(1, dmg // 2)
                elif move.category == "physical" and self._wild_reflect > 0:
                    dmg = max(1, dmg // 2)

        defender.hp = max(0, defender.hp - dmg)

        # Suivi dégâts physiques (Riposte / Furia / Bide)
        if dmg > 0 and move.category == "physical":
            if attacker_is_player:  self._last_phys_to_wild   = dmg
            else:                   self._last_phys_to_player = dmg
        if dmg > 0:
            if not attacker_is_player and self._player_bide:
                turns, acc = self._player_bide
                self._player_bide = (turns, acc + dmg)
            elif attacker_is_player and self._wild_bide:
                turns, acc = self._wild_bide
                self._wild_bide = (turns, acc + dmg)
        # Furia : ATK +1 sur le défenseur si Furia actif
        if dmg > 0:
            if not attacker_is_player and self._player_rage:
                self.apply_stage(attacker, {"atk": +1}, True, msgs)
            elif attacker_is_player and self._wild_rage:
                self.apply_stage(attacker, {"atk": +1}, False, msgs)

        if crit:    msgs.append("Coup critique !")
        if eff == 0:
            msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
        elif eff >= 2:
            msgs.append("C'est super efficace !")
        elif eff < 1:
            msgs.append("Ce n'est pas très efficace…")
        if dmg > 0:
            msgs.append(f"{dpfx}{dname} perd {dmg} PV !")

        # Recul
        if effect.get("recoil") and dmg > 0:
            recoil_dmg = max(1, int(dmg * effect["recoil"]))
            attacker.hp = max(0, attacker.hp - recoil_dmg)
            msgs.append(f"{apfx}{aname} est blessé par le recul !")

        # Auto-destruction
        if effect.get("self_destruct"):
            attacker.hp = 0
            msgs.append(f"{apfx}{aname} s'est sacrifié !")

        # Recharge
        if effect.get("recharge"):
            if attacker_is_player: self._player_recharging = True
            else:                  self._wild_recharging   = True

        # Effets secondaires si défenseur encore vivant
        if defender.hp > 0:
            if "status" in effect:
                chance = effect.get("chance", 100)
                if random.randint(1, 100) <= chance:
                    self.apply_status(defender, effect["status"], not attacker_is_player, msgs)
            if effect.get("confuse"):
                chance = effect.get("chance", 100)
                if random.randint(1, 100) <= chance:
                    self.apply_confusion(defender, not attacker_is_player, msgs)
            if "stages" in effect:
                tgt = effect.get("target", "foe")
                if tgt == "foe":
                    self.apply_stage(defender, effect["stages"], not attacker_is_player, msgs)
                else:
                    self.apply_stage(attacker, effect["stages"], attacker_is_player, msgs)
            if effect.get("drain") and dmg > 0:
                heal_amt = max(1, int(dmg * effect["drain"]))
                attacker.hp = min(attacker.maxhp, attacker.hp + heal_amt)
                msgs.append(f"{apfx}{aname} récupère {heal_amt} PV !")

        # ── Piège ────────────────────────────────────────────────────────
        if effect.get("trap") and dmg > 0 and defender.hp > 0:
            if attacker_is_player:
                self._wild_trapped   = random.randint(2, 5)
                msgs.append(f"Le {dname} ennemi est pris au piège !")
            else:
                self._player_trapped = random.randint(2, 5)
                msgs.append(f"{dname} est pris au piège !")

        # ── Verrou (Triplattaque / Pétale-Danse) ────────────────────────
        if effect.get("lock_move"):
            sym = move.dbSymbol.lower().replace("_", "-")
            if attacker_is_player:
                if self._player_locked is None:
                    self._player_locked = (sym, random.randint(2, 3))
                else:
                    s, t = self._player_locked
                    t -= 1
                    if t <= 0:
                        self._player_locked = None
                        self.apply_confusion(attacker, True, msgs)
                    else:
                        self._player_locked = (s, t)
            else:
                if self._wild_locked is None:
                    self._wild_locked = (sym, random.randint(2, 3))
                else:
                    s, t = self._wild_locked
                    t -= 1
                    if t <= 0:
                        self._wild_locked = None
                        self.apply_confusion(attacker, False, msgs)
                    else:
                        self._wild_locked = (s, t)

        # ── Furia : active le mode rage ───────────────────────────────────
        if effect.get("rage") and dmg > 0:
            if attacker_is_player: self._player_rage = True
            else:                  self._wild_rage   = True

        return msgs
