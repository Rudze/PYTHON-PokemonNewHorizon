"""Shared battle result data model."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BattleResult:
    """Résultat d'un combat, partagé entre client et serveur."""
    outcome: str          # "won" | "lost" | "fled"
    xp_gained: int = 0
    levels_gained: int = 0
    learned_moves: list = field(default_factory=list)
