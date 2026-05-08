import pygame

from sound_manager import SoundManager
from auth_client import AuthClient, AuthError
from config import LOGIN_MENU_SETTINGS


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
            elif event.key == pygame.K_RETURN:
                return
            elif event.key == pygame.K_TAB:
                return
            else:
                if event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
                    self.text += event.unicode

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        border_color = (90, 170, 255) if self.active else (160, 160, 170)

        pygame.draw.rect(surface, (25, 28, 38), self.rect, border_radius=8)
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=8)

        if self.text:
            value = "*" * len(self.text) if self.password else self.text
            text_surface = font.render(value, True, (255, 255, 255))
        else:
            text_surface = font.render(self.placeholder, True, (140, 140, 150))

        surface.blit(text_surface, (self.rect.x + 12, self.rect.y + 11))


class Button:
    def __init__(self, rect: pygame.Rect, text: str) -> None:
        self.rect = rect
        self.text = text

    def clicked(self, event: pygame.event.Event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        color = (70, 150, 255) if hovered else (45, 105, 210)

        pygame.draw.rect(surface, color, self.rect, border_radius=8)

        text_surface = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)


class LoginMenu:
    def __init__(self, screen, api_url: str) -> None:
        self.screen = screen
        self.display = screen.get_display()
        self.auth = AuthClient(api_url)

        # --- GESTION DU SON ---
        # On vérifie si la musique joue déjà pour ne pas la relancer en boucle
        if not pygame.mixer.music.get_busy():
            try:
                pygame.mixer.music.load(LOGIN_MENU_SETTINGS["music"])
                pygame.mixer.music.set_volume(LOGIN_MENU_SETTINGS["volume"])  # Volume à 50%
                pygame.mixer.music.play(-1)  # -1 signifie "boucle infinie"
            except pygame.error as e:
                print(f"Impossible de charger la musique : {e}")
        # ----------------------

        self.clock = pygame.time.Clock()

        self.title_font = pygame.font.SysFont("arial", 44, bold=True)
        self.font = pygame.font.SysFont("arial", 24)
        self.small_font = pygame.font.SysFont("arial", 18)

        width = self.display.get_width()
        height = self.display.get_height()

        box_w = 380
        box_h = 50
        x = width // 2 - box_w // 2

        self.username_box = TextBox(
            pygame.Rect(x, height // 2 - 90, box_w, box_h),
            "Pseudo",
            password=False,
            max_length=24,
        )

        self.password_box = TextBox(
            pygame.Rect(x, height // 2 - 25, box_w, box_h),
            "Mot de passe",
            password=True,
            max_length=72,
        )

        self.login_button = Button(
            pygame.Rect(x, height // 2 + 50, 180, 48),
            "Connexion",
        )

        self.register_button = Button(
            pygame.Rect(x + 200, height // 2 + 50, 180, 48),
            "Créer compte",
        )

        self.status_message = ""
        self.status_color = (255, 255, 255)

        self.username_box.active = True

    def run(self) -> dict | None:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None

                self.username_box.handle_event(event)
                self.password_box.handle_event(event)

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

                if self.login_button.clicked(event):
                    SoundManager.play("click")
                    result = self._login()
                    if result is not None:
                        return result

                if self.register_button.clicked(event):
                    SoundManager.play("click")
                    result = self._register()
                    if result is not None:
                        return result

            self._draw()
            self.screen.update()
            self.clock.tick(60)

    def _switch_box(self) -> None:
        if self.username_box.active:
            self.username_box.active = False
            self.password_box.active = True
        else:
            self.username_box.active = True
            self.password_box.active = False

    def _validate(self) -> bool:
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
        if not self._validate():
            return None

        try:
            return self.auth.login(
                self.username_box.text.strip(),
                self.password_box.text,
            )
        except AuthError as error:
            self.status_message = str(error)
            self.status_color = (255, 90, 90)
            return None

    def _register(self) -> dict | None:
        if not self._validate():
            return None

        try:
            return self.auth.register(
                self.username_box.text.strip(),
                self.password_box.text,
            )
        except AuthError as error:
            self.status_message = str(error)
            self.status_color = (255, 90, 90)
            return None

    def _draw(self) -> None:
        self.display.fill((12, 14, 24))

        title = self.title_font.render("Pokemon New Horizon", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.display.get_width() // 2, 130))
        self.display.blit(title, title_rect)

        subtitle = self.font.render("Connexion au compte", True, (190, 190, 210))
        subtitle_rect = subtitle.get_rect(center=(self.display.get_width() // 2, 185))
        self.display.blit(subtitle, subtitle_rect)

        self.username_box.draw(self.display, self.font)
        self.password_box.draw(self.display, self.font)

        self.login_button.draw(self.display, self.font)
        self.register_button.draw(self.display, self.font)

        if self.status_message:
            status = self.small_font.render(self.status_message, True, self.status_color)
            status_rect = status.get_rect(center=(self.display.get_width() // 2, self.display.get_height() // 2 + 135))
            self.display.blit(status, status_rect)