import pygame

from code.config import SPLASH_SETTINGS

class SplashScreen:
    def __init__(self, screen) -> None:
        self.screen = screen

        # Charger l'image originale
        self.image = pygame.image.load(SPLASH_SETTINGS["image_path"])

        # Récupérer la taille de la fenêtre (Screen)
        size = self.screen.get_size()

        # On redimensionne avec cette taille
        self.image = pygame.transform.smoothscale(self.image, size)

        # Surface noire pour le fondu
        self.fade_duration = SPLASH_SETTINGS["fade_duration"]
        self.fade_surface = pygame.Surface(self.screen.get_size())
        self.fade_surface.fill((0, 0, 0))
        self.fade_alpha = 0  # 0 = transparent, 255 = noir complet

        self.duration = SPLASH_SETTINGS["duration_ms"]
        self.start_time = pygame.time.get_ticks()
        self.is_finished = False

    def update(self):
        current_time = pygame.time.get_ticks()
        elapsed = current_time - self.start_time

        # Calcul du fondu à la fin
        # Si on arrive vers la fin de la durée totale
        time_left = self.duration - elapsed

        if time_left <= self.fade_duration:
            # On calcule l'alpha (de 0 à 255) basé sur le temps restant
            # Plus time_left est petit, plus l'alpha est grand
            self.fade_alpha = 255 - int((time_left / self.fade_duration) * 255)
            self.fade_alpha = max(0, min(255, self.fade_alpha))  # Sécurité entre 0 et 255

        if elapsed >= self.duration:
            self.is_finished = True


    def draw(self):
        # On dessine l'image sur l'écran
        self.screen.display.blit(self.image, (0, 0))

        # Dessiner le calque de fondu par-dessus
        if self.fade_alpha > 0:
            self.fade_surface.set_alpha(self.fade_alpha)
            self.screen.display.blit(self.fade_surface, (0, 0))