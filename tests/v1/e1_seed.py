"""Test helper for the E1/E3 tests: E1b refuses ids that are not in the warehouse, so tests seed the rows they point at."""
import uuid
from datetime import datetime, timezone

from sh_platform.v1 import e1_write as W, wh

LE, SYS, BATCH = (str(uuid.uuid5(uuid.NAMESPACE_DNS, n)) for n in ("e1seed-le", "e1seed-sys", "e1seed-batch"))


def seed(plane, instruments=(), portfolios=(), sources=()) -> None:
    org, now = W.org_id(plane), datetime(2026, 1, 1, tzinfo=timezone.utc)
    with wh.connect(plane) as con:
        def new(table, id, sql, args):
            if not con.execute(f"select 1 from {table} where id = ?", [id]).fetchone():
                con.execute(sql, [id, org, *args])
        new("legal_entities", LE, "insert into legal_entities (id, organization_id, entity_code, entity_name, base_currency) values (?,?,?,?,?)", ["LE", "Entity", "USD"])
        new("source_systems", SYS, "insert into source_systems (id, organization_id, source_code, source_name, source_type, is_active) values (?,?,?,?,?,?)", ["t", "t", "internal", True])
        new("source_batches", BATCH, "insert into source_batches (id, organization_id, source_system_id, batch_reference, received_at, validation_status) values (?,?,?,?,?,?)", [SYS, "b", now, "loaded"])
        for i in instruments:
            new("instruments", i, "insert into instruments (id, organization_id, canonical_name, instrument_type, created_at) values (?,?,?,?,?)", [f"Instrument {str(i)[:4]}", "fund", now])
        for p in portfolios:
            new("portfolios", p, "insert into portfolios (id, organization_id, legal_entity_id, portfolio_code, portfolio_name, base_currency) values (?,?,?,?,?,?)", [LE, f"P{str(p)[:4]}", "Portfolio", "USD"])
        for s in sources:
            new("source_records", s, "insert into source_records (id, organization_id, source_batch_id, record_type, received_at, recorded_at, raw_payload_uri, content_hash, quality_status) values (?,?,?,?,?,?,?,?,?)", [BATCH, "t", now, now, "x", "h", "ok"])
