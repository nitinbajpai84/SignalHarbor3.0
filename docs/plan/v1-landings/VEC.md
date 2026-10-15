# V1 Search by meaning (landed)

## What changed
- `sh_platform/v1/doc_embed.py` (new): the local model (fastembed, BAAI/bge-small-en-v1.5), lazy, thread-safe, cache in `data/_models/` (gitignored with `data/`). `Unavailable` when it cannot load.
- `sh_platform/v1/doc_index.py`: tables `vectors(path, l1, l2, vec)` and `vec_files(path, sig)` (which file version the vectors belong to); `ensure()` queues the embedding in the background pool after writing passages, and deletes a file's vectors with its rows; `search()` fuses BM25 and cosine by reciprocal rank (k=60) and adds `how` to each hit; cosine below 0.45 is ignored so an unrelated question still says "none". `doc_tools.py` is unchanged (it already passes only ticked, readable paths).
- `tools/reindex_vectors.py <company> [--all]`; `requirements.txt` gains `fastembed` (0.9.0; onnxruntime 1.20.1 and numpy 2.4.2 untouched).
- `conftest.py`: tests never load the real model (autouse switch to the words-only fallback); `tests/v1/test_vectors.py` uses a stub.

## Test on the demo
1. Open an intent with the Neera policy documents ticked. Ask North "how much is the family worth in total?" The answer cites the investment policy even though it says "net worth" or similar, not those words.
2. First search after an upgrade: old files are words-only for a moment; the next search (seconds later) includes meaning. Or run `python tools/reindex_vectors.py neera`.
3. Switch the model off (rename `data/_models`, no network): search still works by words; the log shows one warning.

## Ceiling
- Brute-force cosine in numpy over the ticked files' passages: fine to roughly 100k passages; then DuckDB vss or sqlite-vec (marked `ponytail:` in the code).
- English model; ~384 dimensions; the 0.45 floor is tuned for bge-small.
- A slow file (PDF, picture) is embedded after its OCR; until then it is "still reading".

## Multilingual (Chinese documents)
Set `SH_EMBED_MODEL=intfloat/multilingual-e5-small` (fastembed supports it; query/passage prefixes switch automatically), then `python tools/reindex_vectors.py <company> --all`. Re-check the 0.45 floor (e5 scores run higher). BM25 on Chinese needs a different tokenizer (unicode61 does not split Chinese words), so keyword search does not match Chinese. Since the fixes below, a query with no ASCII word skips the keyword half and goes to meaning search, so with the multilingual model Chinese questions find Chinese passages; with the default English model they do not.

## Fixes after review
- A failed model load is remembered (`doc_embed._failed`): later calls raise `Unavailable` at once, with no download attempt; one retry after 10 minutes.
- The conftest fixture also runs `doc_index._submit` inline, so no background job can reach the real model during the suite.
- A query embed no longer waits behind a whole file: files are encoded in batches of 64, the lock taken per batch.
- A vector of the wrong size or a damaged blob costs only the meaning half for that file (one log line); the file's vectors are dropped and re-embedded. Vectors are tied to the model name (`vec_files.sig` is `model|file sig`), so changing `SH_EMBED_MODEL` re-embeds by itself (old rows re-embed once after this upgrade).
- A file changed while its vectors were being computed is queued again when that job ends.
- Non-ASCII queries go to meaning search (the keyword half is skipped when the query has no ASCII word).
- `tools/reindex_vectors.py`: docstring says to stop the server first; logging shows the "model not available" warning.
- `doc_index.forget(plane, path)` removes all rows of a file; the library's delete calls it.
- Once the model is in `data/_models`, `HF_HUB_OFFLINE=1` is set before fastembed is imported.
- Note: fusion interleaves the two lists, so five exact keyword passages may show as three plus two meaning hits.
- Not done: `how` on North's source chips (a product decision for the chips).
