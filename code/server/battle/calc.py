"""Damage calculation helpers (Gen 5 formula)."""
from __future__ import annotations
import math
import random

from code.server.battle.type_chart import type_effectiveness


def stage_mult(stage: int) -> float:
    """Retourne le multiplicateur de stade pour une valeur de -6 à +6."""
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
    Formule officielle Gen 5.
    Retourne (dégâts, multiplicateur_type, coup_critique).
    """
    power = move.power or 0
    if not power or move.category == "status":
        return 0, 1.0, False

    if move.category == "special":
        A = attacker.ats * stage_mult(atk_stage)
        D = defender.dfs * stage_mult(def_stage)
    else:
        A = attacker.atk * stage_mult(atk_stage)
        D = defender.dfe * stage_mult(def_stage)
        if burned:
            A *= 0.5

    D = max(D, 1)
    base = math.floor((math.floor(2 * attacker.level / 5 + 2) * power * A / D) / 50) + 2

    if move.type in attacker.type:
        base = math.floor(base * 1.5)

    eff = type_effectiveness(move.type, defender.type)
    base = math.floor(base * eff)

    crit_threshold = 8 if high_crit else 16
    is_crit = random.randint(1, crit_threshold) == 1
    if is_crit:
        base = math.floor(base * 1.5)

    base = math.floor(base * random.randint(85, 100) / 100)
    return (max(1, base) if eff > 0 else 0), eff, is_crit
