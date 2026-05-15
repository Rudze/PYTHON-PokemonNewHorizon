# Architecture — Pokemon New Horizon

## Structure physique

```
code/
├── client/          # TOUT ce qui touche à pygame / rendu / inputs
│   ├── core/
│   │   ├── game.py            ← Machine d'état principale du client
│   │   ├── controller.py      ← Mapping clavier
│   │   ├── keylistener.py     ← État des touches
│   │   └── screen.py          ← Fenêtre pygame 1280×720
│   ├── entities/
│   │   ├── entity.py          ← Sprite de base (pygame.sprite.Sprite)
│   │   ├── player.py          ← Joueur local (rendu + mouvement)
│   │   ├── remote_player.py   ← Autres joueurs (affichage réseau)
│   │   └── wild_pokemon_entity.py ← Pokémon sauvage en overworld
│   ├── managers/
│   │   ├── interaction_manager.py  ← Détection d'interactions
│   │   ├── sound_manager.py        ← Audio pygame
│   │   ├── spawn_manager.py        ← Entités visuelles de spawn
│   │   └── wild_pokemon_manager.py ← Pokémon sauvages en jeu
│   ├── network/
│   │   ├── client.py          ← WebSocket temps-réel
│   │   ├── protocol.py        ← Protocole de messages
│   │   ├── auth_client.py     ← Authentification REST
│   │   └── api_client.py      ← API REST jeu (inventaire, perso…)
│   ├── ui/
│   │   ├── battle_screen.py   ← Renderer combat (délègue à BattleManager)
│   │   ├── admin_menu.py      ← Debug / cheat menu
│   │   ├── inventory_hud.py   ← Arc d'objets
│   │   ├── motismart.py       ← Téléphone / menu
│   │   ├── dialogue.py        ← Système de dialogues
│   │   ├── escape_menu.py, login_menu.py, splash_screen.py, …
│   │   └── components/
│   │       ├── text_box.py, catalog_selector.py, character_preview.py
│   ├── world/
│   │   ├── map.py             ← Rendu TMX (pyscroll)
│   │   ├── spawn_zone.py      ← Zones de spawn
│   │   └── switch.py          ← Transitions de maps
│   └── utils/
│       ├── sprite_composer.py, sprite_tint.py, grid_placement.py, tool.py
│
├── server/          # TOUT ce qui est logique de jeu / autorité / persistance
│   ├── battle/
│   │   ├── battle_manager.py  ← Moteur de combat complet (autorité)
│   │   ├── type_chart.py      ← Table de types Gen 6+
│   │   ├── status.py          ← Immunités et effets de statut
│   │   ├── move_effects.py    ← ~200 effets de moves
│   │   ├── calc.py            ← Formule de dégâts Gen 5
│   │   └── battle_state.py    ← BattleVolatile dataclass
│   ├── managers/
│   │   ├── inventory_manager.py ← Inventaire serveur + sync DB
│   │   └── save_manager.py      ← Sauvegarde locale (position, map)
│   ├── data/
│   │   └── sql.py             ← Requêtes MySQL
│   ├── api/                   ← (stub — à remplir)
│   ├── entities/              ← (stub — états serveur purs)
│   ├── network/               ← (stub — WebSocket handler serveur)
│   ├── server_api.py          ← FastAPI REST (auth, inventaire, perso…)
│   └── server.py              ← Serveur de jeu temps-réel
│
└── shared/          # ZÉRO pygame, ZÉRO logique de jeu — données pures
    ├── config/
    │   ├── __init__.py        ← Tous les chemins et constantes du projet
    │   └── items.py           ← Définitions des objets (ITEMS, INVENTORY_MAX_SLOTS)
    ├── models/
    │   ├── pokemon.py         ← Modèle Pokémon + formules (sans pygame)
    │   ├── move.py            ← Modèle Move
    │   └── battle.py          ← BattleResult dataclass
    └── protocol/
        └── packets.py         ← Constantes réseau (types de paquets)
```

---

## Règles strictes par couche

### `client/`
- Import pygame **autorisé**
- **Interdit** : logique de jeu (dégâts, collisions serveur, validation)
- Reçoit des états du serveur, les affiche, envoie des inputs

### `server/`
- Import pygame **interdit**
- Contient toute la **logique autoritaire** : calculs, validation, persistance
- Peut être lancé sans affichage (tests unitaires, serveur dédié)
- Point d'entrée logique du combat : `BattleManager`

### `shared/`
- **Ni pygame ni logique de jeu**
- Importable par `client/` ET `server/`
- Dataclasses pures, constantes, protocoles

---

## Interfaces clés

### BattleManager (server/battle/)
```python
BattleManager(player_pokemon, wild_pokemon)
manager.player_use_move(move_idx)   # -> (list[str], bool pending_enemy)
manager.enemy_act()                  # -> list[str]
manager.collect_end_of_turn()        # -> list[str]
manager.on_wild_fainted()            # -> list[str]
manager.end_battle(outcome)
manager.get_outcome()                # -> "won" | "lost" | "fled" | None
manager.auto_move_sym                # property (charge/verrou)
manager.is_transformed               # property
```

### BattleScreen (client/ui/) — renderer pur
```python
BattleScreen(screen, wild_data, player_pokemon, wild_pokemon, zone)
battle_screen.active    # bool
battle_screen.outcome   # str | None
battle_screen.handle_input(keylistener, controller, mouse_pos, mouse_click)
battle_screen.update()
battle_screen.draw(display)
```

### Entrée client
```
python code/main.py          ← lance le client
uvicorn code.server.server_api:app  ← lance l'API REST
```

---

## Shims de compatibilité temporaires

Les anciens packages (`code/core/`, `code/entities/`, etc.) ont leurs
`__init__.py` qui lèvent une `ImportError` avec le nouveau chemin.
Cela permet de détecter rapidement tout code non migré.

`code/config.py` reste comme shim (`from code.shared.config import *`)
pour la rétrocompatibilité maximale.

---

## Feuille de route

| Priorité | Tâche |
|---|---|
| ✅ Fait | Séparation physique client / server / shared |
| ✅ Fait | Moteur de combat extrait dans server/battle/ |
| ✅ Fait | BattleScreen réduit à du rendu pur |
| 🔜 Prochain | Éclater server_api.py en server/api/*.py |
| 🔜 Prochain | Implémenter server/entities/player_state.py |
| 🔜 Prochain | Chunk manager + AOI pour le MMO |
| 🔜 Prochain | Client inventory_manager (cache uniquement) |
| 🔜 Prochain | Protocole réseau complet (shared/protocol/) |
