import pygame

from code.client.config import SFX_SETTINGS


class SoundManager:
    _sounds = {}

    @classmethod
    def load_all_sounds(cls):
        # 1. Forcer l'init du son s'il n'est pas prêt
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        if not cls._sounds:
            try:
                # 2. Charger le son (Vérifie bien que le chemin est correct !)
                path = SFX_SETTINGS["click"]
                cls._sounds["click"] = pygame.mixer.Sound(path)

                # 3. Appliquer le volume
                cls._sounds["click"].set_volume(SFX_SETTINGS["click_volume"])
                print(f"[SoundManager] SFX '{path}' chargé avec succès.")
            except Exception as e:
                print(f"[SoundManager] ERREUR chargement SFX : {e}")

    @classmethod
    def play(cls, name):
        sound = cls._sounds.get(name)
        if sound:
            sound.play()
        else:
            print(f"[SoundManager] Impossible de jouer '{name}' (non chargé).")