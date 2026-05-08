"""
Pokemon New Horizon — API serveur (Auth + Inventaire)

Prérequis SQL (à lancer une fois sur le serveur si pas déjà fait) :
─────────────────────────────────────────────────────────────────────
  ALTER TABLE inventory
    ADD UNIQUE KEY uq_account_item_pocket (account_id, item_db_symbol, pocket);

  -- player_data doit avoir account_id comme PRIMARY KEY (ou UNIQUE)
  -- ALTER TABLE player_data ADD PRIMARY KEY (account_id);
─────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
from datetime import datetime, timedelta, timezone

import bcrypt
import mysql.connector
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{3,24}$")
SESSION_DURATION_DAYS = 7

app = FastAPI(title="Pokemon New Horizon API")


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "37.59.114.12"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "pokemon_new_horizon"),
        user=os.getenv("DB_USER", "server"),
        password=os.getenv("DB_PASSWORD", "1BbGNauPcu^ukbV$sH$$1znb"),
    )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def clean_username(username: str) -> str:
    return username.strip()


def validate_username(username: str) -> None:
    if not USERNAME_REGEX.fullmatch(username):
        raise HTTPException(
            status_code=400,
            detail="Pseudo invalide. Utilise 3 à 24 caractères : lettres, chiffres ou underscore."
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(account_id: int) -> dict:
    token = secrets.token_urlsafe(48)
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO sessions (account_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (account_id, token_hash, expires_at.replace(tzinfo=None)),
    )
    db.commit()
    cursor.close()
    db.close()

    return {"token": token, "expires_at": expires_at.isoformat()}


def require_auth(authorization: str = Header(...)) -> int:
    """
    Dépendance FastAPI : valide le header 'Authorization: Bearer <token>'
    et retourne account_id. Lève 401 si invalide ou expiré.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou mal formé.")
    token = authorization[7:]
    token_hash = hash_token(token)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT account_id, expires_at FROM sessions WHERE token_hash = %s",
        (token_hash,),
    )
    row = cursor.fetchone()
    cursor.close()
    db.close()

    if not row:
        raise HTTPException(status_code=401, detail="Session invalide.")
    if row["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expirée.")
    return int(row["account_id"])


def check_ownership(url_account_id: int, auth_account_id: int) -> None:
    """Empêche un joueur d'accéder aux données d'un autre compte."""
    if url_account_id != auth_account_id:
        raise HTTPException(status_code=403, detail="Accès refusé.")


def _json_load(value) -> dict | list:
    """Désérialise une valeur JSON qui peut être str ou déjà dict/list."""
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=8, max_length=72)


class TokenRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class InventoryFull(BaseModel):
    party: list[dict] = []
    bag:   list[dict] = []
    pc:    list[dict] = []   # [{box_number, slot, data}]


class PartySync(BaseModel):
    pokemons: list[dict]     # [{data, party_position, is_in_party}]


class PCSync(BaseModel):
    data:       dict
    box_number: int
    slot:       int
    is_in_party: bool = False


class ItemSync(BaseModel):
    item_db_symbol: str
    quantity:       int
    pocket:         str


class PlayerDataSync(BaseModel):
    money:     int   = 0
    badges:    list  = []
    play_time: float = 0.0


# ---------------------------------------------------------------------------
# Helpers réseau
# ---------------------------------------------------------------------------

def is_server_reachable(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


# ===========================================================================
# ROUTES AUTH (inchangées, sauf ajout de `token` au niveau racine)
# ===========================================================================

@app.get("/")
def index():
    return {"name": "Pokemon New Horizon API", "status": "online"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(data: AuthRequest):
    username = clean_username(data.username)
    validate_username(username)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM accounts WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close(); db.close()
        raise HTTPException(status_code=409, detail="Ce pseudo est déjà utilisé.")

    password_hash = hash_password(data.password)
    cursor.execute(
        "INSERT INTO accounts (username, password_hash) VALUES (%s, %s)",
        (username, password_hash),
    )
    db.commit()
    account_id = cursor.lastrowid
    cursor.close(); db.close()

    session = create_session(account_id)
    return {
        "ok": True,
        "message": "Compte créé.",
        "token": session["token"],          # ← exposé au niveau racine
        "account": {"id": account_id, "username": username},
        "session": session,
    }


@app.post("/login")
def login(data: AuthRequest):
    username = clean_username(data.username)
    validate_username(username)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, password_hash FROM accounts WHERE username = %s",
        (username,),
    )
    account = cursor.fetchone()
    if not account or not verify_password(data.password, account["password_hash"]):
        cursor.close(); db.close()
        raise HTTPException(status_code=401, detail="Pseudo ou mot de passe incorrect.")

    cursor.execute("UPDATE accounts SET last_login_at = NOW() WHERE id = %s", (account["id"],))
    db.commit()
    cursor.close(); db.close()

    session = create_session(account["id"])
    return {
        "ok": True,
        "message": "Connexion réussie.",
        "token": session["token"],          # ← exposé au niveau racine
        "account": {"id": account["id"], "username": account["username"]},
        "session": session,
    }


@app.post("/me")
def me(data: TokenRequest):
    token_hash = hash_token(data.token)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT accounts.id, accounts.username, sessions.expires_at
        FROM sessions
        JOIN accounts ON accounts.id = sessions.account_id
        WHERE sessions.token_hash = %s
        """,
        (token_hash,),
    )
    row = cursor.fetchone()
    cursor.close(); db.close()

    if not row:
        raise HTTPException(status_code=401, detail="Session invalide.")
    if row["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expirée.")

    return {"ok": True, "account": {"id": row["id"], "username": row["username"]}}


@app.get("/servers")
def servers():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name, host, port, online FROM servers ORDER BY id ASC")
    rows = cursor.fetchall()
    cursor.close(); db.close()

    result = []
    for row in rows:
        admin_enabled = bool(row["online"])
        real_online   = is_server_reachable(row["host"], row["port"]) if admin_enabled else False
        result.append({
            "id":            row["id"],
            "name":          row["name"],
            "host":          row["host"],
            "port":          row["port"],
            "online":        real_online,
            "enabled":       admin_enabled,
            "websocket_url": f"ws://{row['host']}:{row['port']}",
        })
    return {"ok": True, "servers": result}


# ===========================================================================
# ROUTES INVENTAIRE
# ===========================================================================

# ---------------------------------------------------------------------------
# GET  /accounts/{id}/inventory/full   — charge tout depuis MySQL
# ---------------------------------------------------------------------------

@app.get("/accounts/{account_id}/inventory/full")
def get_inventory_full(account_id: int, auth_id: int = Depends(require_auth)):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT data, is_in_party, party_position, box_number
        FROM pokemons
        WHERE account_id = %s
        ORDER BY is_in_party DESC, party_position ASC
        """,
        (account_id,),
    )
    pokemon_rows = cursor.fetchall()

    cursor.execute(
        "SELECT item_db_symbol, quantity, pocket FROM inventory WHERE account_id = %s",
        (account_id,),
    )
    item_rows = cursor.fetchall()

    cursor.close(); db.close()

    # ── Équipe ──────────────────────────────────────────────────────────
    party = []
    for row in pokemon_rows:
        if row["is_in_party"]:
            party.append(_json_load(row["data"]))

    # ── PC ──────────────────────────────────────────────────────────────
    pc = []
    for row in pokemon_rows:
        if not row["is_in_party"]:
            data = _json_load(row["data"])
            slot = data.pop("_pc_slot", 0)   # slot embarqué dans le JSON
            pc.append({
                "box_number": row["box_number"] or 0,
                "slot":       slot,
                "data":       data,
            })

    # ── Sac ─────────────────────────────────────────────────────────────
    bag = [
        {
            "item_db_symbol": r["item_db_symbol"],
            "quantity":       r["quantity"],
            "pocket":         r["pocket"],
        }
        for r in item_rows
    ]

    print(f"[API] GET inventory/full account={account_id} "
          f"— équipe:{len(party)} PC:{len(pc)} sac:{len(bag)}")
    return {"party": party, "bag": bag, "pc": pc}


# ---------------------------------------------------------------------------
# POST /accounts/{id}/inventory/full   — sauvegarde complète (bulk)
# ---------------------------------------------------------------------------

@app.post("/accounts/{account_id}/inventory/full")
def post_inventory_full(
    account_id: int,
    body: InventoryFull,
    auth_id: int = Depends(require_auth),
):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor()

    try:
        # ── Pokémon ─────────────────────────────────────────────────────
        cursor.execute("DELETE FROM pokemons WHERE account_id = %s", (account_id,))

        for i, poke_data in enumerate(body.party):
            cursor.execute(
                """
                INSERT INTO pokemons (account_id, data, is_in_party, party_position, box_number)
                VALUES (%s, %s, TRUE, %s, NULL)
                """,
                (account_id, json.dumps(poke_data), i),
            )

        for entry in body.pc:
            poke_data = dict(entry.get("data", {}))
            poke_data["_pc_slot"] = entry.get("slot", 0)
            cursor.execute(
                """
                INSERT INTO pokemons (account_id, data, is_in_party, party_position, box_number)
                VALUES (%s, %s, FALSE, NULL, %s)
                """,
                (account_id, json.dumps(poke_data), entry.get("box_number", 0)),
            )

        # ── Sac ─────────────────────────────────────────────────────────
        cursor.execute("DELETE FROM inventory WHERE account_id = %s", (account_id,))

        for item in body.bag:
            cursor.execute(
                """
                INSERT INTO inventory (account_id, item_db_symbol, quantity, pocket)
                VALUES (%s, %s, %s, %s)
                """,
                (account_id, item["item_db_symbol"], item["quantity"], item["pocket"]),
            )

        db.commit()
        print(f"[API] POST inventory/full account={account_id} "
              f"— équipe:{len(body.party)} PC:{len(body.pc)} sac:{len(body.bag)}")

    except Exception as exc:
        db.rollback()
        print(f"[API] ERREUR inventory/full: {exc}")
        raise HTTPException(status_code=500, detail=f"Erreur de sauvegarde : {exc}")
    finally:
        cursor.close(); db.close()

    return {"ok": True, "message": "Inventaire sauvegardé."}


# ---------------------------------------------------------------------------
# POST /accounts/{id}/party   — sync équipe seule (capture / soin / échange)
# ---------------------------------------------------------------------------

@app.post("/accounts/{account_id}/party")
def sync_party(
    account_id: int,
    body: PartySync,
    auth_id: int = Depends(require_auth),
):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM pokemons WHERE account_id = %s AND is_in_party = TRUE",
            (account_id,),
        )
        for entry in body.pokemons:
            cursor.execute(
                """
                INSERT INTO pokemons (account_id, data, is_in_party, party_position, box_number)
                VALUES (%s, %s, TRUE, %s, NULL)
                """,
                (account_id, json.dumps(entry.get("data", {})), entry.get("party_position", 0)),
            )
        db.commit()
        print(f"[API] sync_party account={account_id} — {len(body.pokemons)} Pokémon")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur sync équipe : {exc}")
    finally:
        cursor.close(); db.close()

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /accounts/{id}/pc   — ajoute un Pokémon au PC (capture overflow)
# ---------------------------------------------------------------------------

@app.post("/accounts/{account_id}/pc")
def sync_pc_pokemon(
    account_id: int,
    body: PCSync,
    auth_id: int = Depends(require_auth),
):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor()

    try:
        poke_data = dict(body.data)
        poke_data["_pc_slot"] = body.slot
        cursor.execute(
            """
            INSERT INTO pokemons (account_id, data, is_in_party, party_position, box_number)
            VALUES (%s, %s, FALSE, NULL, %s)
            """,
            (account_id, json.dumps(poke_data), body.box_number),
        )
        db.commit()
        print(f"[API] sync_pc_pokemon account={account_id} box={body.box_number} slot={body.slot}")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur sync PC : {exc}")
    finally:
        cursor.close(); db.close()

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /accounts/{id}/inventory   — upsert un objet du sac
# ---------------------------------------------------------------------------

@app.post("/accounts/{account_id}/inventory")
def sync_item(
    account_id: int,
    body: ItemSync,
    auth_id: int = Depends(require_auth),
):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor()

    try:
        # ON DUPLICATE KEY nécessite UNIQUE (account_id, item_db_symbol, pocket)
        cursor.execute(
            """
            INSERT INTO inventory (account_id, item_db_symbol, quantity, pocket)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = %s
            """,
            (account_id, body.item_db_symbol, body.quantity, body.pocket, body.quantity),
        )
        db.commit()
        print(f"[API] sync_item account={account_id} {body.item_db_symbol} ×{body.quantity} ({body.pocket})")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur sync item : {exc}")
    finally:
        cursor.close(); db.close()

    return {"ok": True}


# ---------------------------------------------------------------------------
# DELETE /accounts/{id}/inventory/{item}   — supprime un objet à 0
# ---------------------------------------------------------------------------

@app.delete("/accounts/{account_id}/inventory/{item_db_symbol}")
def delete_item(
    account_id: int,
    item_db_symbol: str,
    pocket: str,
    auth_id: int = Depends(require_auth),
):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM inventory
            WHERE account_id = %s AND item_db_symbol = %s AND pocket = %s
            """,
            (account_id, item_db_symbol, pocket),
        )
        db.commit()
        print(f"[API] delete_item account={account_id} {item_db_symbol} ({pocket})")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur suppression item : {exc}")
    finally:
        cursor.close(); db.close()

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /accounts/{id}/player_data   — argent, badges, temps de jeu
# ---------------------------------------------------------------------------

@app.post("/accounts/{account_id}/player_data")
def sync_player_data(
    account_id: int,
    body: PlayerDataSync,
    auth_id: int = Depends(require_auth),
):
    check_ownership(account_id, auth_id)

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO player_data (account_id, money, badges, play_time)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE money = %s, badges = %s, play_time = %s
            """,
            (
                account_id, body.money, json.dumps(body.badges), body.play_time,
                body.money, json.dumps(body.badges), body.play_time,
            ),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur sync player_data : {exc}")
    finally:
        cursor.close(); db.close()

    return {"ok": True}
