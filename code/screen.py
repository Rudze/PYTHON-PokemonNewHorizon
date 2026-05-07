import pygame


class Screen:
    """
    Screen class to manage the screen
    """
    def __init__(self) -> None:
        self.width = 1280
        self.height = 720
        self.fullscreen = False

        # Initialisation du mode fenêtré par défaut
        self.display = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)

        pygame.display.set_caption("Pokémon")
        pygame.display.set_icon(pygame.image.load("../assets/app/logo_projet_pokemon.png"))

        self.imagescreen: pygame.Surface = pygame.display.get_surface()
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.framerate: int = 60
        self.deltatime: float = 0.0

    def update(self) -> None:
        """
        Update the screen
        :return:
        """
        pygame.display.flip()
        pygame.display.update()
        self.clock.tick(self.framerate)
        self.imagescreen = self.display.copy()
        self.display.fill((0, 0, 0))
        self.deltatime = self.clock.get_time()

    def get_delta_time(self) -> float:
        """
        Get the delta time
        :return:
        """
        return self.deltatime

    def get_size(self) -> tuple[int, int]:
        """
        Get the size of the screen
        :return:
        """
        return self.display.get_size()

    def get_display(self) -> pygame.display:
        """
        Get the display
        :return:
        """
        return self.display

    def image_screen(self):
        """
        Get the image screen
        :return:
        """
        return self.imagescreen

    # Bascule entre plein écran et fenêtré
    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen

        if self.fullscreen:
            # On passe en plein écran (SCALED aide à garder le ratio)
            self.display = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN | pygame.SCALED)
        else:
            # On repasse en mode fenêtré
            self.display = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)