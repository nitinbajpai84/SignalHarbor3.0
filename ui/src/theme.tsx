import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemeChoice = "light" | "dark" | "system";

/** Also read by the pre-paint script in index.html, so keep the two in step. */
export const THEME_KEY = "sh_theme";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system"; // storage blocked: the page still works, it just forgets the choice
  }
}

function deviceIsDark(): boolean {
  try {
    return window.matchMedia(DARK_QUERY).matches;
  } catch {
    return false;
  }
}

/** The legacy CSS expects data-theme="light" or "dark"; no attribute means follow the device. */
function applyChoice(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.dataset.theme = choice;
}

interface Theme {
  choice: ThemeChoice;
  setChoice: (c: ThemeChoice) => void;
  /** What is actually showing, after the device preference is taken into account. */
  effective: "light" | "dark";
}

const ThemeContext = createContext<Theme | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice);
  const [dark, setDark] = useState(deviceIsDark);

  useEffect(() => applyChoice(choice), [choice]);

  useEffect(() => {
    try {
      const mq = window.matchMedia(DARK_QUERY);
      const on = () => setDark(mq.matches);
      mq.addEventListener("change", on);
      return () => mq.removeEventListener("change", on);
    } catch {
      return undefined;
    }
  }, []);

  const setChoice = useCallback((c: ThemeChoice) => {
    setChoiceState(c);
    try {
      localStorage.setItem(THEME_KEY, c);
    } catch {
      // storage blocked: the choice still applies to this page
    }
  }, []);

  const value = useMemo<Theme>(
    () => ({ choice, setChoice, effective: choice === "system" ? (dark ? "dark" : "light") : choice }),
    [choice, setChoice, dark],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  const t = useContext(ThemeContext);
  if (!t) throw new Error("useTheme needs a ThemeProvider");
  return t;
}
