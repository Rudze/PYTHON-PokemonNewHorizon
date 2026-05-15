"""Status condition immunities and helpers."""
from __future__ import annotations

STATUS_IMMUNITIES: dict[str, list[str]] = {
    "BRN": ["fire"],
    "PSN": ["poison", "steel"],
    "TOX": ["poison", "steel"],
    "PAR": ["electric"],
    "FRZ": ["ice"],
}


def can_inflict_status(status: str, target_types: list[str]) -> bool:
    """Retourne True si le statut peut être infligé au Pokémon de ces types."""
    return not any(t in STATUS_IMMUNITIES.get(status, []) for t in target_types)


STATUS_INFLICT_MSG: dict[str, str] = {
    "SLP": "s'endort !",
    "PSN": "est empoisonné !",
    "TOX": "est gravement empoisonné !",
    "BRN": "est brûlé !",
    "PAR": "est paralysé !",
    "FRZ": "est gelé !",
}
