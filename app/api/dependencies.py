import uuid
from typing import Optional
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


class SessionStore:
    """
    In-memory store for MasterCV and TailoredCV objects keyed by session ID.
    Lives for the duration of the server process.
    Simple dict is sufficient — no Redis needed at this scale.
    """
    def __init__(self):
        self._master: dict[str, MasterCV] = {}
        self._tailored: dict[str, TailoredCV] = {}

    def save_master(self, cv: MasterCV) -> str:
        session_id = str(uuid.uuid4())
        self._master[session_id] = cv
        return session_id

    def get_master(self, session_id: str) -> Optional[MasterCV]:
        return self._master.get(session_id)

    def save_tailored(self, cv: TailoredCV) -> str:
        tailored_id = str(uuid.uuid4())
        self._tailored[tailored_id] = cv
        return tailored_id

    def get_tailored(self, tailored_id: str) -> Optional[TailoredCV]:
        return self._tailored.get(tailored_id)


session_store = SessionStore()


def get_session_store() -> SessionStore:
    return session_store