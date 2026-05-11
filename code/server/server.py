"""
PokeWorld multiplayer server — deploy this on your VPS.
Requirements: pip install websockets
Run: python server.py
"""

import asyncio
import json
import random
import uuid

import websockets
from websockets.exceptions import ConnectionClosed

TILE_SIZE         = 16
VALID_DIRECTIONS  = {"left", "right", "up", "down"}

# ── Spawn config — MIRROR de config.py POKEMON_SPAWNS ─────────────────────
# Pour ajouter une zone : ajouter une entrée ici ET dans config.py côté client.
POKEMON_SPAWNS: dict[str, list[dict]] = {
    "route_1": [
        {"pokemon_id": 19, "rarity": 70, "min_level": 2, "max_level": 4},  # Rattata
        {"pokemon_id": 16, "rarity": 30, "min_level": 3, "max_level": 5},  # Roucool
    ],
}

# ── État serveur ────────────────────────────────────────────────────────────

# pid → {ws, map, x, y, dir, sprite, name}
players: dict[str, dict] = {}

# ws → pid
ws_to_pid: dict = {}

# map_name → {wpid → {wpid, pokemon_id, level, shiny, x, y, dir, zone_name}}
wild_pokemons: dict[str, dict[str, dict]] = {}

# map_name → [{name, x, y, w, h, max_pokemon}]  (envoyé par les clients au JOIN)
spawn_zones_by_map: dict[str, list[dict]] = {}

_wpid_counter = 0

AI_TICK_INTERVAL = 2.0   # secondes entre chaque tick d'IA
MOVE_CHANCE      = 0.40  # probabilité qu'un Pokémon bouge par tick


# ── Utilitaires ────────────────────────────────────────────────────────────

def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value, default: str = "", max_length: int = 64) -> str:
    if value is None:
        return default
    value = str(value)
    return value[:max_length]


def is_valid_direction(d: str) -> bool:
    return d in VALID_DIRECTIONS


def is_valid_one_tile_move(ox: int, oy: int, nx: int, ny: int, d: str) -> bool:
    dx, dy = nx - ox, ny - oy
    return {
        "left":  (-TILE_SIZE, 0),
        "right": (TILE_SIZE,  0),
        "up":    (0, -TILE_SIZE),
        "down":  (0,  TILE_SIZE),
    }.get(d) == (dx, dy)


async def broadcast(map_name: str, msg: dict, exclude_ws=None) -> None:
    raw = json.dumps(msg)
    targets = [
        p["ws"] for p in players.values()
        if p.get("map") == map_name and p["ws"] is not exclude_ws
    ]
    if targets:
        await asyncio.gather(
            *[ws.send(raw) for ws in targets],
            return_exceptions=True,
        )


# ── IA des Pokémon sauvages ─────────────────────────────────────────────────

def _next_wpid() -> str:
    global _wpid_counter
    _wpid_counter += 1
    return f"wp_{_wpid_counter}"


def _pick_spawn_entry(zone_name: str) -> dict | None:
    entries = POKEMON_SPAWNS.get(zone_name, [])
    if not entries:
        return None
    total = sum(e["rarity"] for e in entries)
    roll  = random.uniform(0, total)
    cumul = 0.0
    for e in entries:
        cumul += e["rarity"]
        if roll <= cumul:
            return e
    return entries[-1]


def _random_tile_in_zone(zone: dict) -> tuple[int, int]:
    """Position aléatoire alignée sur la grille de tuiles dans la zone."""
    x0 = (zone["x"] // TILE_SIZE) * TILE_SIZE
    y0 = (zone["y"] // TILE_SIZE) * TILE_SIZE
    x1 = ((zone["x"] + zone["w"]) // TILE_SIZE) * TILE_SIZE
    y1 = ((zone["y"] + zone["h"]) // TILE_SIZE) * TILE_SIZE

    xs = list(range(x0, max(x0 + TILE_SIZE, x1), TILE_SIZE))
    ys = list(range(y0, max(y0 + TILE_SIZE, y1), TILE_SIZE))

    return random.choice(xs), random.choice(ys)


def _is_tile_free(current: dict, exclude_wpid: str, x: int, y: int, buffer: int = 1) -> bool:
    """
    True si aucun autre Pokémon n'est dans un rayon de `buffer` tuiles.
    buffer=1 → empêche la superposition exacte.
    buffer=2 → empêche aussi les tuiles adjacentes (sprites 32×32 sur tuiles 16×16).
    """
    half = TILE_SIZE * buffer
    return not any(
        abs(int(wp["x"]) - x) < half and abs(int(wp["y"]) - y) < half
        for wpid, wp in current.items()
        if wpid != exclude_wpid
    )


def _tile_has_player(map_name: str, x: int, y: int) -> bool:
    """True si un joueur se trouve sur la tuile logique (x, y)."""
    tx = x // TILE_SIZE
    ty = y // TILE_SIZE
    return any(
        int(p["x"]) // TILE_SIZE == tx and int(p["y"]) // TILE_SIZE == ty
        for p in players.values()
        if p.get("map") == map_name
    )


def _pick_move(
    wp: dict, zone: dict, current: dict, map_name: str
) -> tuple[int | None, int | None, str | None]:
    """
    Choisit une direction aléatoire valide dans la zone pour ce Pokémon.
    Refuse les cases occupées par un autre Pokémon ou un joueur.
    """
    candidates = [
        ("left",  wp["x"] - TILE_SIZE, wp["y"]),
        ("right", wp["x"] + TILE_SIZE, wp["y"]),
        ("up",    wp["x"],             wp["y"] - TILE_SIZE),
        ("down",  wp["x"],             wp["y"] + TILE_SIZE),
    ]
    random.shuffle(candidates)

    for direction, nx, ny in candidates:
        if (zone["x"] <= nx < zone["x"] + zone["w"] and
                zone["y"] <= ny < zone["y"] + zone["h"] and
                _is_tile_free(current, wp["wpid"], nx, ny) and
                not _tile_has_player(map_name, nx, ny)):
            return nx, ny, direction

    return None, None, None


async def pokemon_ai_loop() -> None:
    """
    Boucle d'IA côté serveur : spawn et déplacement tile-by-tile des Pokémon.
    Tourne en tâche asyncio en parallèle du serveur WebSocket.
    """
    while True:
        await asyncio.sleep(AI_TICK_INTERVAL)

        for map_name, zones in list(spawn_zones_by_map.items()):
            # Ne pas traiter les maps sans joueurs
            if not any(p.get("map") == map_name for p in players.values()):
                continue

            if map_name not in wild_pokemons:
                wild_pokemons[map_name] = {}

            current = wild_pokemons[map_name]

            for zone in zones:
                zone_name = zone.get("name", "")
                max_poke  = int(zone.get("max_pokemon", 3))

                # ── Spawn progressif : 1 max par zone par tick ────────
                zone_count = sum(1 for wp in current.values()
                                 if wp["zone_name"] == zone_name)

                if zone_count < max_poke and random.random() < 0.4:
                    entry = _pick_spawn_entry(zone_name)
                    if entry is not None:
                        x, y, found = 0, 0, False
                        for _ in range(10):
                            x, y = _random_tile_in_zone(zone)
                            if (_is_tile_free(current, "", x, y, buffer=2) and
                                    not _tile_has_player(map_name, x, y)):
                                found = True
                                break

                        if found:
                            level = random.randint(entry["min_level"], entry["max_level"])
                            shiny = random.random() < 0.01
                            wpid  = _next_wpid()

                            wp = {
                                "wpid":       wpid,
                                "pokemon_id": entry["pokemon_id"],
                                "level":      level,
                                "shiny":      shiny,
                                "x":          x,
                                "y":          y,
                                "dir":        "down",
                                "zone_name":  zone_name,
                            }
                            current[wpid] = wp

                            await broadcast(map_name, {
                                "type":       "pokemon_spawned",
                                "wpid":       wpid,
                                "pokemon_id": wp["pokemon_id"],
                                "level":      wp["level"],
                                "shiny":      wp["shiny"],
                                "x":          wp["x"],
                                "y":          wp["y"],
                                "dir":        wp["dir"],
                            })

            # ── Déplacement aléatoire tile-by-tile ────────────────────
            for wpid, wp in list(current.items()):
                if random.random() > MOVE_CHANCE:
                    continue

                zone = next(
                    (z for z in zones if z.get("name") == wp["zone_name"]),
                    None,
                )
                if zone is None:
                    continue

                nx, ny, direction = _pick_move(wp, zone, current, map_name)
                if nx is None:
                    continue

                wp["x"]   = nx
                wp["y"]   = ny
                wp["dir"] = direction

                await broadcast(map_name, {
                    "type": "pokemon_moved",
                    "wpid": wpid,
                    "x":    nx,
                    "y":    ny,
                    "dir":  direction,
                })


# ── Gestionnaire WebSocket ──────────────────────────────────────────────────

async def handler(ws) -> None:
    pid = str(uuid.uuid4())[:8]
    ws_to_pid[ws] = pid
    players[pid]  = {
        "ws":            ws,
        "map":           None,
        "x":             0,
        "y":             0,
        "dir":           "down",
        "sprite":        "",
        "name":          "",
        "customization": {},
    }
    print(f"[+] {pid} connected ({len(players)} online)")

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not isinstance(msg, dict):
                continue

            msg_type = msg.get("type")

            # ── JOIN ───────────────────────────────────────────────────
            if msg_type == "join":
                old_map = players[pid]["map"]
                new_map = safe_str(msg.get("map"), max_length=128)
                if not new_map:
                    continue

                x         = safe_int(msg.get("x"))
                y         = safe_int(msg.get("y"))
                direction = safe_str(msg.get("dir"), default="down", max_length=16)
                sprite    = safe_str(msg.get("sprite"), max_length=128)
                name      = safe_str(msg.get("name"), default="Player", max_length=32)

                if not is_valid_direction(direction):
                    direction = "down"

                # Notifier l'ancienne map du départ
                if old_map and old_map != new_map:
                    await broadcast(old_map, {"type": "player_left", "pid": pid})

                customization = msg.get("customization", {})
                if not isinstance(customization, dict):
                    customization = {}

                players[pid].update({
                    "map": new_map, "x": x, "y": y,
                    "dir": direction, "sprite": sprite, "name": name,
                    "customization": customization,
                })

                # Stocker les zones de spawn envoyées par ce client
                zones_data = msg.get("spawn_zones")
                if isinstance(zones_data, list) and zones_data:
                    spawn_zones_by_map[new_map] = zones_data

                # Snapshot joueurs déjà présents (avec leurs cosmétiques)
                snapshot = [
                    {"pid": op, "x": d["x"], "y": d["y"], "dir": d["dir"],
                     "sprite": d["sprite"], "name": d["name"],
                     "customization": d.get("customization", {})}
                    for op, d in players.items()
                    if d.get("map") == new_map and op != pid
                ]
                await ws.send(json.dumps({"type": "snapshot", "players": snapshot}))

                # Snapshot Pokémon sauvages déjà présents
                existing_poke = [
                    {"wpid": wp["wpid"], "pokemon_id": wp["pokemon_id"],
                     "level": wp["level"], "shiny": wp["shiny"],
                     "x": wp["x"], "y": wp["y"], "dir": wp["dir"]}
                    for wp in wild_pokemons.get(new_map, {}).values()
                ]
                await ws.send(json.dumps({
                    "type":    "pokemon_snapshot",
                    "pokemons": existing_poke,
                }))

                # Annoncer l'arrivée aux autres joueurs (avec cosmétiques)
                await broadcast(new_map, {
                    "type": "player_joined", "pid": pid,
                    "x": x, "y": y, "dir": direction,
                    "sprite": sprite, "name": name,
                    "customization": customization,
                }, exclude_ws=ws)

                print(f"    {pid} joined '{new_map}' at ({x}, {y})")

            # ── MOVE (joueur) ──────────────────────────────────────────
            elif msg_type == "move":
                player = players.get(pid)
                if not player or not player.get("map"):
                    continue

                current_map = player["map"]
                new_x  = safe_int(msg.get("x"), player["x"])
                new_y  = safe_int(msg.get("y"), player["y"])
                new_dir = safe_str(msg.get("dir"), player["dir"], max_length=16)

                if not is_valid_direction(new_dir):
                    continue
                if not is_valid_one_tile_move(player["x"], player["y"], new_x, new_y, new_dir):
                    print(f"[!] Invalid move from {pid}: "
                          f"({player['x']},{player['y']}) → ({new_x},{new_y}) {new_dir}")
                    continue

                player["x"], player["y"], player["dir"] = new_x, new_y, new_dir

                await broadcast(current_map, {
                    "type": "player_moved", "pid": pid,
                    "x": new_x, "y": new_y, "dir": new_dir,
                }, exclude_ws=ws)

            # ── TURN (rotation sur place) ──────────────────────────────
            elif msg_type == "turn":
                player = players.get(pid)
                if not player or not player.get("map"):
                    continue

                new_dir = safe_str(msg.get("dir"), default="down", max_length=16)
                if not is_valid_direction(new_dir):
                    continue

                player["dir"] = new_dir

                await broadcast(player["map"], {
                    "type": "player_turned",
                    "pid":  pid,
                    "dir":  new_dir,
                }, exclude_ws=ws)

            # ── POKEMON_ENCOUNTER ──────────────────────────────────────
            elif msg_type == "pokemon_encounter":
                player = players.get(pid)
                if not player or not player.get("map"):
                    continue

                current_map = player["map"]
                wpid        = safe_str(msg.get("wpid"))
                map_poke    = wild_pokemons.get(current_map, {})

                if wpid not in map_poke:
                    continue  # déjà capturé par quelqu'un d'autre

                wp_data = map_poke.pop(wpid)

                # Tous les clients retirent ce Pokémon
                await broadcast(current_map, {
                    "type": "pokemon_despawned",
                    "wpid": wpid,
                })

                # Le client qui a déclenché l'encounter reçoit les données pour le combat
                await ws.send(json.dumps({
                    "type":       "pokemon_encounter_start",
                    "wpid":       wpid,
                    "pokemon_id": wp_data["pokemon_id"],
                    "level":      wp_data["level"],
                    "shiny":      wp_data["shiny"],
                }))

                print(f"[Encounter] {pid} × Pokémon #{wp_data['pokemon_id']} ({wpid})")

    except ConnectionClosed:
        pass

    finally:
        player = players.pop(pid, None)
        ws_to_pid.pop(ws, None)

        if player and player.get("map"):
            await broadcast(player["map"], {"type": "player_left", "pid": pid})

        print(f"[-] {pid} disconnected ({len(players)} online)")


# ── Point d'entrée ──────────────────────────────────────────────────────────

async def main() -> None:
    host = "0.0.0.0"
    port = 8765

    async with websockets.serve(handler, host, port):
        print(f"PokeWorld server listening on {host}:{port}")
        asyncio.create_task(pokemon_ai_loop())
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
