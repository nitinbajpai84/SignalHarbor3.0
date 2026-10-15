"""Module 2's router. One file per package area so parallel packages never edit the same file:
status.py (scaffold), worklist.py (M2-P01), requests.py (M2-P02), process_map.py (M2-P03), catalogue.py (M2-P04),
signoff.py (M2-P05). Every route here must also be declared in manifest.yaml."""
from fastapi import APIRouter

from modules.m2_baseline.api import catalogue, data_sources, glossary, governance, governed, lens_chat, process_map, requests, signoff, status, technical, worklist

router = APIRouter()
for part in (status, worklist, lens_chat, requests, process_map, catalogue, signoff, glossary, governance, governed, technical, data_sources):
    router.include_router(part.router)
