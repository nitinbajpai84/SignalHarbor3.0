// Typed calls for the control panel (IC-5a routes). fetch stays in client.ts.
import { apiGet, apiSend } from "./client";

export interface ControlCompany {
  id: string;
  display: string | null;
  industry: string | null;
  centres_on: string[];
  modules_on: string[];
  email_domains: string[];
  accounts: { total: number; active: number };
}
export interface Catalogue {
  modules: { id: string; number: number; name: string; description: string; agent: string }[];
  centres: { id: string; name: string; description: string }[];
}
export interface Providers {
  allowed: Record<string, string[]>;
  companies: Record<string, { provider: string; model: string } | null>;
}
export interface CompanySettings {
  email_domains: string[];
  centres: string[];
  egress: { internet: boolean; connectors: boolean; cloud_push: boolean; cloud_push_requested: boolean };
}
export interface EgressEntry {
  time: string | null;
  module: string | null;
  kind: string | null;
  host: string | null;
  decision: string | null;
  reason_code: string | null;
  bytes: number | null;
}
export type EgressKey = "internet" | "connectors" | "cloud_push";

export const listCompanies = () => apiGet<{ companies: ControlCompany[] }>("/api/control/companies");
export const getCatalogue = () => apiGet<Catalogue>("/api/control/catalogue");
export const getProviders = () => apiGet<Providers>("/api/control/providers");
export const setCentre = (company: string, centre: string, on: boolean) =>
  apiSend("PUT", `/api/control/companies/${encodeURIComponent(company)}/centres/${encodeURIComponent(centre)}`, { on });
export const setModule = (company: string, module: string, on: boolean) =>
  apiSend("PUT", `/api/control/companies/${encodeURIComponent(company)}/modules/${encodeURIComponent(module)}`, { on });
export const getSettings = () => apiGet<CompanySettings>("/api/company/settings");
export const setEgress = (key: EgressKey, on: boolean) =>
  apiSend<CompanySettings>("PUT", "/api/company/settings/egress", { [key]: on });
export const getEgressLog = (limit = 50) => apiGet<{ entries: EgressEntry[] }>(`/api/company/egress-log?limit=${limit}`);
export const setEmailDomains = (email_domains: string[]) =>
  apiSend<CompanySettings>("PUT", "/api/company/settings/egress", { email_domains });
