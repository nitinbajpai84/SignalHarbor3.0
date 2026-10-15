"""The shared company profile (LI-PROFILE): `read(plane, viewer)` for every module, `record(plane, path, value, provenance)` to write.
`router` is mounted by sh_platform/app.py."""
from sh_platform.profile.api import router
from sh_platform.profile.reader import sample_bytes
from sh_platform.profile.cards import record_card
from sh_platform.profile.store import record
from sh_platform.profile.view import Viewer, cards_summary, read, read_unrestricted

__all__ = ["Viewer", "cards_summary", "record_card", "read", "read_unrestricted", "record", "sample_bytes", "router"]
