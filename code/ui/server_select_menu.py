import pygame

from code.api.auth_client import AuthClient, AuthError


class ServerSelectMenu:
    def __init__(self, screen, api_url: str) -> None:
        self.screen = screen
        self.display = screen.get_display()
        self.auth = AuthClient(api_url)

        self.clock = pygame.time.Clock()

        self.title_font = pygame.font.SysFont("arial", 42, bold=True)
        self.font = pygame.font.SysFont("arial", 24)
        self.small_font = pygame.font.SysFont("arial", 18)

        self.servers: list[dict] = []
        self.status_message = ""
        self.status_color = (255, 255, 255)

        self._load_servers()

    def _load_servers(self) -> None:
        try:
            self.servers = self.auth.get_servers()
            if not self.servers:
                self.status_message = "Aucun serveur disponible."
                self.status_color = (255, 160, 80)
        except AuthError as error:
            self.status_message = str(error)
            self.status_color = (255, 90, 90)

    def run(self) -> dict | None:
        while True:
            server_rects = self._get_server_rects()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return None

                    if event.key == pygame.K_r:
                        self._load_servers()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for server, rect in server_rects:
                        if rect.collidepoint(event.pos):
                            if bool(server.get("online", False)):
                                return server
                            self.status_message = "Ce serveur est hors ligne."
                            self.status_color = (255, 90, 90)

            self._draw(server_rects)
            self.screen.update()
            self.clock.tick(60)

    def _get_server_rects(self) -> list[tuple[dict, pygame.Rect]]:
        rects = []

        width = self.display.get_width()
        start_y = 250
        rect_w = 520
        rect_h = 58
        gap = 14
        x = width // 2 - rect_w // 2

        for index, server in enumerate(self.servers):
            rect = pygame.Rect(x, start_y + index * (rect_h + gap), rect_w, rect_h)
            rects.append((server, rect))

        return rects

    def _draw(self, server_rects: list[tuple[dict, pygame.Rect]]) -> None:
        self.display.fill((12, 14, 24))

        title = self.title_font.render("Choix du serveur", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.display.get_width() // 2, 130))
        self.display.blit(title, title_rect)

        help_text = self.small_font.render("Clique sur un serveur. Appuie sur R pour rafraîchir.", True, (180, 180, 200))
        help_rect = help_text.get_rect(center=(self.display.get_width() // 2, 180))
        self.display.blit(help_text, help_rect)

        for server, rect in server_rects:
            online = bool(server.get("online", False))
            hovered = rect.collidepoint(pygame.mouse.get_pos())

            if online:
                color = (42, 105, 70) if not hovered else (55, 145, 90)
                status = "En ligne"
                status_color = (120, 255, 150)
            else:
                color = (80, 50, 50) if not hovered else (110, 60, 60)
                status = "Hors ligne"
                status_color = (255, 120, 120)

            pygame.draw.rect(self.display, color, rect, border_radius=10)
            pygame.draw.rect(self.display, (180, 180, 190), rect, 2, border_radius=10)

            name_surface = self.font.render(str(server.get("name", "Serveur")), True, (255, 255, 255))
            self.display.blit(name_surface, (rect.x + 18, rect.y + 15))

            status_surface = self.small_font.render(status, True, status_color)
            status_rect = status_surface.get_rect(midright=(rect.right - 18, rect.centery))
            self.display.blit(status_surface, status_rect)

        if self.status_message:
            status = self.small_font.render(self.status_message, True, self.status_color)
            status_rect = status.get_rect(center=(self.display.get_width() // 2, self.display.get_height() - 80))
            self.display.blit(status, status_rect)