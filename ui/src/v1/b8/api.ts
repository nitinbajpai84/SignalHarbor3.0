// BC1: the architecture room reads the model routes (e0a) and the project's tables; the pipelines room reuses the b6 calls.
import { apiGet } from "../../api/client";

export interface LayerRow { name: string; source: string; layout: string; project_ids: string[]; columns: number }
export interface Layers { bronze: LayerRow[]; silver: { tables: number }; gold: LayerRow[] }
export interface ProjectTables { bronze: string[]; silver: string[]; gold: string[] }
export interface Ref { from: { table: string; column?: string }; to: { table: string; column?: string } }
export interface TableDetail { name: string; note?: string; columns: { name: string; type: string; note?: string; pk?: boolean }[]; refs: Ref[] }

export const getLayers = () => apiGet<Layers>("/api/v1/model/layers");
export const getProjectTables = (pid: string) => apiGet<ProjectTables>(`/api/v1/model/projects/${encodeURIComponent(pid)}/tables`);
export const getTable = (name: string) => apiGet<TableDetail>(`/api/v1/model/tables/${encodeURIComponent(name)}`);
