import { apiGet } from "../../../api/client";
import { BASE } from "../api";
import type { Profile } from "../intake/api";

export interface QualityRule {
  id: string;
  kind: string;
  text: string;
  state: string;
}
/** One source's profile with the quality rules Lens proposed for the measures it feeds (IC-0d). */
export const getSourceProfile = (id: string, sourceId: string) =>
  apiGet<{ profile: Profile | null; quality_rules?: Record<string, QualityRule[]> }>(`${BASE}/assessments/${id}/intake/sources/${sourceId}/profile`);
