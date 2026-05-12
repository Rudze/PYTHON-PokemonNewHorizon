#!/usr/bin/env python3
"""
fetch_pokemon.py — Télécharge les données d'un Pokémon depuis PokeAPI
et les ajoute à assets/json/pokemon_data.json.

Usage:
    python fetch_pokemon.py pikachu
    python fetch_pokemon.py 25
    python fetch_pokemon.py bulbasaur charmander squirtle
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
DATA_FILE = Path(__file__).parent / "assets" / "json" / "pokemon_data.json"

STAT_KEYS = {
    "hp":             "hp",
    "attack":         "attack",
    "defense":        "defense",
    "special-attack": "sp_attack",
    "special-defense":"sp_defense",
    "speed":          "speed",
}


# ── Helpers réseau ─────────────────────────────────────────────────────────────

def _get(url: str) -> dict:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def _french_name(species_url: str) -> str:
    data = _get(species_url)
    for entry in data.get("names", []):
        if entry["language"]["name"] == "fr":
            return entry["name"]
    return ""


# ── Fetch principal ────────────────────────────────────────────────────────────

def fetch_pokemon(identifier: str) -> dict:
    """Retourne un dict avec toutes les données utiles du Pokémon."""
    poke = _get(f"{BASE_URL}/pokemon/{identifier.lower()}")

    # Nom français via l'endpoint species
    name_fr = _french_name(poke["species"]["url"])

    # Stats de base
    stats = {
        STAT_KEYS[s["stat"]["name"]]: s["base_stat"]
        for s in poke["stats"]
        if s["stat"]["name"] in STAT_KEYS
    }

    # Types
    types = [t["type"]["name"] for t in poke["types"]]

    # Talents (abilities)
    abilities = [
        {"name": a["ability"]["name"], "hidden": a["is_hidden"]}
        for a in poke["abilities"]
    ]

    # Learnset — capacités par montée de niveau, filtré par version
    # Priorité : Black/White → B2W2 → XY → SunMoon → SwordShield → tout autre
    VERSION_PRIORITY = [
        "black-white", "black-2-white-2",
        "x-y", "sun-moon", "sword-shield", "scarlet-violet",
    ]

    learnset = []
    for entry in poke["moves"]:
        level_up = {
            d["version_group"]["name"]: d["level_learned_at"]
            for d in entry["version_group_details"]
            if d["move_learn_method"]["name"] == "level-up"
        }
        if not level_up:
            continue

        # Chercher la meilleure version disponible
        level = None
        used_version = None
        for v in VERSION_PRIORITY:
            if v in level_up:
                level = level_up[v]
                used_version = v
                break
        if level is None:
            # Fallback : première version disponible
            used_version, level = next(iter(level_up.items()))

        learnset.append({"move": entry["move"]["name"], "level": level})

    learnset.sort(key=lambda x: x["level"])
    # Dédoublonner si un move apparaît deux fois au même niveau (bord de version)
    seen = set()
    learnset = [e for e in learnset if not (e["move"] in seen or seen.add(e["move"]))]

    # Version source du learnset (pour info dev)
    versions_dispo = {
        d["version_group"]["name"]
        for entry in poke["moves"]
        for d in entry["version_group_details"]
        if d["move_learn_method"]["name"] == "level-up"
    }
    learnset_version = next(
        (v for v in VERSION_PRIORITY if v in versions_dispo),
        next(iter(versions_dispo), "unknown"),
    )

    return {
        "id":               poke["id"],
        "name":             poke["name"],
        "name_fr":          name_fr,
        "types":            types,
        "stats":            stats,
        "abilities":        abilities,
        "learnset":         learnset,
        "learnset_version": learnset_version,
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
        print("Usage : python fetch_pokemon.py <nom_ou_id> [...]")
        print("Exemple : python fetch_pokemon.py pikachu 1 bulbasaur")
        sys.exit(1)

    db = load()
    added = 0

    for identifier in sys.argv[1:]:
        try:
            data    = fetch_pokemon(identifier)
            key     = str(data["id"])
            action  = "mis à jour" if key in db else "ajouté"
            db[key] = data
            added  += 1
            ver = data["learnset_version"]
            flag = "" if ver == "black-white" else f" [fallback: {ver}]"
            print(f"  ✓ #{data['id']:03d} {data['name_fr']:12s} ({data['name']}) — {action}{flag}")
        except requests.HTTPError:
            print(f"  ✗ '{identifier}' introuvable sur PokeAPI")
        except Exception as e:
            print(f"  ✗ '{identifier}' erreur : {e}")

    if added:
        save(db)
        print(f"\n→ {DATA_FILE.relative_to(Path(__file__).parent)}")
        print(f"  {len(db)} Pokémon au total dans le fichier.")


if __name__ == "__main__":
    main()
