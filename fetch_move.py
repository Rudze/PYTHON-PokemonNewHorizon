#!/usr/bin/env python3
"""
fetch_move.py — Télécharge les données d'une capacité depuis PokeAPI
et les ajoute à assets/json/move_data.json.

Usage:
    python fetch_move.py thunderbolt
    python fetch_move.py 85
    python fetch_move.py thunderbolt flamethrower surf
"""

import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("[!] requests non installé — lance : pip install requests")
    sys.exit(1)

BASE_URL  = "https://pokeapi.co/api/v2"
DATA_FILE = Path(__file__).parent / "assets" / "json" / "move_data.json"


# ── Helpers réseau ─────────────────────────────────────────────────────────────

def _get(url: str) -> dict:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def _french_name(names: list) -> str:
    for entry in names:
        if entry["language"]["name"] == "fr":
            return entry["name"]
    return ""


def _french_effect(effect_entries: list) -> str:
    for entry in effect_entries:
        if entry["language"]["name"] == "fr":
            return entry["short_effect"]
    for entry in effect_entries:
        if entry["language"]["name"] == "en":
            return entry["short_effect"]
    return ""


# ── Fetch principal ────────────────────────────────────────────────────────────

def fetch_move(identifier: str) -> dict:
    data = _get(f"{BASE_URL}/move/{identifier.lower()}")

    return {
        "id":            data["id"],
        "name":          data["name"],
        "name_fr":       _french_name(data.get("names", [])),
        "type":          data["type"]["name"],
        "damage_class":  data["damage_class"]["name"],   # physical / special / status
        "power":         data["power"],                  # None si status
        "accuracy":      data["accuracy"],               # None si toujours précis
        "pp":            data["pp"],
        "priority":      data["priority"],               # 0 = normal, +1 = priorité, etc.
        "effect_chance": data["effect_chance"],          # % de déclenchement effet secon.
        "effect":        _french_effect(data.get("effect_entries", [])),
    }


# ── JSON local ────────────────────────────────────────────────────────────────

def load() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}


def save(db: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Entrée ────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage : python fetch_move.py <nom_ou_id> [...]")
        print("Exemple : python fetch_move.py thunderbolt flamethrower surf")
        sys.exit(1)

    db = load()
    added = 0

    for identifier in sys.argv[1:]:
        try:
            data    = fetch_move(identifier)
            key     = str(data["id"])
            action  = "mis à jour" if key in db else "ajouté"
            db[key] = data
            added  += 1

            tag = f"[{data['damage_class']:8s}]"
            pwr = f"Puissance: {data['power'] or '—':>3}"
            acc = f"Précision: {data['accuracy'] or '—':>3}"
            print(f"  ✓ #{data['id']:04d} {data['name_fr']:16s} ({data['name']:20s}) "
                  f"{tag} {pwr}  {acc} — {action}")
        except requests.HTTPError:
            print(f"  ✗ '{identifier}' introuvable sur PokeAPI")
        except Exception as e:
            print(f"  ✗ '{identifier}' erreur : {e}")

    if added:
        save(db)
        print(f"\n→ {DATA_FILE.relative_to(Path(__file__).parent)}")
        print(f"  {len(db)} capacités au total dans le fichier.")


if __name__ == "__main__":
    main()
