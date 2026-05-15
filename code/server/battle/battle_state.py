"""Volatile battle state dataclass — reset at the start of each battle."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BattleVolatile:
    """État volatile d'un combattant (reset à chaque nouveau combat)."""
    sleep_ctr:    int         = 0
    tox_ctr:      int         = 0
    confused:     int         = 0
    recharging:   bool        = False
    charging:     str | None  = None    # sym en charge (Vol, Tunnel…)
    locked:       tuple | None = None   # (sym, turns_left)
    trapped:      int         = 0
    disabled:     tuple | None = None   # (move_sym, turns_left)
    rage:         bool        = False
    focus_energy: bool        = False
    bide:         tuple | None = None   # (turns_left, dmg_accum)
    last_move:    object      = None    # dernier Move utilisé
    last_phys_dmg: int        = 0
    stages: dict = field(default_factory=lambda: {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0})
    leech_seeded: bool        = False
    reflect_turns: int        = 0
    screen_turns:  int        = 0
    mist_turns:    int        = 0
    transformed:  dict | None = None
