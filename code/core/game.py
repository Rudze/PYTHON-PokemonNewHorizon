import pygame

from code.api.game_api_client import GameApiClient
from code.config import AUTH_API_URL
from code.managers.wild_pokemon_manager import WildPokemonManager
from code.utils.sprite_composer import compose_player_spritesheet
from code.core.controller import Controller
from code.core.keylistener import KeyListener
from code.core.screen import Screen
from code.entities.player import Player
from code.entities.remote_player import RemotePlayer
from code.managers.save import Save
from code.managers.sound_manager import SoundManager
from code.network.client import NetworkClient
from code.ui.dialogue import Dialogue
from code.ui.character_creation_menu import CharacterCreationMenu
from code.ui.login_menu import LoginMenu
from code.ui.option import Option
from code.ui.server_select_menu import ServerSelectMenu
from code.ui.splash_screen import SplashScreen
from code.world.map import Map


class Game:
    def __init__(self) -> None:
        self.running: bool = True
        self.screen: Screen = Screen()

        # 1. On prépare l'état initial
        self.state = "SPLASH"
        self.splash = SplashScreen(self.screen)

        # --- CHARGEMENT DÈS ELEMENTS ---
        print("Chargement des SFX !")
        SoundManager.load_all_sounds()
        # -----------------------------------------

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
        self.mouse_click: tuple[int, int] | None = None
        self.api_client:            GameApiClient      | None = None
        self._cached_character:     dict               | None = None
        self.wild_pokemon_manager:  WildPokemonManager | None = None
        self._saving_started:       bool                      = False

    def _setup_game_world(self):
        """ Cette méthode initialise tout le monde de jeu une fois connecté """
        self.account = self.account_data["account"]
        server_host = self.selected_server["host"]
        server_port = self.selected_server["port"]
        self.server_url = f"ws://{server_host}:{server_port}"

        # ── account_id (api_client déjà créé dans run() après le login) ──
        account_id = self.account.get("id")
        if not account_id:
            print("[Game] ATTENTION: account_id introuvable dans account.")
        else:
            print(f"[Game] GameApiClient actif (account_id={account_id})")

        # ── Monde ──────────────────────────────────────────────────────
        self.map = Map(self.screen, self.controller)
        self.player = Player(self.screen, self.controller, 512, 288, self.keylistener)
        self.player.name = self.account["username"]

        # ── Customisation du personnage (cheveux, couleurs…) ───────────
        # Réutilise le résultat mis en cache lors du LOGIN (évite un 2e appel API).
        # Après CHARACTER_CREATION, _cached_character est None — on recharge alors.
        if self.api_client and account_id:
            character_data = self._cached_character or self.api_client.get_character(int(account_id))
            self._cached_character = None   # libère la référence
            if character_data:
                customization = character_data.get("character", {})
                composed = compose_player_spritesheet(customization)
                self.player.reload_spritesheet(composed)

        # ── Inventaire : wire API client AVANT save.load() ────────────
        if self.api_client and account_id:
            self.player.inv.api_client = self.api_client
            self.player.inv.account_id = int(account_id)

        self.dialogue = Dialogue(self.player, self.screen)
        self.save = Save("save_0", self.map, self.player, self.keylistener, self.dialogue)
        self.save.load()          # charge la sauvegarde locale (position, map…)
        self._ensure_map_ready()

        # ── Charge l'inventaire depuis l'API (priorité sur sauvegarde locale) ──
        self.player.inv.load_from_api()

        self.option = Option(self.screen, self.controller, self.map, "fr", self.save, self.keylistener, self.dialogue)
        self.network = NetworkClient(self.server_url)
        self.remote_players = {}

        self.wild_pokemon_manager = WildPokemonManager(self.map)

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
                    token = self.account_data.get("token", "")
                    account_id = self.account_data.get("account", {}).get("id")
                    if token and account_id:
                        self.api_client = GameApiClient(AUTH_API_URL, token)
                        self._cached_character = self.api_client.get_character(int(account_id))
                        if self._cached_character is None:
                            self.state = "CHARACTER_CREATION"
                        else:
                            self.state = "SERVER_SELECT"
                    else:
                        self.state = "SERVER_SELECT"
                else:
                    self.running = False

            elif self.state == "CHARACTER_CREATION":
                account_id = self.account_data.get("account", {}).get("id")
                creation_menu = CharacterCreationMenu(self.screen, self.api_client, int(account_id))
                success = creation_menu.run()
                if success:
                    self.state = "SERVER_SELECT"
                else:
                    self.running = False

            elif self.state == "SERVER_SELECT":
                server_menu = ServerSelectMenu(self.screen, AUTH_API_URL)
                self.selected_server = server_menu.run()
                if self.selected_server:
                    # Coupe la musique
                    pygame.mixer.music.fadeout(1000)
                    self._setup_game_world()  # On crée le monde ici !
                    self.state = "PLAYING"
                else:
                    self.running = False

            elif self.state == "PLAYING":
                # TOUTE la logique de jeu va ici (mouvements, map, réseau)
                self.update_playing_logic()

            elif self.state == "SAVING":
                # 1re frame : dessine l'écran, pygame.display.flip() immédiat
                # 2e appel  : bloque sur les saves réseau, puis quitte
                if not self._saving_started:
                    self._draw_saving_screen()
                    pygame.display.flip()
                    self._saving_started = True
                else:
                    self._perform_save_and_quit()

            self.screen.update()

    # ------------------------------------------------------------------
    # Saving screen + graceful quit
    # ------------------------------------------------------------------

    def _draw_saving_screen(self) -> None:
        disp = self.screen.get_display()
        W, H = self.screen.get_size()

        # Fond semi-transparent sur le dernier frame de jeu
        disp.blit(self.screen.image_screen(), (0, 0))
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        disp.blit(overlay, (0, 0))

        try:
            font_big   = pygame.font.SysFont("segoeui", 32, bold=True)
            font_small = pygame.font.SysFont("segoeui", 18)
        except Exception:
            font_big = font_small = pygame.font.Font(None, 30)

        t1 = font_big.render("Sauvegarde en cours…", True, (220, 235, 248))
        t2 = font_small.render("Envoi des données au serveur. Veuillez patienter.", True, (130, 160, 190))

        disp.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 24)))
        disp.blit(t2, t2.get_rect(center=(W // 2, H // 2 + 20)))

    def _perform_save_and_quit(self) -> None:
        print("[Game] Sauvegarde avant fermeture...")
        if self.save:
            self.save.save()
            print("[Game] Sauvegarde locale : OK")
        if self.player:
            ok = self.player.inv.save_all()
            if not ok:
                print("[Game] ATTENTION: sauvegarde API échouée — données locales préservées.")
        print("[Game] Fermeture du jeu.")
        self.running = False
        pygame.quit()

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
        zones = [
            {"name": z.name, "x": z.rect.x, "y": z.rect.y,
             "w": z.rect.width, "h": z.rect.height,
             "max_pokemon": z.max_pokemon}
            for z in (self.map.spawn_zones or [])
        ]
        self.network.send({
            "type":        "join",
            "map":         map_name,
            "x":           int(self.player.position.x),
            "y":           int(self.player.position.y),
            "dir":         self.player.direction,
            "sprite":      "character",
            "name":        self.player.name,
            "spawn_zones": zones,
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

        elif t == "pokemon_snapshot":
            if self.wild_pokemon_manager:
                self.wild_pokemon_manager.on_snapshot(msg.get("pokemons", []))

        elif t == "pokemon_spawned":
            if self.wild_pokemon_manager:
                self.wild_pokemon_manager.on_spawned(msg)

        elif t == "pokemon_moved":
            if self.wild_pokemon_manager:
                self.wild_pokemon_manager.on_moved(msg)

        elif t == "pokemon_despawned":
            if self.wild_pokemon_manager:
                self.wild_pokemon_manager.on_despawned(msg)

        elif t == "pokemon_encounter_start":
            # TODO: démarrer le système de combat avec ces données
            print(
                f"[Encounter] Pokémon #{msg['pokemon_id']} "
                f"nv.{msg['level']}"
                + (" ✨ Shiny !" if msg.get("shiny") else "")
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
                if self.state == "PLAYING":
                    # Déclenche la séquence de sauvegarde avant de quitter
                    self.state = "SAVING"
                    self._saving_started = False
                else:
                    self.running = False
                    pygame.quit()

            elif event.type == pygame.KEYDOWN:
                self.keylistener.add_key(event.key)

            elif event.type == pygame.KEYUP:
                self.keylistener.remove_key(event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_click = event.pos

    def _find_facing_pokemon(self):
        """
        Retourne (direction, wpid) si le joueur appuie vers une tuile avec un Pokémon.
        Comparaison par indice de tuile — aucune hitbox impliquée.
        """
        TILE = 16
        ctrl = self.controller
        keys = self.keylistener
        px   = int(self.player.position.x) // TILE
        py   = int(self.player.position.y) // TILE

        for direction, (dx, dy) in [("left",  (-1, 0)), ("right", (1, 0)),
                                     ("up",    (0, -1)), ("down",  (0, 1))]:
            if keys.key_pressed(ctrl.get_key(direction)):
                result = self.wild_pokemon_manager.get_pokemon_at_tile(px + dx, py + dy)
                return (direction, result[0]) if result else None
        return None

    def update_playing_logic(self) -> None:
        # 1. Sauvegarder l'état précédent (pour le réseau)
        prev_walking = self.player.animation_walk
        prev_pos = (int(self.player.position.x), int(self.player.position.y))
        prev_map = self.map.current_map.name if self.map.current_map else None

        # 2. Gérer le mouvement et les menus
        if not self.player.menu_option:
            # ── Pokémon sauvages : bloquer + encounter au contact ─────────
            encounter_wpid = None
            if self.wild_pokemon_manager and not self.player.animation_walk and self.player.can_move:
                facing = self._find_facing_pokemon()
                if facing:
                    direction, encounter_wpid = facing
                    self.player.direction = direction   # faire face au Pokémon
                    self.player.can_move  = False       # bloquer le mouvement ce frame

            self.map.update()

            if encounter_wpid:
                self.player.can_move = True
                current_map = self.map.current_map.name if self.map.current_map else ""
                self.wild_pokemon_manager.on_despawned({"wpid": encounter_wpid})
                self.network.send({"type": "pokemon_encounter", "wpid": encounter_wpid, "map": current_map})

            # Touche interaction
            if pygame.K_e in self.keylistener.keys and not self.dialogue.active:
                self.dialogue.load_data(1001, 0)
                self.keylistener.remove_key(pygame.K_e)
            self.dialogue_controller()
            self.mouse_click = None
        else:
            self.option.update(self.mouse_click)
            self.mouse_click = None
            self.dialogue_controller()
            self.option.check_inputs()

        # 3. Gérer le réseau
        self._handle_network(prev_walking, prev_pos, prev_map)