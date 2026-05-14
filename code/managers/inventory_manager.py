from __future__ import annotations

from code.entities.pokemon import Pokemon

PARTY_MAX = 6
PC_BOX_SIZE = 30
PC_MAX_BOXES = 30

POCKET_ITEMS = "items"
POCKET_POKEBALLS = "pokeballs"
POCKET_TM_HM = "tm_hm"
POCKET_KEY_ITEMS = "key_items"
ALL_POCKETS = (POCKET_ITEMS, POCKET_POKEBALLS, POCKET_TM_HM, POCKET_KEY_ITEMS)


class BagItem:
    def __init__(self, item_db_symbol: str, quantity: int, pocket: str,
                 slot_index: int | None = None) -> None:
        self.item_db_symbol = item_db_symbol
        self.quantity = quantity
        self.pocket = pocket
        self.slot_index = slot_index


class Bag:
    def __init__(self) -> None:
        self.pockets: dict[str, list[BagItem]] = {p: [] for p in ALL_POCKETS}

    def add(self, item_db_symbol: str, pocket: str, quantity: int = 1) -> None:
        for item in self.pockets[pocket]:
            if item.item_db_symbol == item_db_symbol:
                item.quantity += quantity
                return
        self.pockets[pocket].append(BagItem(item_db_symbol, quantity, pocket))

    def remove(self, item_db_symbol: str, pocket: str, quantity: int = 1) -> bool:
        for item in self.pockets[pocket]:
            if item.item_db_symbol == item_db_symbol:
                if item.quantity < quantity:
                    return False
                item.quantity -= quantity
                if item.quantity == 0:
                    self.pockets[pocket].remove(item)
                return True
        return False

    def get_quantity(self, item_db_symbol: str, pocket: str) -> int:
        for item in self.pockets[pocket]:
            if item.item_db_symbol == item_db_symbol:
                return item.quantity
        return 0

    def to_dict(self) -> list[dict]:
        result = []
        for pocket, items in self.pockets.items():
            for item in items:
                entry: dict = {
                    "item_db_symbol": item.item_db_symbol,
                    "quantity": item.quantity,
                    "pocket": pocket,
                }
                if item.slot_index is not None:
                    entry["slot_index"] = item.slot_index
                result.append(entry)
        return result

    @staticmethod
    def from_dict(data: list[dict]) -> "Bag":
        bag = Bag()
        for entry in data:
            pocket = entry["pocket"]
            if pocket in bag.pockets:
                bag.pockets[pocket].append(
                    BagItem(entry["item_db_symbol"], entry["quantity"], pocket,
                            entry.get("slot_index"))
                )
        return bag


class PC:
    def __init__(self) -> None:
        # box_number -> list of PC_BOX_SIZE slots (None = empty)
        self.boxes: dict[int, list[Pokemon | None]] = {}

    def _get_or_create_box(self, box_number: int) -> list[Pokemon | None]:
        if box_number not in self.boxes:
            self.boxes[box_number] = [None] * PC_BOX_SIZE
        return self.boxes[box_number]

    def add(self, pokemon: Pokemon) -> tuple[int, int]:
        """Place pokemon in the first free slot. Returns (box_number, slot)."""
        for box_num in range(PC_MAX_BOXES):
            box = self._get_or_create_box(box_num)
            for slot, occupant in enumerate(box):
                if occupant is None:
                    box[slot] = pokemon
                    return box_num, slot
        raise RuntimeError("Le PC est plein !")

    def remove(self, box_number: int, slot: int) -> Pokemon | None:
        box = self.boxes.get(box_number)
        if box is None or slot >= len(box):
            return None
        pokemon = box[slot]
        box[slot] = None
        return pokemon

    def get(self, box_number: int, slot: int) -> Pokemon | None:
        box = self.boxes.get(box_number)
        if box is None or slot >= len(box):
            return None
        return box[slot]

    def to_dict(self) -> list[dict]:
        result = []
        for box_num, box in self.boxes.items():
            for slot, pokemon in enumerate(box):
                if pokemon is not None:
                    result.append({
                        "box_number": box_num,
                        "slot": slot,
                        "data": pokemon.to_dict(),
                    })
        return result

    @staticmethod
    def from_dict(data: list[dict]) -> "PC":
        pc = PC()
        for entry in data:
            box_num = entry["box_number"]
            slot = entry["slot"]
            box = pc._get_or_create_box(box_num)
            box[slot] = Pokemon.from_dict(entry["data"])
        return pc


class InventoryManager:
    """
    Central manager for party (6 slots), bag (pockets), and PC (boxed Pokémon).

    Pass api_client (GameApiClient) and account_id to enable auto-sync.
    Leave api_client=None for local-only / debug mode.
    """

    def __init__(self, party: list[Pokemon], api_client=None, account_id: int | None = None) -> None:
        # party is a shared reference to player.pokemons so both stay in sync.
        self.party = party
        self.bag = Bag()
        self.pc = PC()
        self.api_client = api_client
        self.account_id = account_id

    # ------------------------------------------------------------------
    # Party
    # ------------------------------------------------------------------

    def receive_pokemon(self, pokemon: Pokemon) -> str:
        """
        Add a caught/received Pokémon.
        Returns 'party' if added to the team, 'pc' if the party was full.
        """
        if len(self.party) < PARTY_MAX:
            self.party.append(pokemon)
            self._sync_party()
            return "party"

        box, slot = self.pc.add(pokemon)
        self._sync_pc_pokemon(pokemon, box, slot)
        return "pc"

    def move_from_pc_to_party(self, box_number: int, slot: int) -> bool:
        """Pull a Pokémon out of the PC into the party if there is room."""
        if len(self.party) >= PARTY_MAX:
            return False
        pokemon = self.pc.remove(box_number, slot)
        if pokemon is None:
            return False
        self.party.append(pokemon)
        self._sync_party()
        return True

    def move_from_party_to_pc(self, party_index: int) -> bool:
        """Send a party Pokémon to the PC (keeps at least 1 Pokémon in party)."""
        if len(self.party) <= 1 or party_index >= len(self.party):
            return False
        pokemon = self.party.pop(party_index)
        self.pc.add(pokemon)
        self._sync_party()
        return True

    def heal_party(self) -> None:
        for pokemon in self.party:
            pokemon.hp = pokemon.maxhp
            pokemon.status = ""
        self._sync_party()

    # ------------------------------------------------------------------
    # Bag
    # ------------------------------------------------------------------

    def add_item(self, item_db_symbol: str, pocket: str, quantity: int = 1) -> None:
        self.bag.add(item_db_symbol, pocket, quantity)
        self._sync_item(item_db_symbol, pocket)

    def add_item_with_slot(self, item_db_symbol: str, pocket: str, quantity: int = 1) -> int | None:
        """
        Ajoute un item ET lui assigne le premier slot HUD libre (0-19).
        Retourne le slot_index assigné, ou None si l'inventaire HUD est plein.
        Si l'item existe déjà (avec un slot), incrémente juste la quantité.
        """
        existing = self._find_item_in_pocket(item_db_symbol, pocket)
        if existing:
            existing.quantity += quantity
            self._sync_item(item_db_symbol, pocket)
            return existing.slot_index

        used = {item.slot_index for items in self.bag.pockets.values()
                for item in items if item.slot_index is not None}
        free_slot = next((i for i in range(20) if i not in used), None)

        new_item = BagItem(item_db_symbol, quantity, pocket, free_slot)
        self.bag.pockets[pocket].append(new_item)
        self._sync_item(item_db_symbol, pocket)
        return free_slot

    def use_item(self, item_db_symbol: str, pocket: str, quantity: int = 1) -> bool:
        if not self.bag.remove(item_db_symbol, pocket, quantity):
            return False
        self._sync_item(item_db_symbol, pocket)
        return True

    def swap_hud_slots(self, slot_a: int, slot_b: int) -> None:
        """Échange les slot_index de deux items dans le HUD et synchronise avec l'API."""
        item_a = self._find_item_by_slot(slot_a)
        item_b = self._find_item_by_slot(slot_b)
        if item_a is None and item_b is None:
            return
        if item_a:
            item_a.slot_index = slot_b
        if item_b:
            item_b.slot_index = slot_a
        updates = []
        if item_a:
            updates.append({"item_db_symbol": item_a.item_db_symbol,
                            "pocket": item_a.pocket, "slot_index": slot_b})
        if item_b:
            updates.append({"item_db_symbol": item_b.item_db_symbol,
                            "pocket": item_b.pocket, "slot_index": slot_a})
        if updates and self.api_client and self.account_id:
            self.api_client.update_item_slots(self.account_id, updates)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "party": [p.to_dict() for p in self.party],
            "bag": self.bag.to_dict(),
            "pc": self.pc.to_dict(),
        }

    def load_from_dict(self, data: dict) -> None:
        """Restore state from a dict (API response or save file). Symmetric with to_dict()."""
        self.party.clear()
        party_data = data.get("party", [])
        for p in party_data:
            try:
                pokemon = Pokemon.from_dict(p)
                pokemon.check_level_ups()   # traite les XP accumulées pendant l'offline
                self.party.append(pokemon)
            except Exception as exc:
                print(f"[INV] load_from_dict: erreur reconstruction Pokémon équipe — {exc}")

        self.bag = Bag.from_dict(data.get("bag", []))
        self.pc = PC.from_dict(data.get("pc", []))

    def load_from_api(self) -> bool:
        """
        Load inventory from the API. Returns True on success.
        Safe to call even when api_client is None (no-op, returns False).
        """
        if self.api_client is None or self.account_id is None:
            print("[INV] load_from_api: pas de client API configuré (mode local).")
            return False
        print(f"[INV] Chargement depuis l'API (account_id={self.account_id})...")
        data = self.api_client.load_inventory(self.account_id)
        if not data:
            print("[INV] ERREUR: réponse vide ou API inaccessible.")
            return False
        self.load_from_dict(data)
        print(
            f"[INV] Chargé — équipe: {len(self.party)} Pokémon | "
            f"sac: {sum(len(v) for v in self.bag.pockets.values())} lignes | "
            f"PC: {sum(1 for b in self.pc.boxes.values() for p in b if p)} Pokémon"
        )
        return True

    def reload_from_api(self) -> bool:
        """
        Force-reload: wipes local state then fetches fresh data from API.
        Used by the [FORCE SYNC] debug button.
        """
        print("[INV] FORCE SYNC — réinitialisation locale puis rechargement API...")
        self.party.clear()
        self.bag = Bag()
        self.pc = PC()
        return self.load_from_api()

    def save_all(self) -> bool:
        """
        Bulk-save everything to the API. Returns True on success.
        Blocks for up to 5 s (requests timeout).
        """
        if self.api_client is None or self.account_id is None:
            print("[INV] save_all: pas de client API (mode local, rien envoyé).")
            return False
        print(f"[INV] Sauvegarde complète vers l'API (account_id={self.account_id})...")
        ok = self.api_client.sync_full_inventory(self.account_id, self.to_dict())
        if ok is not None:
            print("[INV] Sauvegarde API : OK")
            return True
        print("[INV] ERREUR: échec de la sauvegarde API.")
        return False

    # ------------------------------------------------------------------
    # Internal sync helpers
    # ------------------------------------------------------------------

    def sync_party(self) -> None:
        """Envoie l'état actuel de l'équipe à l'API (HP, XP, PP, etc.)."""
        if self.api_client is None or self.account_id is None:
            return
        payload = [
            {"data": p.to_dict(), "party_position": i, "is_in_party": True}
            for i, p in enumerate(self.party)
        ]
        self.api_client.sync_party(self.account_id, payload)

    def _sync_party(self) -> None:
        self.sync_party()

    def _sync_pc_pokemon(self, pokemon: Pokemon, box: int, slot: int) -> None:
        if self.api_client is None or self.account_id is None:
            return
        self.api_client.sync_pc_pokemon(self.account_id, pokemon.to_dict(), box, slot)

    def _find_item_in_pocket(self, item_db_symbol: str, pocket: str) -> "BagItem | None":
        for item in self.bag.pockets.get(pocket, []):
            if item.item_db_symbol == item_db_symbol:
                return item
        return None

    def _find_item_by_slot(self, slot_index: int) -> "BagItem | None":
        for pocket_items in self.bag.pockets.values():
            for item in pocket_items:
                if item.slot_index == slot_index:
                    return item
        return None

    def _sync_item(self, item_db_symbol: str, pocket: str) -> None:
        if self.api_client is None or self.account_id is None:
            return
        item = self._find_item_in_pocket(item_db_symbol, pocket)
        quantity = item.quantity if item else 0
        slot_index = item.slot_index if item else None
        if quantity > 0:
            self.api_client.sync_item(self.account_id, item_db_symbol, quantity, pocket, slot_index)
        else:
            self.api_client.delete_item(self.account_id, item_db_symbol, pocket)
