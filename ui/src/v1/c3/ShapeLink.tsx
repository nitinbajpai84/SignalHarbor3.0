import { Link } from "react-router-dom";

/** C3: the Consume page's way into Lumen's conversation. C1's page renders it (the orchestrator wires it). */
export default function ShapeLink() {
  return <Link className="ds-btn" to="/centre/consume/design">Shape what you see</Link>;
}
