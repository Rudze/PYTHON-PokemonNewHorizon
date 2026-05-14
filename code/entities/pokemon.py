import json
import math
import random

from code.config import JSON_DIR
from code.entities.move import Move


class Pokemon:
    """
    Pokémon class to manage the Pokémons
    """
    def __init__(self, data, level: int) -> None:
        """
        Initialize the Pokémons
        :param data:
        :param level:
        """
        self.klass = data['klass']
        self.id = data['id']
        self.dbSymbol = data['dbSymbol']
        self.forms = data['forms']
        self.evolutions = self.forms[0]['evolutions']
        self.type = self.get_types()
        self.baseHp = self.forms[0]['baseHp']
        self.baseAtk = self.forms[0]['baseAtk']
        self.baseDfe = self.forms[0]['baseDfe']
        self.baseSpd = self.forms[0]['baseSpd']
        self.baseAts = self.forms[0]['baseAts']
        self.baseDfs = self.forms[0]['baseDfs']
        self.evHp = self.forms[0]['evHp']
        self.evAtk = self.forms[0]['evAtk']
        self.evDfe = self.forms[0]['evDfe']
        self.evSpd = self.forms[0]['evSpd']
        self.evAts = self.forms[0]['evAts']
        self.evDfs = self.forms[0]['evDfs']
        self.experienceType = self.forms[0]['experienceType']
        self.baseExperience = self.forms[0]['baseExperience']
        self.baseLoyalty = self.forms[0]['baseLoyalty']
        self.catchRate = self.forms[0]['catchRate']
        self.femaleRate = self.forms[0]['femaleRate']
        self.breedGroups = self.forms[0]['breedGroups']
        self.hatchSteps = self.forms[0]['hatchSteps']
        self.babyDbSymbol = self.forms[0]['babyDbSymbol']
        self.babyForm = self.forms[0]['babyForm']
        self.itemHeld = self.forms[0]['itemHeld']
        self.abilities = self.forms[0]['abilities']
        self.frontOffsetY = self.forms[0]['frontOffsetY']
        self.resources = self.forms[0]['resources']
        self.moveSet = self.forms[0]['moveSet']

        self.level = level
        self.gender = "female" if random.randint(1, 100) <= self.femaleRate else "male"
        if self.femaleRate == -1:
            self.gender = "genderless"
        self.ivs = {key: random.randint(1, 31) for key in self.get_base_stats().keys()}
        self.base_stats = self.get_base_stats()

        self.maxhp = self.update_stats("hp")
        self.hp = self.update_stats("hp")
        self.atk = self.update_stats("atk")
        self.dfe = self.update_stats("dfe")
        self.ats = self.update_stats("ats")
        self.dfs = self.update_stats("dfs")
        self.spd = self.update_stats("spd")

        self.shiny = "shiny" if random.randint(1, 10) == 1 else ""
        self.xp = Pokemon._calc_xp_for_level(level, self.experienceType)
        self.points_ev = 0

        self.moves: list[Move] = self.set_moves()
        self.status = ""

        self.xp_to_next_level = self.xp_to_next_level()

        self.evolution = None

        # Files d'attente pour le flux d'apprentissage en overworld.
        # Uniquement peuplés par des appels explicites (admin, gain XP overworld).
        # Le battle_screen gère son propre affichage ; ces listes restent vides
        # lors des montées de niveau en combat.
        self.newly_learned: list[str] = []   # attaques apprises normalement
        self.pending_moves:  list[str] = []  # attaques en attente (4 attaques déjà)

    def get_types(self):
        """
        Get the types of the Pokémon
        :return:
        """
        type1 = self.forms[0]['type1']
        type2 = self.forms[0]['type2']
        if type2 == "__undef__":
            return [type1]
        return [type1, type2]

    def get_base_stats(self):
        """
        Get the base stats of the Pokémon
        :return:
        """
        return {
            "hp": self.forms[0]['baseHp'],
            "atk": self.forms[0]['baseAtk'],
            "dfe": self.forms[0]['baseDfe'],
            "spd": self.forms[0]['baseSpd'],
            "ats": self.forms[0]['baseAts'],
            "dfs": self.forms[0]['baseDfs'],
        }

    def update_stats(self, stat):
        """
        Update the stats of the Pokémon
        :param stat:
        :return:
        """
        base_stat = self.get_base_stats()[stat]
        iv = self.ivs[stat]
        ev = self.get_ev()[stat]
        level = self.level
        nature = 1.0
        if stat == "hp":
            return math.floor((2 * base_stat + iv + math.floor(ev / 4)) * level / 100) + level + 10
        return math.floor((math.floor((2 * base_stat + iv + math.floor(ev / 4)) * level / 100) + 5) * nature)

    @staticmethod
    def _calc_xp_for_level(level: int, experience_type: int) -> int:
        """XP totale cumulée requise pour atteindre 'level'."""
        if level <= 1:
            return 0
        if level >= 100:
            level = 100
        if experience_type == 0:   # Medium Fast (cubique)
            return level ** 3
        elif experience_type == 1:  # Medium Slow
            return math.floor((4 * (level ** 3)) / 5)
        elif experience_type == 2:  # Slow
            return math.floor(5 * (level ** 3) / 4)
        elif experience_type == 3:  # Erratic
            return math.floor(((6 / 5) * (level ** 3)) - (15 * (level ** 2)) + (100 * level) - 140)
        elif experience_type == 4:  # Fluctuating
            if level <= 50:
                return math.floor((level ** 3) * (100 - level) / 50)
            elif level <= 68:
                return math.floor((level ** 3) * (150 - level) / 100)
            elif level <= 98:
                return math.floor((level ** 3) * math.floor((1911 - 10 * level) / 3) / 500)
            else:
                return math.floor((level ** 3) * (160 - level) / 100)
        return level ** 3

    def xp_to_next_level(self):
        """Rétro-compatibilité — retourne le seuil XP du niveau actuel."""
        return Pokemon._calc_xp_for_level(self.level, self.experienceType)

    def xp_progress(self) -> tuple[int, int]:
        """Retourne (XP gagnée depuis le dernier niveau, XP nécessaire pour le prochain)."""
        if self.level >= 100:
            return 0, 1
        xp_this  = Pokemon._calc_xp_for_level(self.level,     self.experienceType)
        xp_next  = Pokemon._calc_xp_for_level(self.level + 1, self.experienceType)
        return max(0, self.xp - xp_this), max(1, xp_next - xp_this)

    def check_level_ups(self) -> tuple[list[str], list[str]]:
        """
        Vérifie si l'XP accumulée permet un ou plusieurs montées de niveau.

        Retourne (learned, pending) :
          learned : attaques apprises directement (< 4 attaques au moment de la montée)
          pending : attaques qui ne peuvent pas être apprises (4 attaques déjà) —
                    le appelant décide d'afficher ou non un menu de remplacement.
        """
        learned: list[str] = []
        pending: list[str] = []
        while self.level < 100:
            xp_needed = Pokemon._calc_xp_for_level(self.level + 1, self.experienceType)
            if self.xp < xp_needed:
                break
            self.level += 1
            old_maxhp  = self.maxhp
            self.maxhp = self.update_stats("hp")
            self.hp    = min(self.hp + (self.maxhp - old_maxhp), self.maxhp)
            self.atk   = self.update_stats("atk")
            self.dfe   = self.update_stats("dfe")
            self.ats   = self.update_stats("ats")
            self.dfs   = self.update_stats("dfs")
            self.spd   = self.update_stats("spd")
            self.xp_to_next_level = Pokemon._calc_xp_for_level(self.level, self.experienceType)
            for entry in self.moveSet:
                if entry.get("level") == self.level:
                    if len(self.moves) < 4:
                        try:
                            new_move = Move.createMove(entry["move"])
                            self.moves.append(new_move)
                            learned.append(new_move.dbSymbol)
                        except Exception:
                            pass
                    else:
                        pending.append(entry["move"])
        return learned, pending

    def set_moves(self):
        """
        Set the moves of the Pokémon
        :return:
        """
        list_move: list[dict] = []
        list_attack: list[Move] = []
        for move in self.moveSet:
            try:
                if move['level'] <= self.level:
                    list_move.append(move)
            except (KeyError, TypeError):
                pass
        minimum = 2
        if len(list_move) < minimum:
            minimum = len(list_move)
        maximum = 4
        if len(list_move) < 4:
            maximum = len(list_move)
        for i in range(random.randint(minimum, maximum)):
            chosen = random.choice(list_move)
            list_move.remove(chosen)
            list_attack.append(Move.createMove(chosen['move']))
        return list_attack

    def get_ev(self):
        """
        Get the effort values of the Pokémon
        :return:
        """
        return {
            "hp": self.forms[0]["evHp"],
            "atk": self.forms[0]["evAtk"],
            "dfe": self.forms[0]["evDfe"],
            "ats": self.forms[0]["evAts"],
            "dfs": self.forms[0]["evDfs"],
            "spd": self.forms[0]["evSpd"]
        }

    def to_dict(self):
        """
        Convertir l'objet Pokémon en dictionnaire sérialisable.
        :return: dict
        """
        return {
            'klass': self.klass,
            'id': self.id,
            'dbSymbol': self.dbSymbol,
            'forms': self.forms,
            'type': self.type,
            'level': self.level,
            'gender': self.gender,
            'ivs': self.ivs,
            'base_stats': self.base_stats,
            'maxhp': self.maxhp,
            'hp': self.hp,
            'atk': self.atk,
            'dfe': self.dfe,
            'ats': self.ats,
            'dfs': self.dfs,
            'spd': self.spd,
            'shiny': self.shiny,
            'xp': self.xp,
            'points_ev': self.points_ev,
            'moves': [move.to_dict() for move in self.moves],
            'status': self.status,
            'xp_to_next_level': self.xp_to_next_level,
            'evolution': self.evolution
        }

    @staticmethod
    def from_dict(data: dict) -> "Pokemon":
        """
        Create a Pokémon from a dictionary
        """
        pokemon = Pokemon.__new__(Pokemon)
        pokemon.__dict__.update(data)
        pokemon.moves = [Move.from_dict(move_data) for move_data in data["moves"]]
        # Restore form-derived attributes absent de to_dict()
        f = pokemon.forms[0] if getattr(pokemon, "forms", None) else {}
        pokemon.evolutions    = f.get("evolutions", [])
        pokemon.experienceType = f.get("experienceType", 0)
        pokemon.baseExperience = f.get("baseExperience", 100)
        pokemon.baseLoyalty   = f.get("baseLoyalty", 70)
        pokemon.catchRate     = f.get("catchRate", 45)
        pokemon.femaleRate    = f.get("femaleRate", 50)
        pokemon.breedGroups   = f.get("breedGroups", [])
        pokemon.hatchSteps    = f.get("hatchSteps", 0)
        pokemon.babyDbSymbol  = f.get("babyDbSymbol", "__undef__")
        pokemon.babyForm      = f.get("babyForm", 0)
        pokemon.itemHeld      = f.get("itemHeld", [])
        pokemon.abilities     = f.get("abilities", [])
        pokemon.frontOffsetY  = f.get("frontOffsetY", 0)
        pokemon.resources     = f.get("resources", {})
        pokemon.moveSet       = f.get("moveSet", [])
        # Attributs runtime non sérialisés — toujours réinitialiser après from_dict
        pokemon.newly_learned = []
        pokemon.pending_moves = []
        return pokemon

    @staticmethod
    def create_from_id(pokemon_id: int, level: int) -> "Pokemon":
        """Create a Pokémon from its national Pokédex ID."""
        all_pokemon = json.load(open(str(JSON_DIR / "pokemon_data.json")))
        entry = all_pokemon.get(str(pokemon_id))
        if entry is None:
            raise ValueError(f"Pokémon id={pokemon_id} introuvable dans pokemon_data.json")
        types = entry["types"]
        stats = entry["stats"]
        forms = [{
            "type1":          types[0] if types else "normal",
            "type2":          types[1] if len(types) > 1 else "__undef__",
            "baseHp":         stats["hp"],
            "baseAtk":        stats["attack"],
            "baseDfe":        stats["defense"],
            "baseSpd":        stats["speed"],
            "baseAts":        stats["sp_attack"],
            "baseDfs":        stats["sp_defense"],
            "evHp": 0, "evAtk": 0, "evDfe": 0,
            "evSpd": 0, "evAts": 0, "evDfs": 0,
            "experienceType": 0,
            "baseExperience": entry.get("base_experience", 100),
            "baseLoyalty":    70,
            "catchRate":      entry.get("capture_rate", 45),
            "femaleRate":     50,
            "breedGroups":    [],
            "hatchSteps":     0,
            "babyDbSymbol":   "__undef__",
            "babyForm":       0,
            "itemHeld":       [],
            "abilities":      [a["name"] for a in entry.get("abilities", []) if not a.get("hidden")],
            "frontOffsetY":   0,
            "resources":      {},
            "moveSet":        entry.get("learnset", []),
            "evolutions":     [],
        }]
        legacy = {
            "klass":    "Pokemon",
            "id":       entry["id"],
            "dbSymbol": entry["name"],
            "forms":    forms,
        }
        return Pokemon(legacy, level)

    @staticmethod
    def create_pokemon(name: str, level: int) -> "Pokemon":
        """
        Create a Pokémon from the name
        :param name:
        :param level:
        :return:
        """
        all_pokemon = json.load(open(str(JSON_DIR / "pokemon_data.json")))
        name_lower = name.lower()
        entry = next(
            (p for p in all_pokemon.values()
             if p["name"].lower() == name_lower
             or p.get("name_fr", "").lower() == name_lower),
            None,
        )
        if entry is None:
            raise ValueError(f"Pokémon '{name}' introuvable dans pokemon_data.json")

        types = entry["types"]
        stats = entry["stats"]
        forms = [{
            "type1":          types[0] if types else "normal",
            "type2":          types[1] if len(types) > 1 else "__undef__",
            "baseHp":         stats["hp"],
            "baseAtk":        stats["attack"],
            "baseDfe":        stats["defense"],
            "baseSpd":        stats["speed"],
            "baseAts":        stats["sp_attack"],
            "baseDfs":        stats["sp_defense"],
            "evHp": 0, "evAtk": 0, "evDfe": 0,
            "evSpd": 0, "evAts": 0, "evDfs": 0,
            "experienceType": 0,
            "baseExperience": 100,
            "baseLoyalty":    70,
            "catchRate":      45,
            "femaleRate":     50,
            "breedGroups":    [],
            "hatchSteps":     0,
            "babyDbSymbol":   "__undef__",
            "babyForm":       0,
            "itemHeld":       [],
            "abilities":      [a["name"] for a in entry.get("abilities", []) if not a.get("hidden")],
            "frontOffsetY":   0,
            "resources":      {},
            "moveSet":        entry.get("learnset", []),
            "evolutions":     [],
        }]
        legacy = {
            "klass":    "Pokemon",
            "id":       entry["id"],
            "dbSymbol": entry["name"],
            "forms":    forms,
        }
        return Pokemon(legacy, level)
