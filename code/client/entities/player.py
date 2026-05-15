import datetime

import pygame

from code.client.config import SPRITES_CHARACTER_DIR
from code.client.core.controller import Controller
from code.client.core.keylistener import KeyListener
from code.client.core.screen import Screen
from code.client.entities.entity import Entity
from code.server.managers.inventory_manager import InventoryManager
from code.client.world.switch import Switch


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
    ) -> None:
        super().__init__(screen, x, y, "character")

        self.keylistener: KeyListener = keylistener
        self.controller: Controller = controller

        self.pokemons: list = []
        self.inv: InventoryManager = InventoryManager(self.pokemons)
        self.pokedex: None = None

        self.name: str = "Lucas"
        self.pokedollars: int = 0

        self.ingame_time: datetime.timedelta = ingame_time

        self.can_move = True

        self.menu_option: bool = False

        self.switchs: list[Switch] = []
        self.collisions: list[pygame.Rect] = []
        self.stairs: list[pygame.Rect] = []
        self.change_map: Switch | None = None

        # Callback réseau.
        # Il sera défini depuis game.py ou main.py.
        self.on_move = None

        # Rotation sur place (PokeMMO-style) :
        # mémorise la dernière direction demandée ; si elle change → simple rotation
        # sans déplacement ; si elle est maintenue → marche.
        self._turn_direction: str | None = None

    def from_dict(self, data: dict) -> None:
        self.position = pygame.math.Vector2(data["position"]["x"], data["position"]["y"])
        self.align_hitbox()
        self.direction = data["direction"]
        self.pokedex = data.get("pokedex")

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
        """Déplacement avec rotation sur place (PokeMMO-style)."""
        if self.animation_walk:
            return

        # Touche de direction actuellement pressée
        cur_dir: str | None = None
        if   self.keylistener.key_pressed(self.controller.get_key("left")):  cur_dir = "left"
        elif self.keylistener.key_pressed(self.controller.get_key("right")): cur_dir = "right"
        elif self.keylistener.key_pressed(self.controller.get_key("up")):    cur_dir = "up"
        elif self.keylistener.key_pressed(self.controller.get_key("down")):  cur_dir = "down"

        if cur_dir is None:
            self._turn_direction = None
            return

        # Première pression dans cette direction → rotation simple, pas de marche
        if self._turn_direction != cur_dir:
            self._turn_direction = cur_dir
            self.direction = cur_dir
            return  # sprite mis à jour, aucun déplacement ce frame

        # Touche maintenue → déplacement normal
        temp_hitbox = self.hitbox.copy()
        if cur_dir == "left":
            temp_hitbox.x -= self.TILE_SIZE
            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)
                self.move_left()
                self.notify_network_move(int(self.position.x - self.TILE_SIZE), int(self.position.y), "left")

        elif cur_dir == "right":
            temp_hitbox.x += self.TILE_SIZE
            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)
                self.move_right()
                self.notify_network_move(int(self.position.x + self.TILE_SIZE), int(self.position.y), "right")

        elif cur_dir == "up":
            temp_hitbox.y -= self.TILE_SIZE
            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)
                self.move_up()
                self.notify_network_move(int(self.position.x), int(self.position.y - self.TILE_SIZE), "up")

        elif cur_dir == "down":
            temp_hitbox.y += self.TILE_SIZE
            if not self.check_collisions(temp_hitbox):
                self.check_collisions_switchs(temp_hitbox)
                self.move_down()
                self.notify_network_move(int(self.position.x), int(self.position.y + self.TILE_SIZE), "down")

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
        # Phone key : vérifiée EN PREMIER, avant le guard animation_walk,
        # pour pouvoir ouvrir le Motismart même pendant un déplacement.
        if self.keylistener.key_pressed(self.controller.get_key("phone")):
            if not self.menu_option:
                self.menu_option = True
                self.can_move    = False
                self.keylistener.remove_key(self.controller.get_key("phone"))
            # Si déjà ouvert : Motismart gère la fermeture via son propre handler
            return

        if self.animation_walk:
            return

        if self.keylistener.key_pressed(self.controller.get_key("bike")):
            self.switch_bike()

    def switch_bike(self, deactive: bool = False) -> None:
        if self.speed == 1 and not deactive:
            self.speed = 4
            bike_sheet = getattr(self, "spritesheet_bike", None) or self.spritesheet
            self.all_images = self.get_all_images(bike_sheet)
        else:
            self.speed = 1
            self.all_images = self.get_all_images(self.spritesheet)

        self.keylistener.remove_key(pygame.K_b)

    def update_ingame_time(self) -> None:
        if self.screen.get_delta_time() > 0:
            self.ingame_time += datetime.timedelta(
                seconds=self.screen.get_delta_time() / 1000
            )