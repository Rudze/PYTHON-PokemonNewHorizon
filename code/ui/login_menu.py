import json

import pygame

from code.api.auth_client import AuthClient, AuthError
from code.config import LOGIN_MENU_SETTINGS, CREDENTIALS_FILE
from code.managers.sound_manager import SoundManager


class TextBox:
    def __init__(
        self,
        rect: pygame.Rect,
        placeholder: str,
        password: bool = False,
        max_length: int = 32,
    ) -> None:
        self.rect = rect
        self.placeholder = placeholder
        self.password = password
        self.max_length = max_length
        self.text = ""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)

        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                return
            else:
                if event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
                    self.text += event.unicode

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        bg_color = (15, 18, 26)
        border_color = (45, 145, 255) if self.active else (45, 50, 65)
        text_color = (245, 245, 245)
        placeholder_color = (125, 132, 150)

        pygame.draw.rect(surface, bg_color, self.rect, border_radius=5)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=5)

        if self.text:
            value = "*" * len(self.text) if self.password else self.text
            text_surface = font.render(value, True, text_color)
        else:
            text_surface = font.render(self.placeholder, True, placeholder_color)

        text_y = self.rect.centery - text_surface.get_height() // 2
        surface.blit(text_surface, (self.rect.x + 14, text_y))


class Checkbox:
    def __init__(self, x: int, y: int, size: int, label: str, checked: bool = False) -> None:
        self.rect = pygame.Rect(x, y, size, size)
        self.label = label
        self.checked = checked

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, (15, 18, 26), self.rect, border_radius=3)
        pygame.draw.rect(surface, (45, 145, 255), self.rect, 2, border_radius=3)
        if self.checked:
            pygame.draw.rect(surface, (45, 145, 255), self.rect.inflate(-6, -6), border_radius=2)
        label_surface = font.render(self.label, True, (200, 205, 220))
        surface.blit(label_surface, (self.rect.right + 10, self.rect.centery - label_surface.get_height() // 2))


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        color: tuple[int, int, int] = (25, 105, 220),
        hover_color: tuple[int, int, int] = (45, 145, 255),
        text_color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        self.rect = rect
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color

    def clicked(self, event: pygame.event.Event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        color = self.hover_color if hovered else self.color

        pygame.draw.rect(surface, color, self.rect, border_radius=5)

        text_surface = font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)


class LoginMenu:
    def __init__(self, screen, api_url: str) -> None:
        self.screen = screen
        self.display = screen.get_display()
        self.auth = AuthClient(api_url)

        self.clock = pygame.time.Clock()

        self.panel_color = (0, 0, 0)

        self.status_message = ""
        self.status_color = (255, 255, 255)

        self.music_muted = False

        self.background_image = self._load_background_image()

        self.login_panel_rect = pygame.Rect(0, 0, 0, 0)

        self.username_box: TextBox | None = None
        self.password_box: TextBox | None = None
        self.remember_checkbox: Checkbox | None = None
        self.login_button: Button | None = None
        self.register_button: Button | None = None
        self.music_button: Button | None = None

        self.title_font = self._load_font(50, bold=True)
        self.font = self._load_font(28)
        self.small_font = self._load_font(20)
        self.bottom_font = self._load_font(21)

        self._start_music()
        self._build_layout()
        self._load_saved_credentials()

    def _load_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        font_path = LOGIN_MENU_SETTINGS.get("font")

        try:
            font = pygame.font.Font(font_path, size)
        except Exception as error:
            print(f"Impossible de charger la police '{font_path}' : {error}")
            font = pygame.font.SysFont("arial", size, bold=bold)

        if bold:
            font.set_bold(True)

        return font

    def _start_music(self) -> None:
        if pygame.mixer.music.get_busy():
            return

        try:
            pygame.mixer.music.load(LOGIN_MENU_SETTINGS["music"])
            pygame.mixer.music.set_volume(LOGIN_MENU_SETTINGS["volume"])
            pygame.mixer.music.play(-1)
        except pygame.error as error:
            print(f"Impossible de charger la musique : {error}")

    def _load_background_image(self) -> pygame.Surface | None:
        image_path = LOGIN_MENU_SETTINGS.get("background_image")

        if not image_path:
            return None

        try:
            return pygame.image.load(image_path).convert()
        except pygame.error as error:
            print(f"Impossible de charger l'image du login menu : {error}")
            return None

    def _build_layout(self) -> None:
        width = self.display.get_width()
        height = self.display.get_height()

        panel_x = width // 2
        panel_w = width - panel_x

        self.login_panel_rect = pygame.Rect(panel_x, 0, panel_w, height)

        form_w = int(panel_w * 0.58)
        form_x = panel_x + (panel_w - form_w) // 2

        title_y = int(height * 0.18)
        input_y = title_y + 95

        self.username_box = TextBox(
            pygame.Rect(form_x, input_y, form_w, 56),
            "Pseudo",
            password=False,
            max_length=24,
        )

        self.password_box = TextBox(
            pygame.Rect(form_x, input_y + 76, form_w, 56),
            "Mot de passe",
            password=True,
            max_length=72,
        )

        checkbox_size = 22
        self.remember_checkbox = Checkbox(
            form_x,
            input_y + 146,
            checkbox_size,
            "Se souvenir de moi",
        )

        self.login_button = Button(
            pygame.Rect(form_x, input_y + 186, form_w, 56),
            "Connexion",
            color=(25, 105, 220),
            hover_color=(45, 145, 255),
        )

        self.register_button = Button(
            pygame.Rect(form_x, input_y + 298, form_w, 50),
            "Créer un compte",
            color=(10, 35, 70),
            hover_color=(20, 80, 150),
        )

        music_button_w = 220
        music_button_h = 48
        music_button_margin = 20

        self.music_button = Button(
            pygame.Rect(
                width - music_button_w - music_button_margin,
                height - music_button_h - music_button_margin,
                music_button_w,
                music_button_h,
            ),
            "Musique : ON",
            color=(8, 16, 30),
            hover_color=(18, 60, 115),
            text_color=(220, 235, 255),
        )

        self.username_box.active = True

    def run(self) -> dict | None:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None

                if self.username_box:
                    self.username_box.handle_event(event)

                if self.password_box:
                    self.password_box.handle_event(event)

                if self.remember_checkbox:
                    self.remember_checkbox.handle_event(event)

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        self._switch_box()

                    elif event.key == pygame.K_RETURN:
                        SoundManager.play("click")
                        result = self._login()
                        if result is not None:
                            return result

                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return None

                if self.login_button and self.login_button.clicked(event):
                    SoundManager.play("click")
                    result = self._login()
                    if result is not None:
                        return result

                if self.register_button and self.register_button.clicked(event):
                    SoundManager.play("click")
                    result = self._register()
                    if result is not None:
                        return result

                if self.music_button and self.music_button.clicked(event):
                    SoundManager.play("click")
                    self._toggle_music()

            self._draw()
            self.screen.update()
            self.clock.tick(60)

    def _switch_box(self) -> None:
        if not self.username_box or not self.password_box:
            return

        if self.username_box.active:
            self.username_box.active = False
            self.password_box.active = True
        else:
            self.username_box.active = True
            self.password_box.active = False

    def _validate(self) -> bool:
        if not self.username_box or not self.password_box:
            return False

        username = self.username_box.text.strip()
        password = self.password_box.text

        if len(username) < 3:
            self.status_message = "Pseudo trop court."
            self.status_color = (255, 90, 90)
            return False

        if len(password) < 8:
            self.status_message = "Mot de passe trop court : minimum 8 caractères."
            self.status_color = (255, 90, 90)
            return False

        return True

    def _login(self) -> dict | None:
        if not self.username_box or not self.password_box:
            return None

        if not self._validate():
            return None

        self.status_message = "Connexion..."
        self.status_color = (220, 220, 220)
        self._draw()
        self.screen.update()

        try:
            result = self.auth.login(
                self.username_box.text.strip(),
                self.password_box.text,
            )
            if self.remember_checkbox and self.remember_checkbox.checked:
                self._save_credentials(self.username_box.text.strip(), self.password_box.text)
            else:
                self._delete_credentials()
            return result
        except AuthError as error:
            self.status_message = str(error)
            self.status_color = (255, 90, 90)
            return None

    def _register(self) -> dict | None:
        if not self.username_box or not self.password_box:
            return None

        if not self._validate():
            return None

        self.status_message = "Création du compte..."
        self.status_color = (220, 220, 220)
        self._draw()
        self.screen.update()

        try:
            return self.auth.register(
                self.username_box.text.strip(),
                self.password_box.text,
            )
        except AuthError as error:
            self.status_message = str(error)
            self.status_color = (255, 90, 90)
            return None

    def _load_saved_credentials(self) -> None:
        try:
            if CREDENTIALS_FILE.exists():
                with open(CREDENTIALS_FILE, "r") as f:
                    data = json.load(f)
                if self.username_box:
                    self.username_box.text = data.get("username", "")
                if self.password_box:
                    self.password_box.text = data.get("password", "")
                if self.remember_checkbox:
                    self.remember_checkbox.checked = True
        except Exception:
            pass

    def _save_credentials(self, username: str, password: str) -> None:
        try:
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump({"username": username, "password": password}, f)
        except Exception as exc:
            print(f"[Login] Impossible de sauvegarder les identifiants : {exc}")

    def _delete_credentials(self) -> None:
        try:
            if CREDENTIALS_FILE.exists():
                CREDENTIALS_FILE.unlink()
        except Exception:
            pass

    def _toggle_music(self) -> None:
        self.music_muted = not self.music_muted

        if self.music_muted:
            pygame.mixer.music.pause()

            if self.music_button:
                self.music_button.text = "Musique : OFF"
                self.music_button.color = (35, 20, 20)
                self.music_button.hover_color = (85, 35, 35)

        else:
            pygame.mixer.music.unpause()
            pygame.mixer.music.set_volume(LOGIN_MENU_SETTINGS["volume"])

            if self.music_button:
                self.music_button.text = "Musique : ON"
                self.music_button.color = (8, 16, 30)
                self.music_button.hover_color = (18, 60, 115)

    def _draw(self) -> None:
        self._draw_fullscreen_background()
        self._draw_panel_fade()
        self._draw_login_panel()
        self._draw_music_button()

    def _draw_fullscreen_background(self) -> None:
        """
        Dessine le background uniquement dans la zone visible à gauche.
        Comme ça, le centre de l'image est aligné avec le centre de la partie visible,
        et non avec le centre total de l'écran.
        """
        self.display.fill((0, 0, 0))

        if self.background_image is None:
            return

        visible_image_rect = pygame.Rect(
            0,
            0,
            self.login_panel_rect.x,
            self.display.get_height()
        )

        scaled = self._scale_cover(
            self.background_image,
            visible_image_rect.size,
        )

        self.display.blit(scaled, visible_image_rect.topleft)

    def _draw_login_panel(self) -> None:
        pygame.draw.rect(self.display, self.panel_color, self.login_panel_rect)

        title = self.title_font.render("Bienvenue", True, (255, 255, 255))
        title_rect = title.get_rect(
            center=(self.login_panel_rect.centerx, int(self.display.get_height() * 0.18))
        )
        self.display.blit(title, title_rect)

        subtitle = self.small_font.render(
            "Connecte-toi pour rejoindre Pokemon New Horizon",
            True,
            (180, 185, 200),
        )
        subtitle_rect = subtitle.get_rect(
            center=(self.login_panel_rect.centerx, int(self.display.get_height() * 0.23))
        )
        self.display.blit(subtitle, subtitle_rect)

        if self.username_box:
            self.username_box.draw(self.display, self.font)

        if self.password_box:
            self.password_box.draw(self.display, self.font)

        if self.remember_checkbox:
            self.remember_checkbox.draw(self.display, self.small_font)

        if self.login_button:
            self.login_button.draw(self.display, self.font)

        if self.register_button:
            info_text = self.bottom_font.render(
                "Pas encore de compte ?",
                True,
                (190, 195, 210),
            )
            info_rect = info_text.get_rect(
                center=(self.login_panel_rect.centerx, self.register_button.rect.y - 18)
            )
            self.display.blit(info_text, info_rect)

            self.register_button.draw(self.display, self.font)

        if self.status_message:
            status = self.small_font.render(self.status_message, True, self.status_color)
            status_rect = status.get_rect(
                center=(self.login_panel_rect.centerx, self.display.get_height() - 55)
            )
            self.display.blit(status, status_rect)

    def _draw_music_button(self) -> None:
        if self.music_button:
            self.music_button.draw(self.display, self.small_font)

    def _draw_panel_fade(self) -> None:
        fade_width = 220
        screen_height = self.display.get_height()

        fade_x = self.login_panel_rect.x - fade_width

        if fade_x < 0:
            fade_x = 0

        fade_surface = pygame.Surface((fade_width, screen_height), pygame.SRCALPHA)

        for x in range(fade_width):
            t = x / max(1, fade_width - 1)

            # Smoothstep : fade plus doux qu'un dégradé linéaire.
            smooth_t = t * t * (3 - 2 * t)
            alpha = int(255 * smooth_t)

            pygame.draw.line(
                fade_surface,
                (0, 0, 0, alpha),
                (x, 0),
                (x, screen_height),
            )

        self.display.blit(fade_surface, (fade_x, 0))

    @staticmethod
    def _scale_cover(
        image: pygame.Surface,
        target_size: tuple[int, int],
    ) -> pygame.Surface:
        target_w, target_h = target_size
        image_w, image_h = image.get_size()

        scale = max(target_w / image_w, target_h / image_h)

        new_w = int(image_w * scale)
        new_h = int(image_h * scale)

        scaled = pygame.transform.smoothscale(image, (new_w, new_h))

        crop_x = max(0, new_w // 2 - target_w // 2)
        crop_y = max(0, new_h // 2 - target_h // 2)

        return scaled.subsurface(
            pygame.Rect(crop_x, crop_y, target_w, target_h)
        ).copy()