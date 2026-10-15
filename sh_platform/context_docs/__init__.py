"""Company context uploads for agents (D-032): documents a company uploads for North, kept inside its own plane.

`context_passages(plane, agent, question)` is what an agent calls; `router` is mounted by sh_platform/app.py.
"""
from sh_platform.context_docs.api import router
from sh_platform.context_docs.retrieval import context_passages
from sh_platform.context_docs.store import documents_for

__all__ = ["context_passages", "documents_for", "router"]
