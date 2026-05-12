import pygame
import pyscroll
import pytmx

from code.config import INTERFACES_DIR, MAPS_DIR
from code.core.controller import Controller
from code.core.screen import Screen
from code.data.sql import SQL
from code.entities.player import Player
from code.utils.tool import Tool
from code.world.spawn_zone import SpawnZone
from code.world.switch import Switch


class Map:
    """
    Map class to manage the map
    """

    def __init__(self, screen: Screen, controller: Controller) -> None:
        self.screen: Screen = screen
        self.controller: Controller = controller

        self.tmx_data: pytmx.TiledMap | None = None
        self.map_layer: pyscroll.BufferedRenderer | None = None
        self.group: pyscroll.PyscrollGroup | None = None

        self.player: Player | None = None
        self.switchs:     list[Switch]      = []
        self.collisions:  list[pygame.Rect] = []
        self.stairs:      dict[str, pygame.Rect] = {}
        self.spawn_zones: list[SpawnZone]   = []

        self.sql: SQL = SQL()

        self.current_map: Switch | None = None
        self.map_name: str | None = None
        self.map_name_text: pygame.Surface | None = None

        self.animation_change_map: int = 0
        self.animation_change_map_active: bool = False

    def switch_map(self, switch: Switch) -> None:
        """
        Switch the map
        """
        old_map = self.current_map

        self.tmx_data = pytmx.load_pygame(str(MAPS_DIR / f"{switch.name}.tmx"))

        map_data = pyscroll.data.TiledMapData(self.tmx_data)
        self.map_layer = pyscroll.BufferedRenderer(map_data, self.screen.get_size())
        self.group = pyscroll.PyscrollGroup(map_layer=self.map_layer, default_layer=9)

        self.animation_change_map = 0
        self.animation_change_map_active = False

        if switch.name.split("_")[0] == "map":
            self.map_layer.zoom = 3
            self.set_draw_change_map(switch.name)
        else:
            self.map_layer.zoom = 4

        self.switchs     = []
        self.collisions  = []
        self.stairs      = {}
        self.spawn_zones = []   # recréée ici → SpawnManager détecte le changement de map

        self._load_tmx_objects()

        print(f"[Map] Loaded map: {switch.name}")
        print(f"[Map] Collisions loaded: {len(self.collisions)}")
        print(f"[Map] Switchs loaded: {len(self.switchs)}")
        print(f"[Map] Stairs loaded: {len(self.stairs)}")

        if self.player is not None:
            self.pose_player(switch, old_map)
            self.player.align_hitbox()
            self.player.step = 16
            self.player.add_switchs(self.switchs)
            self.player.add_collisions(self.collisions)

            self.group.add(self.player)

            print(f"[Map] Collisions assigned to player: {len(self.player.collisions)}")

            if switch.name.split("_")[0] != "map":
                self.player.switch_bike(True)

        self.current_map = switch

    def _load_tmx_objects(self) -> None:
        """
        Load collisions, switches, stairs and Pokémon spawn zones from the TMX.

        Spawn zones : objets dans le layer nommé "pokemonspawn".
            - Le nom de la zone vient de la custom property "spawn_zone"
              ou, à défaut, du nom de l'objet lui-même.
            - Le plafond vient de la custom property "max_pokemon" (défaut 3).
        """
        if self.tmx_data is None:
            return

        # ── Spawn zones : lire par nom de layer ───────────────────────
        # On parcourt les objectgroups séparément pour identifier le bon layer.
        for layer in self.tmx_data.objectgroups:
            if not layer.name.lower().startswith("pokemonspawn"):
                continue
            for obj in layer:
                props       = dict(obj.properties) if obj.properties else {}
                zone_name   = str(props.get("spawn_zone", obj.name or "")).strip()
                max_pokemon = int(props.get("max_pokemon", 3))
                if not zone_name:
                    continue
                self.spawn_zones.append(SpawnZone(
                    name        = zone_name,
                    rect        = pygame.Rect(int(obj.x), int(obj.y),
                                             int(obj.width), int(obj.height)),
                    max_pokemon = max_pokemon,
                ))
        print(f"[Map] Spawn zones loaded: {len(self.spawn_zones)}"
              + (f" {[z.name for z in self.spawn_zones]}" if self.spawn_zones else ""))

        # ── Collisions, switches, stairs ──────────────────────────────
        for obj in self.tmx_data.objects:
            obj_name   = (obj.name or "").strip()
            obj_type   = (getattr(obj, "type", "") or "").strip()
            first_word = obj_name.split(" ")[0].lower() if obj_name else ""
            tiled_type = obj_type.lower()

            rect = pygame.Rect(
                int(obj.x), int(obj.y),
                int(obj.width), int(obj.height),
            )

            if first_word == "collision" or tiled_type == "collision":
                self.collisions.append(rect)
                continue

            if first_word == "switch":
                parts = obj_name.split(" ")
                if len(parts) >= 3:
                    try:
                        self.switchs.append(Switch(parts[0], parts[1], rect, int(parts[-1])))
                    except ValueError:
                        print(f"[Map] Invalid switch object ignored: {obj_name}")
                continue

            if first_word == "stairs":
                parts = obj_name.split(" ")
                if len(parts) >= 2:
                    self.stairs[parts[-1]] = rect
                continue

    def add_player(self, player: Player) -> None:
        """
        Add the player to the map
        """
        self.player = player
        self.player.align_hitbox()

        self.player.add_switchs(self.switchs)
        self.player.add_collisions(self.collisions)

        if self.group is not None:
            self.group.add(self.player)

        print("[Map] Player added")
        print(f"[Map] Collisions given to player: {len(self.player.collisions)}")
        print(f"[Map] Switchs given to player: {len(self.player.switchs)}")

    def add_entity(self, entity) -> None:
        """
        Add any sprite, for example RemotePlayer, to the current pyscroll group.
        """
        if self.group is not None:
            self.group.add(entity)

    def update(self) -> None:
        """
        Update the map
        """
        if self.group is None or self.player is None:
            return

        if self.player.change_map and self.player.step >= 8:
            self.switch_map(self.player.change_map)
            self.player.change_map = None

        elif self.player.step == 0 and not self.player.stairs_walk:
            for key, value in self.stairs.items():
                if self.player.direction == "right":
                    next_rect = pygame.Rect(
                        self.player.hitbox.x + 16,
                        self.player.hitbox.y,
                        self.player.hitbox.w,
                        self.player.hitbox.h
                    )

                    if next_rect.colliderect(value):
                        if key == "right":
                            self.player.stairs_walk = 16
                            self.player.stairs_direction = "down"

                    elif self.player.hitbox.colliderect(value):
                        if key == "left":
                            self.player.stairs_walk = 16
                            self.player.stairs_direction = "down"

                elif self.player.direction == "left":
                    next_rect = pygame.Rect(
                        self.player.hitbox.x - 16,
                        self.player.hitbox.y,
                        self.player.hitbox.w,
                        self.player.hitbox.h
                    )

                    if next_rect.colliderect(value):
                        if key == "left":
                            self.player.stairs_walk = 16
                            self.player.stairs_direction = "up"

                    elif self.player.hitbox.colliderect(value):
                        if key == "right":
                            self.player.stairs_walk = 16
                            self.player.stairs_direction = "up"

        self.group.update()
        self.group.center(self.player.rect.center)
        self.group.draw(self.screen.get_display())

        if self.animation_change_map_active:
            self.draw_change_map()

    def pose_player(self, switch: Switch, old_map: Switch | None = None) -> None:
        """
        Pose the player on the map
        """
        if self.tmx_data is None or self.player is None:
            return

        previous_map_name = old_map.name if old_map is not None else switch.name

        possible_spawn_names = [
            f"spawn {previous_map_name} {switch.port}",
            f"spawn {switch.name} {switch.port}",
            f"spawn {switch.port}",
            "spawn",
        ]

        spawn = None

        for spawn_name in possible_spawn_names:
            try:
                spawn = self.tmx_data.get_object_by_name(spawn_name)
                break
            except ValueError:
                continue

        if spawn is None:
            print(
                f"[Map] Warning: no spawn found for map '{switch.name}' "
                f"with port {switch.port}. Player position unchanged."
            )
            return

        self.player.position = pygame.math.Vector2(int(spawn.x), int(spawn.y))
        self.player.align_hitbox()

    def set_draw_change_map(self, map_name: str) -> None:
        """
        Set the draw change map
        """
        if not self.animation_change_map_active:
            self.map_name = self.sql.get_name_map(map_name)
            self.animation_change_map_active = True
            self.animation_change_map = 0
            self.map_name_text = Tool.create_text(self.map_name, 30, (255, 255, 255))

    def get_surface_change_map(self, alpha: int = 0) -> pygame.Surface:
        surface_change_map = pygame.Surface((215, 53), pygame.SRCALPHA).convert_alpha()
        surface_change_map.fill((20, 20, 20, 220))
        surface_change_map.set_alpha(alpha)
        return surface_change_map

    def draw_change_map(self) -> None:
        """
        Draw the change map animation
        """
        if self.map_name_text is None:
            return

        if self.animation_change_map < 255:
            surface = self.get_surface_change_map(self.animation_change_map).convert_alpha()
            self.screen.display.blit(
                surface,
                (self.screen.display.get_width() - self.animation_change_map, 600)
            )
            self.animation_change_map += 5

        elif self.animation_change_map < 1024:
            surface = self.get_surface_change_map(255)

            Tool.add_text_to_surface(
                surface,
                self.map_name_text,
                surface.get_width() // 2 - self.map_name_text.get_width() // 2,
                4
            )

            self.screen.display.blit(
                surface,
                (self.screen.display.get_width() - 255, 600)
            )
            self.animation_change_map += 2

        elif self.animation_change_map < 1279:
            surface = self.get_surface_change_map(1279 - self.animation_change_map)

            Tool.add_text_to_surface(
                surface,
                self.map_name_text,
                surface.get_width() // 2 - self.map_name_text.get_width() // 2,
                4
            )

            self.screen.display.blit(
                surface,
                (self.screen.display.get_width() - 255, 600)
            )
            self.animation_change_map += 5

        else:
            self.animation_change_map_active = False
            self.animation_change_map = 0

    def load_map(self, map: str) -> None:
        """
        Load the map from the map name
        """
        self.switch_map(Switch("switch", map, pygame.Rect(0, 0, 0, 0), 0))