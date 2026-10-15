CREATE TABLE "entity" (
  "entity_id" varchar PRIMARY KEY,
  "name" varchar,
  "kind" varchar,
  "base_currency" char(3),
  "sensitivity" varchar
);

CREATE TABLE "portfolio" (
  "portfolio_id" varchar PRIMARY KEY,
  "entity_id" varchar,
  "name" varchar,
  "reporting_currency" char(3)
);

CREATE TABLE "instrument" (
  "instrument_id" varchar PRIMARY KEY,
  "kind" varchar,
  "name" varchar,
  "currency" char(3),
  "manager_name" varchar
);

CREATE TABLE "instrument_alias" (
  "scheme" varchar,
  "value" varchar,
  "instrument_id" varchar,
  "confirmed_by" varchar,
  PRIMARY KEY ("scheme", "value")
);

CREATE TABLE "app_user" (
  "user_id" varchar PRIMARY KEY,
  "name" varchar,
  "role" varchar
);

CREATE TABLE "entitlement" (
  "user_id" varchar,
  "entity_id" varchar,
  "level" varchar,
  PRIMARY KEY ("user_id", "entity_id")
);

CREATE TABLE "source_file" (
  "file_id" varchar PRIMARY KEY,
  "source" varchar,
  "file_name" varchar,
  "sha256" char(64),
  "received_at" timestamp,
  "sensitivity" varchar
);

CREATE TABLE "sheet_mapping" (
  "file_pattern" varchar,
  "source_column" varchar,
  "target_kind" varchar,
  "target_field" varchar,
  "confirmed_by" varchar,
  PRIMARY KEY ("file_pattern", "source_column")
);

CREATE TABLE "load_batch" (
  "batch_id" varchar PRIMARY KEY,
  "file_id" varchar,
  "loaded_at" timestamp,
  "row_count" int,
  "expected_total" decimal(24,6),
  "loaded_total" decimal(24,6),
  "status" varchar
);

CREATE TABLE "document" (
  "document_id" varchar PRIMARY KEY,
  "file_id" varchar,
  "doc_type" varchar,
  "instrument_id" varchar,
  "period_end" date,
  "supersedes_document_id" varchar
);

CREATE TABLE "extraction" (
  "extraction_id" varchar PRIMARY KEY,
  "document_id" varchar,
  "field" varchar,
  "value_text" varchar,
  "page" int,
  "line" int,
  "confidence" varchar,
  "verified_by" varchar
);

CREATE TABLE "evidence_event" (
  "event_id" varchar PRIMARY KEY,
  "kind" varchar,
  "entity_id" varchar,
  "instrument_id" varchar,
  "value" decimal(24,6),
  "currency" char(3),
  "effective_at" timestamp,
  "received_at" timestamp,
  "processed_at" timestamp,
  "status" varchar,
  "supersedes_event_id" varchar,
  "batch_id" varchar,
  "extraction_id" varchar
);

CREATE TABLE "rule_version" (
  "rule_id" varchar,
  "version" int,
  "definition" text,
  "effective_from" date,
  "signed_by" varchar,
  PRIMARY KEY ("rule_id", "version")
);

CREATE TABLE "report_version" (
  "report_version_id" varchar PRIMARY KEY,
  "report_name" varchar,
  "portfolio_id" varchar,
  "period_end" date,
  "cutoff_at" timestamp,
  "issued_at" timestamp,
  "status" varchar
);

CREATE TABLE "report_line" (
  "report_version_id" varchar,
  "line_key" varchar,
  "value" decimal(24,6),
  "currency" char(3),
  "status" varchar,
  "event_ids" varchar,
  PRIMARY KEY ("report_version_id", "line_key", "currency")
);

CREATE TABLE "finding" (
  "finding_id" varchar PRIMARY KEY,
  "kind" varchar,
  "entity_id" varchar,
  "effect_amount" decimal(20,2),
  "currency" char(3),
  "materiality" varchar,
  "event_ids" varchar,
  "affected_report_version_ids" varchar,
  "created_at" timestamp
);

CREATE TABLE "work_case" (
  "case_id" varchar PRIMARY KEY,
  "finding_id" varchar,
  "state" varchar,
  "maker_user_id" varchar,
  "checker_user_id" varchar,
  "due_at" timestamp,
  "explanation" text
);

CREATE TABLE "case_event" (
  "case_id" varchar,
  "at" timestamp,
  "by_actor" varchar,
  "action" varchar,
  "note" text,
  PRIMARY KEY ("case_id", "at")
);

COMMENT ON COLUMN "entity"."kind" IS 'holding company, trust, foundation, SPV';

COMMENT ON COLUMN "entity"."sensitivity" IS 'open, internal, restricted';

COMMENT ON COLUMN "instrument"."kind" IS 'private fund, fund share class, equity, bond, cash, derivative, other';

COMMENT ON TABLE "instrument_alias" IS 'How "Evergreen Growth I" in a PDF and code 4471 in an export become the same fund.';

COMMENT ON COLUMN "instrument_alias"."scheme" IS 'isin, administrator id, OMS id, manager name as written';

COMMENT ON COLUMN "instrument_alias"."confirmed_by" IS 'An alias is used only once a person confirms it';

COMMENT ON COLUMN "app_user"."role" IS 'cio, operations, finance, risk, rule_owner, data_engineer, admin';

COMMENT ON TABLE "entitlement" IS 'Checked on every query and before every document search.';

COMMENT ON COLUMN "entitlement"."level" IS 'full, read, none';

COMMENT ON COLUMN "source_file"."source" IS 'administrator export, OMS export, manager email, spreadsheet';

COMMENT ON COLUMN "source_file"."sha256" IS 'Proves the original never changed';

COMMENT ON TABLE "sheet_mapping" IS 'Proposed by the data agent, confirmed once, reused every month.';

COMMENT ON COLUMN "sheet_mapping"."file_pattern" IS 'e.g. "Positions *.xlsx" / sheet "Holdings"';

COMMENT ON COLUMN "sheet_mapping"."target_kind" IS 'which evidence_event kind it feeds';

COMMENT ON COLUMN "sheet_mapping"."target_field" IS 'subject, value, currency, effective date';

COMMENT ON COLUMN "load_batch"."expected_total" IS 'Read from the workbook itself';

COMMENT ON COLUMN "load_batch"."status" IS 'loaded, rejected: totals differ, quarantined';

COMMENT ON TABLE "document" IS 'Searchable passages live in the existing search index, keyed by document_id.';

COMMENT ON COLUMN "document"."doc_type" IS 'statement, capital call, NAV report, policy';

COMMENT ON COLUMN "extraction"."field" IS 'value, units, valuation date';

COMMENT ON COLUMN "extraction"."confidence" IS 'high, medium, low';

COMMENT ON TABLE "evidence_event" IS 'Append-only. As known at time T: latest row per subject with processed_at <= T.';

COMMENT ON COLUMN "evidence_event"."kind" IS 'valuation, position, cash_balance, nav, price, fx_rate, capital_call';

COMMENT ON COLUMN "evidence_event"."instrument_id" IS 'empty for cash or NAV of an entity';

COMMENT ON COLUMN "evidence_event"."effective_at" IS 'true in the world, e.g. valuation date';

COMMENT ON COLUMN "evidence_event"."received_at" IS 'when the office learnt it';

COMMENT ON COLUMN "evidence_event"."processed_at" IS 'when we stored it';

COMMENT ON COLUMN "evidence_event"."status" IS 'estimated, official, revised, stale';

COMMENT ON COLUMN "evidence_event"."batch_id" IS 'from a file or export';

COMMENT ON COLUMN "evidence_event"."extraction_id" IS 'from a document';

COMMENT ON TABLE "rule_version" IS 'Only signed versions are used. Past reports keep the version they used.';

COMMENT ON COLUMN "rule_version"."rule_id" IS 'cash_tolerance, materiality, estimate_use, fx_fixing, statement_due';

COMMENT ON COLUMN "rule_version"."definition" IS 'plain words plus the machine form, e.g. abs(diff) <= 5000';

COMMENT ON COLUMN "report_version"."cutoff_at" IS 'evidence processed after this is not in the report';

COMMENT ON COLUMN "report_version"."status" IS 'draft, issued, superseded';

COMMENT ON COLUMN "report_line"."line_key" IS 'e.g. fund_a_value, total';

COMMENT ON COLUMN "report_line"."event_ids" IS 'the evidence this figure used';

COMMENT ON COLUMN "finding"."kind" IS 'revision, break, missing_document';

COMMENT ON COLUMN "finding"."materiality" IS 'from the signed materiality rule';

COMMENT ON COLUMN "work_case"."case_id" IS 'CASE-0107';

COMMENT ON COLUMN "work_case"."state" IS 'open, waiting_check, resolved, dismissed';

COMMENT ON COLUMN "work_case"."checker_user_id" IS 'never the maker';

COMMENT ON COLUMN "work_case"."explanation" IS 'proposed by an agent, confirmed by the maker';

COMMENT ON COLUMN "case_event"."by_actor" IS 'user or agent';

COMMENT ON COLUMN "case_event"."action" IS 'opened, assigned, submitted, approved, sent_back, resolved, dismissed';

ALTER TABLE "portfolio" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_alias" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_alias" ADD FOREIGN KEY ("confirmed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entitlement" ADD FOREIGN KEY ("user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entitlement" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mapping" ADD FOREIGN KEY ("confirmed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "load_batch" ADD FOREIGN KEY ("file_id") REFERENCES "source_file" ("file_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("file_id") REFERENCES "source_file" ("file_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("supersedes_document_id") REFERENCES "document" ("document_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extraction" ADD FOREIGN KEY ("document_id") REFERENCES "document" ("document_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extraction" ADD FOREIGN KEY ("verified_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("supersedes_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("batch_id") REFERENCES "load_batch" ("batch_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("extraction_id") REFERENCES "extraction" ("extraction_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule_version" ADD FOREIGN KEY ("signed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_version" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("portfolio_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_line" ADD FOREIGN KEY ("report_version_id") REFERENCES "report_version" ("report_version_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "finding" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "work_case" ADD FOREIGN KEY ("finding_id") REFERENCES "finding" ("finding_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "work_case" ADD FOREIGN KEY ("maker_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "work_case" ADD FOREIGN KEY ("checker_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "case_event" ADD FOREIGN KEY ("case_id") REFERENCES "work_case" ("case_id") DEFERRABLE INITIALLY IMMEDIATE;
