// Multipart upload with progress: fetch cannot report upload progress, so this one call uses XMLHttpRequest.
import { csrfToken } from "../../api/client";
import type { FileRow } from "../api";

/** A row as POST /api/v3/files returns it; the duplicate flags are read only if the backend ever sends them. */
export type PostedRow = FileRow & { skipped?: boolean; duplicate?: boolean };

export function postFile(file: File, onProgress: (pct: number) => void): Promise<PostedRow[]> {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", "/api/v3/files");
    x.withCredentials = true;
    x.setRequestHeader("X-CSRF-Token", csrfToken());
    x.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
    x.onerror = () => reject(new Error("The upload did not reach Harbor. Check the connection and try again."));
    x.onload = () => {
      let body: { files?: PostedRow[]; message?: string; detail?: string } = {};
      try { body = JSON.parse(x.responseText) as typeof body; } catch { /* plain-text answer */ }
      if (x.status >= 200 && x.status < 300) resolve(body.files ?? []);
      else reject(new Error(body.message ?? body.detail ?? `The upload failed (${x.status}).`));
    };
    const fd = new FormData();
    fd.append("files", file, file.name);
    x.send(fd);
  });
}

/** Every file in a drop, walking into dropped folders. */
export async function filesFromDrop(dt: DataTransfer): Promise<File[]> {
  const entries = Array.from(dt.items ?? [])
    .map((i) => (typeof i.webkitGetAsEntry === "function" ? i.webkitGetAsEntry() : null))
    .filter((e): e is FileSystemEntry => e !== null);
  if (entries.length === 0) return Array.from(dt.files ?? []);
  const out: File[] = [];
  const walk = async (e: FileSystemEntry): Promise<void> => {
    if (e.isFile) {
      out.push(await new Promise<File>((ok, bad) => (e as FileSystemFileEntry).file(ok, bad)));
    } else if (e.isDirectory) {
      const reader = (e as FileSystemDirectoryEntry).createReader();
      for (;;) {
        const batch = await new Promise<FileSystemEntry[]>((ok, bad) => reader.readEntries(ok, bad));
        if (batch.length === 0) break;
        for (const c of batch) await walk(c);
      }
    }
  };
  for (const e of entries) await walk(e);
  return out;
}
