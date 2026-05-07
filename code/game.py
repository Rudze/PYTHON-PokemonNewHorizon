import pygame

from controller import Controller
from keylistener import KeyListener
from map import Map
from network.client import NetworkClient
from option import Option
from player import Player
from remote_player import RemotePlayer
from save import Save
from screen import Screen
from dialogue import Dialogue
from login_menu import LoginMenu
from server_select_menu import ServerSelectMenu
from splash_screen import SplashScreen

AUTH_API_URL = "http://37.59.114.12:8000"


class Game:
    def __init__(self) -> None:
        self.running: bool = True
        self.screen: Screen = Screen()

        # 1. On prépare l'état initial
        self.state = "SPLASH"
        self.splash = SplashScreen(self.screen)

        # 2. On prépare les variables vides (elles seront remplies plus tard)
        self.account_data = None
        self.selected_server = None
        self.network = None
        self.player = None
        self.map = None
        self._server_map = None
        # ... initialise ici uniquement les outils de base (Controller, KeyListener)
        self.controller = Controller()
        self.keylistener = KeyListener()

    def _setup_game_world(self):
        """ Cette méthode initialise tout le monde de jeu une fois connecté """
        self.account = self.account_data["account"]
        server_host = self.selected_server["host"]
        server_port = self.selected_server["port"]
        self.server_url = f"ws://{server_host}:{server_port}"

        self.map = Map(self.screen, self.controller)
        self.player = Player(self.screen, self.controller, 512, 288, self.keylistener)
        self.player.name = self.account["username"]

        self.dialogue = Dialogue(self.player, self.screen)
        self.save = Save("save_0", self.map, self.player, self.keylistener, self.dialogue)
        self.save.load()
        self._ensure_map_ready()

        self.option = Option(self.screen, self.controller, self.map, "fr", self.save, self.keylistener, self.dialogue)
        self.network = NetworkClient(self.server_url)
        self.remote_players = {}

    def run(self) -> None:
        while self.running:
            self.handle_input()

            # --- GESTION DES ÉTATS ---
            if self.state == "SPLASH":
                self.splash.update()
                self.splash.draw()
                if self.splash.is_finished:
                    self.state = "LOGIN"

            elif self.state == "LOGIN":
                login_menu = LoginMenu(self.screen, AUTH_API_URL)
                self.account_data = login_menu.run()
                if self.account_data:
                    self.state = "SERVER_SELECT"
                else:
                    self.running = False

            elif self.state == "SERVER_SELECT":
                server_menu = ServerSelectMenu(self.screen, AUTH_API_URL)
                self.selected_server = server_menu.run()
                if self.selected_server:
                    self._setup_game_world()  # On crée le monde ici !
                    self.state = "PLAYING"
                else:
                    self.running = False

            elif self.state == "PLAYING":
                # TOUTE la logique de jeu va ici (mouvements, map, réseau)
                self.update_playing_logic()

            self.screen.update()

    def _ensure_map_ready(self) -> None:
        """
        Vérifie que la sauvegarde a bien chargé une map
        et que le joueur est bien dans le groupe de rendu.
        """
        if self.map.group is None:
            raise RuntimeError(
                "Aucune map n'est chargée. Vérifie que save.load() appelle bien map.load_map(...)."
            )

        if self.map.player is None:
            self.map.add_player(self.player)

        print("[Game] Map ready")
        print(f"[Game] Current map: {self.map.current_map.name if self.map.current_map else None}")
        print(f"[Game] Player position: {self.player.position}")
        print(f"[Game] Player collisions: {len(self.player.collisions)}")

    # ------------------------------------------------------------------
    # Network integration
    # ------------------------------------------------------------------

    def _handle_network(
        self,
        prev_walking: bool,
        prev_pos: tuple[int, int],
        prev_map: str | None
    ) -> None:
        current_map = self.map.current_map.name if self.map.current_map else None

        if not self.network.connected and self._server_map is not None:
            self._server_map = None
            self._clear_remote_players()

        if current_map and current_map != self._server_map and self.network.connected:
            self._clear_remote_players()
            self._send_join(current_map)
            self._server_map = current_map

        if self.player.animation_walk and not prev_walking and self.network.connected and current_map:
            target_x = prev_pos[0]
            target_y = prev_pos[1]

            if self.player.direction == "left":
                target_x -= 16
            elif self.player.direction == "right":
                target_x += 16
            elif self.player.direction == "up":
                target_y -= 16
            elif self.player.direction == "down":
                target_y += 16

            self.network.send({
                "type": "move",
                "map": current_map,
                "x": target_x,
                "y": target_y,
                "dir": self.player.direction,
            })

        for msg in self.network.poll():
            self._dispatch(msg)

    def _send_join(self, map_name: str) -> None:
        self.network.send({
            "type": "join",
            "map": map_name,
            "x": int(self.player.position.x),
            "y": int(self.player.position.y),
            "dir": self.player.direction,
            "sprite": f"hero_01_{self.player.gender}",
            "name": self.player.name,
        })

    def _dispatch(self, msg: dict) -> None:
        t = msg.get("type")

        if t == "snapshot":
            self._clear_remote_players()
            for p in msg.get("players", []):
                self._add_remote_player(p)

        elif t == "player_joined":
            self._add_remote_player(msg)

        elif t == "player_left":
            self._remove_remote_player(msg["pid"])

        elif t == "player_moved":
            pid = msg["pid"]
            if pid in self.remote_players:
                self.remote_players[pid].apply_move(
                    int(msg["x"]),
                    int(msg["y"]),
                    msg["dir"]
                )

    def _add_remote_player(self, data: dict) -> None:
        pid = data["pid"]

        if pid in self.remote_players:
            return

        rp = RemotePlayer(
            self.screen,
            pid,
            int(data["x"]),
            int(data["y"]),
            data["dir"],
            data["sprite"],
            data["name"],
        )

        self.remote_players[pid] = rp

        if self.map.group:
            self.map.group.add(rp)

    def _remove_remote_player(self, pid: str) -> None:
        rp = self.remote_players.pop(pid, None)

        if rp:
            rp.kill()

    def _clear_remote_players(self) -> None:
        for rp in self.remote_players.values():
            rp.kill()

        self.remote_players.clear()

    # ------------------------------------------------------------------
    # Existing helpers
    # ------------------------------------------------------------------

    def dialogue_controller(self) -> None:
        if self.dialogue.active:
            self.dialogue.update()

            if self.keylistener.key_pressed(self.controller.get_key("action")):
                self.dialogue.action()
                self.keylistener.remove_key(self.controller.get_key("action"))

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()

            elif event.type == pygame.KEYDOWN:
                self.keylistener.add_key(event.key)

            elif event.type == pygame.KEYUP:
                self.keylistener.remove_key(event.key)

    def update_playing_logic(self) -> None:
        # 1. Sauvegarder l'état précédent (pour le réseau)
        prev_walking = self.player.animation_walk
        prev_pos = (int(self.player.position.x), int(self.player.position.y))
        prev_map = self.map.current_map.name if self.map.current_map else None

        # 2. Gérer le mouvement et les menus
        if not self.player.menu_option:
            self.map.update()
            # Touche interaction
            if pygame.K_e in self.keylistener.keys and not self.dialogue.active:
                self.dialogue.load_data(1001, 0)
                self.keylistener.remove_key(pygame.K_e)
            self.dialogue_controller()
        else:
            self.option.update()
            self.dialogue_controller()
            self.option.check_inputs()

        # 3. Gérer le réseau
        self._handle_network(prev_walking, prev_pos, prev_map)