import { apiGet } from "../../api/client";
import type { PlanDiagramData } from "./layout";

export const getDiagram = (pid: string) => apiGet<PlanDiagramData>(`/api/v1/build/p/${encodeURIComponent(pid)}/diagram`);
