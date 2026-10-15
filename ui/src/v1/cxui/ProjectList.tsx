import ConsumeRoom from "../k10/ConsumeRoom";

// /centre/consume is the reading room, Today first (then Financial health, Markets, Reports, What if), built in ui/src/v1/k10.
// "Your projects" left Consume: projects live in Build. Every link this page used to carry (Office view, Managers, Benchmark, Signed KPIs and offers,
// Statements and evidence, Library, Shape what you see, Offers, Business views) is on one of the tabs, and the project page itself is unchanged.
export default function ProjectList() {
  return <ConsumeRoom tab="today" />;
}
