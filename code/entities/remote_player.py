from code.core.screen import Screen
from code.entities.entity import Entity


class RemotePlayer(Entity):

    TILE_SIZE = 16

    _SRC = {
        "right": (-16,  0),
        "left":  ( 16,  0),
        "up":    (  0, 16),
        "down":  (  0,-16),
    }

    def __init__(
        self,
        screen: Screen,
        pid: str,
        x: int,
        y: int,
        direction: str,
        sprite: str,
        name: str
    ) -> None:
        super().__init__(screen, x, y, sprite)
        self.pid = pid
        self.name = name
        self.direction = direction
        self._pending: list[tuple[int, int, str]] = []

    def apply_move(self, x: int, y: int, direction: str) -> None:
        self._pending.append((x, y, direction))

    def update(self) -> None:
        if not self.animation_walk and self._pending:
            target_x, target_y, direction = self._pending.pop(0)
            self.direction = direction

            ox, oy = self._SRC.get(direction, (0, 0))
            self.set_position(target_x + ox, target_y + oy)

            if direction == "left":
                self.move_left()
            elif direction == "right":
                self.move_right()
            elif direction == "up":
                self.move_up()
            elif direction == "down":
                self.move_down()

        super().update()
