import type { V1Route } from "..";
import BenchmarkPage from "./BenchmarkPage";

// K7: Consume > Benchmark. Linked from nowhere yet; open /centre/consume/benchmark?portfolio=<code>.
export const routes: V1Route[] = [{ path: "consume/benchmark", element: <BenchmarkPage /> }];
