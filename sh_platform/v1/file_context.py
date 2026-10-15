"""What an agent reads from the files dropped into its conversation: one flat line per file, safe for the egress gateway's row
guard (strings only, never a list of records). Reads on the machine with I2's `file_preview`; only these lines reach the model.

- a sample (csv, tsv, xlsx): its columns and a few values;
- a document: its first DOC_CHARS characters of text;
- a picture or PDF: its text if read locally (PyMuPDF, a local picture reader); never the picture itself;
- anything that cannot be read: its name and "I can't read this type yet; ask the person to paste the text"."""
from __future__ import annotations

from sh_platform.context_docs import reader
from sh_platform.v1 import i2_north as N

DOC_CHARS = 1500
CANT = "I can't read this type yet; ask the person to paste the text"


def _flat(s: str) -> str:
    return " ".join(str(s).split())


def preview_for_agent(plane, iid: str, files: list[dict]) -> list[str]:
    out = []
    for f in files or []:
        name = _flat(f.get("name") or "file")
        ext = reader.ext_of(name)
        sample = ext in N.SAMPLE_EXT
        kind = "sample" if sample else "document"
        text = N.file_preview(plane, iid, f) if f.get("path") else ""  # a PDF or picture is read locally; "" when it cannot be
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            out.append(f"{name} ({kind}): {CANT}")
        elif sample:
            out.append(_flat(f"{name} (sample): columns: {lines[0]}; values: {' | '.join(lines[1:4])}")[:DOC_CHARS])
        else:
            out.append(f"{name} (document): {_flat(text)[:DOC_CHARS]}")
    return out


def added_line(files: list[dict]) -> str:
    """What the person's turn says when they dropped files and wrote nothing."""
    return "I added " + ", ".join(str(f.get("name") or "a file") for f in files) + "." if files else ""


def library_lines(plane, iid: str, viewer) -> list[str]:
    """C4: one flat line per context-library item ticked for this conversation that the viewer may see; [] when it cannot be read."""
    try:
        from sh_platform.v1 import c4_library
        return c4_library.lines(plane, iid, viewer)
    except Exception:  # noqa: BLE001 - a broken library never breaks a conversation
        import logging
        logging.getLogger(__name__).warning("the context library could not be read for %s", iid)
        return []
