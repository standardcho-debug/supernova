"""Per-client access tokens for the approval-queue frontend.

Not a real auth system: no login form, no password, no expiry, no way for
a client to revoke their own link. It is just enough that a client's queue
isn't reachable by guessing /clients/<client_id> in the URL — the minimum
bar for handing someone a link that points at their own business's
content and nobody else's. A real client-facing product needs proper auth
before this replaces "someone showing them the page over their shoulder".
"""
from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path


class ClientAccessStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_access (
                    client_id TEXT PRIMARY KEY,
                    token TEXT NOT NULL
                )
                """
            )

    def token_for(self, client_id: str) -> str:
        """Returns the client's existing token, minting one on first call."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT token FROM client_access WHERE client_id = ?", (client_id,)
            ).fetchone()
            if row:
                return row[0]
            token = secrets.token_urlsafe(16)
            conn.execute(
                "INSERT INTO client_access (client_id, token) VALUES (?, ?)",
                (client_id, token),
            )
            conn.commit()
            return token

    def verify(self, client_id: str, token: str | None) -> bool:
        if not token:
            return False
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT token FROM client_access WHERE client_id = ?", (client_id,)
            ).fetchone()
        return row is not None and secrets.compare_digest(row[0], token)

    def all_clients(self) -> list[str]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT client_id FROM client_access ORDER BY client_id").fetchall()
        return [r[0] for r in rows]
