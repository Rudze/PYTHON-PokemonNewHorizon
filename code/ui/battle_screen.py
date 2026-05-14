"""BattleScreen — panel dimensionné sur le background, UI assets."""
from __future__ import annotations
import math
import random
import time
import pygame
from PIL import Image
from code.config import (SPRITES_BATTLE_DIR, BATTLE_ZONE, BATTLE_UI,
                         MOVE_TYPE_ROW, FONTS_DIR, BATTLE_INTERFACES_DIR)
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


def _stage_mult(stage: int) -> float:
    if stage >= 0:
        return (2 + stage) / 2.0
    return 2.0 / (2 - stage)


_STATUS_IMMUNITIES: dict[str, list[str]] = {
    "BRN": ["fire"],
    "PSN": ["poison", "steel"],
    "TOX": ["poison", "steel"],
    "PAR": ["electric"],
    "FRZ": ["ice"],
}


def _can_inflict_status(status: str, target_types: list[str]) -> bool:
    return not any(t in _STATUS_IMMUNITIES.get(status, []) for t in target_types)


_STATUS_INFLICT_MSG: dict[str, str] = {
    "SLP": "s'endort !",
    "PSN": "est empoisonné !",
    "TOX": "est gravement empoisonné !",
    "BRN": "est brûlé !",
    "PAR": "est paralysé !",
    "FRZ": "est gelé !",
}


_MOVE_EFFECTS: dict[str, dict] = {
    # ── Statut pur ────────────────────────────────────────────────────────
    "thunder-wave":     {"status": "PAR", "target": "foe", "acc_override": 100},
    "stun-spore":       {"status": "PAR", "target": "foe"},
    "glare":            {"status": "PAR", "target": "foe"},
    "sleep-powder":     {"status": "SLP", "target": "foe"},
    "spore":            {"status": "SLP", "target": "foe", "acc_override": 100},
    "hypnosis":         {"status": "SLP", "target": "foe"},
    "sing":             {"status": "SLP", "target": "foe"},
    "lovely-kiss":      {"status": "SLP", "target": "foe"},
    "poison-powder":    {"status": "PSN", "target": "foe"},
    "poison-gas":       {"status": "PSN", "target": "foe"},
    "toxic":            {"status": "TOX", "target": "foe"},
    "will-o-wisp":      {"status": "BRN", "target": "foe"},
    "confuse-ray":      {"confuse": True, "target": "foe", "acc_override": 100},
    "supersonic":       {"confuse": True, "target": "foe"},
    "sweet-kiss":       {"confuse": True, "target": "foe"},
    "teeter-dance":     {"confuse": True, "target": "foe", "acc_override": 100},
    # ── Baisser stats adverses ────────────────────────────────────────────
    "growl":            {"stages": {"atk": -1}, "target": "foe"},
    "leer":             {"stages": {"def": -1}, "target": "foe"},
    "tail-whip":        {"stages": {"def": -1}, "target": "foe"},
    "sand-attack":      {"stages": {"acc": -1}, "target": "foe"},
    "smokescreen":      {"stages": {"acc": -1}, "target": "foe"},
    "kinesis":          {"stages": {"acc": -1}, "target": "foe"},
    "flash":            {"stages": {"acc": -1}, "target": "foe"},
    "string-shot":      {"stages": {"spe": -1}, "target": "foe"},
    "screech":          {"stages": {"def": -2}, "target": "foe"},
    "charm":            {"stages": {"atk": -2}, "target": "foe"},
    "feather-dance":    {"stages": {"atk": -2}, "target": "foe"},
    "fake-tears":       {"stages": {"spd": -2}, "target": "foe"},
    "metal-sound":      {"stages": {"spd": -2}, "target": "foe"},
    "tickle":           {"stages": {"atk": -1, "def": -1}, "target": "foe"},
    "captivate":        {"stages": {"spa": -2}, "target": "foe"},
    # ── Monter ses propres stats ──────────────────────────────────────────
    "swords-dance":     {"stages": {"atk": +2}, "target": "self"},
    "meditate":         {"stages": {"atk": +1}, "target": "self"},
    "sharpen":          {"stages": {"atk": +1}, "target": "self"},
    "agility":          {"stages": {"spe": +2}, "target": "self"},
    "double-team":      {"stages": {"eva": +1}, "target": "self"},
    "minimize":         {"stages": {"eva": +2}, "target": "self"},
    "barrier":          {"stages": {"def": +2}, "target": "self"},
    "harden":           {"stages": {"def": +1}, "target": "self"},
    "withdraw":         {"stages": {"def": +1}, "target": "self"},
    "defense-curl":     {"stages": {"def": +1}, "target": "self"},
    "acid-armor":       {"stages": {"def": +2}, "target": "self"},
    "amnesia":          {"stages": {"spa": +2}, "target": "self"},
    "calm-mind":        {"stages": {"spa": +1, "spd": +1}, "target": "self"},
    "nasty-plot":       {"stages": {"spa": +2}, "target": "self"},
    "growth":           {"stages": {"spa": +1}, "target": "self"},
    "howl":             {"stages": {"atk": +1}, "target": "self"},
    "bulk-up":          {"stages": {"atk": +1, "def": +1}, "target": "self"},
    "dragon-dance":     {"stages": {"atk": +1, "spe": +1}, "target": "self"},
    "quiver-dance":     {"stages": {"spa": +1, "spd": +1, "spe": +1}, "target": "self"},
    "shift-gear":       {"stages": {"atk": +1, "spe": +2}, "target": "self"},
    "coil":             {"stages": {"atk": +1, "def": +1}, "target": "self"},
    # ── Soin ─────────────────────────────────────────────────────────────
    "recover":          {"heal": 0.5},
    "softboiled":       {"heal": 0.5},
    "soft-boiled":      {"heal": 0.5},
    "rest":             {"heal": 1.0, "rest_sleep": True},
    "synthesis":        {"heal": 0.5},
    "moonlight":        {"heal": 0.5},
    "morning-sun":      {"heal": 0.5},
    "roost":            {"heal": 0.5},
    "slack-off":        {"heal": 0.5},
    "heal-order":       {"heal": 0.5},
    "milk-drink":       {"heal": 0.5},
    # ── Haze ─────────────────────────────────────────────────────────────
    "haze":             {"haze": True},
    # ── Dégâts fixes ─────────────────────────────────────────────────────
    "sonic-boom":       {"damage": True, "fixed_dmg": 20},
    "dragon-rage":      {"damage": True, "fixed_dmg": 40},
    # ── Dégâts = niveau ──────────────────────────────────────────────────
    "seismic-toss":     {"damage": True, "level_dmg": True},
    "night-shade":      {"damage": True, "level_dmg": True},
    # ── OHKO ─────────────────────────────────────────────────────────────
    "guillotine":       {"damage": True, "ohko": True, "acc_override": 30},
    "fissure":          {"damage": True, "ohko": True, "acc_override": 30},
    "horn-drill":       {"damage": True, "ohko": True, "acc_override": 30},
    "sheer-cold":       {"damage": True, "ohko": True, "acc_override": 30},
    # ── Explosion / Auto-destruction ─────────────────────────────────────
    "self-destruct":    {"damage": True, "self_destruct": True},
    "explosion":        {"damage": True, "self_destruct": True},
    # ── Recharge (Hyper Beam etc.) ────────────────────────────────────────
    "hyper-beam":       {"damage": True, "recharge": True},
    "giga-impact":      {"damage": True, "recharge": True},
    "frenzy-plant":     {"damage": True, "recharge": True},
    "blast-burn":       {"damage": True, "recharge": True},
    "hydro-cannon":     {"damage": True, "recharge": True},
    "rock-wrecker":     {"damage": True, "recharge": True},
    "roar-of-time":     {"damage": True, "recharge": True},
    # ── Coups critiques élevés ────────────────────────────────────────────
    "karate-chop":      {"damage": True, "high_crit": True},
    "slash":            {"damage": True, "high_crit": True},
    "razor-leaf":       {"damage": True, "high_crit": True},
    "crabhammer":       {"damage": True, "high_crit": True},
    "aeroblast":        {"damage": True, "high_crit": True},
    "cross-chop":       {"damage": True, "high_crit": True},
    "sky-attack":       {"damage": True, "high_crit": True},
    "stone-edge":       {"damage": True, "high_crit": True},
    "night-slash":      {"damage": True, "high_crit": True},
    "leaf-blade":       {"damage": True, "high_crit": True},
    "psycho-cut":       {"damage": True, "high_crit": True},
    "razor-wind":       {"damage": True, "high_crit": True},
    "x-scissor":        {"damage": True, "high_crit": True},
    "spacial-rend":     {"damage": True, "high_crit": True},
    # ── Multi-coups ──────────────────────────────────────────────────────
    "double-slap":      {"damage": True, "multi_hit": True},
    "comet-punch":      {"damage": True, "multi_hit": True},
    "fury-attack":      {"damage": True, "multi_hit": True},
    "pin-missile":      {"damage": True, "multi_hit": True},
    "spike-cannon":     {"damage": True, "multi_hit": True},
    "twineedle":        {"damage": True, "multi_hit": (2, 2), "status": "PSN", "target": "foe", "chance": 20},
    "bone-rush":        {"damage": True, "multi_hit": True},
    "fury-swipes":      {"damage": True, "multi_hit": True},
    "barrage":          {"damage": True, "multi_hit": True},
    "arm-thrust":       {"damage": True, "multi_hit": True},
    "bullet-seed":      {"damage": True, "multi_hit": True},
    "rock-blast":       {"damage": True, "multi_hit": True},
    "icicle-spear":     {"damage": True, "multi_hit": True},
    "double-hit":       {"damage": True, "multi_hit": (2, 2)},
    "dual-chop":        {"damage": True, "multi_hit": (2, 2)},
    "bonemerang":       {"damage": True, "multi_hit": (2, 2)},
    "double-kick":      {"damage": True, "multi_hit": (2, 2)},
    "gear-grind":       {"damage": True, "multi_hit": (2, 2)},
    "triple-kick":      {"damage": True, "multi_hit": (3, 3)},
    "tail-slap":        {"damage": True, "multi_hit": True},
    # ── Drain ─────────────────────────────────────────────────────────────
    "absorb":           {"damage": True, "drain": 0.5},
    "mega-drain":       {"damage": True, "drain": 0.5},
    "giga-drain":       {"damage": True, "drain": 0.5},
    "leech-life":       {"damage": True, "drain": 0.5},
    "dream-eater":      {"damage": True, "drain": 0.5, "drain_sleep_only": True},
    "draining-kiss":    {"damage": True, "drain": 0.75},
    "parabolic-charge": {"damage": True, "drain": 0.5},
    "horn-leech":       {"damage": True, "drain": 0.5},
    # ── Recul ─────────────────────────────────────────────────────────────
    "take-down":        {"damage": True, "recoil": 0.25},
    "double-edge":      {"damage": True, "recoil": 0.33},
    "submission":       {"damage": True, "recoil": 0.25},
    "brave-bird":       {"damage": True, "recoil": 0.33},
    "head-smash":       {"damage": True, "recoil": 0.5},
    "volt-tackle":      {"damage": True, "recoil": 0.33, "status": "PAR", "target": "foe", "chance": 10},
    "wood-hammer":      {"damage": True, "recoil": 0.33},
    "wild-charge":      {"damage": True, "recoil": 0.25},
    "flare-blitz":      {"damage": True, "recoil": 0.33, "status": "BRN", "target": "foe", "chance": 10},
    # ── Brûlure secondaire ────────────────────────────────────────────────
    "ember":            {"damage": True, "status": "BRN", "target": "foe", "chance": 10},
    "flamethrower":     {"damage": True, "status": "BRN", "target": "foe", "chance": 10},
    "fire-blast":       {"damage": True, "status": "BRN", "target": "foe", "chance": 10},
    "fire-punch":       {"damage": True, "status": "BRN", "target": "foe", "chance": 10},
    "heat-wave":        {"damage": True, "status": "BRN", "target": "foe", "chance": 10},
    "lava-plume":       {"damage": True, "status": "BRN", "target": "foe", "chance": 30},
    "scald":            {"damage": True, "status": "BRN", "target": "foe", "chance": 30},
    "sacred-fire":      {"damage": True, "status": "BRN", "target": "foe", "chance": 50},
    "blaze-kick":       {"damage": True, "status": "BRN", "target": "foe", "chance": 10},
    # ── Gel secondaire ────────────────────────────────────────────────────
    "blizzard":         {"damage": True, "status": "FRZ", "target": "foe", "chance": 10},
    "ice-beam":         {"damage": True, "status": "FRZ", "target": "foe", "chance": 10},
    "ice-punch":        {"damage": True, "status": "FRZ", "target": "foe", "chance": 10},
    "powder-snow":      {"damage": True, "status": "FRZ", "target": "foe", "chance": 10},
    "freeze-dry":       {"damage": True, "status": "FRZ", "target": "foe", "chance": 10},
    "tri-attack":       {"damage": True, "status": "any_bpf", "target": "foe", "chance": 20},
    # ── Paralysie secondaire ──────────────────────────────────────────────
    "body-slam":        {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    "thunder":          {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    "thunderbolt":      {"damage": True, "status": "PAR", "target": "foe", "chance": 10},
    "thunder-punch":    {"damage": True, "status": "PAR", "target": "foe", "chance": 10},
    "spark":            {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    "discharge":        {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    "force-palm":       {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    "bounce":           {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    "nuzzle":           {"damage": True, "status": "PAR", "target": "foe", "chance": 100},
    "lick":             {"damage": True, "status": "PAR", "target": "foe", "chance": 30},
    # ── Empoisonnement secondaire ─────────────────────────────────────────
    "poison-sting":     {"damage": True, "status": "PSN", "target": "foe", "chance": 30},
    "sludge":           {"damage": True, "status": "PSN", "target": "foe", "chance": 30},
    "sludge-bomb":      {"damage": True, "status": "PSN", "target": "foe", "chance": 30},
    "sludge-wave":      {"damage": True, "status": "PSN", "target": "foe", "chance": 10},
    "smog":             {"damage": True, "status": "PSN", "target": "foe", "chance": 40},
    "cross-poison":     {"damage": True, "status": "PSN", "target": "foe", "chance": 10},
    "gunk-shot":        {"damage": True, "status": "PSN", "target": "foe", "chance": 30},
    "poison-jab":       {"damage": True, "status": "PSN", "target": "foe", "chance": 30},
    # ── Confusion secondaire ──────────────────────────────────────────────
    "confusion":        {"damage": True, "confuse": True, "target": "foe", "chance": 10},
    "psybeam":          {"damage": True, "confuse": True, "target": "foe", "chance": 10},
    "dizzy-punch":      {"damage": True, "confuse": True, "target": "foe", "chance": 20},
    "water-pulse":      {"damage": True, "confuse": True, "target": "foe", "chance": 20},
    "signal-beam":      {"damage": True, "confuse": True, "target": "foe", "chance": 10},
    "hurricane":        {"damage": True, "confuse": True, "target": "foe", "chance": 30},
    "dynamic-punch":    {"damage": True, "confuse": True, "target": "foe", "chance": 100},
    "chatter":          {"damage": True, "confuse": True, "target": "foe", "chance": 10},
    # ── Baisser stats adverses (sur dégâts) ──────────────────────────────
    "acid":             {"damage": True, "stages": {"def": -1},  "target": "foe", "chance": 10},
    "bubble":           {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 10},
    "bubble-beam":      {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 33},
    "constrict":        {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 10},
    "rock-smash":       {"damage": True, "stages": {"def": -1},  "target": "foe", "chance": 50},
    "crunch":           {"damage": True, "stages": {"def": -1},  "target": "foe", "chance": 20},
    "shadow-ball":      {"damage": True, "stages": {"spd": -1},  "target": "foe", "chance": 20},
    "energy-ball":      {"damage": True, "stages": {"spd": -1},  "target": "foe", "chance": 10},
    "psychic":          {"damage": True, "stages": {"spd": -1},  "target": "foe", "chance": 10},
    "earth-power":      {"damage": True, "stages": {"spd": -1},  "target": "foe", "chance": 10},
    "flash-cannon":     {"damage": True, "stages": {"spd": -1},  "target": "foe", "chance": 10},
    "moonblast":        {"damage": True, "stages": {"spa": -1},  "target": "foe", "chance": 30},
    "muddy-water":      {"damage": True, "stages": {"acc": -1},  "target": "foe", "chance": 30},
    "mud-slap":         {"damage": True, "stages": {"acc": -1},  "target": "foe", "chance": 100},
    "icy-wind":         {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 100},
    "bulldoze":         {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 100},
    "electroweb":       {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 100},
    "low-sweep":        {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 100},
    "rock-tomb":        {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 100},
    "mud-shot":         {"damage": True, "stages": {"spe": -1},  "target": "foe", "chance": 100},
    "aurora-beam":      {"damage": True, "stages": {"atk": -1},  "target": "foe", "chance": 10},
    "luster-purge":     {"damage": True, "stages": {"spd": -1},  "target": "foe", "chance": 50},
    "mist-ball":        {"damage": True, "stages": {"spa": -1},  "target": "foe", "chance": 50},
    # ── Deux tours de charge ─────────────────────────────────────────────
    "fly":          {"damage": True, "two_turn": True, "charge_msg": "s'élance dans les airs !"},
    "dig":          {"damage": True, "two_turn": True, "charge_msg": "creuse sous le sol !"},
    "solar-beam":   {"damage": True, "two_turn": True, "charge_msg": "absorbe l'énergie solaire !"},
    "skull-bash":   {"damage": True, "two_turn": True, "charge_msg": "baisse la tête !", "stages": {"def": +1}, "target": "self"},
    "sky-attack":   {"damage": True, "two_turn": True, "high_crit": True, "charge_msg": "cherche la cible !"},
    "razor-wind":   {"damage": True, "two_turn": True, "high_crit": True, "charge_msg": "prépare ses lames !"},
    # ── Attaques verrous (Triplattaque, Pétale-Danse…) ───────────────────
    "thrash":       {"damage": True, "lock_move": True},
    "petal-dance":  {"damage": True, "lock_move": True},
    "outrage":      {"damage": True, "lock_move": True},
    # ── Pièges (Ligotage, Étreinte, Tourbifeu, Kraid…) ──────────────────
    "wrap":         {"damage": True, "trap": True},
    "bind":         {"damage": True, "trap": True},
    "fire-spin":    {"damage": True, "trap": True},
    "clamp":        {"damage": True, "trap": True},
    # ── Effets de terrain / protection ───────────────────────────────────
    "leech-seed":   {"leech_seed": True, "acc_override": 90},
    "light-screen": {"light_screen": True},
    "reflect":      {"reflect_move": True},
    "mist":         {"mist_move": True},
    "focus-energy": {"focus_energy": True},
    # ── Désactivation ────────────────────────────────────────────────────
    "disable":      {"disable_move": True},
    # ── Imitation / transformation ────────────────────────────────────────
    "mimic":        {"mimic": True},
    "mirror-move":  {"mirror_move": True},
    "metronome":    {"metronome": True},
    "transform":    {"transform": True},
    "sketch":       {"mimic": True},
    "copycat":      {"mirror_move": True},
    # ── Riposte / accumulation ────────────────────────────────────────────
    "counter":      {"counter": True},
    "bide":         {"bide": True},
    "rage":         {"damage": True, "rage": True},
    # ── Divers ────────────────────────────────────────────────────────────
    "conversion":   {"conversion": True},
    "whirlwind":    {"end_wild": True},
    "roar":         {"end_wild": True},
    "teleport":     {"end_wild": True},
    "swift":        {"damage": True, "acc_override": 100},
    "super-fang":   {"damage": True, "half_hp": True},
    "psywave":      {"damage": True, "psywave": True},
    "pay-day":      {"damage": True},
    "splash":       {},
    # ── Monter stats propres (sur dégâts) ────────────────────────────────
    "charge-beam":      {"damage": True, "stages": {"spa": +1}, "target": "self", "chance": 70},
    "meteor-mash":      {"damage": True, "stages": {"atk": +1}, "target": "self", "chance": 20},
    "steel-wing":       {"damage": True, "stages": {"def": +1}, "target": "self", "chance": 10},
    "ancient-power":    {"damage": True, "stages": {"atk": +1, "def": +1, "spa": +1, "spd": +1, "spe": +1}, "target": "self", "chance": 10},
    "silver-wind":      {"damage": True, "stages": {"atk": +1, "def": +1, "spa": +1, "spd": +1, "spe": +1}, "target": "self", "chance": 10},
    "ominous-wind":     {"damage": True, "stages": {"atk": +1, "def": +1, "spa": +1, "spd": +1, "spe": +1}, "target": "self", "chance": 10},
}


def _lookup_effect(move_sym: str) -> dict:
    return _MOVE_EFFECTS.get(move_sym.lower().replace("_", "-"), {})


def _calc_damage(attacker, move, defender,
                 atk_stage: int = 0, def_stage: int = 0,
                 burned: bool = False, high_crit: bool = False) -> tuple[int, float, bool]:
    """Formule officielle Gen 5. Retourne (dégâts, multiplicateur_type, coup_critique)."""
    power = move.power or 0
    if not power or move.category == "status":
        return 0, 1.0, False

    if move.category == "special":
        A = attacker.ats * _stage_mult(atk_stage)
        D = defender.dfs * _stage_mult(def_stage)
    else:
        A = attacker.atk * _stage_mult(atk_stage)
        D = defender.dfe * _stage_mult(def_stage)
        if burned:
            A *= 0.5

    D = max(D, 1)
    base = math.floor((math.floor(2 * attacker.level / 5 + 2) * power * A / D) / 50) + 2

    if move.type in attacker.type:
        base = math.floor(base * 1.5)

    eff = _type_effectiveness(move.type, defender.type)
    base = math.floor(base * eff)

    crit_threshold = 8 if high_crit else 16
    is_crit = random.randint(1, crit_threshold) == 1
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

        self._outcome: str | None = None

        # ── États de combat (volatils, réinitialisés à chaque combat) ────
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
        self._player_charging: str | None   = None   # sym en charge (Vol, Tunnel…)
        self._wild_charging:   str | None   = None
        self._player_locked:   tuple | None = None   # (sym, turns_left) Triplattaque…
        self._wild_locked:     tuple | None = None
        self._player_trapped:  int          = 0      # tours de piège restants
        self._wild_trapped:    int          = 0

        # ── Effets de terrain / protection ───────────────────────────────
        self._player_leech_seeded: bool = False
        self._wild_leech_seeded:   bool = False
        self._player_reflect:  int = 0   # tours Miroir (dégâts physiques)
        self._wild_reflect:    int = 0
        self._player_screen:   int = 0   # tours Écran Lumineux (dégâts spéciaux)
        self._wild_screen:     int = 0
        self._player_mist:     int = 0   # tours Brume
        self._wild_mist:       int = 0

        # ── Désactivation / suivi dernier move ────────────────────────────
        self._player_disabled: tuple | None = None   # (move_sym, turns_left)
        self._wild_disabled:   tuple | None = None
        self._last_player_move  = None   # dernier Move utilisé par le joueur
        self._last_wild_move    = None   # dernier Move utilisé par l'adversaire

        # ── Mécaniques spéciales ──────────────────────────────────────────
        self._last_phys_to_player: int  = 0     # dernier dégât physique reçu (Riposte)
        self._last_phys_to_wild:   int  = 0
        self._player_rage:         bool = False  # Furia
        self._wild_rage:           bool = False
        self._player_focus_energy: bool = False  # Concentraction
        self._wild_focus_energy:   bool = False
        self._player_bide:         tuple | None = None   # (turns_left, dmg_accum)
        self._wild_bide:           tuple | None = None
        self._player_transformed:  dict | None = None   # backup pre-transform

        # Icônes de statut (battleStatuses.png — 5 lignes × 16 px)
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
        quit   = controller.get_key("quit")

        hover = self._to_panel(mouse_pos)
        click = self._to_panel(mouse_click)

        if self._state in ("TEXT", "PLAYER_ATTACK", "ENEMY_ATTACK",
                           "WILD_FAINTED", "PLAYER_FAINTED", "END_OF_TURN"):
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
            auto_sym = self._player_charging or (
                self._player_locked[0] if self._player_locked else None
            )
            if auto_sym and self._player_pokemon:
                for i, m in enumerate(self._player_pokemon.moves):
                    if m.dbSymbol.lower().replace("_", "-") == auto_sym:
                        self._move_idx = i
                        self._use_player_move()
                        return
                self._player_charging = None
                self._player_locked   = None
            self._state = "MOVE_SELECT"
            self._move_idx = 0
        elif self._cmd_idx == 3:
            self._outcome = "fled"
            self._active  = False
        # Party (1) et Bag (2) : TODO

    # ------------------------------------------------------------------
    # Helpers statuts & stades
    # ------------------------------------------------------------------

    def _check_can_act(self, is_player: bool) -> tuple[bool, list[str]]:
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

    def _apply_status(self, target_poke, status: str, is_target_player: bool,
                      msgs: list[str]) -> None:
        """Inflige un statut si le cible n'en a pas déjà un et n'est pas immunisée."""
        if not target_poke:
            return
        if target_poke.status:
            return   # déjà un statut
        if not _can_inflict_status(status, getattr(target_poke, "type", [])):
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
        msgs.append(f"{pfx}{tname} {_STATUS_INFLICT_MSG.get(status, '!')}")

    def _apply_stage(self, poke, stages: dict[str, int], is_player: bool,
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

    def _apply_confusion(self, poke, is_player: bool, msgs: list[str]) -> None:
        ctr = self._player_confused if is_player else self._wild_confused
        if ctr > 0:
            return
        turns = random.randint(2, 5)
        if is_player: self._player_confused = turns
        else:          self._wild_confused   = turns
        name = poke.dbSymbol.capitalize()
        pfx  = "" if is_player else f"Le {name} ennemi "
        msgs.append(f"{pfx}{name} est maintenant confus !")

    # ------------------------------------------------------------------
    # Mécaniques spéciales (Métronome, Transformation, Bide, etc.)
    # ------------------------------------------------------------------

    def _try_special(self, attacker, move, defender,
                     attacker_is_player: bool, effect: dict,
                     msgs: list[str]):
        """
        Gère les attaques à mécanique unique.
        Retourne la liste msgs si le move est traité ici, None pour tomber
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
            self._outcome = "fled"
            self._active  = False
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
                from code.entities.move import Move as _M
                new_mv = _M.from_dict(last.to_dict())
                new_mv.pp = min(5, new_mv.maxpp)
                if attacker_is_player and self._player_pokemon:
                    if 0 <= self._move_idx < len(self._player_pokemon.moves):
                        self._player_pokemon.moves[self._move_idx] = new_mv
                mname2 = last.dbSymbol.replace("-", " ").replace("_", " ").title()
                msgs.append(f"{apfx}{aname} a appris {mname2} par Imitation !")
            return msgs

        if effect.get("mirror_move"):
            last = self._last_wild_move if attacker_is_player else self._last_player_move
            if last is None:
                msgs.append("L'attaque échoue !")
            else:
                extra = self._execute_move(attacker, last, defender, attacker_is_player)
                msgs.extend(extra[1:])
            return msgs

        if effect.get("metronome"):
            try:
                import json as _j
                from code.config import JSON_DIR as _JD
                from code.entities.move import Move as _M2
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
                extra = self._execute_move(attacker, temp, defender, attacker_is_player)
                msgs.extend(extra[1:])
            except Exception:
                msgs.append("L'attaque échoue !")
            return msgs

        if effect.get("transform"):
            self._do_transform(attacker, defender, attacker_is_player, msgs)
            return msgs

        if effect.get("counter"):
            lp = self._last_phys_to_player if attacker_is_player else self._last_phys_to_wild
            if lp <= 0:
                msgs.append("L'attaque échoue !")
            else:
                dmg = lp * 2
                defender.hp = max(0, defender.hp - dmg)
                if attacker_is_player:
                    self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
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
                        if attacker_is_player:
                            self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
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

    def _do_transform(self, attacker, defender, attacker_is_player: bool,
                      msgs: list[str]) -> None:
        aname = attacker.dbSymbol.capitalize()
        apfx  = "" if attacker_is_player else f"Le {aname} ennemi "
        if attacker_is_player:
            self._player_transformed = {
                "atk": attacker.atk, "dfe": attacker.dfe,
                "ats": attacker.ats, "dfs": attacker.dfs, "spd": attacker.spd,
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
        from code.entities.move import Move as _M
        attacker.moves = [
            (lambda mv: setattr(mv, "pp", min(5, mv.maxpp)) or mv)(_M.from_dict(m.to_dict()))
            for m in defender.moves
        ]
        if attacker_is_player:
            self._player_stages = dict(self._wild_stages)
        else:
            self._wild_stages = dict(self._player_stages)
        msgs.append(f"{apfx}{aname} se transforme en {defender.dbSymbol.capitalize()} !")

    def _restore_transform(self) -> None:
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

    def _execute_move(
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
        effect = _lookup_effect(move.dbSymbol)
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
        sp = self._try_special(attacker, move, defender, attacker_is_player, effect, msgs)
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
                self._apply_status(target, effect["status"], tgt_is_player, msgs)
            if "stages" in effect:
                self._apply_stage(target, effect["stages"], tgt_is_player, msgs)
            if effect.get("confuse"):
                self._apply_confusion(target, tgt_is_player, msgs)
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
                    self._apply_stage(attacker, effect["stages"], attacker_is_player, msgs)
                return msgs
            else:
                setattr(self, ch_attr, None)   # tour 2 → exécution normale

        # Dream Eater : échoue si la cible n'est pas endormie
        if effect.get("drain_sleep_only") and defender.status != "SLP":
            msgs.append(f"{dpfx}{dname} n'est pas endormi !")
            return msgs

        # OHKO
        if effect.get("ohko"):
            eff = _type_effectiveness(move.type, defender.type)
            if eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            else:
                msgs.append("Coup fatal !")
                defender.hp = 0
                if attacker_is_player:
                    self._wild_hp = 0
            return msgs

        # Dégâts fixes
        if "fixed_dmg" in effect:
            eff = _type_effectiveness(move.type, defender.type)
            if eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            else:
                dmg = effect["fixed_dmg"]
                defender.hp = max(0, defender.hp - dmg)
                if attacker_is_player:
                    self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
                msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Dégâts = niveau
        if effect.get("level_dmg"):
            eff = _type_effectiveness(move.type, defender.type)
            if eff == 0:
                msgs.append(f"Ça n'affecte pas {dpfx}{dname}…")
            else:
                dmg = attacker.level
                defender.hp = max(0, defender.hp - dmg)
                if attacker_is_player:
                    self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
                msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Psyko (dégâts aléatoires 50-150% du niveau)
        if effect.get("psywave"):
            dmg = max(1, int(attacker.level * random.randint(50, 150) / 100))
            defender.hp = max(0, defender.hp - dmg)
            if attacker_is_player:
                self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
            msgs.append(f"{dpfx}{dname} perd {dmg} PV !")
            return msgs

        # Griffe-Acier (demi-PV de la cible)
        if effect.get("half_hp"):
            dmg = max(1, defender.hp // 2)
            defender.hp = max(0, defender.hp - dmg)
            if attacker_is_player:
                self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
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
                h_dmg, h_eff, h_crit = _calc_damage(
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
            if attacker_is_player:
                self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0
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
                    self._apply_status(defender, effect["status"], not attacker_is_player, msgs)
            return msgs

        # Dégâts normaux
        f_e = True if attacker_is_player else False  # focus energy attacker
        hc  = high_crit or (self._player_focus_energy if attacker_is_player else self._wild_focus_energy)
        dmg, eff, crit = _calc_damage(
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
        if attacker_is_player:
            self._wild_hp = self._wild_pokemon.hp if self._wild_pokemon else 0

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
                self._apply_stage(attacker, {"atk": +1}, True, msgs)
            elif attacker_is_player and self._wild_rage:
                self._apply_stage(attacker, {"atk": +1}, False, msgs)

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
                    self._apply_status(defender, effect["status"], not attacker_is_player, msgs)
            if effect.get("confuse"):
                chance = effect.get("chance", 100)
                if random.randint(1, 100) <= chance:
                    self._apply_confusion(defender, not attacker_is_player, msgs)
            if "stages" in effect:
                tgt = effect.get("target", "foe")
                if tgt == "foe":
                    self._apply_stage(defender, effect["stages"], not attacker_is_player, msgs)
                else:
                    self._apply_stage(attacker, effect["stages"], attacker_is_player, msgs)
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
                        self._apply_confusion(attacker, True, msgs)
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
                        self._apply_confusion(attacker, False, msgs)
                    else:
                        self._wild_locked = (s, t)

        # ── Furia : active le mode rage ───────────────────────────────────
        if effect.get("rage") and dmg > 0:
            if attacker_is_player: self._player_rage = True
            else:                  self._wild_rage   = True

        return msgs

    def _collect_end_of_turn(self) -> list[str]:
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

    # ------------------------------------------------------------------
    def _use_player_move(self) -> None:
        if not self._player_pokemon or not self._wild_pokemon:
            return
        moves = self._player_pokemon.moves
        if not moves:
            return
        move     = moves[self._move_idx]
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
                    self._text_box.set_messages([f"{mname_dis} est désactivée !"])
                    self._state = "PLAYER_ATTACK"
                    self._pending_enemy_attack = True
                    return
            if move.pp <= 0:
                self._text_box.set_messages(["Plus de PP pour cette attaque !"])
                self._state = "PLAYER_ATTACK"
                self._pending_enemy_attack = False
                return
            move.pp -= 1

        self._last_player_move = move  # pour Imitation / Miroir / Koud'Boue

        can_act, status_msgs = self._check_can_act(is_player=True)
        if not can_act:
            self._text_box.set_messages(status_msgs)
            self._state = "PLAYER_ATTACK"
            self._pending_enemy_attack = True
            return

        msgs = status_msgs + self._execute_move(
            self._player_pokemon, move, self._wild_pokemon,
            attacker_is_player=True,
        )
        if self._player_pokemon.hp <= 0:
            self._pending_enemy_attack = False
        else:
            self._pending_enemy_attack = (self._wild_pokemon.hp > 0)
        self._text_box.set_messages(msgs)
        self._state = "PLAYER_ATTACK"

    # ------------------------------------------------------------------
    def _enemy_counter_attack(self) -> None:
        if not self._wild_pokemon or not self._player_pokemon:
            self._state = "MENU"
            return

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
                can_act, status_msgs = self._check_can_act(is_player=False)
                self._last_wild_move = auto_move
                if not can_act:
                    self._text_box.set_messages(status_msgs)
                    self._state = "ENEMY_ATTACK"
                    return
                msgs = status_msgs + self._execute_move(
                    self._wild_pokemon, auto_move, self._player_pokemon, False)
                self._text_box.set_messages(msgs)
                self._state = "ENEMY_ATTACK"
                return
            else:
                self._wild_charging = self._wild_locked = self._wild_bide = None

        moves = [m for m in self._wild_pokemon.moves if m.pp > 0]
        if not moves:
            from code.entities.move import Move as _Move
            moves = [_Move({"dbSymbol": "struggle", "type": "normal",
                            "power": 50, "accuracy": 100, "pp": 1,
                            "maxpp": 1, "category": "physical", "priority": 0})]
        move = random.choice(moves)
        if move.pp is not None:
            move.pp = max(0, move.pp - 1)
        self._last_wild_move = move

        can_act, status_msgs = self._check_can_act(is_player=False)
        if not can_act:
            self._text_box.set_messages(status_msgs)
            self._state = "ENEMY_ATTACK"
            return

        msgs = status_msgs + self._execute_move(
            self._wild_pokemon, move, self._player_pokemon,
            attacker_is_player=False,
        )
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
                    learned, _pending = self._player_pokemon.check_level_ups()
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
                eot = self._collect_end_of_turn()
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
                self._state = "MENU"   # rare mais sécurisé
            else:
                self._state = "MENU"

        elif self._state == "WILD_FAINTED":
            self._restore_transform()
            self._outcome = "won"
            self._active  = False
        elif self._state == "PLAYER_FAINTED":
            self._restore_transform()
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
                           "WILD_FAINTED", "PLAYER_FAINTED", "END_OF_TURN"):
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
                           "WILD_FAINTED", "PLAYER_FAINTED", "END_OF_TURN"):
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

        # Icône statut
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

        # Icône statut
        if pp:
            self._draw_status_icon(surf, pp.status, r.x + 4, bar_y - 18)

        # Barre EXP — animée via _exp_displayed_ratio
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
