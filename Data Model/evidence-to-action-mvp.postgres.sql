CREATE TABLE "organizations" (
  "id" uuid PRIMARY KEY,
  "name" varchar(200) NOT NULL,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "users" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "external_identity_id" varchar(255) NOT NULL,
  "display_name" varchar(200) NOT NULL,
  "email" varchar(255) NOT NULL,
  "business_role" varchar(100),
  "is_active" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "access_groups" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "group_name" varchar(150) NOT NULL,
  "description" text
);

CREATE TABLE "access_group_memberships" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "access_group_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "granted_at" timestamptz NOT NULL,
  "granted_by" uuid,
  "expires_at" timestamptz
);

CREATE TABLE "access_group_scopes" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "access_group_id" uuid NOT NULL,
  "scope_type" varchar(40) NOT NULL,
  "scope_value" varchar(255) NOT NULL,
  "access_level" varchar(20) NOT NULL
);

CREATE TABLE "legal_entities" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "entity_code" varchar(80) NOT NULL,
  "entity_name" varchar(200) NOT NULL,
  "base_currency" char(3) NOT NULL,
  "active_from" date,
  "active_to" date
);

CREATE TABLE "portfolios" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "legal_entity_id" uuid NOT NULL,
  "portfolio_code" varchar(80) NOT NULL,
  "portfolio_name" varchar(200) NOT NULL,
  "base_currency" char(3) NOT NULL,
  "active_from" date,
  "active_to" date
);

CREATE TABLE "instruments" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "canonical_name" varchar(255) NOT NULL,
  "instrument_type" varchar(80) NOT NULL,
  "asset_class" varchar(80),
  "manager_name" varchar(200),
  "currency" char(3),
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "instrument_identifiers" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "instrument_id" uuid NOT NULL,
  "source_system_id" uuid NOT NULL,
  "identifier_type" varchar(80) NOT NULL,
  "identifier_value" varchar(255) NOT NULL,
  "valid_from" date,
  "valid_to" date,
  "mapping_status" varchar(40) NOT NULL,
  "proposed_by_agent_run_id" uuid,
  "approved_by" uuid,
  "approved_at" timestamptz
);

CREATE TABLE "source_systems" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_code" varchar(80) NOT NULL,
  "source_name" varchar(200) NOT NULL,
  "source_type" varchar(80) NOT NULL,
  "connection_method" varchar(80),
  "owner_user_id" uuid,
  "licence_scope" varchar(255),
  "permitted_use" varchar(255),
  "expected_cadence" varchar(80),
  "is_active" boolean NOT NULL DEFAULT true
);

CREATE TABLE "sheet_mappings" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_system_id" uuid NOT NULL,
  "file_pattern" varchar(255) NOT NULL,
  "sheet_name" varchar(150),
  "header_row" int,
  "version_number" int NOT NULL,
  "mapping_status" varchar(40) NOT NULL,
  "proposed_by_agent_run_id" uuid,
  "approved_by" uuid,
  "approved_at" timestamptz
);

CREATE TABLE "sheet_mapping_columns" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "sheet_mapping_id" uuid NOT NULL,
  "source_column" varchar(150) NOT NULL,
  "target_table" varchar(80) NOT NULL,
  "target_field" varchar(80) NOT NULL,
  "transform_rule" varchar(255)
);

CREATE TABLE "source_batches" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_system_id" uuid NOT NULL,
  "sheet_mapping_id" uuid,
  "batch_reference" varchar(150) NOT NULL,
  "received_at" timestamptz NOT NULL,
  "loaded_at" timestamptz,
  "source_period_end" date,
  "content_hash" varchar(128),
  "storage_uri" text,
  "validation_status" varchar(40) NOT NULL,
  "validation_summary" text
);

CREATE TABLE "batch_control_totals" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_batch_id" uuid NOT NULL,
  "measure_name" varchar(150) NOT NULL,
  "expected_value" numeric(28,8) NOT NULL,
  "loaded_value" numeric(28,8),
  "tolerance" numeric(28,8),
  "passed" boolean
);

CREATE TABLE "source_records" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_batch_id" uuid NOT NULL,
  "external_record_id" varchar(255),
  "record_type" varchar(100) NOT NULL,
  "effective_at" timestamptz,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "sheet_name" varchar(150),
  "row_number" int,
  "cell_range" varchar(50),
  "raw_payload_uri" text NOT NULL,
  "content_hash" varchar(128) NOT NULL,
  "supersedes_record_id" uuid,
  "quality_status" varchar(40) NOT NULL
);

CREATE TABLE "documents" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_system_id" uuid NOT NULL,
  "source_record_id" uuid,
  "access_group_id" uuid NOT NULL,
  "instrument_id" uuid,
  "external_document_id" varchar(255),
  "document_type" varchar(100) NOT NULL,
  "title" varchar(300) NOT NULL,
  "original_filename" varchar(300),
  "original_uri" text NOT NULL,
  "content_hash" varchar(128) NOT NULL,
  "document_date" date,
  "valuation_date" date,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "document_status" varchar(40) NOT NULL,
  "supersedes_document_id" uuid,
  "processing_status" varchar(40) NOT NULL,
  "contains_personal_data" boolean
);

CREATE TABLE "document_passages" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "document_id" uuid NOT NULL,
  "access_group_id" uuid NOT NULL,
  "passage_order" int NOT NULL,
  "page_number" int,
  "line_from" int,
  "line_to" int,
  "section_label" varchar(200),
  "table_reference" varchar(100),
  "passage_text" text NOT NULL,
  "search_text" tsvector,
  "embedding" vector(384),
  "extraction_confidence" numeric(5,4),
  "embedding_model_version" varchar(100),
  "indexed_at" timestamptz
);

CREATE TABLE "extracted_fields" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "document_id" uuid NOT NULL,
  "document_passage_id" uuid,
  "field_name" varchar(100) NOT NULL,
  "value_text" varchar(255),
  "value_numeric" numeric(28,10),
  "currency" char(3),
  "page_number" int,
  "line_number" int,
  "confidence" varchar(20) NOT NULL,
  "extracted_by_agent_run_id" uuid,
  "review_status" varchar(40) NOT NULL,
  "reviewed_by" uuid,
  "reviewed_at" timestamptz,
  "corrected_value_text" varchar(255)
);

CREATE TABLE "transactions" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_record_id" uuid NOT NULL,
  "portfolio_id" uuid NOT NULL,
  "instrument_id" uuid NOT NULL,
  "external_trade_id" varchar(200),
  "transaction_type" varchar(80) NOT NULL,
  "trade_date" date,
  "effective_date" date NOT NULL,
  "settlement_date" date,
  "quantity_delta" numeric(28,10),
  "cash_amount" numeric(28,8),
  "currency" char(3) NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "status" varchar(40) NOT NULL,
  "supersedes_transaction_id" uuid
);

CREATE TABLE "position_snapshots" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_record_id" uuid NOT NULL,
  "portfolio_id" uuid NOT NULL,
  "instrument_id" uuid NOT NULL,
  "position_date" date NOT NULL,
  "as_of_at" timestamptz NOT NULL,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "quantity" numeric(28,10),
  "source_market_value" numeric(28,8),
  "currency" char(3),
  "view_type" varchar(50) NOT NULL,
  "data_status" varchar(50) NOT NULL,
  "supersedes_position_id" uuid
);

CREATE TABLE "valuation_observations" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "instrument_id" uuid NOT NULL,
  "portfolio_id" uuid,
  "source_record_id" uuid,
  "evidence_document_id" uuid,
  "extracted_field_id" uuid,
  "valuation_date" date NOT NULL,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "value_amount" numeric(28,8) NOT NULL,
  "currency" char(3) NOT NULL,
  "valuation_type" varchar(80) NOT NULL,
  "approval_status" varchar(40) NOT NULL,
  "supersedes_valuation_id" uuid
);

CREATE TABLE "cash_movements" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_record_id" uuid NOT NULL,
  "portfolio_id" uuid NOT NULL,
  "instrument_id" uuid,
  "movement_type" varchar(80) NOT NULL,
  "effective_date" date NOT NULL,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "amount" numeric(28,8) NOT NULL,
  "currency" char(3) NOT NULL,
  "confirmation_status" varchar(40) NOT NULL,
  "supersedes_cash_movement_id" uuid
);

CREATE TABLE "market_observations" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "source_record_id" uuid NOT NULL,
  "instrument_id" uuid,
  "series_key" varchar(150) NOT NULL,
  "observation_type" varchar(50) NOT NULL,
  "observed_at" timestamptz NOT NULL,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "value" numeric(28,10) NOT NULL,
  "base_currency" char(3),
  "quote_currency" char(3),
  "quality_status" varchar(40) NOT NULL,
  "supersedes_observation_id" uuid
);

CREATE TABLE "nav_snapshots" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "portfolio_id" uuid NOT NULL,
  "source_record_id" uuid NOT NULL,
  "nav_period_end" date NOT NULL,
  "received_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  "nav_amount" numeric(28,8) NOT NULL,
  "currency" char(3) NOT NULL,
  "nav_status" varchar(50) NOT NULL,
  "approved_at" timestamptz,
  "supersedes_nav_id" uuid
);

CREATE TABLE "business_rules" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "rule_code" varchar(100) NOT NULL,
  "rule_type" varchar(50) NOT NULL,
  "owner_user_id" uuid NOT NULL
);

CREATE TABLE "rule_versions" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "business_rule_id" uuid NOT NULL,
  "version_number" int NOT NULL,
  "definition_text" text NOT NULL,
  "parameters" jsonb,
  "effective_from" date NOT NULL,
  "effective_to" date,
  "approval_status" varchar(40) NOT NULL,
  "approved_by" uuid,
  "approved_at" timestamptz
);

CREATE TABLE "benchmark_definitions" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "benchmark_code" varchar(100) NOT NULL,
  "benchmark_name" varchar(200) NOT NULL,
  "version_number" int NOT NULL,
  "reporting_currency" char(3) NOT NULL,
  "effective_from" date NOT NULL,
  "effective_to" date,
  "calculation_method" text NOT NULL,
  "approval_status" varchar(40) NOT NULL,
  "approved_by" uuid
);

CREATE TABLE "benchmark_components" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "benchmark_definition_id" uuid NOT NULL,
  "market_series_key" varchar(150) NOT NULL,
  "component_weight" numeric(18,10) NOT NULL,
  "spread_bps" numeric(12,4),
  "weight_effective_from" date NOT NULL,
  "weight_effective_to" date,
  "treatment_note" text
);

CREATE TABLE "decision_intents" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "requested_by" uuid NOT NULL,
  "business_owner_id" uuid,
  "title" varchar(250) NOT NULL,
  "business_question" text NOT NULL,
  "intended_audience" varchar(255),
  "permitted_use" varchar(100) NOT NULL,
  "value_basis" varchar(40),
  "output_description" text,
  "acceptance_tests" text,
  "open_choices" text,
  "status" varchar(50) NOT NULL,
  "contract_version" int NOT NULL DEFAULT 1,
  "approved_at" timestamptz,
  "created_at" timestamptz NOT NULL
);

CREATE TABLE "metric_definitions" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "decision_intent_id" uuid,
  "metric_code" varchar(120) NOT NULL,
  "metric_name" varchar(200) NOT NULL,
  "version_number" int NOT NULL,
  "definition_text" text NOT NULL,
  "implementation_ref" varchar(255) NOT NULL,
  "owner_user_id" uuid NOT NULL,
  "approval_status" varchar(40) NOT NULL
);

CREATE TABLE "calculation_runs" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "decision_intent_id" uuid,
  "started_at" timestamptz NOT NULL,
  "finished_at" timestamptz,
  "knowledge_cutoff_at" timestamptz NOT NULL,
  "reporting_date" date NOT NULL,
  "code_version" varchar(120) NOT NULL,
  "rule_versions_used" jsonb,
  "input_manifest_uri" text NOT NULL,
  "run_status" varchar(50) NOT NULL,
  "validation_status" varchar(50) NOT NULL
);

CREATE TABLE "metric_values" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "calculation_run_id" uuid NOT NULL,
  "metric_definition_id" uuid NOT NULL,
  "portfolio_id" uuid,
  "instrument_id" uuid,
  "reporting_date" date NOT NULL,
  "numeric_value" numeric(28,10),
  "currency" char(3),
  "value_status" varchar(50) NOT NULL,
  "published_at" timestamptz
);

CREATE TABLE "metric_evidence" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "metric_value_id" uuid NOT NULL,
  "source_record_id" uuid,
  "document_passage_id" uuid,
  "extracted_field_id" uuid,
  "evidence_role" varchar(80) NOT NULL,
  "note" text
);

CREATE TABLE "reports" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "decision_intent_id" uuid,
  "report_code" varchar(100) NOT NULL,
  "report_name" varchar(200) NOT NULL,
  "audience" varchar(150),
  "reporting_currencies" varchar(20)
);

CREATE TABLE "report_versions" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "report_id" uuid NOT NULL,
  "calculation_run_id" uuid NOT NULL,
  "period_end" date NOT NULL,
  "cutoff_at" timestamptz NOT NULL,
  "status" varchar(40) NOT NULL,
  "approved_by" uuid,
  "issued_at" timestamptz,
  "supersedes_report_version_id" uuid
);

CREATE TABLE "exceptions" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "decision_intent_id" uuid,
  "calculation_run_id" uuid,
  "portfolio_id" uuid,
  "instrument_id" uuid,
  "exception_type" varchar(100) NOT NULL,
  "title" varchar(250) NOT NULL,
  "description" text,
  "detected_at" timestamptz NOT NULL,
  "candidate_impact_amount" numeric(28,8),
  "impact_currency" char(3),
  "materiality_status" varchar(50) NOT NULL,
  "materiality_rule_version_id" uuid,
  "status" varchar(50) NOT NULL,
  "owner_user_id" uuid,
  "due_at" timestamptz,
  "resolution_code" varchar(100),
  "resolved_at" timestamptz
);

CREATE TABLE "exception_impacts" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "exception_id" uuid NOT NULL,
  "report_version_id" uuid NOT NULL,
  "metric_value_id" uuid,
  "issued_value" numeric(28,10),
  "draft_value" numeric(28,10),
  "currency" char(3)
);

CREATE TABLE "exception_events" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "exception_id" uuid NOT NULL,
  "performed_by_user_id" uuid,
  "agent_run_id" uuid,
  "event_type" varchar(80) NOT NULL,
  "event_note" text,
  "occurred_at" timestamptz NOT NULL,
  "source_record_id" uuid,
  "evidence_document_id" uuid
);

CREATE TABLE "approvals" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "decision_intent_id" uuid,
  "calculation_run_id" uuid,
  "exception_id" uuid,
  "report_version_id" uuid,
  "rule_version_id" uuid,
  "sheet_mapping_id" uuid,
  "approval_type" varchar(100) NOT NULL,
  "requested_from_user_id" uuid NOT NULL,
  "decision_by_user_id" uuid,
  "status" varchar(40) NOT NULL,
  "rationale" text,
  "requested_at" timestamptz NOT NULL,
  "decided_at" timestamptz
);

CREATE TABLE "pulse_items" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "recipient_user_id" uuid NOT NULL,
  "exception_id" uuid,
  "metric_value_id" uuid,
  "headline" varchar(250) NOT NULL,
  "summary" text NOT NULL,
  "generated_at" timestamptz NOT NULL,
  "as_of_at" timestamptz NOT NULL,
  "urgency" varchar(40) NOT NULL,
  "action_type" varchar(80),
  "delivery_status" varchar(40) NOT NULL,
  "acknowledged_at" timestamptz,
  "outcome" varchar(40)
);

CREATE TABLE "agent_runs" (
  "id" uuid PRIMARY KEY,
  "organization_id" uuid NOT NULL,
  "decision_intent_id" uuid,
  "exception_id" uuid,
  "acting_for_user_id" uuid,
  "agent_type" varchar(100) NOT NULL,
  "model_id" varchar(150) NOT NULL,
  "prompt_version" varchar(100) NOT NULL,
  "tool_policy_version" varchar(100) NOT NULL,
  "started_at" timestamptz NOT NULL,
  "finished_at" timestamptz,
  "run_status" varchar(50) NOT NULL,
  "tool_calls" int,
  "cost_usd" numeric(12,6),
  "trace_id" varchar(150),
  "output_artifact_uri" text,
  "human_review_status" varchar(50)
);

CREATE UNIQUE INDEX ON "users" ("organization_id", "external_identity_id");

CREATE INDEX ON "users" ("organization_id", "email");

CREATE UNIQUE INDEX ON "access_groups" ("organization_id", "group_name");

CREATE UNIQUE INDEX ON "access_group_memberships" ("access_group_id", "user_id");

CREATE UNIQUE INDEX ON "access_group_scopes" ("access_group_id", "scope_type", "scope_value");

CREATE UNIQUE INDEX ON "legal_entities" ("organization_id", "entity_code");

CREATE UNIQUE INDEX ON "portfolios" ("organization_id", "portfolio_code");

CREATE INDEX ON "instruments" ("organization_id", "canonical_name");

CREATE UNIQUE INDEX ON "instrument_identifiers" ("organization_id", "source_system_id", "identifier_type", "identifier_value", "valid_from");

CREATE INDEX ON "instrument_identifiers" ("instrument_id", "source_system_id");

CREATE UNIQUE INDEX ON "source_systems" ("organization_id", "source_code");

CREATE UNIQUE INDEX ON "sheet_mappings" ("source_system_id", "file_pattern", "sheet_name", "version_number");

CREATE UNIQUE INDEX ON "sheet_mapping_columns" ("sheet_mapping_id", "source_column");

CREATE UNIQUE INDEX ON "source_batches" ("source_system_id", "batch_reference");

CREATE INDEX ON "source_batches" ("organization_id", "received_at");

CREATE UNIQUE INDEX ON "batch_control_totals" ("source_batch_id", "measure_name");

CREATE INDEX ON "source_records" ("source_batch_id", "external_record_id");

CREATE INDEX ON "source_records" ("organization_id", "record_type", "effective_at");

CREATE INDEX ON "source_records" ("organization_id", "received_at");

CREATE INDEX ON "source_records" ("organization_id", "recorded_at");

CREATE INDEX ON "documents" ("organization_id", "document_type", "received_at");

CREATE INDEX ON "documents" ("instrument_id", "valuation_date");

CREATE INDEX ON "documents" ("content_hash");

CREATE UNIQUE INDEX ON "document_passages" ("document_id", "passage_order");

CREATE INDEX ON "document_passages" ("organization_id", "indexed_at");

CREATE INDEX ON "extracted_fields" ("document_id", "field_name");

CREATE INDEX ON "extracted_fields" ("organization_id", "review_status");

CREATE INDEX ON "transactions" ("portfolio_id", "instrument_id", "effective_date");

CREATE INDEX ON "transactions" ("external_trade_id", "recorded_at");

CREATE INDEX ON "position_snapshots" ("portfolio_id", "instrument_id", "position_date", "received_at");

CREATE INDEX ON "position_snapshots" ("organization_id", "recorded_at");

CREATE INDEX ON "valuation_observations" ("instrument_id", "portfolio_id", "valuation_date", "received_at");

CREATE INDEX ON "valuation_observations" ("organization_id", "recorded_at");

CREATE INDEX ON "cash_movements" ("portfolio_id", "instrument_id", "effective_date");

CREATE INDEX ON "market_observations" ("series_key", "observed_at", "received_at");

CREATE INDEX ON "nav_snapshots" ("portfolio_id", "nav_period_end", "received_at");

CREATE UNIQUE INDEX ON "business_rules" ("organization_id", "rule_code");

CREATE UNIQUE INDEX ON "rule_versions" ("business_rule_id", "version_number");

CREATE UNIQUE INDEX ON "benchmark_definitions" ("organization_id", "benchmark_code", "version_number");

CREATE INDEX ON "benchmark_components" ("benchmark_definition_id", "market_series_key", "weight_effective_from");

CREATE INDEX ON "decision_intents" ("organization_id", "status", "created_at");

CREATE UNIQUE INDEX ON "metric_definitions" ("organization_id", "metric_code", "version_number");

CREATE INDEX ON "calculation_runs" ("organization_id", "reporting_date", "knowledge_cutoff_at");

CREATE INDEX ON "metric_values" ("portfolio_id", "reporting_date", "metric_definition_id");

CREATE INDEX ON "metric_values" ("calculation_run_id", "metric_definition_id");

CREATE INDEX ON "metric_evidence" ("metric_value_id", "evidence_role");

CREATE UNIQUE INDEX ON "reports" ("organization_id", "report_code");

CREATE INDEX ON "report_versions" ("report_id", "period_end", "issued_at");

CREATE INDEX ON "exceptions" ("organization_id", "status", "due_at");

CREATE INDEX ON "exceptions" ("portfolio_id", "detected_at");

CREATE INDEX ON "exception_impacts" ("exception_id", "report_version_id");

CREATE INDEX ON "exception_events" ("exception_id", "occurred_at");

CREATE INDEX ON "approvals" ("organization_id", "status", "requested_from_user_id");

CREATE INDEX ON "pulse_items" ("recipient_user_id", "generated_at");

CREATE INDEX ON "pulse_items" ("organization_id", "urgency", "delivery_status");

CREATE INDEX ON "agent_runs" ("organization_id", "agent_type", "started_at");

CREATE INDEX ON "agent_runs" ("trace_id");

COMMENT ON COLUMN "access_group_scopes"."scope_type" IS 'legal_entity, portfolio, document_type';

COMMENT ON COLUMN "access_group_scopes"."scope_value" IS 'legal_entity id, portfolio id or document type';

COMMENT ON COLUMN "access_group_scopes"."access_level" IS 'full, read, preview';

COMMENT ON COLUMN "instruments"."instrument_type" IS 'Examples: listed_equity, fund, bond, option, swap';

COMMENT ON COLUMN "instrument_identifiers"."mapping_status" IS 'proposed, approved, rejected';

COMMENT ON COLUMN "instrument_identifiers"."proposed_by_agent_run_id" IS 'ADDED: which agent proposed the alias';

COMMENT ON COLUMN "source_systems"."source_type" IS 'OMS, administrator, manager, market_data, internal, spreadsheet';

COMMENT ON COLUMN "source_systems"."permitted_use" IS 'ADDED: e.g. display_only, may_index, may_send_to_model';

COMMENT ON COLUMN "sheet_mappings"."file_pattern" IS 'e.g. Positions *.xlsx';

COMMENT ON COLUMN "sheet_mappings"."mapping_status" IS 'proposed, approved, retired';

COMMENT ON COLUMN "sheet_mapping_columns"."target_table" IS 'e.g. position_snapshots';

COMMENT ON COLUMN "sheet_mapping_columns"."transform_rule" IS 'e.g. date dd/mm/yyyy, values in thousands';

COMMENT ON COLUMN "source_batches"."sheet_mapping_id" IS 'ADDED: mapping version used for a spreadsheet batch';

COMMENT ON COLUMN "source_batches"."loaded_at" IS 'ADDED';

COMMENT ON COLUMN "source_batches"."validation_status" IS 'loaded, rejected_totals, quarantined';

COMMENT ON COLUMN "batch_control_totals"."measure_name" IS 'e.g. row count, total market value, total cash';

COMMENT ON COLUMN "batch_control_totals"."expected_value" IS 'Read from the source file';

COMMENT ON COLUMN "source_records"."recorded_at" IS 'ADDED: when we stored it; drives as-known-at queries';

COMMENT ON COLUMN "source_records"."sheet_name" IS 'ADDED: locator for spreadsheet rows';

COMMENT ON COLUMN "source_records"."row_number" IS 'ADDED';

COMMENT ON COLUMN "source_records"."cell_range" IS 'ADDED';

COMMENT ON COLUMN "documents"."recorded_at" IS 'ADDED';

COMMENT ON COLUMN "documents"."document_status" IS 'estimate, revised_estimate, final, policy, research';

COMMENT ON COLUMN "documents"."contains_personal_data" IS 'ADDED: from the local scan; such passages need approval before indexing';

COMMENT ON COLUMN "document_passages"."line_from" IS 'ADDED';

COMMENT ON COLUMN "document_passages"."line_to" IS 'ADDED';

COMMENT ON COLUMN "document_passages"."search_text" IS 'ADDED: keyword search';

COMMENT ON COLUMN "document_passages"."embedding" IS 'ADDED: pgvector, meaning search; dimension follows the embedding model';

COMMENT ON COLUMN "extracted_fields"."field_name" IS 'e.g. nav, units, valuation_date, call_amount, due_date';

COMMENT ON COLUMN "extracted_fields"."confidence" IS 'high, medium, low';

COMMENT ON COLUMN "extracted_fields"."review_status" IS 'pending, confirmed, corrected, rejected';

COMMENT ON COLUMN "position_snapshots"."recorded_at" IS 'ADDED';

COMMENT ON COLUMN "position_snapshots"."view_type" IS 'operational, investment, accounting';

COMMENT ON COLUMN "position_snapshots"."data_status" IS 'indicative, estimated, official';

COMMENT ON COLUMN "position_snapshots"."supersedes_position_id" IS 'ADDED';

COMMENT ON COLUMN "valuation_observations"."extracted_field_id" IS 'ADDED: the exact value read, with page and line';

COMMENT ON COLUMN "valuation_observations"."recorded_at" IS 'ADDED';

COMMENT ON COLUMN "valuation_observations"."valuation_type" IS 'manager_estimate, manager_final, internal, administrator';

COMMENT ON COLUMN "cash_movements"."movement_type" IS 'subscription, redemption, call, distribution, dividend, fee';

COMMENT ON COLUMN "cash_movements"."recorded_at" IS 'ADDED';

COMMENT ON COLUMN "cash_movements"."confirmation_status" IS 'expected, noticed, confirmed, cancelled';

COMMENT ON COLUMN "cash_movements"."supersedes_cash_movement_id" IS 'ADDED';

COMMENT ON COLUMN "market_observations"."observation_type" IS 'price, index_level, rate, fx';

COMMENT ON COLUMN "market_observations"."recorded_at" IS 'ADDED';

COMMENT ON COLUMN "market_observations"."supersedes_observation_id" IS 'ADDED';

COMMENT ON COLUMN "nav_snapshots"."recorded_at" IS 'ADDED';

COMMENT ON COLUMN "nav_snapshots"."nav_status" IS 'draft, approved_official, restated';

COMMENT ON COLUMN "business_rules"."rule_code" IS 'e.g. cash_tolerance, cio_materiality, estimate_use, fx_fixing, statement_due';

COMMENT ON COLUMN "business_rules"."rule_type" IS 'tolerance, materiality, policy, fixing, deadline';

COMMENT ON COLUMN "rule_versions"."definition_text" IS 'Plain words';

COMMENT ON COLUMN "rule_versions"."parameters" IS 'Machine form, e.g. {"abs_amount": 5000, "currency": "USD"}';

COMMENT ON COLUMN "rule_versions"."approval_status" IS 'draft, approved, retired';

COMMENT ON COLUMN "benchmark_definitions"."approval_status" IS 'draft, in_progress, approved; in_progress is never certified';

COMMENT ON COLUMN "benchmark_components"."spread_bps" IS 'ADDED: premium over the index, e.g. index plus 300 bps';

COMMENT ON COLUMN "decision_intents"."value_basis" IS 'ADDED: investment_estimate or official';

COMMENT ON COLUMN "decision_intents"."acceptance_tests" IS 'ADDED: e.g. rebuild July and August within 1 USD';

COMMENT ON COLUMN "decision_intents"."open_choices" IS 'ADDED';

COMMENT ON COLUMN "decision_intents"."status" IS 'draft, pending_approval, approved, retired';

COMMENT ON COLUMN "metric_definitions"."implementation_ref" IS 'Versioned SQL/dbt/Python reference, not free-form model output';

COMMENT ON COLUMN "calculation_runs"."knowledge_cutoff_at" IS 'Only facts with recorded_at <= this are used';

COMMENT ON COLUMN "calculation_runs"."rule_versions_used" IS 'ADDED: rule_version ids applied in this run';

COMMENT ON COLUMN "metric_values"."value_status" IS 'draft, indicative, certified';

COMMENT ON COLUMN "metric_evidence"."extracted_field_id" IS 'ADDED';

COMMENT ON COLUMN "metric_evidence"."evidence_role" IS 'input, adjustment, explanation, policy';

COMMENT ON COLUMN "reports"."reporting_currencies" IS 'e.g. USD,SGD';

COMMENT ON COLUMN "report_versions"."status" IS 'draft, ready_for_review, approved, issued, superseded';

COMMENT ON COLUMN "exceptions"."exception_type" IS 'revision, break, missing_document, stale_data, limit_breach';

COMMENT ON COLUMN "exceptions"."materiality_status" IS 'unknown, below_threshold, material';

COMMENT ON COLUMN "exceptions"."materiality_rule_version_id" IS 'ADDED: the signed rule that set materiality';

COMMENT ON COLUMN "exceptions"."status" IS 'new, assigned, investigating, resolved, rejected';

COMMENT ON COLUMN "exception_events"."agent_run_id" IS 'ADDED: set when an agent proposed this step';

COMMENT ON COLUMN "exception_events"."event_type" IS 'opened, assigned, explanation_proposed, explanation_confirmed, escalated, resolved, reopened';

COMMENT ON COLUMN "approvals"."report_version_id" IS 'ADDED';

COMMENT ON COLUMN "approvals"."rule_version_id" IS 'ADDED';

COMMENT ON COLUMN "approvals"."sheet_mapping_id" IS 'ADDED';

COMMENT ON COLUMN "approvals"."status" IS 'requested, approved, rejected, withdrawn';

COMMENT ON COLUMN "pulse_items"."outcome" IS 'ADDED: acted, dismissed_with_reason, ignored; feeds the usefulness measure';

COMMENT ON COLUMN "agent_runs"."acting_for_user_id" IS 'ADDED: agents act inside this person''s permissions';

COMMENT ON COLUMN "agent_runs"."agent_type" IS 'intent, intake, data, investigation, briefing';

COMMENT ON COLUMN "agent_runs"."tool_calls" IS 'ADDED: counted against the run limit';

COMMENT ON COLUMN "agent_runs"."cost_usd" IS 'ADDED';

ALTER TABLE "users" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_groups" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_group_memberships" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_group_memberships" ADD FOREIGN KEY ("access_group_id") REFERENCES "access_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_group_memberships" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_group_memberships" ADD FOREIGN KEY ("granted_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_group_scopes" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "access_group_scopes" ADD FOREIGN KEY ("access_group_id") REFERENCES "access_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "legal_entities" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "portfolios" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "portfolios" ADD FOREIGN KEY ("legal_entity_id") REFERENCES "legal_entities" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instruments" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifiers" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifiers" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifiers" ADD FOREIGN KEY ("source_system_id") REFERENCES "source_systems" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifiers" ADD FOREIGN KEY ("proposed_by_agent_run_id") REFERENCES "agent_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "instrument_identifiers" ADD FOREIGN KEY ("approved_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_systems" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_systems" ADD FOREIGN KEY ("owner_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mappings" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mappings" ADD FOREIGN KEY ("source_system_id") REFERENCES "source_systems" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mappings" ADD FOREIGN KEY ("proposed_by_agent_run_id") REFERENCES "agent_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mappings" ADD FOREIGN KEY ("approved_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mapping_columns" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sheet_mapping_columns" ADD FOREIGN KEY ("sheet_mapping_id") REFERENCES "sheet_mappings" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_batches" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_batches" ADD FOREIGN KEY ("source_system_id") REFERENCES "source_systems" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_batches" ADD FOREIGN KEY ("sheet_mapping_id") REFERENCES "sheet_mappings" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "batch_control_totals" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "batch_control_totals" ADD FOREIGN KEY ("source_batch_id") REFERENCES "source_batches" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_records" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_records" ADD FOREIGN KEY ("source_batch_id") REFERENCES "source_batches" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "source_records" ADD FOREIGN KEY ("supersedes_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("source_system_id") REFERENCES "source_systems" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("access_group_id") REFERENCES "access_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "documents" ADD FOREIGN KEY ("supersedes_document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document_passages" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document_passages" ADD FOREIGN KEY ("document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "document_passages" ADD FOREIGN KEY ("access_group_id") REFERENCES "access_groups" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extracted_fields" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extracted_fields" ADD FOREIGN KEY ("document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extracted_fields" ADD FOREIGN KEY ("document_passage_id") REFERENCES "document_passages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extracted_fields" ADD FOREIGN KEY ("extracted_by_agent_run_id") REFERENCES "agent_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "extracted_fields" ADD FOREIGN KEY ("reviewed_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transactions" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transactions" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transactions" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transactions" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "transactions" ADD FOREIGN KEY ("supersedes_transaction_id") REFERENCES "transactions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position_snapshots" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position_snapshots" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position_snapshots" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position_snapshots" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "position_snapshots" ADD FOREIGN KEY ("supersedes_position_id") REFERENCES "position_snapshots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("evidence_document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("extracted_field_id") REFERENCES "extracted_fields" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "valuation_observations" ADD FOREIGN KEY ("supersedes_valuation_id") REFERENCES "valuation_observations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cash_movements" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cash_movements" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cash_movements" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cash_movements" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "cash_movements" ADD FOREIGN KEY ("supersedes_cash_movement_id") REFERENCES "cash_movements" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "market_observations" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "market_observations" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "market_observations" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "market_observations" ADD FOREIGN KEY ("supersedes_observation_id") REFERENCES "market_observations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "nav_snapshots" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "nav_snapshots" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "nav_snapshots" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "nav_snapshots" ADD FOREIGN KEY ("supersedes_nav_id") REFERENCES "nav_snapshots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "business_rules" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "business_rules" ADD FOREIGN KEY ("owner_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule_versions" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule_versions" ADD FOREIGN KEY ("business_rule_id") REFERENCES "business_rules" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "rule_versions" ADD FOREIGN KEY ("approved_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark_definitions" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark_definitions" ADD FOREIGN KEY ("approved_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark_components" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "benchmark_components" ADD FOREIGN KEY ("benchmark_definition_id") REFERENCES "benchmark_definitions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "decision_intents" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "decision_intents" ADD FOREIGN KEY ("requested_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "decision_intents" ADD FOREIGN KEY ("business_owner_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_definitions" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_definitions" ADD FOREIGN KEY ("decision_intent_id") REFERENCES "decision_intents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_definitions" ADD FOREIGN KEY ("owner_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "calculation_runs" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "calculation_runs" ADD FOREIGN KEY ("decision_intent_id") REFERENCES "decision_intents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_values" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_values" ADD FOREIGN KEY ("calculation_run_id") REFERENCES "calculation_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_values" ADD FOREIGN KEY ("metric_definition_id") REFERENCES "metric_definitions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_values" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_values" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_evidence" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_evidence" ADD FOREIGN KEY ("metric_value_id") REFERENCES "metric_values" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_evidence" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_evidence" ADD FOREIGN KEY ("document_passage_id") REFERENCES "document_passages" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "metric_evidence" ADD FOREIGN KEY ("extracted_field_id") REFERENCES "extracted_fields" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reports" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reports" ADD FOREIGN KEY ("decision_intent_id") REFERENCES "decision_intents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_versions" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_versions" ADD FOREIGN KEY ("report_id") REFERENCES "reports" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_versions" ADD FOREIGN KEY ("calculation_run_id") REFERENCES "calculation_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_versions" ADD FOREIGN KEY ("approved_by") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "report_versions" ADD FOREIGN KEY ("supersedes_report_version_id") REFERENCES "report_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("decision_intent_id") REFERENCES "decision_intents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("calculation_run_id") REFERENCES "calculation_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("portfolio_id") REFERENCES "portfolios" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("instrument_id") REFERENCES "instruments" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("materiality_rule_version_id") REFERENCES "rule_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exceptions" ADD FOREIGN KEY ("owner_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_impacts" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_impacts" ADD FOREIGN KEY ("exception_id") REFERENCES "exceptions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_impacts" ADD FOREIGN KEY ("report_version_id") REFERENCES "report_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_impacts" ADD FOREIGN KEY ("metric_value_id") REFERENCES "metric_values" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_events" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_events" ADD FOREIGN KEY ("exception_id") REFERENCES "exceptions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_events" ADD FOREIGN KEY ("performed_by_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_events" ADD FOREIGN KEY ("agent_run_id") REFERENCES "agent_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_events" ADD FOREIGN KEY ("source_record_id") REFERENCES "source_records" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "exception_events" ADD FOREIGN KEY ("evidence_document_id") REFERENCES "documents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("decision_intent_id") REFERENCES "decision_intents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("calculation_run_id") REFERENCES "calculation_runs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("exception_id") REFERENCES "exceptions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("report_version_id") REFERENCES "report_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("rule_version_id") REFERENCES "rule_versions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("sheet_mapping_id") REFERENCES "sheet_mappings" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("requested_from_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "approvals" ADD FOREIGN KEY ("decision_by_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_items" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_items" ADD FOREIGN KEY ("recipient_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_items" ADD FOREIGN KEY ("exception_id") REFERENCES "exceptions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "pulse_items" ADD FOREIGN KEY ("metric_value_id") REFERENCES "metric_values" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("decision_intent_id") REFERENCES "decision_intents" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("exception_id") REFERENCES "exceptions" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "agent_runs" ADD FOREIGN KEY ("acting_for_user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;
