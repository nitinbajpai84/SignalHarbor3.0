import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { PageFrame } from "../../design";
import Canvas from "../b7/Canvas";
import RefreshLine from "../b7/RefreshLine";
import { getRefresh, type Refresh } from "../b7/api";
import Comments from "../n2/Comments";
import { getDashboardById, type Dashboard } from "./api";
import TileCard from "./TileCard";

// C2, OP1: /centre/consume/d/:dashboardId. What the audience sees: the published version, read-only. Built and changed in Build › Dashboard studio.
export default function DashboardView() {
  const { dashboardId = "" } = useParams();
  const [board, setBoard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState<Refresh | null>(null);
  useEffect(() => {
    getDashboardById(dashboardId).then(setBoard, () => setError("This dashboard is not shared with you, or no longer exists."));
    getRefresh(dashboardId).then(setRefresh, () => setRefresh(null));  // the line is a courtesy: the dashboard opens without it
  }, [dashboardId]);
  if (error) return <PageFrame title="Dashboard"><p role="alert">{error}</p></PageFrame>;
  if (!board) return <PageFrame title="Dashboard"><p className="ds-muted">Opening the dashboard…</p></PageFrame>;
  const tiles = board.tiles.filter((t) => t.state === "accepted");
  return (
    <PageFrame title={board.title} subline="The accepted tiles of this dashboard.">
      <RefreshLine refresh={refresh} />
      {board.layout?.items.length ? <Canvas pid={board.project_id} did={board.id} layout={board.layout} />
        : tiles.length ? tiles.map((t) => <div key={t.id}><TileCard pid={board.project_id} did={board.id} tile={t} /><Comments eager target={{ kind: "widget", id: `${board.id}/${t.id}` }} /></div>) : <p className="ds-muted">No tiles have been accepted yet.</p>}
      <h2>Comments on this dashboard</h2>
      <Comments eager target={{ kind: "dashboard", id: board.id }} />
    </PageFrame>
  );
}
