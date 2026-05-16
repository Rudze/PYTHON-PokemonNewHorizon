"""
ability_handler.py — Effets des talents Pokémon dans le combat.

Intégration dans BattleManager :
  - get_atk_modifier()    → multiplicateur ATK/ATS de l'attaquant
  - get_def_modifier()    → multiplicateur DEF/DFS du défenseur
  - is_move_absorbed()    → immunité + soin (Absorb-eau, Volt-Absorb, Feu-Force…)
  - is_immune_to_status() → immunités de statut
  - blocks_stat_drop()    → bloque les baisses de stats adverses
  - prevents_crit()       → bloque les coups critiques
  - get_acc_modifier()    → modificateur de précision de l'attaquant
  - get_sec_chance_mult() → multiplicateur de chance d'effet secondaire
  - on_contact()          → effets de contact (Statik, Corps-Brûlé…)
  - on_end_of_turn()      → effets de fin de tour
  - on_battle_start()     → effets d'entrée (Intimidation…)
"""
from __future__ import annotations
import random
import math


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ──────────────────────────────────────────────────────────────────────────────

def _ability(pokemon) -> str:
    """Retourne le talent actif du Pokémon (lowercase, tirets)."""
    ab = getattr(pokemon, "ability", None) or ""
    return ab.lower().replace("_", "-")

def _hp_ratio(pokemon) -> float:
    return pokemon.hp / pokemon.maxhp if getattr(pokemon, "maxhp", 0) else 1.0

def _has_status(pokemon) -> bool:
    return bool(getattr(pokemon, "status", ""))


# ──────────────────────────────────────────────────────────────────────────────
# Modificateurs de dégâts
# ──────────────────────────────────────────────────────────────────────────────

_PINCH_ABILITIES = {
    "overgrow":  "grass",
    "blaze":     "fire",
    "torrent":   "water",
    "swarm":     "bug",
}

def get_atk_modifier(attacker, move) -> float:
    """Multiplicateur appliqué à l'ATK/ATS de l'attaquant."""
    ab  = _ability(attacker)
    mod = 1.0

    # ── Talents "pinch" (×1.5 si HP ≤ 1/3) ──────────────────────────────────
    pinch_type = _PINCH_ABILITIES.get(ab)
    if pinch_type and getattr(move, "type", "") == pinch_type and _hp_ratio(attacker) <= 1 / 3:
        mod *= 1.5

    # ── Puissance double ATK ────────────────────────────────────────────────
    if ab in ("huge-power", "pure-power"):
        if getattr(move, "category", "") == "physical":
            mod *= 2.0

    # ── Hustle : +1.5× physique (précision gérée séparément) ────────────────
    if ab == "hustle" and getattr(move, "category", "") == "physical":
        mod *= 1.5

    # ── Guts : +1.5× physique si statué ────────────────────────────────────
    if ab == "guts" and _has_status(attacker) and getattr(move, "category", "") == "physical":
        mod *= 1.5

    # ── Solar-power : +1.5× spécial sous soleil (simplifié : toujours actif) ─
    if ab == "solar-power" and getattr(move, "category", "") == "special":
        mod *= 1.5

    # ── Plus / Minus : +1.5× spécial (talent de duo, simplifié) ────────────
    if ab in ("plus", "minus") and getattr(move, "category", "") == "special":
        mod *= 1.5

    return mod


def get_def_modifier(defender, move) -> float:
    """Multiplicateur appliqué à la DEF/DFS du défenseur."""
    ab  = _ability(defender)
    mod = 1.0
    cat = getattr(move, "category", "")
    typ = getattr(move, "type", "")

    # ── Marvel Scale : +1.5× DEF si statué ─────────────────────────────────
    if ab == "marvel-scale" and _has_status(defender) and cat == "physical":
        mod *= 1.5

    # ── Thick Fat / Heat Proof : ×0.5 Feu/Glace ────────────────────────────
    if ab == "thick-fat" and typ in ("fire", "ice"):
        mod *= 2.0   # double la DEF effective = divise les dégâts par 2
    if ab == "heatproof" and typ == "fire":
        mod *= 2.0

    # ── Fur Coat : ×0.5 physique ────────────────────────────────────────────
    if ab == "fur-coat" and cat == "physical":
        mod *= 2.0

    return mod


# ──────────────────────────────────────────────────────────────────────────────
# Absorption de moves (immunité + effet positif)
# ──────────────────────────────────────────────────────────────────────────────

_ABSORB_ABILITIES: dict[str, dict] = {
    "volt-absorb":   {"type": "electric", "heal": 0.25},
    "water-absorb":  {"type": "water",    "heal": 0.25},
    "dry-skin":      {"type": "water",    "heal": 0.25},
    "flash-fire":    {"type": "fire",     "heal": 0.0, "boost_type": "fire"},
    "lightning-rod": {"type": "electric", "heal": 0.0, "stage": {"spa": 1}},
    "motor-drive":   {"type": "electric", "heal": 0.0, "stage": {"spe": 1}},
    "storm-drain":   {"type": "water",    "heal": 0.0, "stage": {"spa": 1}},
    "sap-sipper":    {"type": "grass",    "heal": 0.0, "stage": {"atk": 1}},
    "earth-eater":   {"type": "ground",   "heal": 0.25},
    "well-baked-body": {"type": "fire",   "heal": 0.0, "stage": {"def": 2}},
}

def is_move_absorbed(defender, move, manager, is_defender_player: bool, msgs: list[str]) -> bool:
    """
    Vérifie si le talent du défenseur absorbe ce move.
    Si oui, applique l'effet et retourne True.
    """
    ab  = _ability(defender)
    cfg = _ABSORB_ABILITIES.get(ab)
    if not cfg:
        return False
    if getattr(move, "type", "") != cfg["type"]:
        return False

    name = defender.dbSymbol.capitalize()
    pfx  = "" if is_defender_player else f"Le {name} ennemi "
    msgs.append(f"{pfx}{name} absorbe l'attaque grâce à {ab} !")

    # Soin
    if cfg.get("heal", 0) > 0:
        heal = max(1, int(defender.maxhp * cfg["heal"]))
        defender.hp = min(defender.maxhp, defender.hp + heal)
        msgs.append(f"{pfx}{name} récupère {heal} PV !")

    # Bonus de stade
    if "stage" in cfg and manager is not None:
        manager.apply_stage(defender, cfg["stage"], is_defender_player, msgs)

    # Flash Fire : boost interne (géré comme flag dans le manager si besoin)

    return True


# ──────────────────────────────────────────────────────────────────────────────
# Immunités de statut
# ──────────────────────────────────────────────────────────────────────────────

_STATUS_IMMUNITY_ABILITIES: dict[str, set[str]] = {
    "limber":       {"PAR"},
    "insomnia":     {"SLP"},
    "vital-spirit": {"SLP"},
    "immunity":     {"PSN", "TOX"},
    "magma-armor":  {"FRZ"},
    "water-veil":   {"BRN"},
    "water-bubble": {"BRN"},
    "leaf-guard":   {"SLP"},  # simplifié (normalement soleil)
    "sweet-veil":   {"SLP"},
    "comatose":     {"SLP", "PSN", "TOX", "BRN", "PAR", "FRZ"},
    "purifying-salt": {"SLP", "PSN", "TOX", "BRN", "PAR", "FRZ"},
    "own-tempo":    {"confusion"},
    "oblivious":    {"attraction"},
    "soundproof":   set(),  # géré manuellement pour les sons
    "shields-down": set(),
}

def is_immune_to_status(pokemon, status: str) -> bool:
    """Vrai si le talent empêche d'infliger ce statut."""
    ab = _ability(pokemon)
    return status in _STATUS_IMMUNITY_ABILITIES.get(ab, set())


# ──────────────────────────────────────────────────────────────────────────────
# Protection des statistiques
# ──────────────────────────────────────────────────────────────────────────────

_STAT_PROTECT_ABILITIES = {
    "clear-body", "white-smoke", "full-metal-body",
    "hyper-cutter",   # protège seulement ATK, géré globalement ici
    "keen-eye",       # protège seulement Précision
    "big-pecks",      # protège seulement DEF
    "mirror-armor",   # renvoie les baisses (simplifié : bloque)
}

def blocks_stat_drop(pokemon) -> bool:
    """Vrai si le talent bloque les baisses de stats adverses (globalement)."""
    return _ability(pokemon) in _STAT_PROTECT_ABILITIES


# ──────────────────────────────────────────────────────────────────────────────
# Coups critiques
# ──────────────────────────────────────────────────────────────────────────────

def prevents_crit(defender) -> bool:
    """Vrai si le talent bloque les coups critiques."""
    return _ability(defender) in ("battle-armor", "shell-armor")


# ──────────────────────────────────────────────────────────────────────────────
# Précision / Effets secondaires
# ──────────────────────────────────────────────────────────────────────────────

def get_acc_modifier(attacker) -> float:
    """Multiplicateur de précision de l'attaquant (appliqué à move.accuracy)."""
    ab = _ability(attacker)
    if ab == "compound-eyes":
        return 1.30
    if ab == "hustle":
        return 0.80
    if ab == "tangled-feet":  # simplifié (normalement si confus)
        return 0.50 if random.random() < 0.5 else 1.0
    return 1.0

def get_sec_chance_mult(attacker) -> float:
    """Multiplicateur de chance d'effet secondaire (Grâce Naturelle…)."""
    if _ability(attacker) == "serene-grace":
        return 2.0
    return 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Effets de contact
# ──────────────────────────────────────────────────────────────────────────────

def on_contact(attacker, defender, move, manager, attacker_is_player: bool,
               msgs: list[str]) -> None:
    """
    Appeler après un coup physique qui touche.
    Gère : Static, Corps-Brûlé, Point-Poison, Peau-Rugueuse, Filament.
    """
    if getattr(move, "category", "") != "physical":
        return

    ab_def = _ability(defender)
    ab_att = _ability(attacker)

    aname = attacker.dbSymbol.capitalize()
    apfx  = "" if attacker_is_player else f"Le {aname} ennemi "

    # ── Talents du défenseur qui affectent l'attaquant ───────────────────────
    # Peau Rugueuse / Filament : 1/8 PV en dégâts
    if ab_def in ("rough-skin", "iron-barbs"):
        dmg = max(1, attacker.maxhp // 8)
        attacker.hp = max(0, attacker.hp - dmg)
        msgs.append(f"{apfx}{aname} est blessé par le talent de {defender.dbSymbol.capitalize()} !")

    # Statik → PAR (30 %)
    if ab_def == "static" and not attacker.status and random.randint(1, 100) <= 30:
        if manager: manager.apply_status(attacker, "PAR", attacker_is_player, msgs)

    # Corps-Brûlé → BRN (30 %)
    if ab_def == "flame-body" and not attacker.status and random.randint(1, 100) <= 30:
        if manager: manager.apply_status(attacker, "BRN", attacker_is_player, msgs)

    # Point-Poison → PSN (30 %)
    if ab_def == "poison-point" and not attacker.status and random.randint(1, 100) <= 30:
        if manager: manager.apply_status(attacker, "PSN", attacker_is_player, msgs)

    # Pollen Spore / Spore → SLP, PSN ou PAR (30 %)
    if ab_def == "effect-spore" and not attacker.status and random.randint(1, 100) <= 30:
        status = random.choice(["SLP", "PAR", "PSN"])
        if manager: manager.apply_status(attacker, status, attacker_is_player, msgs)

    # ── Talents de l'attaquant qui s'activent au contact ─────────────────────
    # Éclair Statique de l'attaquant → non applicable ici (le défenseur toucherait)
    # Roc Solide : si le défenseur a roc-solid, diviser les dégâts de super-efficaces
    # (géré dans get_def_modifier)


# ──────────────────────────────────────────────────────────────────────────────
# Effets de fin de tour
# ──────────────────────────────────────────────────────────────────────────────

def on_end_of_turn(pokemon, is_player: bool, manager, msgs: list[str]) -> None:
    """Talents à effet de fin de tour."""
    ab   = _ability(pokemon)
    name = pokemon.dbSymbol.capitalize()
    pfx  = "" if is_player else f"Le {name} ennemi "

    if pokemon.hp <= 0:
        return

    # Turbo : +1 Vitesse par tour
    if ab == "speed-boost":
        stages = manager._player_stages if is_player else manager._wild_stages
        cur = stages.get("spe", 0)
        if cur < 6:
            stages["spe"] = cur + 1
            msgs.append(f"{pfx}{name} gagne de la Vitesse grâce à Turbo !")

    # Mue : 33 % de guérir un statut
    if ab == "shed-skin" and pokemon.status:
        if random.randint(1, 3) == 1:
            pokemon.status = ""
            msgs.append(f"{pfx}{name} a mué et guéri son statut !")

    # Grive → soigne 1/16 (simplifié, normalement pluie)
    if ab == "rain-dish":
        heal = max(1, pokemon.maxhp // 16)
        pokemon.hp = min(pokemon.maxhp, pokemon.hp + heal)
        msgs.append(f"{pfx}{name} récupère des PV grâce à Grive !")

    # Peau Sèche → dégâts sous soleil (simplifié : 1/8 par tour si pas d'eau)
    if ab == "dry-skin":
        dmg = max(1, pokemon.maxhp // 8)
        pokemon.hp = max(0, pokemon.hp - dmg)
        msgs.append(f"{pfx}{name} est blessé par la sécheresse !")

    # Synchro : copie le statut au manager
    if ab == "synchronize" and pokemon.status and manager:
        target    = manager._wild_pokemon if is_player else manager._player_pokemon
        tgt_pl    = not is_player
        if target and not target.status:
            target_msgs: list[str] = []
            manager.apply_status(target, pokemon.status, tgt_pl, target_msgs)
            msgs.extend(target_msgs)

    # Ardeur → +1 SPE après apeurement (simplif : +1 SPE si statué PAR)
    if ab == "steadfast" and pokemon.status == "PAR":
        stages = manager._player_stages if is_player else manager._wild_stages
        cur = stages.get("spe", 0)
        if cur < 6:
            stages["spe"] = cur + 1
            msgs.append(f"{pfx}{name} gagne de la Vitesse grâce à Ardeur !")


# ──────────────────────────────────────────────────────────────────────────────
# Effets d'entrée en combat
# ──────────────────────────────────────────────────────────────────────────────

def on_battle_start(player_poke, wild_poke, manager, msgs: list[str]) -> None:
    """Talents qui s'activent en entrant sur le terrain."""
    # Intimidation → -1 ATK adversaire
    if _ability(player_poke) == "intimidate":
        manager.apply_stage(wild_poke, {"atk": -1}, False, msgs)

    if _ability(wild_poke) == "intimidate":
        manager.apply_stage(player_poke, {"atk": -1}, True, msgs)

    # Traquenard (Pressure) → message d'entrée uniquement
    if _ability(wild_poke) == "pressure":
        msgs.append(f"Le {wild_poke.dbSymbol.capitalize()} ennemi exerce une Pression !")


# ──────────────────────────────────────────────────────────────────────────────
# Wonder Guard
# ──────────────────────────────────────────────────────────────────────────────

def wonder_guard_blocks(defender, move_effectiveness: float) -> bool:
    """Vrai si Garde-Mystik bloque ce move (efficacité ≤ 1×)."""
    return _ability(defender) == "wonder-guard" and move_effectiveness <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Lévitation (immunité Sol)
# ──────────────────────────────────────────────────────────────────────────────

def is_levitating(pokemon) -> bool:
    """Vrai si le talent rend immunisé aux moves Sol."""
    return _ability(pokemon) == "levitate"


# ──────────────────────────────────────────────────────────────────────────────
# Sturdy (1 PV survive)
# ──────────────────────────────────────────────────────────────────────────────

def check_sturdy(defender, damage: int) -> int:
    """
    Si le talent est Sturdy et que le Pokémon est à PV max,
    réduit les dégâts à hp-1 pour éviter le KO d'un coup.
    """
    if _ability(defender) != "sturdy":
        return damage
    if defender.hp == defender.maxhp and damage >= defender.hp:
        return defender.hp - 1   # survit avec 1 PV
    return damage


# ──────────────────────────────────────────────────────────────────────────────
# Early Bird (sommeil plus court)
# ──────────────────────────────────────────────────────────────────────────────

def sleep_turns_for(pokemon, base_turns: int) -> int:
    """Retourne les tours de sommeil initiaux, modifiés par le talent."""
    if _ability(pokemon) == "early-bird":
        return max(1, base_turns // 2)
    return base_turns


# ──────────────────────────────────────────────────────────────────────────────
# Anger Point (+6 ATK sur coup critique reçu)
# ──────────────────────────────────────────────────────────────────────────────

def on_critical_received(defender, is_player: bool, manager, msgs: list[str]) -> None:
    """Appeler quand le défenseur reçoit un coup critique."""
    if _ability(defender) == "anger-point":
        stages = manager._player_stages if is_player else manager._wild_stages
        stages["atk"] = 6
        msgs.append(f"{defender.dbSymbol.capitalize()} atteint son maximum d'Attaque grâce à Colère !")
