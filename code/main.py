import logging
import pygame

from code.core.game import Game

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

pygame.init()

if __name__ == "__main__":
    game: Game = Game()
    game.run()
