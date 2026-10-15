// L3: the library by folder (sh_platform/v1/l3_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";
import type { LibItem } from "../c4/api";

export interface Folder { folder: string; icon: string; count: number; items: LibItem[] }
export interface Folders { folders: Folder[]; sorting: boolean; all: string[] }

export const getFolders = (q = "") => apiGet<Folders>(`/api/v1/library/folders${q ? `?q=${encodeURIComponent(q)}` : ""}`);
export const moveItem = (id: string, folder: string) => apiSend<LibItem>("PUT", `/api/v1/library/${encodeURIComponent(id)}/folder`, { folder });

// INT3: where a library file opens when the page has no ?iid=. The source page reads a file through a project the viewer may open
// (G3 /benchmarks/sheet/doc: G1 gates the project, K1 the file). A file ticked in one of the viewer's projects opens there; any other
// file opens through the viewer's first project. No project at all: no Open (there is no project-free file route).
export interface OpenPlaces { byItem: Record<string, string>; first?: string }
export async function getOpenPlaces(max = 20): Promise<OpenPlaces> {
  const got = await apiGet<{ intents?: { id: string }[] } | { id: string }[]>("/api/intents");
  const ids = (Array.isArray(got) ? got : got.intents ?? []).map((x) => x.id).filter(Boolean);
  const byItem: Record<string, string> = {};
  // ponytail: one context read per project, capped at `max`; a server-side item->project map if libraries outgrow it
  const ctx = await Promise.all(ids.slice(0, max).map((id) =>
    apiGet<{ library_ids?: string[] }>(`/api/v1/intents/${encodeURIComponent(id)}/context`).then((c) => [id, c.library_ids ?? []] as const, () => [id, []] as const)));
  for (const [id, lib] of ctx) for (const li of lib) byItem[li] ??= id;
  return { byItem, first: ids[0] };
}

// W06: a library file read without a project (sh_platform/v1/l3b_routes.py); the server shows it only to whoever may read it.
export interface FileView { name: string; lines: { n: number; text: string }[] }
export const getFileView = (file: string) => apiGet<FileView>(`/api/v1/library/view?file=${encodeURIComponent(file)}`);
