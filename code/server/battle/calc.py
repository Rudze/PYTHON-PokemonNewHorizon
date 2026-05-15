"""Damage calculation helpers (Gen 5 formula + ability modifiers)."""
from __future__ import annotations
import math
import random

from code.server.battle.type_chart import type_effectiveness
from code.server.battle import ability_handler as ab


def stage_mult(stage: int) -> float:
    if stage >= 0:
        return (2 + stage) / 2.0
    return 2.0 / (2 - stage)


def calc_damage(
    attacker,
    move,
    defender,
    atk_stage: int = 0,
    def_stage: int = 0,
    burned: bool = False,
    high_crit: bool = False,
) -> tuple[int, float, bool]:
    """
    Formule Gen 5 avec modificateurs de talents.
    Retourne (dégâts, multiplicateur_type, coup_critique).
    """
    power = move.power or 0
    if not power or move.category == "status":
        return 0, 1.0, False

    # Lévitation : immunité Sol
    if ab.is_levitating(defender) and getattr(move, "type", "") == "ground":
        return 0, 0.0, False

    eff = type_effectiveness(move.type, defender.type)

    # Wonder Guard : immune aux non-super-efficaces
    if ab.wonder_guard_blocks(defender, eff):
        return 0, eff, False

    if move.category == "special":
        A = attacker.ats * stage_mult(atk_stage) * ab.get_atk_modifier(attacker, move)
        D = defender.dfs * stage_mult(def_stage) * ab.get_def_modifier(defender, move)
    else:
        A = attacker.atk * stage_mult(atk_stage) * ab.get_atk_modifier(attacker, move)
        D = defender.dfe * stage_mult(def_stage) * ab.get_def_modifier(defender, move)
        if burned:
            A *= 0.5

    D = max(D, 1)
    base = math.floor((math.floor(2 * attacker.level / 5 + 2) * power * A / D) / 50) + 2

    if move.type in attacker.type:
        base = math.floor(base * 1.5)

    base = math.floor(base * eff)

    # Coup critique (bloqué par Battle Armor / Shell Armor)
    crit_threshold = 8 if high_crit else 16
    is_crit = (not ab.prevents_crit(defender)) and (random.randint(1, crit_threshold) == 1)
    if is_crit:
        base = math.floor(base * 1.5)

    base = math.floor(base * random.randint(85, 100) / 100)

    # Sturdy : survivre à un KO d'un coup si PV max
    final = max(1, base) if eff > 0 else 0
    final = ab.check_sturdy(defender, final)

    return final, eff, is_crit
