from code.core.screen import Screen
from code.entities.entity import Entity


class RemotePlayer(Entity):

    TILE_SIZE = 16

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

            dx = target_x - int(self.position.x)
            dy = target_y - int(self.position.y)

            self.direction = direction

            # Mouvement normal d'une seule case
            if dx == -self.TILE_SIZE and dy == 0:
                self.move_left()
            elif dx == self.TILE_SIZE and dy == 0:
                self.move_right()
            elif dx == 0 and dy == -self.TILE_SIZE:
                self.move_up()
            elif dx == 0 and dy == self.TILE_SIZE:
                self.move_down()
            else:
                # Si le remote est désynchronisé, on le replace proprement
                self.set_position(target_x, target_y)
                self.align_hitbox()

        super().update()