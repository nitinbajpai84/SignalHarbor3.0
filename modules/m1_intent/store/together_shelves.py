"""The shelf each cluster sits on (A-058) and the audit of every move, beside the together file:

  intents/m1_intent/together_shelves/<session id>.json
      shelves: {cluster id: {shelf, reason, review_date}}    the latest shelf of a cluster (none: it has not been shelved)
      moves:   [{by, by_account, at, cluster, from, to}]                  every move, oldest first; the board's edit log has the same "by"
Strict reads, atomic writes, one lock per plane (the same base as the board and together stores).
"""
from modules.m1_intent.store.board import _Files
from modules.m1_intent.store.files import UNREADABLE, StoreError, read_json

_MOVE = {"by", "by_account", "at", "cluster", "from", "to"}


class ShelfStore(_Files):
    folder = "together_shelves"

    def get(self, sid: str) -> dict:
        data = read_json(self._path(sid))
        if data is None:
            return {"session_id": sid, "updated_at": None, "shelves": {}, "moves": []}
        if not (isinstance(data, dict) and data.get("session_id") == sid and set(data) == {"session_id", "updated_at", "shelves", "moves"}
                and isinstance(data["shelves"], dict) and isinstance(data["moves"], list)
                and all(isinstance(m, dict) and set(m) == _MOVE for m in data["moves"])):
            raise StoreError(UNREADABLE)
        return data
