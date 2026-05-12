from __future__ import annotations

import requests


class GameApiClient:
    """
    Handles all game-data API calls (inventory, Pokémon, player_data).
    Authentication token is obtained from the login flow and passed in.

    All methods are fire-and-forget: failures are logged but never crash the game.
    """

    def __init__(self, api_url: str, token: str) -> None:
        self.api_url = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------
    # Customisation du personnage
    # ------------------------------------------------------------------

    def get_character(self, account_id: int) -> dict | None:
        return self._get(f"/accounts/{account_id}/character")

    def save_character(self, account_id: int, customization: dict) -> dict | None:
        return self._post(f"/accounts/{account_id}/character", customization)

    # ------------------------------------------------------------------
    # Party
    # ------------------------------------------------------------------

    def sync_party(self, account_id: int, payload: list[dict]) -> None:
        """
        payload = [{"data": <pokemon_dict>, "party_position": int, "is_in_party": True}, ...]
        Replaces the full party on the server side.
        """
        self._post(f"/accounts/{account_id}/party", {"pokemons": payload})

    # ------------------------------------------------------------------
    # PC
    # ------------------------------------------------------------------

    def sync_pc_pokemon(self, account_id: int, pokemon_data: dict, box: int, slot: int) -> None:
        self._post(f"/accounts/{account_id}/pc", {
            "data": pokemon_data,
            "box_number": box,
            "slot": slot,
            "is_in_party": False,
        })

    # ------------------------------------------------------------------
    # Bag / Inventory
    # ------------------------------------------------------------------

    def sync_item(self, account_id: int, item_db_symbol: str, quantity: int, pocket: str) -> None:
        """Upsert a single item row."""
        self._post(f"/accounts/{account_id}/inventory", {
            "item_db_symbol": item_db_symbol,
            "quantity": quantity,
            "pocket": pocket,
        })

    def delete_item(self, account_id: int, item_db_symbol: str, pocket: str) -> None:
        """Remove an item that reached quantity 0."""
        try:
            r = requests.delete(
                f"{self.api_url}/accounts/{account_id}/inventory/{item_db_symbol}",
                params={"pocket": pocket},
                headers=self._headers,
                timeout=5,
            )
            r.raise_for_status()
        except Exception as exc:
            print(f"[GameAPI] delete_item failed: {exc}")

    # ------------------------------------------------------------------
    # Full inventory (load & bulk save)
    # ------------------------------------------------------------------

    def load_inventory(self, account_id: int) -> dict | None:
        """Returns {party, bag, pc} or None on error."""
        return self._get(f"/accounts/{account_id}/inventory/full")

    def sync_full_inventory(self, account_id: int, data: dict) -> dict | None:
        """Bulk-save everything at once. Returns API response dict or None on failure."""
        return self._post(f"/accounts/{account_id}/inventory/full", data)

    # ------------------------------------------------------------------
    # Player data (money, badges, play_time)
    # ------------------------------------------------------------------

    def sync_player_data(self, account_id: int, money: int, badges: list, play_time: float) -> None:
        self._post(f"/accounts/{account_id}/player_data", {
            "money": money,
            "badges": badges,
            "play_time": play_time,
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict | None:
        try:
            r = requests.post(self.api_url + path, json=payload, headers=self._headers, timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            print(f"[GameAPI] POST {path} failed: {exc}")
            return None

    def _get(self, path: str) -> dict | None:
        try:
            r = requests.get(self.api_url + path, headers=self._headers, timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            print(f"[GameAPI] GET {path} failed: {exc}")
            return None
