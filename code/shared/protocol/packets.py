"""Packet type constants for the MMO protocol."""
from __future__ import annotations

# ── Client → Server ───────────────────────────────────────────────────────────
PKT_BATTLE_START   = "battle_start"    # début d'un combat
PKT_BATTLE_MOVE    = "battle_move"     # joueur utilise un move
PKT_BATTLE_RUN     = "battle_run"      # joueur tente de fuir
PKT_BATTLE_ITEM    = "battle_item"     # joueur utilise un objet

# ── Server → Client ───────────────────────────────────────────────────────────
PKT_BATTLE_STATE   = "battle_state"    # état complet du combat
PKT_BATTLE_MSGS    = "battle_msgs"     # liste de messages à afficher
PKT_BATTLE_END     = "battle_end"      # résultat final (BattleResult)

# ── Bidirectionnel ────────────────────────────────────────────────────────────
PKT_PING           = "ping"
PKT_PONG           = "pong"
