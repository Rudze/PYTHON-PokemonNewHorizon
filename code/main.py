"""
This is the main file of the game. It initializes the game and runs it.
"""
import pygame

from code.core.game import Game

pygame.init()

if __name__ == "__main__":
    game: Game = Game()  # Ici on appelle le __init__ (préparation)
    game.run()  # ICI on lance la boucle infinie
