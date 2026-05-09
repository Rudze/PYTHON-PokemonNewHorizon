import datetime

import pygame

from code.config import SPRITES_DIR
from code.core.controller import Controller
from code.core.keylistener import KeyListener
from code.core.screen import Screen
from code.entities.entity import Entity
from code.entities.pokemon import Pokemon
from code.managers.inventory_manager import InventoryManager
from code.world.switch import Switch


class Player(Entity):
    """
    Player class to manage the player
    """

    TILE_SIZE = 16

    def __init__(
        self,
        screen: Screen,
        controller: Controller,
        x: int,
        y: int,
        keylistener: KeyListener,
        ingame_time: datetime.timedelta = datetime.timedelta(seconds=0),
        gender: str = "red_m"
    ) -> None:
        super().__init__(screen, x, y, f"hero_01_{gender}")

        self.keylistener: KeyListener = keylistener
        self.controller: Controller = controller

        self.pokemons: list[Pokemon] = []
        self.inv: InventoryManager = InventoryManager(self.pokemons)
        self.pokedex: None = None

        self.name: str = "Lucas"
        self.gender: str = gender
        self.pokedollars: int = 0

        self.pokemons.append(Pokemon.create_pokemon("Bulbasaur", 5))
        self.ingame_time: datetime.timedelta = ingame_time

        self.can_move = True

        self.spritesheet_bike: pygame.Surface = pygame.image.load(
            str(SPRITES_DIR / "hero_01_red_m_cycle_roll.png")
        ).convert_alpha()

        self.menu_option: bool = False

        self.switchs: list[Switch] = []
        self.collisions: list[pygame.Rect] = []
        self.stairs: list[pygame.Rect] = []
        self.change_map: Switch | None = None

        # Callback réseau.
        # Il sera défini depuis game.py ou main.py.
        self.on_move = None

    def from_dict(self, data: dict) -> None:
        self.name = data["name"]
        self.gender = data["gender"]
        self.position = pygame.math.Vector2(data["position"]["x"], data["position"]["y"])
        self.align_hitbox()
        self.direction = data["direction"]
        self.pokemons.clear()
        for p in data["pokemons"]:
            self.pokemons.append(Pokemon.from_dict(p))
        if "inventory" in data and isinstance(data["inventory"], dict):
            self.inv.load_from_dict(data["inventory"])
        self.pokedex = data.get("pokedex")
        self.pokedollars = data.get("pokedollars", 0)
        self.ingame_time = datetime.timedelta(seconds=data["ingame_time"])

    def update(self) -> None:
        self.update_ingame_time()

        if self.can_move:
            self.check_move()

        self.check_input()
        super().update()

    def notify_network_move(self, target_x: int, target_y: int, direction: str) -> None:
        """
        Envoie au réseau uniquement les déplacements validés par les collisions.
        target_x / target_y = position cible du sprite, pas la hitbox.
        """
        if self.on_move is not None:
            self.on_move(target_x, target_y, direction)

    def check_move(self) -> None:
        """
        Check the move of the player
        """
        if self.animation_walk:
            return

        temp_hitbox = self.hitbox.copy()

        if self.keylistener.key_pressed(self.controller.get_key("left")):
            temp_hitbox.x -= self.TILE_SIZE

            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)

                target_x = int(self.position.x - self.TILE_SIZE)
                target_y = int(self.position.y)

                self.move_left()
                self.notify_network_move(target_x, target_y, "left")
            else:
                self.direction = "left"

        elif self.keylistener.key_pressed(self.controller.get_key("right")):
            temp_hitbox.x += self.TILE_SIZE

            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)

                target_x = int(self.position.x + self.TILE_SIZE)
                target_y = int(self.position.y)

                self.move_right()
                self.notify_network_move(target_x, target_y, "right")
            else:
                self.direction = "right"

        elif self.keylistener.key_pressed(self.controller.get_key("up")):
            temp_hitbox.y -= self.TILE_SIZE

            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)

                target_x = int(self.position.x)
                target_y = int(self.position.y - self.TILE_SIZE)

                self.move_up()
                self.notify_network_move(target_x, target_y, "up")
            else:
                self.direction = "up"

        elif self.keylistener.key_pressed(self.controller.get_key("down")):
            temp_hitbox.y += self.TILE_SIZE

            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)

                target_x = int(self.position.x)
                target_y = int(self.position.y + self.TILE_SIZE)

                self.move_down()
                self.notify_network_move(target_x, target_y, "down")
            else:
                self.direction = "down"

    def add_switchs(self, switchs: list[Switch]) -> None:
        self.switchs = switchs if switchs is not None else []

    def check_collisions_switchs(self, temp_hitbox: pygame.Rect) -> None:
        if self.switchs:
            for switch in self.switchs:
                if switch.check_collision(temp_hitbox):
                    self.change_map = switch
                    return

    def add_collisions(self, collisions: list[pygame.Rect]) -> None:
        self.collisions = collisions if collisions is not None else []

    def check_collisions(self, temp_hitbox: pygame.Rect) -> bool:
        for collision in self.collisions:
            if temp_hitbox.colliderect(collision):
                return True
        return False

    def check_input(self) -> None:
        if self.animation_walk:
            return

        if self.keylistener.key_pressed(self.controller.get_key("bike")):
            self.switch_bike()

        if self.keylistener.key_pressed(self.controller.get_key("quit")):
            self.menu_option = True
            self.keylistener.remove_key(self.controller.get_key("quit"))
            return

    def switch_bike(self, deactive: bool = False) -> None:
        if self.speed == 1 and not deactive:
            self.speed = 4
            self.all_images = self.get_all_images(self.spritesheet_bike)
        else:
            self.speed = 1
            self.all_images = self.get_all_images(self.spritesheet)

        self.keylistener.remove_key(pygame.K_b)

    def update_ingame_time(self) -> None:
        if self.screen.get_delta_time() > 0:
            self.ingame_time += datetime.timedelta(
                seconds=self.screen.get_delta_time() / 1000
            )