import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";

import { THEME_KEY } from "../theme";
import ThemePick from "./ThemePick";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("theme pick", () => {
  test("System by default; Dark and Light set data-theme and are stored; System removes it", async () => {
    const user = userEvent.setup();
    render(<ThemePick />);
    const pick = screen.getByRole("combobox", { name: "Theme" });
    expect(pick).toHaveValue("system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    await user.selectOptions(pick, "dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    await user.selectOptions(pick, "light");
    expect(document.documentElement.dataset.theme).toBe("light");
    await user.selectOptions(pick, "system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
  });

  test("a stored choice is restored on the next visit", () => {
    localStorage.setItem(THEME_KEY, "dark");
    render(<ThemePick />);
    expect(screen.getByRole("combobox", { name: "Theme" })).toHaveValue("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  test("blocked storage still switches the page", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    const user = userEvent.setup();
    render(<ThemePick />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Theme" }), "dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

// The tokens themselves: every light token has a dark value, both dark rules agree, and text holds 4.5:1.
const CSS = readFileSync(`${process.cwd().replace(/\\/g, "/")}/src/v3/v3.css`, "utf-8");
const blockAfter = (sel: string) => {
  const i = CSS.indexOf(sel);
  return Object.fromEntries([...CSS.slice(i, CSS.indexOf("}", i)).matchAll(/(--[\w-]+):(#[0-9A-Fa-f]{6})/g)].map((m) => [m[1], m[2]]));
};
const light = blockAfter(":root,.v3,.v3c,.lg-page{");
const dark = blockAfter(':root[data-theme="dark"]:has');
const device = blockAfter(':root:not([data-theme="light"]):has');
function lum(hex: string) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0]! + 0.7152 * c[1]! + 0.0722 * c[2]!;
}
const ratio = (a: string, b: string) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi! + 0.05) / (lo! + 0.05); };

describe("v3 dark tokens", () => {
  test("every colour token has a dark value, and the device rule matches the explicit Dark rule", () => {
    const named = Object.keys(light).filter((k) => !k.startsWith("--print"));
    expect(named.length).toBeGreaterThan(20);
    expect(Object.keys(dark).sort()).toEqual(named.sort());
    expect(device).toEqual(dark);
    expect(dark["--paper"]).not.toBe("#000000");
  });

  test("dark text holds 4.5:1: ink and mute on the grounds, each meaning on the card and on its own tint, fill text on each fill", () => {
    const t = (k: string) => dark[k]!;
    for (const text of ["--ink", "--mute", "--info", "--act"]) for (const g of ["--paper", "--card"]) expect(ratio(t(text), t(g))).toBeGreaterThanOrEqual(4.5);
    for (const m of ["act", "needs", "done", "problem", "harbor", "info"]) {
      expect(ratio(t(`--${m}`), t("--card"))).toBeGreaterThanOrEqual(4.5);
      expect(ratio(t(`--${m}`), t(`--${m}-soft`))).toBeGreaterThanOrEqual(4.5);
      if (m !== "info") expect(ratio(t("--on-fill"), t(`--${m}`))).toBeGreaterThanOrEqual(4.5);
    }
    expect(ratio(t("--deep-ink"), t("--deep"))).toBeGreaterThanOrEqual(4.5);
    expect(ratio(t("--deep-mute"), t("--deep"))).toBeGreaterThanOrEqual(4.5);
  });
});
