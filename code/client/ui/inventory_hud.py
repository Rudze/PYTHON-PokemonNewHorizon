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

# ---------------------------------------------------------------------------
# Constantes visuelles
# ---------------------------------------------------------------------------
SLOTS_PER_ROW  = INVENTORY_MAX_SLOTS // 2   # 10 par rangée

SLOT_RADIUS    = 28     # rayon du cercle de slot (px) — doublé
SLOT_BORDER    = 2      # épaisseur du contour

# Même rayon pour les deux rangées → même espacement horizontal dans chaque ligne.
# La séparation verticale vient uniquement de la différence de hauteur (_ROW_*_PCT).
ARC_RADIUS     = 520

# Arc de 50° → espacement horizontal ≈ 9 px entre les bords des cercles.
# Avec 8 slots : pas angulaire = 50/7 ≈ 7.14°,
# distance centre-à-centre = 2×520×sin(3.57°) ≈ 65 px, gap = 65-56 = 9 px.
ARC_START_DEG  = 65.0
ARC_END_DEG    = 115.0

# Séparation verticale ≈ même gap : (row_out - row_in) × 720 ≈ 65 px → gap ≈ 9 px.
_ROW_OUT_PCT   = 0.22
_ROW_IN_PCT    = 0.13

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

        self.on_slot_swap: Callable[[int, int], None] | None = None

        self._drag_from: int | None = None
        self._drag_pos  = (0, 0)
        self._prev_btn  = False

        self._textures: dict[str, pygame.Surface] = {}
        self._font_qty:     pygame.font.Font | None = None
        self._font_name:    pygame.font.Font | None = None
        self._font_party:   pygame.font.Font | None = None
        self._font_party_s: pygame.font.Font | None = None
        self._built = False

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
        row_in  = int(H * _ROW_IN_PCT)

        positions = self._all_positions(cx, cy, row_out, row_in)
        self._handle_drag(positions)
        self._draw(positions, cx, cy, row_out, money)
        if party is not None:
            self._draw_party(party)

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
        self, cx: int, cy: int, row_out: int, row_in: int
    ) -> list[tuple[int, int]]:
        """Retourne les 16 positions : 8 rangée ext. + 8 rangée int."""
        return (
            self._arc_positions(cx, cy, row_out)   # slots 0-7
            + self._arc_positions(cx, cy, row_in)  # slots 8-15
        )

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def _handle_drag(self, positions: list[tuple[int, int]]) -> None:
        mouse = pygame.mouse.get_pos()
        btn   = pygame.mouse.get_pressed()[0]

        if btn and not self._prev_btn:
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

    def _draw(
        self, positions: list[tuple[int, int]], cx: int, cy: int,
        row_out: int, money: int
    ) -> None:
        disp  = self.screen.get_display()
        mouse = pygame.mouse.get_pos()

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
    # Colonne équipe (gauche de l'écran)
    # ------------------------------------------------------------------

    def _draw_party(self, party: list) -> None:
        if not party:
            return

        disp        = self.screen.get_display()
        W, H        = self.screen.get_size()
        CARD_W      = 120
        CARD_H      = 68
        CARD_GAP    = 6
        MARGIN_X    = 8
        BAR_H       = 8
        BAR_W       = CARD_W - 20

        total_h = len(party) * CARD_H + (len(party) - 1) * CARD_GAP
        start_y = max(8, (H - total_h) // 2)

        for i, pkmn in enumerate(party):
            cx = MARGIN_X
            cy = start_y + i * (CARD_H + CARD_GAP)

            # Fond semi-transparent
            bg = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            is_ko = getattr(pkmn, "hp", 1) <= 0
            bg.fill((30, 30, 50, 200) if not is_ko else (50, 20, 20, 200))
            disp.blit(bg, (cx, cy))
            border_col = (80, 80, 180) if not is_ko else (160, 60, 60)
            pygame.draw.rect(disp, border_col, (cx, cy, CARD_W, CARD_H), 1, border_radius=5)

            # Nom (dbSymbol humanisé)
            name   = getattr(pkmn, "dbSymbol", "???").replace("_", " ").capitalize()
            level  = getattr(pkmn, "level",  1)
            hp     = max(0, getattr(pkmn, "hp",    0))
            maxhp  = max(1, getattr(pkmn, "maxhp", 1))
            ratio  = hp / maxhp

            if self._font_party:
                nt = self._font_party.render(name[:14], True, (230, 230, 230))
                disp.blit(nt, (cx + 8, cy + 6))

            if self._font_party_s:
                lt = self._font_party_s.render(f"Nv.{level}", True, (180, 180, 180))
                disp.blit(lt, (cx + 8, cy + 22))

            # Barre HP
            bar_x = cx + 10
            bar_y = cy + CARD_H - BAR_H - 10
            pygame.draw.rect(disp, (40, 40, 60), (bar_x, bar_y, BAR_W, BAR_H), border_radius=3)
            if ratio > 0:
                if ratio > 0.5:
                    bar_col = (50, 200, 70)
                elif ratio > 0.2:
                    bar_col = (230, 180, 30)
                else:
                    bar_col = (220, 50, 50)
                filled = max(1, int(BAR_W * ratio))
                pygame.draw.rect(disp, bar_col, (bar_x, bar_y, filled, BAR_H), border_radius=3)

            if self._font_party_s:
                hp_txt = f"{hp}/{maxhp}"
                ht = self._font_party_s.render(hp_txt, True, (160, 160, 160))
                disp.blit(ht, (bar_x + BAR_W - ht.get_width(), bar_y - ht.get_height() - 1))

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
