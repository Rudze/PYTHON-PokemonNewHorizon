import logging
import threading
import time

import pygame

_log = logging.getLogger(__name__)

from code.client.network.api_client import GameApiClient
from code.client.config import AUTH_API_URL
from code.client.managers.interaction_manager import Interaction, InteractionManager
from code.client.managers.wild_pokemon_manager import WildPokemonManager
from code.client.utils.sprite_composer import compose_player_spritesheet
from code.client.core.controller import Controller
from code.client.core.keylistener import KeyListener
from code.client.core.screen import Screen
from code.client.entities.player import Player
from code.shared.models.pokemon import Pokemon
from code.client.entities.remote_player import RemotePlayer
from code.server.managers.save_manager import Save
from code.client.managers.sound_manager import SoundManager
from code.client.network.client import NetworkClient
from code.client.ui.battle_screen import BattleScreen
from code.client.ui.components.text_box import TextBox
from code.client.ui.dialogue import Dialogue
from code.client.ui.character_creation_menu import CharacterCreationMenu
from code.client.ui.login_menu import LoginMenu
from code.client.ui.inventory_hud import InventoryHUD
from code.client.ui.motismart import Motismart
from code.client.ui.escape_menu import EscapeMenu
from code.client.ui.move_learn_menu import MoveLearnMenu
from code.client.ui.server_select_menu import ServerSelectMenu
from code.client.ui.splash_screen import SplashScreen
from code.client.world.map import Map


class Game:
    def __init__(self) -> None:
        self.running: bool = True
        self.screen: Screen = Screen()

        # 1. On prépare l'état initial
        self.state = "SPLASH"
        self.splash = SplashScreen(self.screen)

        # --- CHARGEMENT DÈS ELEMENTS ---
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
        self.battle_screen:         BattleScreen       | None = None
        self._battle_wpid:        str  | None = None
        self._battle_entity                 = None
        self._pending_battle_data: dict | None = None  # données en attente de pokemon_encounter_start
        self._saving_started:      bool         = False
        self._notify_box:          TextBox | None = None
        self._inv_pending_refresh: bool         = False
        self._inv_last_reload:    float        = 0.0
        self._move_learn_menu: MoveLearnMenu  | None = None
        self._pending_move_for_menu: tuple    | None = None

    def _setup_game_world(self):
        """ Cette méthode initialise tout le monde de jeu une fois connecté """
        self.account = self.account_data["account"]
        server_host = self.selected_server["host"]
        server_port = self.selected_server["port"]
        self.server_url = f"ws://{server_host}:{server_port}"

        # ── account_id (api_client déjà créé dans run() après le login) ──
        account_id = self.account.get("id")
        if not account_id:
            _log.warning("account_id introuvable dans account — mode hors-ligne.")
        else:
            _log.info("GameApiClient actif (account_id=%s)", account_id)

        # ── Monde ──────────────────────────────────────────────────────
        self.map = Map(self.screen, self.controller)
        self.player = Player(self.screen, self.controller, 512, 288, self.keylistener)
        self.player.name = self.account["username"]

        # ── Customisation du personnage (cheveux, couleurs…) ───────────
        # Réutilise le résultat mis en cache lors du LOGIN (évite un 2e appel API).
        # Après CHARACTER_CREATION, _cached_character est None — on recharge alors.
        self._player_customization: dict = {}
        if self.api_client and account_id:
            character_data = self._cached_character or self.api_client.get_character(int(account_id))
            self._cached_character = None   # libère la référence
            if character_data:
                self._player_customization = character_data.get("character", {})
                composed = compose_player_spritesheet(self._player_customization)
                self.player.reload_spritesheet(composed)

        # ── Inventaire : wire API client AVANT save.load() ────────────
        if self.api_client and account_id:
            self.player.inv.api_client = self.api_client
            self.player.inv.account_id = int(account_id)

        self.dialogue = Dialogue(self.player, self.screen)
        self.save = Save("save_0", self.map, self.player)
        self.save.load()          # charge la sauvegarde locale (position, map…)
        self._ensure_map_ready()

        # ── Charge l'inventaire et les Pokédollars depuis l'API ──
        self.player.inv.load_from_api()
        self.player.inv.load_money_from_api()
        self._inv_last_reload = time.time()   # démarre le TTL du cache inventaire

        self.option       = Motismart(self.screen, self.controller, self.keylistener, self.save, self.player)
        self.escape_menu  = EscapeMenu(self.screen, self.controller, self.keylistener)
        self.inv_hud      = InventoryHUD(self.screen)
        self.inv_hud.on_slot_swap = lambda a, b: self.player.inv.swap_hud_slots(a, b)
        self.network = NetworkClient(self.server_url)
        self.remote_players = {}

        self.wild_pokemon_manager  = WildPokemonManager(self.map)
        self.interaction_manager   = InteractionManager()
        self.interaction_manager.register(self.wild_pokemon_manager.get_interaction_source())

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
    # Helpers
    # ------------------------------------------------------------------

    _INV_RELOAD_TTL = 60.0  # secondes entre deux rechargements API

    def _open_inv_hud(self) -> None:
        """
        Ouvre le HUD inventaire sans lag.
        Le cache local est toujours à jour (syncs en arrière-plan).
        Recharge depuis l'API au maximum toutes les 60 s pour éviter la race
        condition entre le thread de swap et le thread de reload.
        """
        self.inv_hud.load_from_inventory(self.player.inv.bag)
        self.inv_hud.toggle()

        ttl_ok   = time.time() - self._inv_last_reload < self._INV_RELOAD_TTL
        syncing  = self.player.inv._pending_syncs > 0
        if ttl_ok or syncing:
            return   # données locales à jour, ou sync en cours → ne pas écraser

        def _refresh() -> None:
            if self.player.inv.reload_from_api():
                self.player.inv.auto_assign_slots()
                self._inv_pending_refresh = True

        threading.Thread(target=_refresh, daemon=True).start()
        self._inv_last_reload = time.time()

    def _player_screen_pos(self) -> tuple[int, int]:
        W, H = self.screen.get_size()
        try:
            vr   = self.map.map_layer.view_rect
            zoom = self.map.map_layer.zoom
            cx = int((self.player.position.x - vr.left) * zoom)
            cy = int((self.player.position.y - vr.top)  * zoom)
            return cx, cy
        except Exception:
            return W // 2, H // 2

    # ------------------------------------------------------------------
    # Saving screen + graceful quit
    # ------------------------------------------------------------------

    def _open_dialogue(self, messages: list[str],
                        rect: pygame.Rect | None = None) -> None:
        """
        Ouvre une boîte de dialogue en jeu.
        Utilise TextBox + fond overlay_message.png scalé au rect.
        Bloque le mouvement du joueur jusqu'à confirmation (E ou clic).

        rect : None → fenêtre standard en bas de l'écran (overworld)
               pygame.Rect → taille/position personnalisées (ex. combat)
        """
        from code.client.config import BATTLE_UI
        W, H = self.screen.get_size()
        if rect is None:
            bw = int(W * 0.68)
            bh = int(H * 0.20)
            rect = pygame.Rect((W - bw) // 2, H - bh - 16, bw, bh)

        try:
            bg = pygame.transform.scale(
                pygame.image.load(str(BATTLE_UI["overlay_message"])).convert_alpha(),
                (rect.width, rect.height),
            )
        except Exception:
            bg = None

        self._notify_box = TextBox(rect, bg_surf=bg, text_color=(255, 255, 255))
        self._notify_box.set_messages(messages)
        if self.player:
            self.player.can_move = False

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
        if self.save:
            self.save.save()
        if self.player:
            ok = self.player.inv.save_all()
            if not ok:
                _log.warning("Sauvegarde API échouée — données locales préservées.")
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

        _log.info("Map ready — %s pos=%s collisions=%d",
                  self.map.current_map.name if self.map.current_map else "?",
                  self.player.position, len(self.player.collisions))

    # ------------------------------------------------------------------
    # Network integration
    # ------------------------------------------------------------------

    def _handle_network(
        self,
        prev_walking:  bool,
        prev_pos:      tuple[int, int],
        prev_map:      str | None,
        prev_dir:      str,
    ) -> None:
        current_map = self.map.current_map.name if self.map.current_map else None

        if not self.network.connected and self._server_map is not None:
            self._server_map = None
            self._clear_remote_players()

        if current_map and current_map != self._server_map and self.network.connected:
            self._clear_remote_players()
            self._send_join(current_map)
            self._server_map = current_map

        if not self.network.connected or not current_map:
            for msg in self.network.poll():
                self._dispatch(msg)
            return

        walk_started = self.player.animation_walk and not prev_walking
        turned       = (not self.player.animation_walk and not prev_walking
                        and self.player.direction != prev_dir)

        if walk_started:
            offsets = {"left": (-16, 0), "right": (16, 0), "up": (0, -16), "down": (0, 16)}
            dx, dy  = offsets.get(self.player.direction, (0, 0))
            self.network.send({
                "type": "move",
                "map":  current_map,
                "x":    prev_pos[0] + dx,
                "y":    prev_pos[1] + dy,
                "dir":  self.player.direction,
            })
        elif turned:
            self.network.send({"type": "turn", "dir": self.player.direction})

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
            "type":          "join",
            "map":           map_name,
            "x":             int(self.player.position.x),
            "y":             int(self.player.position.y),
            "dir":           self.player.direction,
            "sprite":        "character",
            "name":          self.player.name,
            "spawn_zones":   zones,
            "customization": self._player_customization,
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
            pid = msg.get("pid")
            if pid:
                self._remove_remote_player(pid)

        elif t == "player_moved":
            pid = msg.get("pid")
            if pid and pid in self.remote_players:
                try:
                    self.remote_players[pid].apply_move(
                        int(msg["x"]), int(msg["y"]), msg["dir"]
                    )
                except (KeyError, ValueError):
                    pass

        elif t == "player_turned":
            pid = msg.get("pid")
            if pid and pid in self.remote_players:
                self.remote_players[pid].direction = msg.get("dir", "down")

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
            self._on_encounter_confirmed(msg)

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

        customization = data.get("customization")
        if customization:
            composed = compose_player_spritesheet(customization)
            rp.reload_spritesheet(composed)

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

    def _handle_interaction(self) -> None:
        """
        Appelé quand le joueur appuie sur E.
        Interroge l'InteractionManager et dispatche selon le type.
        Ajouter ici les nouveaux types au fur et à mesure.
        """
        result = self.interaction_manager.check(
            self.player.position,
            self.player.direction,
        )
        if result is None:
            return

        if result.kind == "battle":
            self._start_wild_battle(result.data)

        elif result.kind == "dialogue":
            # TODO: lancer le dialogue avec result.data["id"]
            pass

    def _start_wild_battle(self, data: dict) -> None:
        """Demande au serveur de confirmer le combat après vérification locale."""
        # Check HP local AVANT tout envoi réseau — évite le despawn serveur inutile
        able = [p for p in self.player.pokemons if p.hp > 0]
        if not able:
            self._open_dialogue(["Aucun Pokémon en état de combattre !"])
            return  # n'envoie rien au serveur → le Pokémon sauvage reste

        wpid        = data["wpid"]
        current_map = self.map.current_map.name if self.map.current_map else ""

        self._battle_entity       = self.wild_pokemon_manager.get_entity(wpid)
        self._battle_wpid         = wpid
        self._pending_battle_data = data
        if self._battle_entity:
            self._battle_entity.frozen = True

        self.network.send({
            "type": "pokemon_encounter",
            "wpid": wpid,
            "map":  current_map,
        })

    def _on_encounter_confirmed(self, msg: dict) -> None:
        """Appelé quand le serveur confirme le combat (pokemon_encounter_start)."""
        data = self._pending_battle_data
        self._pending_battle_data = None
        if not data:
            return

        try:
            wild_pokemon = Pokemon.create_from_id(msg["pokemon_id"], msg["level"])
        except Exception as e:
            _log.error("Impossible de créer le Pokémon sauvage: %s", e)
            wild_pokemon = None

        able = [p for p in self.player.pokemons if p.hp > 0]
        self.battle_screen = BattleScreen(
            self.screen, data, able[0] if able else None,
            wild_pokemon=wild_pokemon, zone=data.get("zone_name", "")
        )
        self.player.can_move = False

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
        prev_walking = self.player.animation_walk
        prev_pos     = (int(self.player.position.x), int(self.player.position.y))
        prev_map     = self.map.current_map.name if self.map.current_map else None
        prev_dir     = self.player.direction

        # ── Menu Échap : prioritaire, s'ouvre sur pression Échap hors combat/menu ─
        quit_key = self.controller.get_key("quit")
        if (not self.player.menu_option
                and not self.escape_menu.active
                and not (self.battle_screen and self.battle_screen.active)
                and self.keylistener.key_pressed(quit_key)):
            self.keylistener.remove_key(quit_key)
            self.escape_menu.open()

        if self.escape_menu.active:
            self.player.can_move = False          # bloque les déplacements
            self.map.update()
            self.escape_menu.update(self.mouse_click)
            self.mouse_click = None
            if not self.escape_menu.active:       # vient de se fermer
                self.player.can_move = True
            if self.escape_menu.result == self.escape_menu.RESULT_QUIT:
                self.state = "SAVING"
                self._saving_started = False
            elif self.escape_menu.result == self.escape_menu.RESULT_DISCONNECT:
                self.state = "SAVING"
                self._saving_started = False
            self._handle_network(prev_walking, prev_pos, prev_map, prev_dir)
            return

        # ── Menu d'apprentissage d'attaque ──────────────────────────────────────
        if self._move_learn_menu:
            self.map.update()
            result = self._move_learn_menu.update(self.mouse_click)
            self.mouse_click = None
            if result is not None:
                self._move_learn_menu = None
                self.player.can_move  = True
            self._handle_network(prev_walking, prev_pos, prev_map, prev_dir)
            return

        # ── Dialogue in-world : prioritaire sur tout ─────────────────────────────
        if self._notify_box:
            self.map.update()                                      # rendu monde
            self._notify_box.update()
            self._notify_box.draw(self.screen.get_display())
            action_key = self.controller.get_key("action")
            if self.keylistener.key_pressed(action_key) or self.mouse_click:
                self._notify_box.action()
                if self.keylistener.key_pressed(action_key):
                    self.keylistener.remove_key(action_key)
                self.mouse_click = None
                if self._notify_box.done:
                    self._notify_box       = None
                    self.player.can_move   = True
            self._handle_network(prev_walking, prev_pos, prev_map, prev_dir)
            return  # tout le reste est bypassé pendant un dialogue

        # 2. La map tourne TOUJOURS (Pokephone et combat se dessinent par-dessus)
        in_battle = self.battle_screen and self.battle_screen.active

        if not self.player.menu_option:
            # Pokémon sauvages : bloquer le mouvement avant map.update()
            if (self.wild_pokemon_manager and not self.player.animation_walk
                    and self.player.can_move and not in_battle):
                facing = self._find_facing_pokemon()
                if facing:
                    direction, _ = facing
                    self.player.direction = direction
                    self.player.can_move  = False

        self.map.update()   # monde toujours actif (animations, Pokémon sauvages…)
        cx, cy = self._player_screen_pos()
        self.inv_hud.update(cx, cy,
                            money=self.player.inv.money,
                            party=self.player.pokemons)   # arc inventaire + colonne équipe

        if self.player.menu_option:
            # Pokephone par-dessus le monde en mouvement
            self.option.update(self.mouse_click)
            self.mouse_click = None
            self.option.check_inputs()

        elif in_battle:
            # Combat par-dessus le monde
            self.battle_screen.handle_input(
                self.keylistener,
                self.controller,
                mouse_pos   = pygame.mouse.get_pos(),
                mouse_click = self.mouse_click,
            )
            self.mouse_click = None
            self.battle_screen.update()
            self.battle_screen.draw(self.screen.get_display())
            if not self.battle_screen.active:
                _log.info("Combat terminé — synchronisation équipe")
                self.player.inv.sync_party()
                outcome    = self.battle_screen.outcome
                wild_poke  = self.battle_screen._manager.wild_pokemon if self.battle_screen._manager else None
                # Le Pokémon disparaît seulement s'il a perdu des PV
                # (si plein PV = fuite joueur sans dégâts, ou victoire sauvage)
                wild_took_damage = bool(
                    wild_poke and wild_poke.hp < wild_poke.maxhp
                )
                if outcome == "won" or wild_took_damage:
                    self.wild_pokemon_manager.on_despawned({"wpid": self._battle_wpid})
                elif self._battle_entity:
                    self._battle_entity.frozen = False  # reste sur la carte
                self._battle_wpid    = None
                self._battle_entity  = None
                self.battle_screen   = None
                self.player.can_move = True

        else:
            # Jeu normal : restaurer can_move uniquement si aucun menu bloquant n'est ouvert
            if (self.player and not self.player.can_move
                    and not self.player.animation_walk
                    and not self.inv_hud.active):
                self.player.can_move = True

            # Inventaire (R) — ouverture instantanée + refresh API en arrière-plan
            inv_key = self.controller.get_key("inventory")
            if self.keylistener.key_pressed(inv_key):
                self.keylistener.remove_key(inv_key)
                if not self.inv_hud.active:
                    self._open_inv_hud()
                    self.player.can_move = False
                else:
                    self.inv_hud.toggle()
                    self.player.can_move = True

            # Appliquer le résultat du refresh API si le thread a terminé
            if self._inv_pending_refresh:
                self._inv_pending_refresh = False
                if self.inv_hud.active:
                    self.inv_hud.load_from_inventory(self.player.inv.bag)

            # ── Nouvelles attaques apprises (notification simple) ─────────────
            if not self._notify_box:
                for pkmn in self.player.pokemons:
                    if pkmn.newly_learned:
                        sym   = pkmn.newly_learned.pop(0)
                        pname = pkmn.dbSymbol.replace("_", " ").capitalize()
                        mname = sym.replace("_", " ").capitalize()
                        self._open_dialogue([f"{pname} a appris {mname} !"])
                        break

            # ── Attaques en attente (4 attaques déjà → menu de remplacement) ─
            if not self._notify_box and not self._move_learn_menu:
                for pkmn in self.player.pokemons:
                    if pkmn.pending_moves:
                        sym  = pkmn.pending_moves.pop(0)
                        pname = pkmn.dbSymbol.replace("_", " ").capitalize()
                        mname = sym.replace("_", " ").capitalize()
                        self._open_dialogue(
                            [f"{pname} peut apprendre {mname} !",
                             f"Mais il connaît déjà 4 attaques.",
                             f"Voulez-vous remplacer une attaque ?"]
                        )
                        self._pending_move_for_menu = (pkmn, sym)
                        break

            # Ouvrir le menu de remplacement après confirmation du dialogue
            if (not self._notify_box
                    and not self._move_learn_menu
                    and hasattr(self, "_pending_move_for_menu")
                    and self._pending_move_for_menu):
                pkmn, sym = self._pending_move_for_menu
                self._pending_move_for_menu = None
                self._move_learn_menu = MoveLearnMenu(self.screen, pkmn, sym)
                self.player.can_move  = False

            action_key = self.controller.get_key("action")
            if (self.keylistener.key_pressed(action_key)
                    and not self.dialogue.active
                    and not self.player.animation_walk):
                self._handle_interaction()
                self.keylistener.remove_key(action_key)
            self.dialogue_controller()
            self.mouse_click = None

        # 3. Gérer le réseau
        self._handle_network(prev_walking, prev_pos, prev_map, prev_dir)