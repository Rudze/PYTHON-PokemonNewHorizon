import json
import os

from code.config import SAVES_DIR
from code.core.keylistener import KeyListener
from code.data.sql import SQL
from code.entities.player import Player
from code.ui.dialogue import Dialogue
from code.world.map import Map


class Save:
    """
    Save class to manage the save
    """
    def __init__(self, path: str, map: Map, player: Player, keylistener: KeyListener, dialogue: Dialogue):
        """
        Initialize the save
        :param path:
        :param map:
        """
        self.path: str = path
        self.map: Map = map
        self.player: Player = player
        self.keylistener: KeyListener = keylistener
        self.dialogue: Dialogue = dialogue
        self.sql: SQL = SQL()

    def save(self) -> None:
        """
        Save the game
        :return:
        """
        position = self.map.player.position
        data = {
            "player": {
                "position": {"x": position[0], "y": position[1]},
                "direction": self.map.player.direction,
                "pokedex": self.map.player.pokedex,
            },
            "map": {
                "path": self.map.current_map.name,
                "map_name": self.map.map_name,
            },
        }

        save_file = SAVES_DIR / self.path / "data.pkmn"
        if not save_file.exists():
            os.makedirs(save_file.parent, exist_ok=True)
            save_file.touch()

        with open(save_file, "w") as file:
            file.write(self.dump(data))

        self.dialogue.load_data(100, 0)

    def load(self) -> None:
        """
        Load the game from the save
        :return:
        """
        save_file = SAVES_DIR / self.path / "data.pkmn"
        if save_file.exists():
            with open(save_file, "r") as file:
                data = json.load(file)
            self.map.load_map(data["map"]["path"])
            self.player.from_dict(data["player"])
        else:
            self.map.load_map("map_0")
            self.player.set_position(512, 288)
            self.player.align_hitbox()
        self.map.add_player(self.player)

    def dump(self, element: dict) -> str:
        """
        Dump the element in json format
        :param element:
        :return:
        """
        return json.dumps(element, indent=4)
