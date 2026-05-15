from __future__ import annotations
from typing import TYPE_CHECKING
import json
import os

from code.server.config import SAVES_DIR

if TYPE_CHECKING:
    from code.client.world.map import Map
    from code.client.entities.player import Player


class Save:
    def __init__(self, path: str, map: "Map", player: "Player") -> None:
        self.path   = path
        self.map    = map
        self.player = player

    def save(self) -> None:
        position = self.map.player.position
        data = {
            "player": {
                "position":  {"x": position[0], "y": position[1]},
                "direction": self.map.player.direction,
            },
            "map": {
                "path":     self.map.current_map.name,
                "map_name": self.map.map_name,
            },
        }
        save_file = SAVES_DIR / self.path / "data.pkmn"
        os.makedirs(save_file.parent, exist_ok=True)
        save_file.write_text(json.dumps(data, indent=4))

    def load(self) -> None:
        save_file = SAVES_DIR / self.path / "data.pkmn"
        if save_file.exists():
            data = json.loads(save_file.read_text())
            self.map.load_map(data["map"]["path"])
            self.player.from_dict(data["player"])
        else:
            self.map.load_map("map_0")
            self.player.set_position(512, 288)
            self.player.align_hitbox()
        self.map.add_player(self.player)
