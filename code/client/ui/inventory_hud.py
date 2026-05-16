"""
inventory_hud.py — Inventaire arc, 2 rangées, au-dessus du joueur.

Touche R : ouvre / ferme l'inventaire.
Drag-and-drop via clic gauche maintenu.
Slots = cercles blancs simples.
"""
from __future__ import annotations

import math
from typing import Callable

import pygame

from code.shared.config.items import ITEMS, INVENTORY_MAX_SLOTS
from code.client.config import SPRITES_DIR, SPRITES_BATTLE_DIR

_ICONS_DIR = SPRITES_DIR / "icons"

# Couleurs des types
_TYPE_COLORS: dict[str, tuple] = {
    "normal": (168, 167, 122), "fire": (238, 129, 48),  "water": (99, 144, 240),
    "electric": (247, 208, 44), "grass": (122, 199, 76), "ice": (150, 217, 214),
    "fighting": (194, 46, 40), "poison": (163, 62, 161), "ground": (226, 191, 101),
    "flying": (169, 143, 243), "psychic": (249, 85, 135), "bug": (166, 185, 26),
    "rock": (182, 161, 100), "ghost": (115, 87, 151),   "dragon": (111, 53, 252),
    "dark": (112, 87, 70),   "steel": (183, 183, 206),  "fairy": (214, 133, 173),
}
_TYPE_FR: dict[str, str] = {
    "normal": "Normal", "fire": "Feu", "water": "Eau", "electric": "Electrik",
    "grass": "Plante", "ice": "Glace", "fighting": "Combat", "poison": "Poison",
    "ground": "Sol", "flying": "Vol", "psychic": "Psy", "bug": "Insecte",
    "rock": "Roche", "ghost": "Spectre", "dragon": "Dragon", "dark": "Ténèbres",
    "steel": "Acier", "fairy": "Fée",
}

# ---------------------------------------------------------------------------
# Constantes visuelles
# ---------------------------------------------------------------------------
SLOTS_PER_ROW  = INVENTORY_MAX_SLOTS // 3   # 7 par rangée

SLOT_RADIUS    = 28     # rayon du cercle de slot (px) — doublé
SLOT_BORDER    = 2      # épaisseur du contour

# Même rayon pour les deux rangées → même espacement horizontal dans chaque ligne.
# La séparation verticale vient uniquement de la différence de hauteur (_ROW_*_PCT).
ARC_RADIUS     = 520

# Arc de 50° → espacement horizontal ≈ 9 px entre les bords des cercles.
# Avec 8 slots : pas angulaire = 50/7 ≈ 7.14°,
# distance centre-à-centre = 2×520×sin(3.57°) ≈ 65 px, gap = 65-56 = 9 px.
ARC_START_DEG  = 68.0
ARC_END_DEG    = 112.0

# 3 rangées espacées pour garder ~9 px de gap entre les bords des cercles (H=720).
_ROW_OUT_PCT   = 0.30   # rangée la plus haute
_ROW_MID_PCT   = 0.21   # rangée centrale
_ROW_IN_PCT    = 0.12   # rangée la plus proche du joueur

# Couleurs
C_SLOT         = (255, 255, 255)       # blanc — normal
C_SLOT_SEL     = (255, 215, 50)        # doré  — sélectionné
C_SLOT_HOVER   = (140, 200, 255)       # bleu  — cible drag
C_SLOT_FILL    = (0,   0,   0,   70)  # fond semi-transparent
C_QTY          = (255, 255, 255)
C_NAME         = (255, 255, 255)


# ---------------------------------------------------------------------------
# Modèle de données
# ---------------------------------------------------------------------------

class ItemStack:
    __slots__ = ("item_id", "quantity")

    def __init__(self, item_id: str, quantity: int = 1) -> None:
        self.item_id  = item_id
        self.quantity = quantity


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------

class InventoryHUD:
    """
    Inventaire arc en 2 rangées affiché au-dessus du joueur.

    Nécessite d'être créé après pygame.init().
    Appeler update(player) après map.update() chaque frame.
    """

    def __init__(self, screen) -> None:
        self.screen    = screen
        self.slots: list[ItemStack | None] = [None] * INVENTORY_MAX_SLOTS

        self.active    = False           # affiché seulement si True
        self._selected = 0

        self.on_slot_swap:   Callable[[int, int], None] | None = None
        self.on_party_swap:  Callable[[int, int], None] | None = None

        self._drag_from: int | None = None
        self._drag_pos  = (0, 0)
        self._prev_btn  = False
        self._prev_rbtn = False          # suivi clic droit précédent

        # Drag-and-drop équipe
        self._party_drag_from: int | None = None
        self._party_drag_pos   = (0, 0)
        self._prev_lbtn_party  = False

        self._textures: dict[str, pygame.Surface] = {}
        self._poke_icons: dict[str, list[pygame.Surface]] = {}  # cache icônes

        # Menu contextuel (clic droit sur un slot)
        self._ctx_pkmn    = None          # Pokémon ciblé
        self._ctx_rect: pygame.Rect | None = None   # position du menu

        self._font_qty:     pygame.font.Font | None = None
        self._font_name:    pygame.font.Font | None = None
        self._font_party:   pygame.font.Font | None = None
        self._font_party_s: pygame.font.Font | None = None
        self._built = False

        # Exposé à game.py : pkmn sur lequel le joueur a fait clic droit
        self.stats_request = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def toggle(self) -> None:
        if self.active:
            # Fermeture : vider les slots (le serveur fait foi, pas le client)
            self.slots = [None] * INVENTORY_MAX_SLOTS
        self.active = not self.active

    def load_from_inventory(self, bag) -> None:
        """
        Peuple les slots depuis le sac.
        - Items avec slot_index → placés dans leur slot exact.
        - Items sans slot_index (NULL) → placés dans le premier slot libre (fallback).
        """
        self.slots = [None] * INVENTORY_MAX_SLOTS

        # 1re passe : items avec slot_index fixé
        for pocket_items in bag.pockets.values():
            for item in pocket_items:
                si = item.slot_index
                if si is not None and 0 <= si < INVENTORY_MAX_SLOTS:
                    self.slots[si] = ItemStack(item.item_db_symbol, item.quantity)

        # 2e passe : items sans slot_index → premier slot libre
        # On met aussi à jour item.slot_index pour que swap_hud_slots puisse retrouver l'item.
        for pocket_items in bag.pockets.values():
            for item in pocket_items:
                if item.slot_index is None:
                    for i in range(INVENTORY_MAX_SLOTS):
                        if self.slots[i] is None:
                            self.slots[i] = ItemStack(item.item_db_symbol, item.quantity)
                            item.slot_index = i   # synchronise le bag avec l'affichage
                            break

    def update(self, cx: int, cy: int, money: int = 0, party: list | None = None) -> None:
        """
        cx, cy : position écran du joueur.
        money  : Pokédollars (affiché en bas-gauche de l'arc).
        party  : liste de Pokemon pour la colonne équipe à gauche.
        """
        if not self._built:
            self._build()
        if not self.active:
            return

        _, H    = self.screen.get_size()
        row_out = int(H * _ROW_OUT_PCT)
        row_mid = int(H * _ROW_MID_PCT)
        row_in  = int(H * _ROW_IN_PCT)

        positions = self._all_positions(cx, cy, row_out, row_mid, row_in)
        self._handle_drag(positions)
        self._draw(positions, cx, cy, row_out, money)
        if party is not None:
            self._draw_party(party)

    def handle_event(self, event: pygame.event.Event, party: list | None = None) -> None:
        """Consomme les événements liés à l'inventaire (Escape ferme, etc.)."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.toggle()

    # --- Inventaire -------------------------------------------------------

    def add_item(self, item_id: str, quantity: int = 1) -> bool:
        definition = ITEMS.get(item_id)
        if not definition:
            return False
        stackable = definition.get("stackable", True)
        max_stack = definition.get("max_stack", 99)
        if stackable:
            for slot in self.slots:
                if slot and slot.item_id == item_id and slot.quantity < max_stack:
                    slot.quantity = min(max_stack, slot.quantity + quantity)
                    return True
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = ItemStack(item_id, min(quantity, max_stack))
                return True
        return False

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        for i, slot in enumerate(self.slots):
            if slot and slot.item_id == item_id and slot.quantity >= quantity:
                slot.quantity -= quantity
                if slot.quantity == 0:
                    self.slots[i] = None
                return True
        return False

    def get_selected(self) -> ItemStack | None:
        return self.slots[self._selected]

    def select_next(self) -> None:
        self._selected = (self._selected + 1) % INVENTORY_MAX_SLOTS

    def select_prev(self) -> None:
        self._selected = (self._selected - 1) % INVENTORY_MAX_SLOTS

    # ------------------------------------------------------------------
    # Construction (lazy)
    # ------------------------------------------------------------------

    def _build(self) -> None:
        try:
            self._font_qty    = pygame.font.SysFont("segoeui", 11, bold=True)
            self._font_name   = pygame.font.SysFont("segoeui", 13, bold=True)
            self._font_party  = pygame.font.SysFont("segoeui", 12, bold=True)
            self._font_party_s = pygame.font.SysFont("segoeui", 11)
        except Exception:
            f = pygame.font.Font(None, 14)
            self._font_qty = self._font_name = self._font_party = self._font_party_s = f

        icon_size = SLOT_RADIUS * 2 - 8
        for item_id, defn in ITEMS.items():
            path = defn.get("texture")
            if path and path.exists():
                try:
                    img = pygame.image.load(str(path)).convert_alpha()
                    self._textures[item_id] = pygame.transform.smoothscale(
                        img, (icon_size, icon_size)
                    )
                except Exception:
                    pass
        self._built = True

    # ------------------------------------------------------------------
    # Géométrie
    # ------------------------------------------------------------------

    def _arc_positions(
        self, cx: int, cy: int, row_height: int
    ) -> list[tuple[int, int]]:
        """
        Retourne SLOTS_PER_ROW positions sur un arc de rayon ARC_RADIUS.
        Le centre de l'arc est décalé vers le bas pour que le sommet
        soit exactement à row_height px au-dessus du joueur.
        """
        arc_cy = cy + (ARC_RADIUS - row_height)
        n      = SLOTS_PER_ROW
        start  = math.radians(ARC_START_DEG)
        end    = math.radians(ARC_END_DEG)
        return [
            (
                int(cx + ARC_RADIUS * math.cos(start + i / max(n - 1, 1) * (end - start))),
                int(arc_cy - ARC_RADIUS * math.sin(start + i / max(n - 1, 1) * (end - start))),
            )
            for i in range(n)
        ]

    def _all_positions(
        self, cx: int, cy: int, row_out: int, row_mid: int, row_in: int
    ) -> list[tuple[int, int]]:
        """Retourne les 21 positions : 7 rangée ext. + 7 rangée moy. + 7 rangée int."""
        return (
            self._arc_positions(cx, cy, row_out)   # slots 0-6
            + self._arc_positions(cx, cy, row_mid)  # slots 7-13
            + self._arc_positions(cx, cy, row_in)   # slots 14-20
        )

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def _handle_drag(self, positions: list[tuple[int, int]]) -> None:
        mouse = pygame.mouse.get_pos()
        btn   = pygame.mouse.get_pressed()[0]

        if btn and not self._prev_btn and self._party_drag_from is None:
            for i, pos in enumerate(positions):
                if math.dist(mouse, pos) <= SLOT_RADIUS:
                    self._selected = i
                    if self.slots[i] is not None:
                        self._drag_from = i
                    break

        if btn:
            self._drag_pos = mouse

        if not btn and self._prev_btn and self._drag_from is not None:
            for i, pos in enumerate(positions):
                if math.dist(mouse, pos) <= SLOT_RADIUS and i != self._drag_from:
                    from_slot = self._drag_from
                    self.slots[from_slot], self.slots[i] = (
                        self.slots[i], self.slots[from_slot]
                    )
                    self._selected = i
                    if self.on_slot_swap:
                        self.on_slot_swap(from_slot, i)
                    break
            self._drag_from = None

        self._prev_btn = btn

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------

    def _draw_arc_background(self, disp: pygame.Surface, positions: list[tuple[int, int]]) -> None:
        """Fond blanc unique en blob — cercles superposés qui suivent la courbe de l'arc."""
        if not positions:
            return
        pad = 10
        r   = SLOT_RADIUS + pad
        xs  = [p[0] for p in positions]
        ys  = [p[1] for p in positions]
        x1  = min(xs) - r - 1
        y1  = min(ys) - r - 1
        x2  = max(xs) + r + 1
        y2  = max(ys) + r + 1
        w, h = x2 - x1, y2 - y1
        bg  = pygame.Surface((w, h), pygame.SRCALPHA)
        for pos in positions:
            pygame.draw.circle(bg, (255, 255, 255, 230), (pos[0] - x1, pos[1] - y1), r)
        disp.blit(bg, (x1, y1))

    def _draw(
        self, positions: list[tuple[int, int]], cx: int, cy: int,
        row_out: int, money: int
    ) -> None:
        disp  = self.screen.get_display()
        mouse = pygame.mouse.get_pos()

        self._draw_arc_background(disp, positions)

        for i, pos in enumerate(positions):
            slot       = self.slots[i]
            is_sel     = (i == self._selected)
            is_dragged = (i == self._drag_from)
            is_target  = (
                self._drag_from is not None
                and i != self._drag_from
                and math.dist(mouse, pos) <= SLOT_RADIUS
            )

            # Fond sombre
            bg = pygame.Surface((SLOT_RADIUS * 2, SLOT_RADIUS * 2), pygame.SRCALPHA)
            pygame.draw.circle(bg, C_SLOT_FILL, (SLOT_RADIUS, SLOT_RADIUS), SLOT_RADIUS)
            disp.blit(bg, (pos[0] - SLOT_RADIUS, pos[1] - SLOT_RADIUS))

            # Contour
            if is_target:
                color, width = C_SLOT_HOVER, 3
            elif is_sel:
                color, width = C_SLOT_SEL,  3
            else:
                color, width = C_SLOT,      SLOT_BORDER
            pygame.draw.circle(disp, color, pos, SLOT_RADIUS, width)

            # Icône (masquée si en cours de drag)
            if slot and not is_dragged:
                self._draw_icon(disp, slot.item_id, pos)
                if slot.quantity > 1:
                    self._draw_qty(disp, slot.quantity, pos)

        # Icône suivant le curseur pendant le drag
        if self._drag_from is not None:
            slot = self.slots[self._drag_from]
            if slot:
                self._draw_icon(disp, slot.item_id, self._drag_pos, scale=1.2)

        # Nom du slot sélectionné — au-dessus de l'arc extérieur
        sel_slot = self.slots[self._selected]
        if sel_slot and self._font_name:
            name = ITEMS.get(sel_slot.item_id, {}).get("name_fr", sel_slot.item_id)
            txt  = self._font_name.render(name, True, C_NAME)
            pad  = 6
            bg2  = pygame.Surface((txt.get_width() + pad * 2, txt.get_height() + pad),
                                   pygame.SRCALPHA)
            bg2.fill((0, 0, 0, 130))
            y_name = cy - row_out - SLOT_RADIUS - 14
            disp.blit(bg2, (cx - bg2.get_width() // 2, y_name - bg2.get_height() // 2))
            disp.blit(txt, txt.get_rect(center=(cx, y_name)))

        # Pokédollars — en bas à gauche de l'arc (sous le slot 19, le plus à gauche)
        if self._font_name:
            lx, ly = positions[-1]   # slot le plus à gauche de la rangée intérieure
            money_str = f"P$ {money:,}".replace(",", " ")  # espace fine comme séparateur
            mt  = self._font_name.render(money_str, True, (255, 220, 50))
            pad = 5
            mbg = pygame.Surface((mt.get_width() + pad * 2, mt.get_height() + pad),
                                  pygame.SRCALPHA)
            mbg.fill((0, 0, 0, 140))
            mx = lx - mt.get_width() // 2 - pad
            my = ly + SLOT_RADIUS + 6
            disp.blit(mbg, (mx, my))
            disp.blit(mt,  (mx + pad, my + pad // 2))

    # ------------------------------------------------------------------
    # Colonne équipe (gauche de l'écran) — icône seule, 6 slots fixes
    # ------------------------------------------------------------------

    _SLOT_W   = 56
    _SLOT_H   = 56
    _SLOT_GAP = 4
    _SLOT_MX  = 8
    _N_SLOTS  = 6

    def _poke_icon_frames(self, pkmn) -> list[pygame.Surface]:
        """Charge et met en cache les 2 frames d'animation de l'icône (128×64 → 2×40×40)."""
        pid   = getattr(pkmn, "id", None)
        shiny = getattr(pkmn, "shiny", "")
        if pid is None:
            return []
        suffix = "s" if shiny else "n"
        key    = f"{pid}-b-{suffix}"
        if key in self._poke_icons:
            return self._poke_icons[key]
        path = _ICONS_DIR / f"{key}.png"
        if not path.exists():
            path = _ICONS_DIR / f"{pid}-b-n.png"
        frames: list[pygame.Surface] = []
        if path.exists():
            try:
                sheet = pygame.image.load(str(path)).convert_alpha()
                sw, sh = sheet.get_size()
                fw = sw // 2   # largeur d'une frame (64 px)
                for i in range(2):
                    sub = sheet.subsurface(pygame.Rect(i * fw, 0, fw, sh))
                    sub = pygame.transform.smoothscale(sub, (40, 40))
                    frames.append(sub)
            except Exception:
                pass
        self._poke_icons[key] = frames
        return frames

    def _draw_party(self, party: list) -> None:
        disp = self.screen.get_display()
        W, H = self.screen.get_size()

        CARD_W = self._SLOT_W
        CARD_H = self._SLOT_H
        GAP    = self._SLOT_GAP
        MX     = self._SLOT_MX

        total_h = self._N_SLOTS * CARD_H + (self._N_SLOTS - 1) * GAP
        start_y = max(8, (H - total_h) // 2)

        mouse  = pygame.mouse.get_pos()
        lbtn   = pygame.mouse.get_pressed()[0]
        rbtn   = pygame.mouse.get_pressed()[2]

        # ── Drag-and-drop équipe ───────────────────────────────────────
        l_press  = lbtn and not self._prev_lbtn_party
        l_release = not lbtn and self._prev_lbtn_party

        if l_press and self._party_drag_from is None and self._drag_from is None:
            for i in range(min(self._N_SLOTS, len(party))):
                sx = W - MX - CARD_W
                sy = start_y + i * (CARD_H + GAP)
                if party[i] is not None and pygame.Rect(sx, sy, CARD_W, CARD_H).collidepoint(mouse):
                    self._party_drag_from = i
                    self._ctx_pkmn = None   # annule le menu contextuel
                    break

        if lbtn:
            self._party_drag_pos = mouse

        if l_release and self._party_drag_from is not None:
            for i in range(min(self._N_SLOTS, len(party))):
                sx = W - MX - CARD_W
                sy = start_y + i * (CARD_H + GAP)
                if i != self._party_drag_from and pygame.Rect(sx, sy, CARD_W, CARD_H).collidepoint(mouse):
                    src = self._party_drag_from
                    party[src], party[i] = party[i], party[src]
                    if self.on_party_swap:
                        self.on_party_swap(src, i)
                    break
            self._party_drag_from = None

        self._prev_lbtn_party = lbtn

        # ── Clic droit (seulement hors drag) ──────────────────────────
        r_click = rbtn and not self._prev_rbtn and self._party_drag_from is None
        self._prev_rbtn = rbtn

        # ── Dessin des slots ───────────────────────────────────────────
        for i in range(self._N_SLOTS):
            sx = W - MX - CARD_W
            sy = start_y + i * (CARD_H + GAP)

            pkmn   = party[i] if i < len(party) else None
            is_ko  = pkmn is not None and getattr(pkmn, "hp", 1) <= 0
            is_src = (i == self._party_drag_from)

            # Fond
            bg = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            if pkmn is None:
                bg.fill((55, 55, 55, 120))
            elif is_src:
                bg.fill((80, 100, 80, 160))    # légèrement vert pendant le drag
            elif is_ko:
                bg.fill((90, 40, 40, 200))
            else:
                bg.fill((75, 75, 75, 200))
            disp.blit(bg, (sx, sy))

            # Bordure — surbrillance si la cible du drag passe dessus
            slot_rect  = pygame.Rect(sx, sy, CARD_W, CARD_H)
            is_target  = (self._party_drag_from is not None
                          and i != self._party_drag_from
                          and slot_rect.collidepoint(mouse))
            if is_target:
                border_col = (100, 200, 100)
            elif pkmn is None:
                border_col = (120, 120, 120)
            elif is_ko:
                border_col = (200, 80, 80)
            else:
                border_col = (200, 200, 200)
            pygame.draw.rect(disp, border_col, (sx, sy, CARD_W, CARD_H),
                             2 if is_target else 1, border_radius=6)

            if pkmn is None or is_src:
                continue

            # Icône — frame 0 au survol, frame 1 par défaut
            frames = self._poke_icon_frames(pkmn)
            if frames:
                hovered = slot_rect.collidepoint(mouse) and self._party_drag_from is None
                frame   = frames[0 if hovered and len(frames) > 1 else (1 if len(frames) > 1 else 0)]
                ir = frame.get_rect(center=(sx + CARD_W // 2, sy + CARD_H // 2))
                disp.blit(frame, ir)

            if r_click and slot_rect.collidepoint(mouse):
                self._ctx_pkmn = pkmn
                self._ctx_rect = pygame.Rect(sx - 94, sy, 90, 30)

        # ── Ghost du Pokémon draggué ───────────────────────────────────
        if self._party_drag_from is not None and self._party_drag_from < len(party):
            pkmn = party[self._party_drag_from]
            if pkmn:
                frames = self._poke_icon_frames(pkmn)
                if frames:
                    ghost = frames[0].copy()
                    ghost.set_alpha(180)
                    disp.blit(ghost, ghost.get_rect(center=self._party_drag_pos))

        # ── Menu contextuel ────────────────────────────────────────────
        if self._ctx_pkmn is not None and self._ctx_rect is not None:
            r = self._ctx_rect
            bg2 = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            bg2.fill((72, 72, 72, 235))
            disp.blit(bg2, r.topleft)
            pygame.draw.rect(disp, (200, 200, 200), r, 1, border_radius=4)
            if self._font_party:
                lt = self._font_party.render("Résumé", True, (220, 220, 255))
                disp.blit(lt, lt.get_rect(center=r.center))
            if lbtn and r.collidepoint(mouse):
                self.stats_request = self._ctx_pkmn
                self._ctx_pkmn = None
                self._ctx_rect = None
            elif lbtn and not r.collidepoint(mouse):
                self._ctx_pkmn = None
                self._ctx_rect = None

    def _draw_icon(
        self,
        disp: pygame.Surface,
        item_id: str,
        pos: tuple[int, int],
        scale: float = 1.0,
    ) -> None:
        img = self._textures.get(item_id)
        if not img:
            return
        if scale != 1.0:
            w, h = img.get_size()
            img  = pygame.transform.smoothscale(img, (int(w * scale), int(h * scale)))
        disp.blit(img, img.get_rect(center=pos))

    def _draw_qty(
        self, disp: pygame.Surface, qty: int, pos: tuple[int, int]
    ) -> None:
        if not self._font_qty:
            return
        txt    = self._font_qty.render(str(qty), True, C_QTY)
        shadow = self._font_qty.render(str(qty), True, (0, 0, 0))
        x = pos[0] + SLOT_RADIUS - txt.get_width()  - 2
        y = pos[1] + SLOT_RADIUS - txt.get_height() - 2
        disp.blit(shadow, (x + 1, y + 1))
        disp.blit(txt,    (x,     y))

