"""
config_items.py — Source unique de vérité pour tous les items du jeu.

Structure de chaque item :
    id          : str   — identifiant unique snake_case
    name_fr     : str   — nom affiché en français
    name_en     : str   — nom en anglais
    stackable   : bool  — peut-on empiler plusieurs exemplaires dans un même slot ?
    max_stack   : int   — quantité max par slot (1 si non stackable)
    texture     : Path  — chemin vers l'icône PNG dans assets/items/icon_16/
    category    : str   — "medicine" | "pokeball" | "tm_hm" | "key" | "berry" | "misc"
    description_fr : str
    description_en : str
"""
from pathlib import Path

# Dossier des icônes d'items — chemin depuis la racine du projet
# items.py est dans code/shared/config/ → 4 .parent pour atteindre la racine
_ITEMS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "items"

# Nombre maximum de slots dans l'inventaire arc du joueur
INVENTORY_MAX_SLOTS: int = 16   # 8 slots × 2 rangées

# ---------------------------------------------------------------------------
# Registre des items
# Clé = id de l'item (même valeur que le champ "id")
# ---------------------------------------------------------------------------
ITEMS: dict[str, dict] = {

    # ── Soins ───────────────────────────────────────────────────────────────
    "potion": {
        "id":             "potion",
        "name_fr":        "Potion",
        "name_en":        "Potion",
        "stackable":      True,
        "max_stack":      99,
        "texture":        _ITEMS_DIR / "icon_16.png",
        "category":       "medicine",
        "description_fr": "Restaure 20 PV d'un Pokémon.",
        "description_en": "Restores 20 HP to one Pokémon.",
    },
    "super_potion": {
        "id":             "super_potion",
        "name_fr":        "Super Potion",
        "name_en":        "Super Potion",
        "stackable":      True,
        "max_stack":      99,
        "texture":        _ITEMS_DIR / "icon_16.png",
        "category":       "medicine",
        "description_fr": "Restaure 50 PV d'un Pokémon.",
        "description_en": "Restores 50 HP to one Pokémon.",
    },
    "hyper_potion": {
        "id":             "hyper_potion",
        "name_fr":        "Hyper Potion",
        "name_en":        "Hyper Potion",
        "stackable":      True,
        "max_stack":      99,
        "texture":        _ITEMS_DIR / "icon_16.png",
        "category":       "medicine",
        "description_fr": "Restaure 200 PV d'un Pokémon.",
        "description_en": "Restores 200 HP to one Pokémon.",
    },
    "max_potion": {
        "id":             "max_potion",
        "name_fr":        "Potion Max",
        "name_en":        "Max Potion",
        "stackable":      True,
        "max_stack":      99,
        "texture":        _ITEMS_DIR / "icon_16.png",
        "category":       "medicine",
        "description_fr": "Restaure tous les PV d'un Pokémon.",
        "description_en": "Fully restores a Pokémon's HP.",
    },
    "antidote": {
        "id":             "antidote",
        "name_fr":        "Antidote",
        "name_en":        "Antidote",
        "stackable":      True,
        "max_stack":      99,
        "texture":        _ITEMS_DIR / "icon_16.png",
        "category":       "medicine",
        "description_fr": "Guérit le statut Poison.",
        "description_en": "Cures the Poison status condition.",
    },
    "revive": {
        "id":             "revive",
        "name_fr":        "Rappel",
        "name_en":        "Revive",
        "stackable":      True,
        "max_stack":      99,
        "texture":        _ITEMS_DIR / "icon_16.png",
        "category":       "medicine",
        "description_fr": "Ranime un Pokémon KO avec la moitié de ses PV.",
        "description_en": "Revives a fainted Pokémon with half its HP.",
    },

    # ── Poké Balls ──────────────────────────────────────────────────────────
    "poke_ball": {
        "id":             "poke_ball",
        "name_fr":        "Poké Ball",
        "name_en":        "Poké Ball",
        "stackable":      True,
        "max_stack":      999,
        "texture":        _ITEMS_DIR / "poke_ball.png",
        "category":       "pokeball",
        "description_fr": "Ball de capture basique.",
        "description_en": "A basic Poké Ball for catching Pokémon.",
    },
    "super_ball": {
        "id":             "super_ball",
        "name_fr":        "Super Ball",
        "name_en":        "Great Ball",
        "stackable":      True,
        "max_stack":      999,
        "texture":        _ITEMS_DIR / "super_ball.png",
        "category":       "pokeball",
        "description_fr": "Ball de capture améliorée.",
        "description_en": "A higher-performance Ball.",
    },
    "hyper_ball": {
        "id":             "hyper_ball",
        "name_fr":        "Hyper Ball",
        "name_en":        "Ultra Ball",
        "stackable":      True,
        "max_stack":      999,
        "texture":        _ITEMS_DIR / "hyper_ball.png",
        "category":       "pokeball",
        "description_fr": "Ball de capture très efficace.",
        "description_en": "An ultra-high performance Ball.",
    },
    "master_ball": {
        "id":             "master_ball",
        "name_fr":        "Master Ball",
        "name_en":        "Master Ball",
        "stackable":      False,
        "max_stack":      1,
        "texture":        _ITEMS_DIR / "master_ball.png",
        "category":       "pokeball",
        "description_fr": "Attrape n'importe quel Pokémon sans faute.",
        "description_en": "Catches any Pokémon without fail.",
    },

    # ── Objets clés ─────────────────────────────────────────────────────────
    "bicycle": {
        "id":             "bicycle",
        "name_fr":        "Vélo",
        "name_en":        "Bicycle",
        "stackable":      False,
        "max_stack":      1,
        "texture":        _ITEMS_DIR / "bicycle.png",
        "category":       "key",
        "description_fr": "Permet de se déplacer plus vite.",
        "description_en": "Allows faster travel.",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_item(item_id: str) -> dict | None:
    """Retourne la définition d'un item par son id, ou None si inconnu."""
    return ITEMS.get(item_id)


def get_item_name(item_id: str, lang: str = "fr") -> str:
    """Retourne le nom affiché d'un item (fr ou en)."""
    item = ITEMS.get(item_id)
    if not item:
        return item_id
    return item.get(f"name_{lang}", item.get("name_fr", item_id))
