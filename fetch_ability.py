#!/usr/bin/env python3
"""
fetch_ability.py — Télécharge les données d'un talent depuis PokeAPI
et les ajoute à assets/json/ability_data.json.

Usage:
    python fetch_ability.py static
    python fetch_ability.py 9
    python fetch_ability.py overgrow blaze torrent
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
DATA_FILE = Path(__file__).parent / "assets" / "json" / "ability_data.json"


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


def _french_flavor(flavor_entries: list) -> str:
    for entry in flavor_entries:
        if entry["language"]["name"] == "fr":
            return entry["flavor_text"].replace("\n", " ").replace("\f", " ")

    for entry in flavor_entries:
        if entry["language"]["name"] == "en":
            return entry["flavor_text"].replace("\n", " ").replace("\f", " ")

    return ""


# ── Fetch principal ────────────────────────────────────────────────────────────

def fetch_ability(identifier: str) -> dict:
    data = _get(f"{BASE_URL}/ability/{identifier.lower()}")

    pokemon_list = []

    for p in data.get("pokemon", []):
        pokemon_list.append({
            "name": p["pokemon"]["name"],
            "hidden": p["is_hidden"],
            "slot": p["slot"],
        })

    return {
        "id": data["id"],
        "name": data["name"],
        "name_fr": _french_name(data.get("names", [])),

        # Génération du talent
        "generation": data["generation"]["name"],

        # Effets
        "effect": _french_effect(data.get("effect_entries", [])),
        "flavor_text": _french_flavor(data.get("flavor_text_entries", [])),

        # Combat / gameplay
        "is_main_series": data.get("is_main_series", True),

        # Pokémon possédant ce talent
        "pokemon": pokemon_list,
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
        print("Usage : python fetch_ability.py <nom_ou_id> [...]")
        print("Exemple : python fetch_ability.py static overgrow levitate")
        sys.exit(1)

    db = load()
    added = 0

    for identifier in sys.argv[1:]:
        try:
            data = fetch_ability(identifier)

            key = str(data["id"])

            action = "mis à jour" if key in db else "ajouté"

            db[key] = data
            added += 1

            print(
                f"  ✓ #{data['id']:03d} "
                f"{data['name_fr']:20s} "
                f"({data['name']}) "
                f"— {action}"
            )

        except requests.HTTPError:
            print(f"  ✗ '{identifier}' introuvable sur PokeAPI")

        except Exception as e:
            print(f"  ✗ '{identifier}' erreur : {e}")

    if added:
        save(db)

        print(f"\n→ {DATA_FILE.relative_to(Path(__file__).parent)}")
        print(f"  {len(db)} talents au total dans le fichier.")


if __name__ == "__main__":
    main()