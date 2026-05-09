import requests


class AuthError(Exception):
    pass


class AuthClient:
    def __init__(self, api_url: str) -> None:
        self.api_url = api_url.rstrip("/")

    def register(self, username: str, password: str) -> dict:
        return self._post("/register", {
            "username": username,
            "password": password,
        })

    def login(self, username: str, password: str) -> dict:
        return self._post("/login", {
            "username": username,
            "password": password,
        })

    def get_servers(self) -> list[dict]:
        url = self.api_url + "/servers"

        try:
            response = requests.get(url, timeout=5)
        except requests.RequestException:
            raise AuthError("Impossible de contacter le serveur.")

        try:
            data = response.json()
        except ValueError:
            raise AuthError("Réponse invalide du serveur.")

        if response.status_code >= 400:
            raise AuthError(data.get("detail", "Erreur serveur."))

        return data.get("servers", [])

    def _post(self, path: str, payload: dict) -> dict:
        url = self.api_url + path

        try:
            response = requests.post(url, json=payload, timeout=5)
        except requests.RequestException:
            raise AuthError("Impossible de contacter le serveur.")

        try:
            data = response.json()
        except ValueError:
            raise AuthError("Réponse invalide du serveur.")

        if response.status_code >= 400:
            raise AuthError(data.get("detail", "Erreur inconnue."))

        return data