"""
CharacterPreview — composant UI réutilisable pour afficher un aperçu du personnage.

POURQUOI CE FICHIER EXISTE SEUL ?
  Le principe de "responsabilité unique" : chaque fichier fait UNE chose.
  CharacterPreview ne sait rien du menu qui l'utilise. Le menu ne sait rien
  des sprites. Chacun fait son travail, et on peut réutiliser ce composant
  dans n'importe quel menu sans copier-coller de code.

COMMENT L'UTILISER :
  1. Créer une instance dans le __init__ du menu :
         self.preview = CharacterPreview(x, y, width, height, customization)

  2. Appeler draw() dans la boucle de rendu :
         self.preview.draw(self.display)

  3. Mettre à jour la customisation (avec couleur optionnelle) :
         self.preview.update_customization({
             "hair":       "hood_basic",
             "hair_color": (220, 50, 50),    # rouge
             "shirt":      "basic_shirt",
             "shirt_color": (30, 100, 220),  # bleu
         })

SYSTÈME DE TINTING (coloration dynamique)
  Les éléments marqués colorable=True dans CUSTOMIZATION_CATALOG sont
  automatiquement teintés si une clé "<element>_color" est présente dans
  le dict de customisation. Sinon, la couleur par défaut du catalogue est utilisée.

  Le catalogue (config.CUSTOMIZATION_CATALOG) est la source de vérité :
  c'est là qu'on définit si un élément accepte la recoloration ou non.

STRUCTURE DES ASSETS :
  Sprite de base : assets/sprite/character/character_walk.png
  Calques       : assets/sprite/<dossier_du_calque>/<variant>_topdown.png
  (les dossiers sont définis dans CUSTOMIZATION_CATALOG)

  Chaque spritesheet topdown est une grille 4×4 :
      - 4 colonnes = 4 frames d'animation (0 = idle, 1-3 = marche)
      - 4 lignes   = 4 directions (bas, gauche, droite, haut)
"""

from __future__ import annotations

import pygame

from code.config import SPRITES_CHARACTER_DIR, CUSTOMIZATION_CATALOG
from code.utils.tool import Tool
from code.utils.sprite_tint import tint_surface, clear_tint_cache


class CharacterPreview:
    """
    Affiche 3 vues du personnage côte à côte (face, profil, dos)
    en superposant le sprite de base et les calques définis dans CUSTOMIZATION_CATALOG.

    SCALABILITÉ — pour ajouter un nouveau type de calque (vêtements, chapeaux…) :
      1. Ajouter une entrée dans config.CUSTOMIZATION_CATALOG
      2. Créer le dossier et les assets correspondants
      C'est tout. Ce composant se met à jour automatiquement.
    """

    # ---------------------------------------------------------------
    # OVERLAY_ORDER — ordre de dessin calculé depuis le catalogue
    #
    # Trié par "overlay_order" croissant :
    #   0 = dessiné en premier (sous tout le reste, ex: skin)
    #   8 = dessiné en dernier (par-dessus tout, ex: back)
    #
    # Calculé ici (variable de classe) = une seule fois au chargement
    # du module, pas à chaque création d'instance CharacterPreview.
    # ---------------------------------------------------------------
    OVERLAY_ORDER: list[str] = sorted(
        CUSTOMIZATION_CATALOG.keys(),
        key=lambda k: CUSTOMIZATION_CATALOG[k]["overlay_order"],
    )

    # ---------------------------------------------------------------
    # Ligne du spritesheet selon la direction
    # Le spritesheet est organisé en 4 lignes : bas, gauche, droite, haut
    # ---------------------------------------------------------------
    DIRECTION_ROW = {
        "down":  0,   # personnage de face
        "left":  1,   # personnage de profil gauche
        "right": 2,   # personnage de profil droit
        "up":    3,   # personnage de dos
    }

    # Les 3 vues affichées : (direction, libellé)
    VIEWS = [
        ("down",  "FACE"),
        ("right", "PROFIL"),
        ("up",    "DOS"),
    ]

    # ---------------------------------------------------------------
    # Palette de couleurs (modifier ici pour changer le thème)
    # ---------------------------------------------------------------
    COLOR_BG             = (20,  22,  34)    # fond du composant
    COLOR_BORDER         = (60,  80,  140)   # contour bleu
    COLOR_LABEL          = (160, 180, 220)   # texte FACE / PROFIL / DOS
    COLOR_SEPARATOR      = (40,  50,  80)    # ligne entre les colonnes
    COLOR_PLACEHOLDER_BG = (45,  50,  75)    # fond si sprite manquant
    COLOR_PLACEHOLDER_FG = (90,  100, 140)   # croix sur le placeholder

    # ---------------------------------------------------------------
    # Dimensions internes
    # ---------------------------------------------------------------
    PADDING  = 14   # marge interne du composant (px)
    LABEL_H  = 18   # hauteur réservée pour le libellé en bas (px)

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        customization: dict[str, str],
        scale: int = 4,
    ) -> None:
        """
        Paramètres
        ----------
        x, y          : position du coin supérieur gauche du composant
        width, height : dimensions totales du composant
        customization : dict { "skin": "default", "hair": "brown", ... }
        scale         : agrandissement des sprites pixel-art (défaut 4×)
                        → un sprite de 24×32 px deviendra 96×128 px
        """
        self.rect          = pygame.Rect(x, y, width, height)
        self.customization = customization
        self.scale         = scale

        # Police pour les libellés FACE / PROFIL / DOS
        self._font = pygame.font.SysFont("arial", 11)

        # Charger les spritesheets depuis le disque
        # (silencieux si un fichier est absent)
        self._layers = self._load_layers()

        # Pré-calculer les 3 images composées (une seule fois au démarrage)
        self._previews = self._build_all_previews()

    # ===================================================================
    # CHARGEMENT DES SPRITES
    # ===================================================================

    def _load_layers(self) -> dict[str, pygame.Surface]:
        """
        Charge le sprite de base puis tous les calques du catalogue.

        Pour chaque calque :
          1. On récupère le variant choisi ("feathered", "none", etc.)
          2. On charge le fichier PNG depuis le dossier du catalogue
          3. Si le calque est colorable, on applique la teinte choisie
             (ou la couleur par défaut du catalogue si aucune n'est spécifiée)

        Clés du dict retourné :
          "_base"  → sprite de corps complet (chargé depuis character_walk.png)
          "hair"   → calque cheveux teinté (si variant != "none" et fichier existe)
          "shirt"  → calque haut teinté (idem)
          ...

        Si un fichier est absent, le calque est ignoré silencieusement.
        """
        layers: dict[str, pygame.Surface] = {}

        # ── 1. Sprite de base (corps complet, toujours chargé) ────────
        base_path = SPRITES_CHARACTER_DIR / "character_walk.png"
        try:
            layers["_base"] = pygame.image.load(str(base_path)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            pass

        # ── 2. Calques optionnels pilotés par le catalogue ─────────────
        for layer_name, info in CUSTOMIZATION_CATALOG.items():
            variant = self.customization.get(layer_name, "none")

            # "none" = pas de calque pour cette catégorie (ex: chauve)
            if variant == "none":
                continue

            path = info["sprite_dir"] / f"{variant}{info['view_suffix']}"
            try:
                raw = pygame.image.load(str(path)).convert_alpha()
            except (pygame.error, FileNotFoundError):
                continue

            # ── Tinting (coloration dynamique) ─────────────────────────
            # On regarde les propriétés du VARIANT précis (pas de la catégorie),
            # car certains variants d'une même catégorie sont tintables et d'autres non.
            variant_info = info.get("variants", {}).get(variant, {})
            if variant_info.get("colorable", False):
                # Priorité : couleur choisie par le joueur > couleur par défaut du variant
                color = (
                    self.customization.get(f"{layer_name}_color")
                    or variant_info.get("default_color")
                )
                if color is not None:
                    raw = tint_surface(raw, tuple(color))

            layers[layer_name] = raw

        return layers

    def _extract_idle_frame(self, spritesheet: pygame.Surface, direction: str) -> pygame.Surface:
        """
        Extrait la frame "idle" (immobile, colonne 0) pour une direction donnée.

        Le spritesheet est une grille 4×4 :
          colonnes 0-3 : frames d'animation
          lignes   0-3 : directions (bas, gauche, droite, haut)

        On utilise Tool.split_image() qui est déjà défini dans le projet.
        """
        frame_w = spritesheet.get_width()  // 4   # largeur d'une frame
        frame_h = spritesheet.get_height() // 4   # hauteur d'une frame
        row     = self.DIRECTION_ROW[direction]

        # x=0 → colonne 0 = frame idle (pas d'animation dans un aperçu)
        return Tool.split_image(spritesheet, 0, row * frame_h, frame_w, frame_h)

    # ===================================================================
    # COMPOSITION DES VUES
    # ===================================================================

    def _compose_view(self, direction: str) -> pygame.Surface | None:
        """
        Compose une image finale pour une direction en superposant les calques.

        Ordre de rendu :
          1. "_base" — le corps complet du personnage
          2. "hair"  — les cheveux par-dessus (si sélectionnés)
          3. ...     — autres calques futurs dans OVERLAY_ORDER

        Retourne None si même le sprite de base est absent.
        """
        if "_base" not in self._layers:
            # Impossible de composer sans le corps du personnage
            return None

        base = self._layers["_base"]
        frame_w = base.get_width()  // 4
        frame_h = base.get_height() // 4

        # Canvas transparent sur lequel on empile les calques
        composite = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)

        # 1. Sprite de base en premier
        frame = self._extract_idle_frame(base, direction)
        composite.blit(frame, (0, 0))

        # 2. Calques optionnels par-dessus, dans l'ordre défini
        for layer_name in self.OVERLAY_ORDER:
            if layer_name not in self._layers:
                continue
            frame = self._extract_idle_frame(self._layers[layer_name], direction)
            composite.blit(frame, (0, 0))

        return composite

    def _build_all_previews(self) -> dict[str, pygame.Surface | None]:
        """
        Construit les 3 surfaces composées (face, profil, dos) une seule fois.

        On fait ça à l'initialisation plutôt que dans draw() pour éviter
        de recharger / recomposer les sprites 60 fois par seconde.
        """
        return {
            direction: self._compose_view(direction)
            for direction, _ in self.VIEWS
        }

    # ===================================================================
    # API PUBLIQUE
    # ===================================================================

    def update_customization(self, customization: dict) -> None:
        """
        Met à jour la tenue et les couleurs, puis reconstruit les previews.

        Le cache de tinting est vidé pour garantir que les nouvelles couleurs
        sont bien appliquées (et non servies depuis le cache de l'ancienne tenue).

        Exemple :
            preview.update_customization({
                "hair":       "feathered",
                "hair_color": (200, 60, 60),   # rouge
                "shirt":      "basic",
                "shirt_color": (30, 80, 200),  # bleu
            })
        """
        self.customization = customization
        # On vide le cache : les surfaces brutes chargées depuis le disque
        # sont les mêmes, mais les couleurs demandées ont changé.
        clear_tint_cache()
        self._layers   = self._load_layers()
        self._previews = self._build_all_previews()

    def draw(self, surface: pygame.Surface) -> None:
        """
        Dessine le composant complet sur la surface fournie.

        C'est la SEULE méthode que le menu doit appeler.
        Le menu n'a pas besoin de savoir comment les sprites sont gérés.
        """
        # ── 1. Fond et bordure ───────────────────────────────────────
        pygame.draw.rect(surface, self.COLOR_BG,     self.rect, border_radius=8)
        pygame.draw.rect(surface, self.COLOR_BORDER, self.rect, width=2, border_radius=8)

        # ── 2. Zone intérieure (après padding) ───────────────────────
        inner = self.rect.inflate(-self.PADDING * 2, -self.PADDING * 2)
        col_w = inner.width // 3

        # ── 3. Dessiner chaque vue (face, profil, dos) ───────────────
        for i, (direction, label) in enumerate(self.VIEWS):
            col_x    = inner.x + i * col_w
            col_rect = pygame.Rect(col_x, inner.y, col_w, inner.height)

            # Trait séparateur entre les colonnes (pas avant la première)
            if i > 0:
                pygame.draw.line(
                    surface, self.COLOR_SEPARATOR,
                    (col_x, inner.y + 6),
                    (col_x, inner.bottom - 6),
                    1,
                )

            # Sprite composé (ou placeholder si assets absents)
            preview = self._previews.get(direction)
            if preview is not None:
                self._render_character(surface, preview, col_rect)
            else:
                self._render_placeholder(surface, col_rect)

            # Libellé en bas de la colonne
            label_surf = self._font.render(label, True, self.COLOR_LABEL)
            label_pos  = label_surf.get_rect(
                centerx=col_rect.centerx,
                bottom=col_rect.bottom,
            )
            surface.blit(label_surf, label_pos)

    # ===================================================================
    # RENDU INTERNE
    # ===================================================================

    def _render_character(
        self,
        surface: pygame.Surface,
        character_surf: pygame.Surface,
        col_rect: pygame.Rect,
    ) -> None:
        """
        Agrandit le sprite (pixel-art) et le centre dans la colonne.

        pygame.transform.scale avec des entiers conserve le rendu pixel-art
        sans flou (contrairement à smoothscale).
        """
        scaled_w = character_surf.get_width()  * self.scale
        scaled_h = character_surf.get_height() * self.scale

        # Centrer dans la colonne, en réservant de la place pour le libellé
        available_h = col_rect.height - self.LABEL_H
        draw_x = col_rect.centerx - scaled_w // 2
        draw_y = col_rect.y + available_h // 2 - scaled_h // 2

        scaled = pygame.transform.scale(character_surf, (scaled_w, scaled_h))
        surface.blit(scaled, (draw_x, draw_y))

    def _render_placeholder(self, surface: pygame.Surface, col_rect: pygame.Rect) -> None:
        """
        Affiche une silhouette vide quand les sprites sont manquants.

        Visible pendant le développement, avant que les assets soient créés.
        La croix indique "image manquante" (convention UI classique).
        """
        ph_w = 48
        ph_h = 80
        ph_x = col_rect.centerx - ph_w // 2
        ph_y = col_rect.y + (col_rect.height - self.LABEL_H) // 2 - ph_h // 2
        ph_rect = pygame.Rect(ph_x, ph_y, ph_w, ph_h)

        pygame.draw.rect(surface, self.COLOR_PLACEHOLDER_BG, ph_rect, border_radius=4)
        pygame.draw.rect(surface, self.COLOR_PLACEHOLDER_FG, ph_rect, width=1, border_radius=4)

        # Croix centrale
        cx, cy = ph_rect.centerx, ph_rect.centery
        pygame.draw.line(surface, self.COLOR_PLACEHOLDER_FG, (cx - 8, cy - 8), (cx + 8, cy + 8), 2)
        pygame.draw.line(surface, self.COLOR_PLACEHOLDER_FG, (cx + 8, cy - 8), (cx - 8, cy + 8), 2)
