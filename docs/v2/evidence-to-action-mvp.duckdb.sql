-- Generated from evidence-to-action-mvp.dbml for DuckDB (types mapped; foreign keys and checks enforced in code).
-- Interim schema until E0a apply() owns migrations.

CREATE TABLE IF NOT EXISTS organizations (
  id VARCHAR PRIMARY KEY,
  name VARCHAR NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  external_identity_id VARCHAR NOT NULL,
  display_name VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  business_role VARCHAR,
  is_active BOOLEAN NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS access_groups (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  group_name VARCHAR NOT NULL,
  description VARCHAR
);

CREATE TABLE IF NOT EXISTS access_group_memberships (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  access_group_id VARCHAR NOT NULL,
  user_id VARCHAR NOT NULL,
  granted_at TIMESTAMPTZ NOT NULL,
  granted_by VARCHAR,
  expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS access_group_scopes (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  access_group_id VARCHAR NOT NULL,
  scope_type VARCHAR NOT NULL,
  scope_value VARCHAR NOT NULL,
  access_level VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_entities (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  entity_code VARCHAR NOT NULL,
  entity_name VARCHAR NOT NULL,
  base_currency VARCHAR NOT NULL,
  active_from DATE,
  active_to DATE
);

CREATE TABLE IF NOT EXISTS portfolios (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  legal_entity_id VARCHAR NOT NULL,
  portfolio_code VARCHAR NOT NULL,
  portfolio_name VARCHAR NOT NULL,
  base_currency VARCHAR NOT NULL,
  active_from DATE,
  active_to DATE
);

CREATE TABLE IF NOT EXISTS instruments (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  canonical_name VARCHAR NOT NULL,
  instrument_type VARCHAR NOT NULL,
  asset_class VARCHAR,
  manager_name VARCHAR,
  currency VARCHAR,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS instrument_identifiers (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  source_system_id VARCHAR NOT NULL,
  identifier_type VARCHAR NOT NULL,
  identifier_value VARCHAR NOT NULL,
  valid_from DATE,
  valid_to DATE,
  mapping_status VARCHAR NOT NULL,
  proposed_by_agent_run_id VARCHAR,
  approved_by VARCHAR,
  approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS source_systems (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_code VARCHAR NOT NULL,
  source_name VARCHAR NOT NULL,
  source_type VARCHAR NOT NULL,
  connection_method VARCHAR,
  owner_user_id VARCHAR,
  licence_scope VARCHAR,
  permitted_use VARCHAR,
  expected_cadence VARCHAR,
  is_active BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS sheet_mappings (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_system_id VARCHAR NOT NULL,
  file_pattern VARCHAR NOT NULL,
  sheet_name VARCHAR,
  header_row INTEGER,
  version_number INTEGER NOT NULL,
  mapping_status VARCHAR NOT NULL,
  proposed_by_agent_run_id VARCHAR,
  approved_by VARCHAR,
  approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sheet_mapping_columns (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  sheet_mapping_id VARCHAR NOT NULL,
  source_column VARCHAR NOT NULL,
  target_table VARCHAR NOT NULL,
  target_field VARCHAR NOT NULL,
  transform_rule VARCHAR,
  confidence VARCHAR
);

CREATE TABLE IF NOT EXISTS source_batches (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_system_id VARCHAR NOT NULL,
  sheet_mapping_id VARCHAR,
  batch_reference VARCHAR NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  loaded_at TIMESTAMPTZ,
  source_period_end DATE,
  content_hash VARCHAR,
  storage_uri VARCHAR,
  validation_status VARCHAR NOT NULL,
  validation_summary VARCHAR,
  arrived_on_time BOOLEAN,
  manual_fix BOOLEAN
);

CREATE TABLE IF NOT EXISTS batch_control_totals (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_batch_id VARCHAR NOT NULL,
  measure_name VARCHAR NOT NULL,
  expected_value DECIMAL(28,8) NOT NULL,
  loaded_value DECIMAL(28,8),
  tolerance DECIMAL(28,8),
  passed BOOLEAN
);

CREATE TABLE IF NOT EXISTS source_records (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_batch_id VARCHAR NOT NULL,
  external_record_id VARCHAR,
  record_type VARCHAR NOT NULL,
  effective_at TIMESTAMPTZ,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  sheet_name VARCHAR,
  row_number INTEGER,
  cell_range VARCHAR,
  raw_payload_uri VARCHAR NOT NULL,
  content_hash VARCHAR NOT NULL,
  supersedes_record_id VARCHAR,
  quality_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_system_id VARCHAR NOT NULL,
  source_record_id VARCHAR,
  access_group_id VARCHAR NOT NULL,
  instrument_id VARCHAR,
  external_document_id VARCHAR,
  document_type VARCHAR NOT NULL,
  title VARCHAR NOT NULL,
  original_filename VARCHAR,
  original_uri VARCHAR NOT NULL,
  content_hash VARCHAR NOT NULL,
  document_date DATE,
  valuation_date DATE,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  document_status VARCHAR NOT NULL,
  supersedes_document_id VARCHAR,
  processing_status VARCHAR NOT NULL,
  contains_personal_data BOOLEAN
);

CREATE TABLE IF NOT EXISTS document_passages (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  document_id VARCHAR NOT NULL,
  access_group_id VARCHAR NOT NULL,
  passage_order INTEGER NOT NULL,
  page_number INTEGER,
  line_from INTEGER,
  line_to INTEGER,
  section_label VARCHAR,
  table_reference VARCHAR,
  passage_text VARCHAR NOT NULL,
  search_text VARCHAR,
  embedding FLOAT[384],
  extraction_confidence DECIMAL(5,4),
  embedding_model_version VARCHAR,
  indexed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS extracted_fields (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  document_id VARCHAR NOT NULL,
  document_passage_id VARCHAR,
  field_name VARCHAR NOT NULL,
  value_text VARCHAR,
  value_numeric DECIMAL(38,10),
  currency VARCHAR,
  page_number INTEGER,
  line_number INTEGER,
  confidence VARCHAR NOT NULL,
  extracted_by_agent_run_id VARCHAR,
  review_status VARCHAR NOT NULL,
  reviewed_by VARCHAR,
  reviewed_at TIMESTAMPTZ,
  corrected_value_text VARCHAR
);

CREATE TABLE IF NOT EXISTS transactions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  portfolio_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  external_trade_id VARCHAR,
  transaction_type VARCHAR NOT NULL,
  trade_date DATE,
  effective_date DATE NOT NULL,
  settlement_date DATE,
  quantity_delta DECIMAL(38,10),
  cash_amount DECIMAL(28,8),
  currency VARCHAR NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  status VARCHAR NOT NULL,
  supersedes_transaction_id VARCHAR,
  counterparty_name VARCHAR,
  status_reason VARCHAR
);

CREATE TABLE IF NOT EXISTS position_snapshots (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  portfolio_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  position_date DATE NOT NULL,
  as_of_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  quantity DECIMAL(38,10),
  source_market_value DECIMAL(28,8),
  currency VARCHAR,
  view_type VARCHAR NOT NULL,
  data_status VARCHAR NOT NULL,
  supersedes_position_id VARCHAR
);

CREATE TABLE IF NOT EXISTS valuation_observations (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  portfolio_id VARCHAR,
  source_record_id VARCHAR,
  evidence_document_id VARCHAR,
  extracted_field_id VARCHAR,
  valuation_date DATE NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  value_amount DECIMAL(28,8) NOT NULL,
  currency VARCHAR NOT NULL,
  valuation_type VARCHAR NOT NULL,
  approval_status VARCHAR NOT NULL,
  supersedes_valuation_id VARCHAR
);

CREATE TABLE IF NOT EXISTS commitments (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  legal_entity_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  source_record_id VARCHAR,
  commitment_amount DECIMAL(28,8) NOT NULL,
  currency VARCHAR NOT NULL,
  committed_on DATE NOT NULL,
  called_to_date DECIMAL(28,8),
  called_as_at DATE,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_commitment_id VARCHAR
);

CREATE TABLE IF NOT EXISTS cash_movements (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  portfolio_id VARCHAR NOT NULL,
  instrument_id VARCHAR,
  movement_type VARCHAR NOT NULL,
  effective_date DATE NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  amount DECIMAL(28,8) NOT NULL,
  currency VARCHAR NOT NULL,
  confirmation_status VARCHAR NOT NULL,
  supersedes_cash_movement_id VARCHAR,
  due_date DATE,
  notice_kind VARCHAR,
  commitment_id VARCHAR,
  bank_account_id VARCHAR,
  counterparty_portfolio_id VARCHAR,
  payment_stage VARCHAR,
  payee_name VARCHAR,
  reference VARCHAR
);

CREATE TABLE IF NOT EXISTS market_observations (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  instrument_id VARCHAR,
  series_key VARCHAR NOT NULL,
  observation_type VARCHAR NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  value DECIMAL(38,10) NOT NULL,
  base_currency VARCHAR,
  quote_currency VARCHAR,
  quality_status VARCHAR NOT NULL,
  supersedes_observation_id VARCHAR
);

CREATE TABLE IF NOT EXISTS nav_snapshots (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  portfolio_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  nav_period_end DATE NOT NULL,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  nav_amount DECIMAL(28,8) NOT NULL,
  currency VARCHAR NOT NULL,
  nav_status VARCHAR NOT NULL,
  approved_at TIMESTAMPTZ,
  supersedes_nav_id VARCHAR
);

CREATE TABLE IF NOT EXISTS business_rules (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  rule_code VARCHAR NOT NULL,
  rule_type VARCHAR NOT NULL,
  owner_user_id VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_versions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  business_rule_id VARCHAR NOT NULL,
  version_number INTEGER NOT NULL,
  definition_text VARCHAR NOT NULL,
  parameters JSON,
  effective_from DATE NOT NULL,
  effective_to DATE,
  approval_status VARCHAR NOT NULL,
  approved_by VARCHAR,
  approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS benchmark_definitions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  benchmark_code VARCHAR NOT NULL,
  benchmark_name VARCHAR NOT NULL,
  version_number INTEGER NOT NULL,
  reporting_currency VARCHAR NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE,
  calculation_method VARCHAR NOT NULL,
  approval_status VARCHAR NOT NULL,
  approved_by VARCHAR
);

CREATE TABLE IF NOT EXISTS benchmark_components (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  benchmark_definition_id VARCHAR NOT NULL,
  market_series_key VARCHAR NOT NULL,
  component_weight DECIMAL(18,10) NOT NULL,
  spread_bps DECIMAL(12,4),
  weight_effective_from DATE NOT NULL,
  weight_effective_to DATE,
  treatment_note VARCHAR
);

CREATE TABLE IF NOT EXISTS decision_intents (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  requested_by VARCHAR NOT NULL,
  business_owner_id VARCHAR,
  title VARCHAR NOT NULL,
  business_question VARCHAR NOT NULL,
  intended_audience VARCHAR,
  permitted_use VARCHAR NOT NULL,
  value_basis VARCHAR,
  output_description VARCHAR,
  acceptance_tests VARCHAR,
  open_choices VARCHAR,
  status VARCHAR NOT NULL,
  contract_version INTEGER NOT NULL,
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_definitions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  decision_intent_id VARCHAR,
  metric_code VARCHAR NOT NULL,
  metric_name VARCHAR NOT NULL,
  version_number INTEGER NOT NULL,
  definition_text VARCHAR NOT NULL,
  implementation_ref VARCHAR NOT NULL,
  owner_user_id VARCHAR NOT NULL,
  approval_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS calculation_runs (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  decision_intent_id VARCHAR,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  knowledge_cutoff_at TIMESTAMPTZ NOT NULL,
  reporting_date DATE NOT NULL,
  code_version VARCHAR NOT NULL,
  rule_versions_used JSON,
  input_manifest_uri VARCHAR NOT NULL,
  run_status VARCHAR NOT NULL,
  validation_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_values (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  calculation_run_id VARCHAR NOT NULL,
  metric_definition_id VARCHAR NOT NULL,
  portfolio_id VARCHAR,
  instrument_id VARCHAR,
  reporting_date DATE NOT NULL,
  numeric_value DECIMAL(38,10),
  currency VARCHAR,
  value_status VARCHAR NOT NULL,
  published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS metric_evidence (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  metric_value_id VARCHAR NOT NULL,
  source_record_id VARCHAR,
  document_passage_id VARCHAR,
  extracted_field_id VARCHAR,
  evidence_role VARCHAR NOT NULL,
  note VARCHAR
);

CREATE TABLE IF NOT EXISTS reports (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  decision_intent_id VARCHAR,
  report_code VARCHAR NOT NULL,
  report_name VARCHAR NOT NULL,
  audience VARCHAR,
  reporting_currencies VARCHAR
);

CREATE TABLE IF NOT EXISTS report_versions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  report_id VARCHAR NOT NULL,
  calculation_run_id VARCHAR NOT NULL,
  period_end DATE NOT NULL,
  cutoff_at TIMESTAMPTZ NOT NULL,
  status VARCHAR NOT NULL,
  approved_by VARCHAR,
  issued_at TIMESTAMPTZ,
  supersedes_report_version_id VARCHAR
);

CREATE TABLE IF NOT EXISTS exceptions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  decision_intent_id VARCHAR,
  calculation_run_id VARCHAR,
  portfolio_id VARCHAR,
  instrument_id VARCHAR,
  exception_type VARCHAR NOT NULL,
  title VARCHAR NOT NULL,
  description VARCHAR,
  detected_at TIMESTAMPTZ NOT NULL,
  candidate_impact_amount DECIMAL(28,8),
  impact_currency VARCHAR,
  materiality_status VARCHAR NOT NULL,
  materiality_rule_version_id VARCHAR,
  status VARCHAR NOT NULL,
  owner_user_id VARCHAR,
  due_at TIMESTAMPTZ,
  resolution_code VARCHAR,
  resolved_at TIMESTAMPTZ,
  external_ref VARCHAR,
  legal_entity_id VARCHAR
);

CREATE TABLE IF NOT EXISTS exception_impacts (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  exception_id VARCHAR NOT NULL,
  report_version_id VARCHAR NOT NULL,
  metric_value_id VARCHAR,
  issued_value DECIMAL(38,10),
  draft_value DECIMAL(38,10),
  currency VARCHAR
);

CREATE TABLE IF NOT EXISTS exception_events (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  exception_id VARCHAR NOT NULL,
  performed_by_user_id VARCHAR,
  agent_run_id VARCHAR,
  event_type VARCHAR NOT NULL,
  event_note VARCHAR,
  occurred_at TIMESTAMPTZ NOT NULL,
  source_record_id VARCHAR,
  evidence_document_id VARCHAR
);

CREATE TABLE IF NOT EXISTS approvals (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  decision_intent_id VARCHAR,
  calculation_run_id VARCHAR,
  exception_id VARCHAR,
  report_version_id VARCHAR,
  rule_version_id VARCHAR,
  sheet_mapping_id VARCHAR,
  cash_movement_id VARCHAR,
  approval_type VARCHAR NOT NULL,
  requested_from_user_id VARCHAR NOT NULL,
  decision_by_user_id VARCHAR,
  status VARCHAR NOT NULL,
  rationale VARCHAR,
  requested_at TIMESTAMPTZ NOT NULL,
  decided_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pulse_items (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  recipient_user_id VARCHAR NOT NULL,
  exception_id VARCHAR,
  metric_value_id VARCHAR,
  headline VARCHAR NOT NULL,
  summary VARCHAR NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  as_of_at TIMESTAMPTZ NOT NULL,
  urgency VARCHAR NOT NULL,
  action_type VARCHAR,
  delivery_status VARCHAR NOT NULL,
  acknowledged_at TIMESTAMPTZ,
  outcome VARCHAR
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  decision_intent_id VARCHAR,
  exception_id VARCHAR,
  acting_for_user_id VARCHAR,
  agent_type VARCHAR NOT NULL,
  model_id VARCHAR NOT NULL,
  prompt_version VARCHAR NOT NULL,
  tool_policy_version VARCHAR NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  run_status VARCHAR NOT NULL,
  tool_calls INTEGER,
  cost_usd DECIMAL(12,6),
  trace_id VARCHAR,
  output_artifact_uri VARCHAR,
  human_review_status VARCHAR
);

CREATE TABLE IF NOT EXISTS fx_confirmations (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  trade_reference VARCHAR NOT NULL,
  trade_date DATE NOT NULL,
  value_date DATE,
  currency_bought VARCHAR,
  amount_bought DECIMAL(28,8),
  currency_sold VARCHAR,
  amount_sold DECIMAL(28,8),
  rate DECIMAL(28,10),
  counterparty VARCHAR,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_fx_confirmation_id VARCHAR
);

CREATE TABLE IF NOT EXISTS expected_statements (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  source_record_id VARCHAR,
  period_end DATE NOT NULL,
  due_date DATE,
  frequency VARCHAR NOT NULL,
  source VARCHAR NOT NULL,
  due_reason VARCHAR,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_expected_statement_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bank_accounts (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_bank_account_id VARCHAR,
  holder_kind VARCHAR NOT NULL,
  legal_entity_id VARCHAR,
  instrument_id VARCHAR,
  holder_name VARCHAR,
  account_purpose VARCHAR NOT NULL,
  bank_name VARCHAR NOT NULL,
  account_ref VARCHAR NOT NULL,
  currency VARCHAR,
  cash_instrument_id VARCHAR,
  status VARCHAR NOT NULL,
  opened_on DATE,
  closed_on DATE,
  verified_on DATE,
  verified_by VARCHAR
);

CREATE TABLE IF NOT EXISTS credit_facilities (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_credit_facility_id VARCHAR,
  facility_ref VARCHAR NOT NULL,
  legal_entity_id VARCHAR NOT NULL,
  lender VARCHAR NOT NULL,
  facility_type VARCHAR NOT NULL,
  currency VARCHAR NOT NULL,
  limit_amount DECIMAL(28,8),
  drawn_amount DECIMAL(28,8) NOT NULL,
  interest_rate DECIMAL(12,6),
  rate_basis VARCHAR,
  maturity_date DATE,
  collateral VARCHAR,
  as_at DATE NOT NULL,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS family_members (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_family_member_id VARCHAR,
  member_name VARCHAR NOT NULL,
  relationship VARCHAR,
  legal_entity_id VARCHAR,
  user_id VARCHAR,
  allowance_amount DECIMAL(28,8),
  allowance_currency VARCHAR,
  allowance_frequency VARCHAR,
  allowance_from DATE,
  allowance_to DATE,
  paid_from_portfolio_id VARCHAR,
  active_from DATE,
  active_to DATE
);

CREATE TABLE IF NOT EXISTS vendor_contracts (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_vendor_contract_id VARCHAR,
  vendor_name VARCHAR NOT NULL,
  service VARCHAR,
  contract_ref VARCHAR,
  legal_entity_id VARCHAR,
  owner_user_id VARCHAR,
  start_date DATE,
  end_date DATE,
  next_renewal_date DATE,
  auto_renews BOOLEAN,
  notice_days INTEGER,
  annual_cost DECIMAL(28,8),
  currency VARCHAR,
  status VARCHAR NOT NULL,
  contract_kind VARCHAR,
  sum_insured DECIMAL(28,8),
  covered_asset_ref VARCHAR
);

CREATE TABLE IF NOT EXISTS deal_pipeline (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_deal_id VARCHAR,
  deal_name VARCHAR NOT NULL,
  manager_name VARCHAR,
  strategy VARCHAR,
  asset_class VARCHAR,
  instrument_id VARCHAR,
  target_commitment DECIMAL(28,8),
  currency VARCHAR,
  stage VARCHAR NOT NULL,
  stage_on DATE NOT NULL,
  owner_user_id VARCHAR
);

CREATE TABLE IF NOT EXISTS committee_decisions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_committee_decision_id VARCHAR,
  committee VARCHAR NOT NULL,
  decided_on DATE NOT NULL,
  title VARCHAR NOT NULL,
  subject_type VARCHAR,
  subject_id VARCHAR,
  outcome VARCHAR NOT NULL,
  conditions VARCHAR,
  amount DECIMAL(28,8),
  currency VARCHAR,
  recorded_by VARCHAR
);

CREATE TABLE IF NOT EXISTS office_expenses (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_office_expense_id VARCHAR,
  spent_on DATE NOT NULL,
  category VARCHAR NOT NULL,
  payee_name VARCHAR,
  legal_entity_id VARCHAR,
  currency VARCHAR NOT NULL,
  amount DECIMAL(28,8) NOT NULL,
  reference VARCHAR,
  approver_name VARCHAR,
  approver_user_id VARCHAR
);

CREATE TABLE IF NOT EXISTS corporate_actions (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_corporate_action_id VARCHAR,
  instrument_id VARCHAR NOT NULL,
  action_type VARCHAR NOT NULL,
  custodian_ref VARCHAR,
  announced_on DATE,
  ex_date DATE,
  record_date DATE,
  pay_date DATE,
  rate_per_unit DECIMAL(28,10),
  currency VARCHAR,
  election_required BOOLEAN,
  election_deadline DATE,
  elected_option VARCHAR,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS real_assets (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_real_asset_id VARCHAR,
  asset_ref VARCHAR NOT NULL,
  asset_name VARCHAR NOT NULL,
  asset_type VARCHAR NOT NULL,
  legal_entity_id VARCHAR,
  title_holder_name VARCHAR,
  currency VARCHAR NOT NULL,
  appraised_value DECIMAL(28,8),
  appraised_on DATE,
  appraiser VARCHAR,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS tax_lots (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_tax_lot_id VARCHAR,
  portfolio_id VARCHAR NOT NULL,
  instrument_id VARCHAR NOT NULL,
  lot_ref VARCHAR NOT NULL,
  acquired_on DATE NOT NULL,
  quantity DECIMAL(28,10) NOT NULL,
  unit_cost DECIMAL(28,10),
  cost_amount DECIMAL(28,8) NOT NULL,
  currency VARCHAR NOT NULL,
  as_at DATE NOT NULL,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS tax_obligations (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_tax_obligation_id VARCHAR,
  obligation_ref VARCHAR NOT NULL,
  legal_entity_id VARCHAR NOT NULL,
  obligation VARCHAR NOT NULL,
  due_date DATE NOT NULL,
  prepared_by VARCHAR,
  estimated_amount DECIMAL(28,8),
  currency VARCHAR,
  status VARCHAR NOT NULL,
  filed_on DATE,
  paid_on DATE
);

CREATE TABLE IF NOT EXISTS grants (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_grant_id VARCHAR,
  grant_ref VARCHAR NOT NULL,
  charity_name VARCHAR NOT NULL,
  charity_registered_on DATE,
  purpose VARCHAR,
  legal_entity_id VARCHAR,
  amount DECIMAL(28,8) NOT NULL,
  currency VARCHAR NOT NULL,
  requested_on DATE,
  decided_on DATE,
  paid_on DATE,
  payment_reference VARCHAR,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_payroll (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_staff_payroll_id VARCHAR,
  pay_period DATE NOT NULL,
  employee_name VARCHAR NOT NULL,
  title VARCHAR,
  employment_kind VARCHAR NOT NULL,
  legal_entity_id VARCHAR,
  currency VARCHAR NOT NULL,
  gross_pay DECIMAL(28,8) NOT NULL,
  employee_contribution DECIMAL(28,8),
  employer_contribution DECIMAL(28,8),
  net_pay DECIMAL(28,8),
  pay_date DATE,
  run_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS kyc_records (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_kyc_record_id VARCHAR,
  subject_kind VARCHAR NOT NULL,
  subject_name VARCHAR NOT NULL,
  legal_entity_id VARCHAR,
  document_kind VARCHAR NOT NULL,
  issued_on DATE,
  expires_on DATE,
  verified_on DATE,
  verified_by VARCHAR,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fund_holdings (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_fund_holding_id VARCHAR,
  instrument_id VARCHAR NOT NULL,
  holding_name VARCHAR NOT NULL,
  sector VARCHAR,
  weight_pct DECIMAL(12,6) NOT NULL,
  as_at DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS system_access_grants (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_system_access_grant_id VARCHAR,
  person_name VARCHAR NOT NULL,
  user_id VARCHAR,
  system_name VARCHAR NOT NULL,
  access_level VARCHAR,
  granted_on DATE,
  approved_by_name VARCHAR,
  approved_by_user_id VARCHAR,
  last_used_on DATE,
  revoked_on DATE,
  status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_ownership (
  id VARCHAR PRIMARY KEY,
  organization_id VARCHAR NOT NULL,
  source_record_id VARCHAR NOT NULL,
  source_document_id VARCHAR,
  source_page INTEGER,
  received_at TIMESTAMPTZ NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  supersedes_entity_ownership_id VARCHAR,
  owner_kind VARCHAR NOT NULL,
  owner_entity_id VARCHAR,
  owner_family_member_id VARCHAR,
  owned_entity_id VARCHAR NOT NULL,
  ownership_pct DECIMAL(9,6) NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE
);

