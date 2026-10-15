CREATE TYPE "party_kind" AS ENUM (
  'person',
  'organisation'
);

CREATE TYPE "entity_kind" AS ENUM (
  'family_holding',
  'trust',
  'foundation',
  'company',
  'spv',
  'partnership',
  'individual_account',
  'other'
);

CREATE TYPE "instrument_kind" AS ENUM (
  'equity',
  'bond',
  'fund_share_class',
  'private_fund',
  'cash',
  'deposit',
  'derivative',
  'real_asset',
  'loan',
  'other'
);

CREATE TYPE "evidence_status" AS ENUM (
  'estimated',
  'indicative',
  'official',
  'final',
  'revised',
  'stale',
  'withdrawn'
);

CREATE TABLE "party" (
  "party_id" varchar PRIMARY KEY,
  "kind" party_kind,
  "display_name" varchar,
  "country" varchar,
  "created_at" timestamp
);

CREATE TABLE "party_role" (
  "party_id" varchar,
  "role" varchar,
  "valid_from" date,
  "valid_to" date,
  PRIMARY KEY ("party_id", "role", "valid_from")
);

CREATE TABLE "entity" (
  "entity_id" varchar PRIMARY KEY,
  "name" varchar,
  "kind" entity_kind,
  "domicile" varchar,
  "base_currency" char(3),
  "tax_id_ref" varchar,
  "sensitivity" varchar,
  "valid_from" date,
  "valid_to" date
);

CREATE TABLE "entity_ownership" (
  "parent_entity_id" varchar,
  "child_entity_id" varchar,
  "ownership_pct" decimal(9,6),
  "effective_from" date,
  "effective_to" date,
  "source_event_id" varchar,
  PRIMARY KEY ("parent_entity_id", "child_entity_id", "effective_from")
);

CREATE TABLE "portfolio" (
  "portfolio_id" varchar PRIMARY KEY,
  "name" varchar,
  "owner_entity_id" varchar,
  "strategy" varchar,
  "reporting_currency" char(3),
  "valid_from" date,
  "valid_to" date
);

CREATE TABLE "account" (
  "account_id" varchar PRIMARY KEY,
  "entity_id" varchar,
  "portfolio_id" varchar,
  "provider_party_id" varchar,
  "account_kind" varchar,
  "account_ref_masked" varchar,
  "currency" char(3),
  "opened_on" date,
  "closed_on" date
);

CREATE TABLE "app_user" (
  "user_id" varchar PRIMARY KEY,
  "party_id" varchar,
  "email" varchar,
  "role" varchar,
  "active" boolean
);

CREATE TABLE "entitlement" (
  "user_id" varchar,
  "scope_kind" varchar,
  "scope_id" varchar,
  "level" varchar,
  "valid_from" timestamp,
  "valid_to" timestamp,
  "granted_by" varchar,
  PRIMARY KEY ("user_id", "scope_kind", "scope_id", "valid_from")
);

CREATE TABLE "currency" (
  "code" char(3) PRIMARY KEY,
  "name" varchar,
  "decimals" int
);

CREATE TABLE "calendar_day" (
  "calendar" varchar,
  "day" date,
  "is_business_day" boolean,
  PRIMARY KEY ("calendar", "day")
);

CREATE TABLE "instrument" (
  "instrument_id" varchar PRIMARY KEY,
  "kind" instrument_kind,
  "name" varchar,
  "currency" char(3),
  "issuer_party_id" varchar,
  "manager_party_id" varchar,
  "liquidity" varchar,
  "valid_from" date,
  "valid_to" date
);

CREATE TABLE "instrument_identifier" (
  "instrument_id" varchar,
  "scheme" varchar,
  "value" varchar,
  "valid_from" date,
  "valid_to" date,
  "confirmed_by" varchar,
  PRIMARY KEY ("scheme", "value", "valid_from")
);

CREATE TABLE "classification" (
  "instrument_id" varchar,
  "scheme" varchar,
  "value" varchar,
  "valid_from" date,
  "valid_to" date,
  PRIMARY KEY ("instrument_id", "scheme", "valid_from")
);

CREATE TABLE "fund_terms" (
  "instrument_id" varchar PRIMARY KEY,
  "vintage_year" int,
  "fund_size" decimal(20,2),
  "management_fee_pct" decimal(9,6),
  "carry_pct" decimal(9,6),
  "hurdle_pct" decimal(9,6),
  "valuation_frequency" varchar,
  "administrator_party_id" varchar
);

CREATE TABLE "derivative_terms" (
  "instrument_id" varchar PRIMARY KEY,
  "underlying_instrument_id" varchar,
  "contract_type" varchar,
  "notional" decimal(20,2),
  "notional_currency" char(3),
  "trade_date" date,
  "maturity_date" date,
  "counterparty_party_id" varchar
);

CREATE TABLE "source_system" (
  "source_id" varchar PRIMARY KEY,
  "name" varchar,
  "kind" varchar,
  "owner_user_id" varchar,
  "licence_class" varchar,
  "permitted_use" varchar,
  "freshness_rule" varchar
);

CREATE TABLE "source_file" (
  "file_id" varchar PRIMARY KEY,
  "source_id" varchar,
  "file_name" varchar,
  "sha256" char(64),
  "storage_uri" varchar,
  "sender" varchar,
  "received_at" timestamp,
  "sensitivity" varchar,
  "pii_found" boolean
);

CREATE TABLE "load_batch" (
  "batch_id" varchar PRIMARY KEY,
  "source_id" varchar,
  "file_id" varchar,
  "started_at" timestamp,
  "finished_at" timestamp,
  "row_count" int,
  "status" varchar
);

CREATE TABLE "document" (
  "document_id" varchar PRIMARY KEY,
  "file_id" varchar,
  "doc_type" varchar,
  "manager_party_id" varchar,
  "instrument_id" varchar,
  "period_end" date,
  "version_label" varchar,
  "supersedes_document_id" varchar,
  "pages" int
);

CREATE TABLE "passage" (
  "passage_id" varchar PRIMARY KEY,
  "document_id" varchar,
  "page" int,
  "line_from" int,
  "line_to" int,
  "text" text,
  "embedding" vector,
  "embed_model" varchar
);

CREATE TABLE "extraction" (
  "extraction_id" varchar PRIMARY KEY,
  "document_id" varchar,
  "field" varchar,
  "value_text" varchar,
  "value_number" decimal(24,6),
  "page" int,
  "line" int,
  "confidence" varchar,
  "extracted_by" varchar,
  "verified_by" varchar,
  "verified_at" timestamp
);

CREATE TABLE "evidence_event" (
  "event_id" varchar PRIMARY KEY,
  "kind" varchar,
  "subject_type" varchar,
  "subject_id" varchar,
  "value_number" decimal(24,6),
  "currency" char(3),
  "effective_at" timestamp,
  "received_at" timestamp,
  "processed_at" timestamp,
  "status" evidence_status,
  "supersedes_event_id" varchar,
  "source_batch_id" varchar,
  "extraction_id" varchar,
  "reviewed_by" varchar
);

CREATE TABLE "commitment" (
  "commitment_id" varchar PRIMARY KEY,
  "entity_id" varchar,
  "instrument_id" varchar,
  "amount" decimal(20,2),
  "currency" char(3),
  "committed_on" date,
  "source_event_id" varchar
);

CREATE TABLE "capital_flow" (
  "flow_id" varchar PRIMARY KEY,
  "commitment_id" varchar,
  "kind" varchar,
  "notice_date" date,
  "due_date" date,
  "amount" decimal(20,2),
  "currency" char(3),
  "status" varchar,
  "source_event_id" varchar
);

CREATE TABLE "transaction" (
  "txn_id" varchar PRIMARY KEY,
  "account_id" varchar,
  "instrument_id" varchar,
  "kind" varchar,
  "trade_date" date,
  "settle_date" date,
  "effective_at" timestamp,
  "quantity" decimal(24,8),
  "price" decimal(24,8),
  "amount" decimal(20,2),
  "currency" char(3),
  "booking_status" varchar,
  "source_event_id" varchar
);

CREATE TABLE "corporate_action" (
  "action_id" varchar PRIMARY KEY,
  "instrument_id" varchar,
  "kind" varchar,
  "ex_date" date,
  "details" varchar,
  "source_event_id" varchar
);

CREATE TABLE "position" (
  "account_id" varchar,
  "instrument_id" varchar,
  "as_of" date,
  "quantity" decimal(24,8),
  "cost_basis" decimal(20,2),
  "source_event_id" varchar,
  PRIMARY KEY ("account_id", "instrument_id", "as_of", "source_event_id")
);

CREATE TABLE "price" (
  "instrument_id" varchar,
  "price_date" date,
  "observed_at" timestamp,
  "price" decimal(24,8),
  "currency" char(3),
  "source_id" varchar,
  "price_type" varchar,
  PRIMARY KEY ("instrument_id", "price_date", "source_id", "observed_at")
);

CREATE TABLE "fx_rate" (
  "from_ccy" char(3),
  "to_ccy" char(3),
  "rate_date" date,
  "fixing" varchar,
  "rate" decimal(18,10),
  "source_id" varchar,
  PRIMARY KEY ("from_ccy", "to_ccy", "rate_date", "fixing")
);

CREATE TABLE "valuation" (
  "instrument_id" varchar,
  "entity_id" varchar,
  "valuation_date" date,
  "value" decimal(20,2),
  "currency" char(3),
  "status" evidence_status,
  "method" varchar,
  "source_event_id" varchar,
  PRIMARY KEY ("instrument_id", "entity_id", "valuation_date", "source_event_id")
);

CREATE TABLE "administrator_nav" (
  "nav_id" varchar PRIMARY KEY,
  "entity_id" varchar,
  "portfolio_id" varchar,
  "period_end" date,
  "nav" decimal(20,2),
  "currency" char(3),
  "approval_status" varchar,
  "approved_at" timestamp,
  "source_event_id" varchar
);

CREATE TABLE "gl_account" (
  "gl_account_id" varchar PRIMARY KEY,
  "entity_id" varchar,
  "code" varchar,
  "name" varchar,
  "kind" varchar
);

CREATE TABLE "journal_line" (
  "line_id" varchar PRIMARY KEY,
  "gl_account_id" varchar,
  "posting_date" date,
  "amount" decimal(20,2),
  "currency" char(3),
  "reference" varchar,
  "source_event_id" varchar
);

CREATE TABLE "rule" (
  "rule_id" varchar PRIMARY KEY,
  "kind" varchar,
  "name" varchar,
  "owner_user_id" varchar
);

CREATE TABLE "rule_version" (
  "rule_id" varchar,
  "version" int,
  "definition" text,
  "effective_from" date,
  "effective_to" date,
  "signed_by" varchar,
  "signed_at" timestamp,
  "state" varchar,
  PRIMARY KEY ("rule_id", "version")
);

CREATE TABLE "calculation_version" (
  "calc_id" varchar PRIMARY KEY,
  "name" varchar,
  "code_hash" varchar,
  "rule_versions" varchar,
  "released_at" timestamp,
  "released_by" varchar
);

CREATE TABLE "benchmark" (
  "benchmark_id" varchar PRIMARY KEY,
  "name" varchar,
  "currency" char(3),
  "owner_user_id" varchar,
  "methodology_rule_id" varchar
);

CREATE TABLE "benchmark_component" (
  "benchmark_id" varchar,
  "index_instrument_id" varchar,
  "weight" decimal(9,6),
  "spread_bps" decimal(9,2),
  "valid_from" date,
  "valid_to" date,
  PRIMARY KEY ("benchmark_id", "index_instrument_id", "valid_from")
);

CREATE TABLE "allocation_limit" (
  "limit_id" varchar PRIMARY KEY,
  "portfolio_id" varchar,
  "dimension" varchar,
  "bucket" varchar,
  "target_pct" decimal(9,4),
  "min_pct" decimal(9,4),
  "max_pct" decimal(9,4),
  "rule_id" varchar,
  "effective_from" date,
  "effective_to" date
);

CREATE TABLE "performance_result" (
  "portfolio_id" varchar,
  "period_start" date,
  "period_end" date,
  "currency" char(3),
  "method" varchar,
  "value" decimal(18,8),
  "calc_id" varchar,
  "as_known_at" timestamp,
  PRIMARY KEY ("portfolio_id", "period_end", "currency", "method", "calc_id", "as_known_at")
);

CREATE TABLE "report_definition" (
  "report_id" varchar PRIMARY KEY,
  "name" varchar,
  "audience" varchar,
  "contract_id" varchar,
  "reporting_currencies" varchar
);

CREATE TABLE "report_version" (
  "report_version_id" varchar PRIMARY KEY,
  "report_id" varchar,
  "period_end" date,
  "cutoff_at" timestamp,
  "issued_at" timestamp,
  "status" varchar,
  "calc_id" varchar,
  "approved_by" varchar,
  "supersedes_version_id" varchar
);

CREATE TABLE "report_line" (
  "report_version_id" varchar,
  "line_key" varchar,
  "value" decimal(24,6),
  "currency" char(3),
  "status" evidence_status,
  "evidence_event_ids" varchar,
  PRIMARY KEY ("report_version_id", "line_key", "currency")
);

CREATE TABLE "decision_contract" (
  "contract_id" varchar PRIMARY KEY,
  "question" text,
  "audience" varchar,
  "estimate_or_official" varchar,
  "sources" varchar,
  "acceptance_tests" text,
  "open_choices" text,
  "owner_user_id" varchar,
  "signed_version" int,
  "signed_at" timestamp
);

CREATE TABLE "finding" (
  "finding_id" varchar PRIMARY KEY,
  "kind" varchar,
  "subject_type" varchar,
  "subject_id" varchar,
  "effect_amount" decimal(20,2),
  "effect_currency" char(3),
  "calc_id" varchar,
  "evidence_event_ids" varchar,
  "materiality" varchar,
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

CREATE TABLE "report_impact" (
  "finding_id" varchar,
  "report_version_id" varchar,
  "line_key" varchar,
  "draft_value" decimal(24,6),
  PRIMARY KEY ("finding_id", "report_version_id", "line_key")
);

CREATE TABLE "pulse_card" (
  "card_id" varchar PRIMARY KEY,
  "user_id" varchar,
  "finding_id" varchar,
  "case_id" varchar,
  "bucket" varchar,
  "shown_on" date,
  "acted" varchar
);

CREATE TABLE "workbook_sheet" (
  "sheet_id" varchar PRIMARY KEY,
  "file_id" varchar,
  "sheet_name" varchar,
  "header_row" int,
  "data_range" varchar,
  "sheet_purpose" varchar,
  "owner_user_id" varchar,
  "status" varchar
);

CREATE TABLE "column_mapping" (
  "sheet_id" varchar,
  "source_column" varchar,
  "target_table" varchar,
  "target_field" varchar,
  "transform" varchar,
  "proposed_by" varchar,
  "confirmed_by" varchar,
  PRIMARY KEY ("sheet_id", "source_column")
);

CREATE TABLE "control_total" (
  "sheet_id" varchar,
  "measure" varchar,
  "expected_value" decimal(24,6),
  "loaded_value" decimal(24,6),
  "passed" boolean,
  PRIMARY KEY ("sheet_id", "measure")
);

CREATE TABLE "wh_source_config" (
  "source_id" varchar PRIMARY KEY,
  "system_name" varchar,
  "export_format" varchar,
  "delivery" varchar
);

CREATE TABLE "wh_dual_currency_policy" (
  "report_id" varchar PRIMARY KEY,
  "primary_ccy" char(3),
  "secondary_ccy" char(3),
  "fx_rule_id" varchar
);

CREATE TABLE "wh_benchmark_sheet_status" (
  "benchmark_id" varchar,
  "workbook_sheet_id" varchar,
  "sheet_review_status" varchar,
  "open_question" text,
  PRIMARY KEY ("benchmark_id", "workbook_sheet_id")
);

COMMENT ON TABLE "party" IS 'Any person or organisation: family members, managers, banks, administrators, counterparties.';

COMMENT ON COLUMN "party"."display_name" IS 'Tokenised before any model call';

COMMENT ON COLUMN "party_role"."role" IS 'family_member, beneficiary, trustee, manager, gp, custodian, administrator, bank, counterparty, auditor';

COMMENT ON TABLE "entity" IS 'A legal entity the office reports on: holding company, trust, foundation, SPV.';

COMMENT ON COLUMN "entity"."tax_id_ref" IS 'Pointer only; the number itself stays restricted';

COMMENT ON COLUMN "entity"."sensitivity" IS 'open, internal, restricted';

COMMENT ON TABLE "entity_ownership" IS 'Effective-dated ownership tree, so look-through and consolidation can be rebuilt for any date.';

COMMENT ON COLUMN "portfolio"."strategy" IS 'e.g. liquid, private markets, real assets, cash';

COMMENT ON COLUMN "account"."provider_party_id" IS 'bank, custodian or broker';

COMMENT ON COLUMN "account"."account_kind" IS 'custody, bank, brokerage, fund_holding, loan';

COMMENT ON COLUMN "account"."account_ref_masked" IS 'Last digits only';

COMMENT ON COLUMN "app_user"."role" IS 'cio, operations, finance, risk, rule_owner, data_engineer, company_admin';

COMMENT ON TABLE "entitlement" IS 'Checked before every query, search and tool call. Search filters by this before retrieval.';

COMMENT ON COLUMN "entitlement"."scope_kind" IS 'entity, portfolio, document_class, project';

COMMENT ON COLUMN "entitlement"."level" IS 'full, read, preview, none';

COMMENT ON COLUMN "calendar_day"."calendar" IS 'e.g. SG, US, HK';

COMMENT ON TABLE "instrument" IS 'One row per thing the office can hold. Source systems name it differently; see instrument_identifier.';

COMMENT ON COLUMN "instrument"."manager_party_id" IS 'for funds';

COMMENT ON COLUMN "instrument"."liquidity" IS 'daily, monthly, quarterly, locked, illiquid';

COMMENT ON TABLE "instrument_identifier" IS 'The crosswalk. A new alias proposed by the intake agent is not used until a person confirms it.';

COMMENT ON COLUMN "instrument_identifier"."scheme" IS 'isin, cusip, sedol, figi, ticker, internal, administrator_id, oms_id, manager_name_alias';

COMMENT ON COLUMN "classification"."scheme" IS 'asset_class, region, sector, strategy, saa_bucket';

COMMENT ON TABLE "fund_terms" IS 'Private fund and fund-of-fund terms.';

COMMENT ON COLUMN "fund_terms"."valuation_frequency" IS 'monthly, quarterly';

COMMENT ON TABLE "derivative_terms" IS 'Terms only. Pricing models and Greeks stay in the risk system; we read their outputs.';

COMMENT ON COLUMN "derivative_terms"."contract_type" IS 'forward, swap, option, future';

COMMENT ON COLUMN "source_system"."name" IS 'e.g. administrator export, OMS export, manager email, market data, spreadsheet';

COMMENT ON COLUMN "source_system"."kind" IS 'system_export, api, mailbox, spreadsheet, document_share';

COMMENT ON COLUMN "source_system"."licence_class" IS 'internal, vendor_licensed, public';

COMMENT ON COLUMN "source_system"."permitted_use" IS 'e.g. may_index, may_send_to_model, display_only';

COMMENT ON COLUMN "source_system"."freshness_rule" IS 'e.g. daily by 08:00, monthly within 10 business days';

COMMENT ON TABLE "source_file" IS 'Every file that ever arrived, kept as received.';

COMMENT ON COLUMN "source_file"."sha256" IS 'Proves the original never changed';

COMMENT ON COLUMN "source_file"."storage_uri" IS 'Object store path of the untouched original';

COMMENT ON TABLE "load_batch" IS 'One run of ingestion. Raw rows keep their batch, so any figure traces to the file it came from.';

COMMENT ON COLUMN "load_batch"."status" IS 'loaded, failed, quarantined';

COMMENT ON COLUMN "document"."doc_type" IS 'statement, capital_call, distribution_notice, nav_report, policy, sop, email, memo, workbook';

COMMENT ON COLUMN "document"."version_label" IS 'original, amended, final';

COMMENT ON TABLE "passage" IS 'The RAG unit: 800 to 1,200 characters with page and line, searched by words and meaning.';

COMMENT ON COLUMN "passage"."embedding" IS 'pgvector at the client; local vector table on the laptop';

COMMENT ON TABLE "extraction" IS 'What the intake agent read. Low confidence or material values wait for a person.';

COMMENT ON COLUMN "extraction"."field" IS 'e.g. nav, units, valuation_date, call_amount, due_date';

COMMENT ON COLUMN "extraction"."confidence" IS 'high, medium, low';

COMMENT ON COLUMN "extraction"."extracted_by" IS 'agent and model version';

COMMENT ON TABLE "evidence_event" IS 'Append-only. "As known at T" = the latest event per subject with processed_at <= T and not superseded by then.';

COMMENT ON COLUMN "evidence_event"."kind" IS 'valuation, position, cash_flow, capital_call, distribution, price, fx_rate, nav, commitment, corporate_action';

COMMENT ON COLUMN "evidence_event"."subject_type" IS 'instrument, account, entity, portfolio';

COMMENT ON COLUMN "evidence_event"."effective_at" IS 'When it is true in the world, e.g. valuation date';

COMMENT ON COLUMN "evidence_event"."received_at" IS 'When the office learnt it';

COMMENT ON COLUMN "evidence_event"."processed_at" IS 'When we stored it';

COMMENT ON TABLE "capital_flow" IS 'Feeds the liquidity and commitment radar.';

COMMENT ON COLUMN "capital_flow"."kind" IS 'capital_call, distribution, recallable_distribution, fee, expense';

COMMENT ON COLUMN "capital_flow"."status" IS 'forecast, noticed, paid, received';

COMMENT ON TABLE "transaction" IS 'A backdated or amended trade is a new row that supersedes, never an edit.';

COMMENT ON COLUMN "transaction"."kind" IS 'buy, sell, subscription, redemption, income, fee, transfer, fx, cash';

COMMENT ON COLUMN "transaction"."booking_status" IS 'booked, amended, cancelled, backdated';

COMMENT ON COLUMN "corporate_action"."kind" IS 'split, dividend, merger, spin_off, name_change';

COMMENT ON COLUMN "price"."price_type" IS 'close, bid, mid, nav, manual';

COMMENT ON COLUMN "fx_rate"."fixing" IS 'e.g. WMR 4pm London; the fixing is a signed rule';

COMMENT ON TABLE "valuation" IS 'Estimated and official values live side by side, each with its status.';

COMMENT ON COLUMN "valuation"."method" IS 'market, manager_nav, administrator_nav, model, cost, proxy';

COMMENT ON TABLE "administrator_nav" IS 'The official accounting view. The product reads it and never changes it.';

COMMENT ON COLUMN "administrator_nav"."approval_status" IS 'draft, approved, restated';

COMMENT ON COLUMN "gl_account"."kind" IS 'asset, liability, equity, income, expense';

COMMENT ON COLUMN "rule"."kind" IS 'tolerance, materiality, formula, source_of_truth, fx_fixing, due_date, estimate_use';

COMMENT ON TABLE "rule_version" IS 'A rule takes effect only once signed. Past reports keep the version they used.';

COMMENT ON COLUMN "rule_version"."definition" IS 'Plain words plus the machine form';

COMMENT ON COLUMN "rule_version"."state" IS 'draft, signed, retired';

COMMENT ON COLUMN "calculation_version"."name" IS 'e.g. twr_monthly, benchmark_blend, cash_recon';

COMMENT ON COLUMN "calculation_version"."rule_versions" IS 'rule_id:version list used';

COMMENT ON COLUMN "benchmark_component"."spread_bps" IS 'premium over an index, e.g. index + 300 bps';

COMMENT ON COLUMN "allocation_limit"."dimension" IS 'asset_class, region, manager, liquidity, single_name';

COMMENT ON COLUMN "performance_result"."method" IS 'twr, mwr, irr, tvpi, dpi';

COMMENT ON COLUMN "report_definition"."audience" IS 'cio, family, investment_committee, finance';

COMMENT ON COLUMN "report_definition"."reporting_currencies" IS 'e.g. USD,SGD';

COMMENT ON COLUMN "report_version"."cutoff_at" IS 'Evidence processed after this is not in the report';

COMMENT ON COLUMN "report_version"."status" IS 'draft, ready_for_review, approved, issued, superseded';

COMMENT ON COLUMN "report_line"."line_key" IS 'e.g. fund_a_value, total_nav, ytd_return_usd';

COMMENT ON COLUMN "report_line"."evidence_event_ids" IS 'The events this figure used';

COMMENT ON COLUMN "finding"."kind" IS 'revision, break, missing_document, limit_breach, stale_data';

COMMENT ON COLUMN "finding"."materiality" IS 'low, medium, high, from the signed materiality rule';

COMMENT ON COLUMN "work_case"."case_id" IS 'CASE-0107 style number';

COMMENT ON COLUMN "work_case"."state" IS 'open, in_progress, waiting_check, resolved, dismissed';

COMMENT ON COLUMN "work_case"."checker_user_id" IS 'Never the same person as the maker';

COMMENT ON COLUMN "work_case"."explanation" IS 'Proposed by the investigation agent; confirmed by the maker';

COMMENT ON TABLE "case_event" IS 'Append-only audit trail.';

COMMENT ON COLUMN "case_event"."by_actor" IS 'user id or agent name';

COMMENT ON COLUMN "case_event"."action" IS 'opened, assigned, delegated, commented, submitted, approved, sent_back, resolved, dismissed, reopened';

COMMENT ON TABLE "report_impact" IS 'Which issued reports a finding touches, and the draft revised figure.';

COMMENT ON COLUMN "pulse_card"."bucket" IS 'needs_me, worth_a_look';

COMMENT ON COLUMN "pulse_card"."acted" IS 'opened, acted, dismissed, ignored';

COMMENT ON COLUMN "workbook_sheet"."sheet_purpose" IS 'positions, valuations, cash, benchmark, mapping, notes; proposed by the agent';

COMMENT ON COLUMN "workbook_sheet"."status" IS 'profiled, mapped, validated, loaded, in_progress_in_workbook';

COMMENT ON COLUMN "column_mapping"."transform" IS 'e.g. parse date dd/mm/yyyy, units in thousands';

COMMENT ON COLUMN "column_mapping"."proposed_by" IS 'agent';

COMMENT ON TABLE "control_total" IS 'A sheet is accepted only when what we loaded adds up to what the workbook says.';

COMMENT ON COLUMN "control_total"."measure" IS 'e.g. total NAV, row count, sum of cash';

COMMENT ON COLUMN "control_total"."expected_value" IS 'Read from the workbook itself';

COMMENT ON COLUMN "control_total"."loaded_value" IS 'Computed after load';

COMMENT ON TABLE "wh_source_config" IS '[Ardmore] Sources are configuration rows, never hard-coded tables. * subject to licence and permitted use.';

COMMENT ON COLUMN "wh_source_config"."system_name" IS '[Ardmore] LGH (trades, positions), SS&C (administrator NAV, accounting), SAP B1 (ledger), Bloomberg* (prices, indices), Burgiss* (private markets), manager email and portals, the benchmark workbook';

COMMENT ON COLUMN "wh_source_config"."delivery" IS 'SFTP, API, mailbox, manual upload';

COMMENT ON TABLE "wh_dual_currency_policy" IS '[Ardmore] Dual-currency P&L and performance was a deal-breaking requirement in their past vendor evaluation.';

COMMENT ON COLUMN "wh_dual_currency_policy"."primary_ccy" IS '[Ardmore] USD';

COMMENT ON COLUMN "wh_dual_currency_policy"."secondary_ccy" IS '[Ardmore] SGD';

COMMENT ON TABLE "wh_benchmark_sheet_status" IS '[Ardmore] Sheets still In Progress raise a question to the rule owner; they are never certified automatically.';

COMMENT ON COLUMN "wh_benchmark_sheet_status"."sheet_review_status" IS '[Ardmore] e.g. Approved or In Progress, as marked in the benchmark specification workbook';

COMMENT ON COLUMN "wh_benchmark_sheet_status"."open_question" IS 'e.g. replacement for a discontinued reference rate';

ALTER TABLE "party_role" ADD FOREIGN KEY ("party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entity" ADD FOREIGN KEY ("base_currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entity_ownership" ADD FOREIGN KEY ("parent_entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entity_ownership" ADD FOREIGN KEY ("child_entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entity_ownership" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "portfolio" ADD FOREIGN KEY ("owner_entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "portfolio" ADD FOREIGN KEY ("reporting_currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "account" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "account" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("portfolio_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "account" ADD FOREIGN KEY ("provider_party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "account" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "app_user" ADD FOREIGN KEY ("party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entitlement" ADD FOREIGN KEY ("user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "entitlement" ADD FOREIGN KEY ("granted_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument" ADD FOREIGN KEY ("issuer_party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument" ADD FOREIGN KEY ("manager_party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifier" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifier" ADD FOREIGN KEY ("confirmed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "classification" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "fund_terms" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "fund_terms" ADD FOREIGN KEY ("administrator_party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "derivative_terms" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "derivative_terms" ADD FOREIGN KEY ("underlying_instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "derivative_terms" ADD FOREIGN KEY ("notional_currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "derivative_terms" ADD FOREIGN KEY ("counterparty_party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_system" ADD FOREIGN KEY ("owner_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_file" ADD FOREIGN KEY ("source_id") REFERENCES "source_system" ("source_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "load_batch" ADD FOREIGN KEY ("source_id") REFERENCES "source_system" ("source_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "load_batch" ADD FOREIGN KEY ("file_id") REFERENCES "source_file" ("file_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("file_id") REFERENCES "source_file" ("file_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("manager_party_id") REFERENCES "party" ("party_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document" ADD FOREIGN KEY ("supersedes_document_id") REFERENCES "document" ("document_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "passage" ADD FOREIGN KEY ("document_id") REFERENCES "document" ("document_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extraction" ADD FOREIGN KEY ("document_id") REFERENCES "document" ("document_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extraction" ADD FOREIGN KEY ("verified_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("supersedes_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("source_batch_id") REFERENCES "load_batch" ("batch_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("extraction_id") REFERENCES "extraction" ("extraction_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_event" ADD FOREIGN KEY ("reviewed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commitment" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commitment" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commitment" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commitment" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "capital_flow" ADD FOREIGN KEY ("commitment_id") REFERENCES "commitment" ("commitment_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "capital_flow" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "capital_flow" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transaction" ADD FOREIGN KEY ("account_id") REFERENCES "account" ("account_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transaction" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transaction" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transaction" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "corporate_action" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "corporate_action" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position" ADD FOREIGN KEY ("account_id") REFERENCES "account" ("account_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "price" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "price" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "price" ADD FOREIGN KEY ("source_id") REFERENCES "source_system" ("source_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "fx_rate" ADD FOREIGN KEY ("from_ccy") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "fx_rate" ADD FOREIGN KEY ("to_ccy") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "fx_rate" ADD FOREIGN KEY ("source_id") REFERENCES "source_system" ("source_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation" ADD FOREIGN KEY ("instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "administrator_nav" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "administrator_nav" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("portfolio_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "administrator_nav" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "administrator_nav" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "gl_account" ADD FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "journal_line" ADD FOREIGN KEY ("gl_account_id") REFERENCES "gl_account" ("gl_account_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "journal_line" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "journal_line" ADD FOREIGN KEY ("source_event_id") REFERENCES "evidence_event" ("event_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule" ADD FOREIGN KEY ("owner_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule_version" ADD FOREIGN KEY ("rule_id") REFERENCES "rule" ("rule_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule_version" ADD FOREIGN KEY ("signed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "calculation_version" ADD FOREIGN KEY ("released_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark" ADD FOREIGN KEY ("owner_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark" ADD FOREIGN KEY ("methodology_rule_id") REFERENCES "rule" ("rule_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark_component" ADD FOREIGN KEY ("benchmark_id") REFERENCES "benchmark" ("benchmark_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark_component" ADD FOREIGN KEY ("index_instrument_id") REFERENCES "instrument" ("instrument_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "allocation_limit" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("portfolio_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "allocation_limit" ADD FOREIGN KEY ("rule_id") REFERENCES "rule" ("rule_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "performance_result" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolio" ("portfolio_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "performance_result" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "performance_result" ADD FOREIGN KEY ("calc_id") REFERENCES "calculation_version" ("calc_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_definition" ADD FOREIGN KEY ("contract_id") REFERENCES "decision_contract" ("contract_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_version" ADD FOREIGN KEY ("report_id") REFERENCES "report_definition" ("report_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_version" ADD FOREIGN KEY ("calc_id") REFERENCES "calculation_version" ("calc_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_version" ADD FOREIGN KEY ("approved_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_version" ADD FOREIGN KEY ("supersedes_version_id") REFERENCES "report_version" ("report_version_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_line" ADD FOREIGN KEY ("report_version_id") REFERENCES "report_version" ("report_version_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_line" ADD FOREIGN KEY ("currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "decision_contract" ADD FOREIGN KEY ("owner_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "finding" ADD FOREIGN KEY ("effect_currency") REFERENCES "currency" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "finding" ADD FOREIGN KEY ("calc_id") REFERENCES "calculation_version" ("calc_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "work_case" ADD FOREIGN KEY ("finding_id") REFERENCES "finding" ("finding_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "work_case" ADD FOREIGN KEY ("maker_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "work_case" ADD FOREIGN KEY ("checker_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "case_event" ADD FOREIGN KEY ("case_id") REFERENCES "work_case" ("case_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_impact" ADD FOREIGN KEY ("finding_id") REFERENCES "finding" ("finding_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_impact" ADD FOREIGN KEY ("report_version_id") REFERENCES "report_version" ("report_version_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_card" ADD FOREIGN KEY ("user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_card" ADD FOREIGN KEY ("finding_id") REFERENCES "finding" ("finding_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_card" ADD FOREIGN KEY ("case_id") REFERENCES "work_case" ("case_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "workbook_sheet" ADD FOREIGN KEY ("file_id") REFERENCES "source_file" ("file_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "workbook_sheet" ADD FOREIGN KEY ("owner_user_id") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "column_mapping" ADD FOREIGN KEY ("sheet_id") REFERENCES "workbook_sheet" ("sheet_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "column_mapping" ADD FOREIGN KEY ("confirmed_by") REFERENCES "app_user" ("user_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "control_total" ADD FOREIGN KEY ("sheet_id") REFERENCES "workbook_sheet" ("sheet_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "wh_source_config" ADD FOREIGN KEY ("source_id") REFERENCES "source_system" ("source_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "wh_dual_currency_policy" ADD FOREIGN KEY ("report_id") REFERENCES "report_definition" ("report_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "wh_dual_currency_policy" ADD FOREIGN KEY ("fx_rule_id") REFERENCES "rule" ("rule_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "wh_benchmark_sheet_status" ADD FOREIGN KEY ("benchmark_id") REFERENCES "benchmark" ("benchmark_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "wh_benchmark_sheet_status" ADD FOREIGN KEY ("workbook_sheet_id") REFERENCES "workbook_sheet" ("sheet_id") DEFERRABLE INITIALLY IMMEDIATE;
