import { useEffect, useState } from "react";

import { THEME_KEY } from "../theme"; // the same stored choice as the sign-in page and the pre-paint script in index.html

type Choice = "light" | "dark" | "system";

function stored(): Choice {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system"; // storage blocked: follow the device
  }
}

/** Light, Dark or System (the default: follows the device). Sets data-theme on the page root; v3.css does the rest. */
export default function ThemePick() {
  const [choice, setChoice] = useState<Choice>(stored);
  useEffect(() => {
    const root = document.documentElement;
    if (choice === "system") root.removeAttribute("data-theme");
    else root.dataset.theme = choice;
  }, [choice]);
  const pick = (c: Choice) => {
    setChoice(c);
    try {
      localStorage.setItem(THEME_KEY, c);
    } catch {
      // storage blocked: the choice still applies to this page
    }
  };
  return (
    <select className="v3-theme" aria-label="Theme" value={choice} onChange={(e) => pick(e.target.value as Choice)}>
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  );
}
