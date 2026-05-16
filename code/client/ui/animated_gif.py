"""Classe AnimatedGif partagée entre battle_screen et motismart."""
from __future__ import annotations
import pygame


class AnimatedGif:
    """Charge un GIF animé via Pillow et expose la frame courante comme Surface pygame."""

    def __init__(self, path) -> None:
        self._frames: list[pygame.Surface] = []
        self._delays: list[float] = []
        self._frame_idx = 0
        self._elapsed   = 0.0
        self._load(path)

    def _load(self, path) -> None:
        try:
            from PIL import Image
            img = Image.open(str(path))
            try:
                while True:
                    frame = img.convert("RGBA")
                    data  = frame.tobytes()
                    w, h  = frame.size
                    surf  = pygame.image.fromstring(data, (w, h), "RGBA").convert_alpha()
                    self._frames.append(surf)
                    delay = img.info.get("duration", 100) / 1000.0
                    self._delays.append(max(delay, 0.05))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        except Exception:
            pass

    @property
    def valid(self) -> bool:
        return bool(self._frames)

    def get_size(self) -> tuple[int, int]:
        return self._frames[0].get_size() if self._frames else (0, 0)

    def get_width(self)  -> int: return self.get_size()[0]
    def get_height(self) -> int: return self.get_size()[1]

    def update(self, dt: float) -> None:
        if len(self._frames) <= 1:
            return
        self._elapsed += dt
        while self._elapsed >= self._delays[self._frame_idx]:
            self._elapsed  -= self._delays[self._frame_idx]
            self._frame_idx = (self._frame_idx + 1) % len(self._frames)

    def current_frame(self) -> pygame.Surface | None:
        return self._frames[self._frame_idx] if self._frames else None
