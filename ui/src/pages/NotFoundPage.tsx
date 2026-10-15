import { Link } from "react-router-dom";

import { copy } from "../copy";

export default function NotFoundPage() {
  return (
    <main className="n-panel narrow">
      <h1 className="n-page-title">{copy.product}</h1>
      <p>{copy.notFound.message}</p>
      <p>
        <Link to="/">{copy.notFound.home}</Link>
      </p>
    </main>
  );
}
