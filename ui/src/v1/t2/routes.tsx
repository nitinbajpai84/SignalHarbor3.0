import type { V1Route } from "..";
import TicketPage from "./TicketPage";
import TicketsPage from "./TicketsPage";

export const routes: V1Route[] = [
  { path: "tickets", element: <TicketsPage /> },
  { path: "tickets/:id", element: <TicketPage /> },
];
