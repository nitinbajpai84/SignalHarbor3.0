import { useEffect, useState } from "react";

const PHONE = "(max-width: 719px)";
const mq = () => (typeof window.matchMedia === "function" ? window.matchMedia(PHONE) : null);

/** True under 720px wide; false where matchMedia is missing (tests, old browsers): the desktop layout. */
export function usePhone(): boolean {
  const [phone, setPhone] = useState(() => !!mq()?.matches);
  useEffect(() => {
    const m = mq();
    if (!m) return undefined;
    const on = () => setPhone(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return phone;
}
