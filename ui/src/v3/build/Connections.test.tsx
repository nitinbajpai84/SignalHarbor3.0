import { expect, test } from "vitest";

import type { ConnectorRow } from "../api";
import { statusLine } from "./Connections";

const row = (o: Partial<ConnectorRow>): ConnectorRow => ({ id: "plaid", label: "Plaid", kind: "api", missing: [], state: "connected", last_run: null, files: 0, errors: [], message: "", ...o });

test("a card says connected, what is missing by name, or the error", () => {
  expect(statusLine(row({}))).toEqual({ pill: "done", text: "Connected" });
  expect(statusLine(row({ state: "needs_settings", missing: ["PLAID_CLIENT_ID", "PLAID_SECRET"] })).text).toBe("Not connected yet: needs PLAID_CLIENT_ID, PLAID_SECRET");
  expect(statusLine(row({ state: "error", errors: ["The run failed: boom"] }))).toEqual({ pill: "problem", text: "The run failed: boom" });
});
