import pygame

from code.api.game_api_client import GameApiClient
from code.config import LOGIN_MENU_SETTINGS
from code.config import CUSTOMIZATION_SETTINGS
from code.managers.sound_manager import SoundManager
from code.ui.components.catalog_selector import CatalogSelector
from code.ui.components.character_preview import CharacterPreview

# Valeurs par défaut pour les éléments sans sélecteur actif
DEFAULT_CUSTOMIZATION = {
    "skin":    "default",
    "back":    "default",
    "bicycle": "default",
    "eyes":    "default",
    "face":    "default",
    "gloves":  "default",
    "hair":    "none",
    "legs":    "default",
    "shoes":   "default",
    "shirt":   "default",
}

PREVIEW_WIDTH  = 460
PREVIEW_HEIGHT = 200


class CharacterCreationMenu:
    def __init__(self, screen, api_client: GameApiClient, account_id: int) -> None:
        self.screen     = screen
        self.display    = screen.get_display()
        self.api_client = api_client
        self.account_id = account_id

        self.clock          = pygame.time.Clock()
        self.status_message = ""
        self.status_color   = (255, 255, 255)

        self.font_title = self._load_font(48, bold=True)
        self.font       = self._load_font(28)
        self.font_small = self._load_font(20)

        # ── Default gender ────────────────────────────────────────────
        self.gender = "male"

        self.gender_sprite = pygame.image.load(CUSTOMIZATION_SETTINGS["gender_icon"]).convert_alpha()

        self.gender_sprite = pygame.transform.scale(self.gender_sprite, (200, 100))

        self.img_gender_male = self.gender_sprite.subsurface((0, 0, 100, 100))
        self.img_gender_female = self.gender_sprite.subsurface((100, 0, 100, 100))

        self.btn_gender_male = pygame.Rect(0, 0, 0, 0)
        self.btn_gender_female = pygame.Rect(0, 0, 0, 0)

        # ── Sélecteurs de customisation ───────────────────────────────
        self.selectors: list[CatalogSelector] = [
            # CatalogSelector("peau", self.font_small),
             CatalogSelector("hair", self.font_small),
        ]

        self.preview = CharacterPreview(
            x=0, y=0,
            width=PREVIEW_WIDTH,
            height=PREVIEW_HEIGHT,
            customization=self._build_customization(),
        )

        # Initialisé à Rect vide pour que les clics avant le 1er _draw() ne plantent pas
        self.btn_create = pygame.Rect(0, 0, 0, 0)

    def _build_customization(self) -> dict:
        result = {**DEFAULT_CUSTOMIZATION}
        for selector in self.selectors:
            result.update(selector.get_customization())
        return result

    def _load_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        path = LOGIN_MENU_SETTINGS.get("font")
        try:
            f = pygame.font.Font(path, size)
        except Exception:
            f = pygame.font.SysFont("arial", size, bold=bold)
        if bold:
            f.set_bold(True)
        return f

    def run(self) -> bool:
        while True:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return False

                # CLICK MOUSE
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                    # Sélecteurs (hair etc.)
                    clicked_selector = False

                    for selector in self.selectors:
                        if selector.handle_click(event.pos, self.screen):
                            SoundManager.play("click")
                            self.preview.update_customization(self._build_customization())
                            clicked_selector = True
                            break

                    if not clicked_selector:

                        # Bouton create
                        if self.btn_create.collidepoint(event.pos):
                            SoundManager.play("click")
                            if self._create_character():
                                return True

                        # Gender buttons
                        if self.btn_gender_male.collidepoint(event.pos):
                            self.gender = "male"
                            SoundManager.play("click")

                        elif self.btn_gender_female.collidepoint(event.pos):
                            self.gender = "female"
                            SoundManager.play("click")

            self._draw()
            self.screen.update()
            self.clock.tick(60)

    def _create_character(self) -> bool:
        self.status_message = "Création en cours..."
        self.status_color   = (220, 220, 220)
        self._draw()
        self.screen.update()

        result = self.api_client.save_character(self.account_id, self._build_customization())
        if result is None:
            self.status_message = "Erreur lors de la création. Réessaie."
            self.status_color   = (255, 90, 90)
            return False

        return True

    def _draw(self) -> None:
        w, h = self.display.get_width(), self.display.get_height()
        self.display.fill((8, 10, 18))

        # Titre
        title_rect = pygame.Rect(w // 2 - 320 // 2, 60, 320, 58)
        title = self.font_title.render("Créer ton personnage", True, (255, 255, 255))
        self.display.blit(title, title.get_rect(center=title_rect.center))

        # ── Preview du personnage ──────────────────────────────────────────
        self.preview.rect.centerx = w // 2
        self.preview.rect.top     = title_rect.bottom + 30
        self.preview.draw(self.display)

        # ── Sélecteurs du genre ────────────────────────────────────────────

        mouse = pygame.mouse.get_pos()

        self.btn_gender_male = self.img_gender_male.get_rect(
            center=(w // 2 - 80, self.preview.rect.bottom + 60)
        )

        self.btn_gender_female = self.img_gender_female.get_rect(
            center=(w // 2 + 80, self.preview.rect.bottom + 60)
        )

        self.display.blit(self.img_gender_male, self.btn_gender_male)
        self.display.blit(self.img_gender_female, self.btn_gender_female)

        if self.gender == "male":
            pygame.draw.rect(self.display, (80, 160, 255), self.btn_gender_male, 3)

        if self.gender == "female":
            pygame.draw.rect(self.display, (255, 120, 180), self.btn_gender_female, 3)

        # hover
        if self.btn_gender_male.collidepoint(mouse):
            pygame.draw.rect(self.display, (255, 255, 255), self.btn_gender_male, 1)

        if self.btn_gender_female.collidepoint(mouse):
            pygame.draw.rect(self.display, (255, 255, 255), self.btn_gender_female, 1)

        # ── Sélecteurs empilés verticalement sous la preview ───────────────
        sel_y = self.preview.rect.bottom + 20
        for selector in self.selectors:
            selector.draw(self.display, w, sel_y)
            sel_y += CatalogSelector.ROW_H + 12

        # Bouton "Commencer l'aventure"
        self.btn_create = pygame.Rect(w // 2 - 320 // 2, h * 3 // 4, 320, 58)
        hovered = self.btn_create.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.display, (45, 145, 255) if hovered else (25, 105, 220), self.btn_create, border_radius=6)
        btn_play = self.font.render("Commencer l'aventure", True, (255, 255, 255))
        self.display.blit(btn_play, btn_play.get_rect(center=self.btn_create.center))

        if self.status_message:
            status = self.font_small.render(self.status_message, True, self.status_color)
            self.display.blit(status, status.get_rect(center=(w // 2, self.btn_create.bottom + 28)))
