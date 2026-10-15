import { useState } from "react";

import { Chip } from "../../design";
import { Segmented, useCurrency } from "./ConsumeBar";
import EmailPreview from "./EmailPreview";
import SlackThread from "./SlackThread";

// Deliveries: how the Morning Note reaches people, by email and in Slack. It used to be the Delivery tab of Consume; it belongs with Operations, where the
// data team sees whether everything arrives. Mounted by k3/OperationsPage as <DeliveriesSection />; it needs nothing from the page around it.
export default function DeliveriesSection() {
  const [via, setVia] = useState<"email" | "slack">("email");
  const [ccy, setCcy] = useCurrency();
  return (
    <section aria-label="Deliveries" id="deliveries">
      <h2 style={{ fontSize: 17 }}>Deliveries</h2>
      <p className="ds-muted">How the Morning Note reaches people each morning. These are previews of what goes out; nothing is sent from here.</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", margin: "8px 0" }}>
        <div role="group" aria-label="Channel" style={{ display: "flex", gap: 8 }}>
          <Chip tone={via === "email" ? "active" : "default"} onClick={() => setVia("email")}>Email</Chip>
          <Chip tone={via === "slack" ? "active" : "default"} onClick={() => setVia("slack")}>Slack</Chip>
        </div>
        <Segmented label="Currency" value={ccy} options={[["USD", "USD"], ["SGD", "SGD"]]} onChange={setCcy} />
      </div>
      {via === "email" ? <EmailPreview ccy={ccy} /> : <SlackThread ccy={ccy} />}
    </section>
  );
}
