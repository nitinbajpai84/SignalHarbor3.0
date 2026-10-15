import { useParams } from "react-router-dom";

import GuestShell from "../components/GuestShell";
import { m1Room } from "../modules/m1_intent/copy";
import JoinScreen from "../modules/m1_intent/room/JoinScreen";

/** The page behind /join/<code>. Needs no sign-in: the guest look (header and theme choice, no top bar). */
export default function JoinPage() {
  const { code = "" } = useParams();
  return (
    <GuestShell title={m1Room.join.title}>
      <JoinScreen code={code} />
    </GuestShell>
  );
}
