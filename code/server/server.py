"""
PokeWorld multiplayer server — deploy this on your VPS.
Requirements: pip install websockets
Run: python server.py
"""

import asyncio
import json
import uuid

import websockets
from websockets.exceptions import ConnectionClosed

TILE_SIZE = 16
VALID_DIRECTIONS = {"left", "right", "up", "down"}

# pid -> {ws, map, x, y, dir, sprite, name}
players: dict[str, dict] = {}

# ws -> pid
ws_to_pid: dict = {}


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value, default: str = "", max_length: int = 64) -> str:
    if value is None:
        return default

    value = str(value)

    if len(value) > max_length:
        value = value[:max_length]

    return value


def is_valid_direction(direction: str) -> bool:
    return direction in VALID_DIRECTIONS


def is_valid_one_tile_move(old_x: int, old_y: int, new_x: int, new_y: int, direction: str) -> bool:
    dx = new_x - old_x
    dy = new_y - old_y

    if direction == "left":
        return dx == -TILE_SIZE and dy == 0

    if direction == "right":
        return dx == TILE_SIZE and dy == 0

    if direction == "up":
        return dx == 0 and dy == -TILE_SIZE

    if direction == "down":
        return dx == 0 and dy == TILE_SIZE

    return False


async def broadcast(map_name: str, msg: dict, exclude_ws=None) -> None:
    raw = json.dumps(msg)

    targets = [
        p["ws"]
        for p in players.values()
        if p.get("map") == map_name and p["ws"] is not exclude_ws
    ]

    if targets:
        await asyncio.gather(
            *[ws.send(raw) for ws in targets],
            return_exceptions=True
        )


async def handler(ws) -> None:
    pid = str(uuid.uuid4())[:8]

    ws_to_pid[ws] = pid
    players[pid] = {
        "ws": ws,
        "map": None,
        "x": 0,
        "y": 0,
        "dir": "down",
        "sprite": "",
        "name": "",
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

            if msg_type == "join":
                old_map = players[pid]["map"]
                new_map = safe_str(msg.get("map"), max_length=128)

                if not new_map:
                    continue

                x = safe_int(msg.get("x"))
                y = safe_int(msg.get("y"))
                direction = safe_str(msg.get("dir"), default="down", max_length=16)
                sprite = safe_str(msg.get("sprite"), max_length=128)
                name = safe_str(msg.get("name"), default="Player", max_length=32)

                if not is_valid_direction(direction):
                    direction = "down"

                # Notify old map of departure
                if old_map and old_map != new_map:
                    await broadcast(old_map, {
                        "type": "player_left",
                        "pid": pid,
                    })

                players[pid].update({
                    "map": new_map,
                    "x": x,
                    "y": y,
                    "dir": direction,
                    "sprite": sprite,
                    "name": name,
                })

                # Send snapshot of players already on this map, excluding self
                snapshot = [
                    {
                        "pid": other_pid,
                        "x": data["x"],
                        "y": data["y"],
                        "dir": data["dir"],
                        "sprite": data["sprite"],
                        "name": data["name"],
                    }
                    for other_pid, data in players.items()
                    if data.get("map") == new_map and other_pid != pid
                ]

                await ws.send(json.dumps({
                    "type": "snapshot",
                    "players": snapshot,
                }))

                # Announce arrival to the rest of the map
                await broadcast(new_map, {
                    "type": "player_joined",
                    "pid": pid,
                    "x": x,
                    "y": y,
                    "dir": direction,
                    "sprite": sprite,
                    "name": name,
                }, exclude_ws=ws)

                print(f"    {pid} joined map '{new_map}' at ({x}, {y})")

            elif msg_type == "move":
                player = players.get(pid)

                if not player:
                    continue

                current_map = player.get("map")

                if not current_map:
                    continue

                new_x = safe_int(msg.get("x"), default=player["x"])
                new_y = safe_int(msg.get("y"), default=player["y"])
                new_dir = safe_str(msg.get("dir"), default=player["dir"], max_length=16)

                if not is_valid_direction(new_dir):
                    continue

                old_x = int(player["x"])
                old_y = int(player["y"])

                if not is_valid_one_tile_move(old_x, old_y, new_x, new_y, new_dir):
                    print(
                        f"[!] Invalid move ignored from {pid}: "
                        f"old=({old_x}, {old_y}) new=({new_x}, {new_y}) dir={new_dir}"
                    )
                    continue

                player["x"] = new_x
                player["y"] = new_y
                player["dir"] = new_dir

                await broadcast(current_map, {
                    "type": "player_moved",
                    "pid": pid,
                    "x": new_x,
                    "y": new_y,
                    "dir": new_dir,
                }, exclude_ws=ws)

    except ConnectionClosed:
        pass

    finally:
        player = players.pop(pid, None)
        ws_to_pid.pop(ws, None)

        if player and player.get("map"):
            await broadcast(player["map"], {
                "type": "player_left",
                "pid": pid,
            })

        print(f"[-] {pid} disconnected ({len(players)} online)")


async def main() -> None:
    host = "0.0.0.0"
    port = 8765

    async with websockets.serve(handler, host, port):
        print(f"PokeWorld server listening on {host}:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())