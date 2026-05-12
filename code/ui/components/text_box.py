"""
TextBox — boîte de texte réutilisable avec effet machine à écrire.

Utilisable pour : dialogues de combat, messages de PNJ, événements, tutoriels.

Usage
-----
    box = TextBox(pygame.Rect(x, y, w, h), bg_surf=image)
    box.set_messages(["Que va faire Pikachu ?"])

    # boucle principale :
    box.update()
    box.draw(surface)

    # sur pression du bouton d'action :
    box.action()
    # → 1re pression pendant animation : affiche tout le message immédiatement
    # → 1re pression quand texte fini   : passe au message suivant (ou done=True)

    if box.done:
        next_state()
"""
from __future__ import annotations
import time
import pygame

_PADDING    = 12
_CHAR_DELAY = 0.04   # secondes entre chaque caractère


class TextBox:
    """
    Paramètres
    ----------
    rect        : zone de dessin sur la surface parente (pygame.Rect)
    bg_surf     : fond pré-scalé à blit avant le texte ; None → fond transparent
    font        : police pygame ; None → SysFont arial 16
    text_color  : couleur RGB(A) du texte
    char_delay  : délai en secondes entre deux caractères
    """

    def __init__(
        self,
        rect: pygame.Rect,
        *,
        bg_surf: pygame.Surface | None = None,
        font: pygame.font.Font | None = None,
        text_color: tuple = (30, 30, 30),
        char_delay: float = _CHAR_DELAY,
    ) -> None:
        self.rect    = rect
        self._bg     = bg_surf
        self._color  = text_color
        self._delay  = char_delay
        self._font   = font or _make_font(16)

        self._messages: list[str]       = []
        self._wrapped:  list[list[str]] = []
        self._msg_idx   = 0
        self._char_idx  = 0
        self._last_tick = 0.0
        self._done      = False

    # ------------------------------------------------------------------
    def set_messages(self, messages: list[str]) -> None:
        """Charge une séquence de messages et repart de zéro."""
        self._messages  = [m for m in messages if m]
        self._wrapped   = [self._wrap(m) for m in self._messages]
        self._msg_idx   = 0
        self._char_idx  = 0
        self._last_tick = time.time()
        self._done      = False

    # ------------------------------------------------------------------
    def action(self) -> None:
        """
        Pression du bouton de confirmation :
          - texte en cours d'animation → affiche tout immédiatement
          - texte fini, pas le dernier  → message suivant
          - dernier message fini        → done = True
        """
        if self._done or not self._messages:
            return

        if self._char_idx < self._total_chars():
            self._char_idx = self._total_chars()
        elif self._msg_idx < len(self._messages) - 1:
            self._msg_idx  += 1
            self._char_idx  = 0
            self._last_tick = time.time()
        else:
            self._done = True

    # ------------------------------------------------------------------
    def update(self) -> None:
        """Avance l'animation d'un caractère si le délai est écoulé."""
        if self._done or not self._messages:
            return
        if self._char_idx >= self._total_chars():
            return
        if time.time() - self._last_tick >= self._delay:
            self._last_tick = time.time()
            self._char_idx += 1

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dessine le fond puis le texte animé sur `surface`."""
        if not self._messages:
            return

        if self._bg:
            surface.blit(self._bg, self.rect.topleft)

        if not self._wrapped:
            return

        lines = self._wrapped[self._msg_idx]
        shown = self._full_text()[:self._char_idx]

        ty = self.rect.y + _PADDING
        lh = self._font.get_linesize()
        remaining = len(shown)

        for line in lines:
            if remaining <= 0:
                break
            visible   = line[:remaining]
            remaining -= len(line) + 1   # +1 pour le retour à la ligne implicite
            surface.blit(self._font.render(visible, True, self._color),
                         (self.rect.x + _PADDING, ty))
            ty += lh

        # Curseur ▼ quand le message attend une confirmation
        if self.waiting_confirm:
            cur = self._font.render("▼", True, self._color)
            surface.blit(cur, (
                self.rect.right  - cur.get_width()  - _PADDING,
                self.rect.bottom - cur.get_height() - _PADDING // 2,
            ))

    # ------------------------------------------------------------------
    @property
    def done(self) -> bool:
        """True quand tous les messages ont été confirmés."""
        return self._done

    @property
    def waiting_confirm(self) -> bool:
        """True quand l'animation est terminée mais pas encore confirmée."""
        return (
            not self._done
            and bool(self._messages)
            and self._char_idx >= self._total_chars()
        )

    # ------------------------------------------------------------------
    def _full_text(self) -> str:
        if not self._wrapped:
            return ""
        return "\n".join(self._wrapped[self._msg_idx])

    def _total_chars(self) -> int:
        return len(self._full_text())

    def _wrap(self, text: str) -> list[str]:
        """Découpe `text` en lignes tenant dans la largeur du rect."""
        max_w = self.rect.width - _PADDING * 2
        lines, line = [], ""
        for word in text.split():
            test = f"{line} {word}".strip()
            if self._font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines or [""]


def _make_font(size: int, bold: bool = False) -> pygame.font.Font:
    try:    return pygame.font.SysFont("arial", size, bold=bold)
    except: return pygame.font.Font(None, size)
