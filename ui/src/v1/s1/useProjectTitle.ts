import { useEffect, useState } from "react";
import { apiGet } from "../../api/client";

/** The project's title for page headers; falls back to the id until the list has loaded or if the project is not found. */
export function useProjectTitle(projectId: string | undefined): string {
  const [title, setTitle] = useState<string>(projectId ?? "");
  useEffect(() => {
    let live = true;
    if (!projectId) return;
    apiGet<{ projects: { id: string; title: string }[] }>("/api/v1/projects")
      .then((r) => { const p = r.projects.find((x) => x.id === projectId); if (live && p?.title) setTitle(p.title); })
      .catch(() => undefined);
    return () => { live = false; };
  }, [projectId]);
  return title;
}
