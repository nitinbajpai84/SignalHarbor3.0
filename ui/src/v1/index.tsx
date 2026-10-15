// Signal Harbor 1.0: every slim card owns ui/src/v1/<card>/routes.tsx exporting `routes: V1Route[]` (paths relative to /centre,
// literal, no leading slash). App.tsx mounts them inside the centre shell; nobody edits App.tsx for a new screen.
import type { ReactNode } from "react";

export interface V1Route { path: string; element: ReactNode }

const found = import.meta.glob<{ routes?: V1Route[] }>("./*/routes.tsx", { eager: true });
export const v1Routes: V1Route[] = Object.values(found).flatMap((m) => m.routes ?? []);
