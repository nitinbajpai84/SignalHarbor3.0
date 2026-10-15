# Upload proposal speed ("Add context")

Bug: `POST /api/v1/library/proposal` took 28 to 220 s per file (North's chat reply: about 15 s).

## Where the time went
The proposal ran the file reader three separate times (personal-data scan, outline for the topic, "unread?" check). For a picture or a
scanned PDF each read is OCR. Only the last 4 pictures were cached (by bytes), so a scanned PDF was OCR'd up to three times, 20 pages each,
at 200 dpi, and phone pictures (4000 px) went to RapidOCR at full size. The model topic call (router, up to 6 tries, no timeout) ran when the rules
gave no topic. The catalogue is not scanned by the proposal; the personal-data scan itself is under 10 ms.

## Timings, this machine (other dev servers using CPU, so noisy; `.sh-tmp/time_proposal.py`)
| Step | Before | After |
|---|---|---|
| Engine start (RapidOCR) | once, 1.7 s (lru_cache) | once per process, under a lock, 0.4 to 1.8 s |
| Phone picture 4000x3000, OCR | 8 to 10 s per read, read 3 times | shrunk to 1600 px, read once: 2.7 to 3.0 s (first of a new shape up to about 8 s) |
| Picture 1200x900, proposal | 3 reads | one read: 2.1 to 2.6 s |
| Scanned PDF 8 pages, OCR | 3 full reads: 18 to 22 s | first 5 pages, 4 s budget, once: 3.4 to 4.0 s; Restricted until fully read |
| Text PDF 3 pages / md / csv | under 0.05 s | under 0.05 s |
| PII scan, outline, unread check | 3 reads | share one read: 0.00 s each |
| Topic model call | router, up to 6 tries, no limit | only when rules give no topic and no personal data; 8 s limit, one try, falls back to the rules / "Other" |

## Changes
- `ocr_local.py`: engine built once per process under a lock; pictures shrunk to 1600 px long side; no rotation check.
- `reader.py`: `read_segments`/`_pdf_segments` take `ocr_pages`, `ocr_seconds`, `partial` (defaults unchanged, so the full 20-page background read is as before).
- `k1_classify.py`: one shared read per proposal; 5 pages and 4 s for scans; topic call in a pool with an 8 s wait.
- `k1_routes.py`: at most 3 proposals read at once.
- Personal-data rule kept: no text read (no reader, empty picture), or scan pages left unread, means Restricted until checked.
- The upload itself (`stamp`) uses the same proposal, so it is quick too; the full read for the agents still happens later in the background.

Test: `tests/v1/test_proposal_speed.py` (3-page text PDF and 1200x900 picture under 5 s with a stub model that must not be called; unread pages stay Restricted).
