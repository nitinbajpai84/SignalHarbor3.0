import { useState } from "react";

import ConsumeBar, { Segmented, useCurrency, type Tab } from "./ConsumeBar";
import Health from "./Health";
import MarketSignals from "./MarketSignals";
import MorningNote from "./MorningNote";
import ReportsLibrary from "./ReportsLibrary";
import type { Period } from "./api";

// The Consume reading room (CONS1): five tabs and one currency switch. Today, Financial health and Markets are here; What if is the K11 page (k11/AttributionTab),
// which draws the same bar. Delivery lives on the Operations page, dashboards are built in Build and listed under Reports. Nothing here is a project list.
export type { Tab };
export default function ConsumeRoom({ tab }: { tab: Exclude<Tab, "whatif"> }) {
  const [ccy] = useCurrency();
  const [period, setPeriod] = useState<Period>("month");
  const periods = tab === "markets" ? <Segmented label="Period" value={period} onChange={setPeriod} options={[["month", "Month"], ["ytd", "Year to date"], ["inception", "Since inception"]]} /> : null;
  return (
    <>
      <ConsumeBar here={tab} extra={periods} />
      {tab === "today" ? <MorningNote ccy={ccy} /> : tab === "health" ? <Health ccy={ccy} /> : tab === "markets" ? <MarketSignals ccy={ccy} period={period} /> : <ReportsLibrary />}
    </>
  );
}
