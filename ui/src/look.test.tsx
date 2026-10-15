import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "./App";
import ThemeControl from "./components/ThemeControl";
import { readFileSync, readdirSync, statSync } from "node:fs";

import { THEME_KEY, ThemeProvider } from "./theme";

// The legacy look (decision D-027): stylesheet order, no colour literals, theme control, brand marks, index.html.
// Source files are read from disk: vitest's CSS handling turns ?raw and glob imports of CSS into empty strings.

const SRC = `${process.cwd().replace(/\\/g, "/")}/src`; // vitest runs from the ui folder
const indexHtml = readFileSync(`${SRC}/../index.html`, "utf-8");
const mainSrc = readFileSync(`${SRC}/main.tsx`, "utf-8");

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = `${dir}/${name}`;
    if (statSync(path).isDirectory()) return path.endsWith("/styles/legacy") ? [] : cssFiles(path);
    return name.endsWith(".css") ? [path] : [];
  });
}
const css = Object.fromEntries(cssFiles(SRC).map((f) => [f.slice(SRC.length + 1), readFileSync(f, "utf-8")]));

const NAMED =
  "white|black|red|green|blue|gray|grey|silver|orange|yellow|purple|pink|brown|navy|teal|maroon|olive|lime|aqua|cyan|magenta|fuchsia|gold|coral|crimson|indigo|violet|tan|beige|ivory";

/** Colour literals in a stylesheet: hex, colour functions, and named colours used as values. */
function colourLiterals(src: string): string[] {
  const clean = src.replace(/\/\*[\s\S]*?\*\//g, "");
  const hits: string[] = clean.match(/#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch)\(/g) ?? [];
  for (const block of clean.matchAll(/\{([^{}]*)\}/g)) {
    for (const decl of (block[1] ?? "").split(";")) {
      const value = decl.slice(decl.indexOf(":") + 1).replace(/var\([^)]*\)/g, "");
      hits.push(...(value.match(new RegExp(`\\b(?:${NAMED})\\b`, "gi")) ?? []));
    }
  }
  return hits;
}

// M1-UI1: the screens files module 1 uses (docs/design/legacy-css.md step 2: "then only the screens-*.css files a module needs"),
// in the earlier index.html's order. Exactly these: anything else (foresight, evidence, context) stays out. e2 is here for the process map (M2-P03).
const MODULE_1_SCREEN_SHEETS = [
  "./styles/legacy/screens-e3.css",
  "./styles/legacy/screens-e1.css",
  "./styles/legacy/screens-peek.css",
  "./styles/legacy/screens-flow.css",
  "./styles/legacy/screens-team-rooms.css",
  "./styles/legacy/screens-v3-rail.css",
  "./styles/legacy/screens-v3-intent.css",
  "./styles/legacy/screens-v3-baseline.css",
  "./styles/legacy/screens-e2.css", // M2-P03: the as-is swimlane
];

describe("stylesheets", () => {
  test("main.tsx imports legacy sh.css first, then exactly the screens files module 1 uses, then shell.css, all above the app", () => {
    const imports = [...mainSrc.matchAll(/^import\s+(?:[^"\n]*from\s+)?"([^"]+)";/gm)].map((m) => m[1]);
    const sheets = imports.filter((i) => i?.endsWith(".css"));
    expect(sheets[0]).toBe("./styles/legacy/sh.css");
    expect(sheets[sheets.length - 1]).toBe("./styles/shell.css");
    expect(sheets.slice(1, -1)).toEqual(MODULE_1_SCREEN_SHEETS);
    expect(imports.indexOf("./styles/shell.css")).toBeLessThan(imports.indexOf("./App"));
  });

  test("every screens file that is imported is a real file in styles/legacy", () => {
    for (const sheet of MODULE_1_SCREEN_SHEETS) expect(readFileSync(`${SRC}/${sheet.slice(2)}`, "utf-8").length).toBeGreaterThan(100);
  });

  test("the old scaffold token file is gone and shell.css was really read", () => {
    expect(Object.keys(css).filter((k) => !k.startsWith("intents/") && !k.startsWith("v3/")).sort()).toEqual(["modules/m1_intent/define/define.css", "modules/m1_intent/wall/wall.css", "pages/build/chain.css", "styles/design.css", "styles/shell.css", "v1/b11/b11.css", "v1/b7/studio.css", "v1/b9/b9.css", "v1/b9verify/verify.css", "v1/d1/d1.css", "v1/k10/slack.css", "v1/t1/templates.css", "v1/workbench/workbench.css"]);
    expect((css["styles/shell.css"] ?? "").length).toBeGreaterThan(500);
  });

  test("the literal scanner catches hex, functions and named colours, and ignores tokens", () => {
    expect(colourLiterals("a { color: #3A4A59; }")).toHaveLength(1);
    expect(colourLiterals("a { background: rgba(0,0,0,.5); }")).toHaveLength(1);
    expect(colourLiterals("a { color: white; border: 1px solid black; }")).toHaveLength(2);
    expect(colourLiterals("a { color: var(--teal); border-color: transparent; } .x:hover { color: var(--ink2); }")).toEqual([]);
  });

  test("no colour literals in any CSS outside styles/legacy", () => {
    // design.css declares the tokens themselves (D-027 allows literals only where a token is declared): scan it without its :root blocks
    // 3.0 declares its own tokens in v3/v3.css (docs/v3/COLOURS.md); every other 3.0 stylesheet must use them
    const withoutTokens = (name: string, src: string) => (name === "styles/design.css" || name === "v3/v3.css" ? src.replace(/:root[^{]*\{[^}]*\}/g, "") : src);
    const hits = Object.entries(css)
      .map(([name, src]) => [name, colourLiterals(withoutTokens(name, src))] as const)
      .filter(([, found]) => found.length > 0);
    expect(hits).toEqual([]);
  });
});

describe("index.html", () => {
  test("fonts link with preconnect, 32 px icon, no inline-SVG icon, pre-paint theme script", () => {
    expect(indexHtml).toContain('rel="preconnect" href="https://fonts.googleapis.com"');
    expect(indexHtml).toContain("fonts.gstatic.com");
    expect(indexHtml).toContain("family=Manrope");
    expect(indexHtml).toContain("JetBrains+Mono");
    expect(indexHtml).toMatch(/<link[^>]*rel="icon"[^>]*href="\/brand\/signal-harbor-mark-32\.png"/);
    expect(indexHtml).not.toContain("data:image/svg");
    expect(indexHtml).toContain(THEME_KEY);
    expect(indexHtml).toMatch(/<script>[\s\S]*try[\s\S]*catch[\s\S]*<\/script>/);
    expect(indexHtml.indexOf("<script>")).toBeLessThan(indexHtml.indexOf("/src/main.tsx"));
  });
});

function setSystemDark(dark: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: dark && q.includes("dark"),
    media: q,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

function renderControl() {
  return render(
    <ThemeProvider>
      <ThemeControl />
    </ThemeProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme control", () => {
  test("is a labelled group with three plainly named choices", () => {
    renderControl();
    const group = screen.getByRole("group", { name: "Theme" });
    expect(within(group).getAllByRole("radio").map((r) => (r as HTMLInputElement).labels?.[0]?.textContent)).toEqual([
      "Light",
      "Dark",
      "Match my device",
    ]);
    expect(screen.getByRole("radio", { name: "Match my device" })).toBeChecked();
  });

  test("Dark and Light set data-theme; Match my device removes it; the choice is stored", async () => {
    const user = userEvent.setup();
    renderControl();
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    await user.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    await user.click(screen.getByRole("radio", { name: "Match my device" }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
  });

  test("a stored choice is restored; junk is ignored", () => {
    localStorage.setItem(THEME_KEY, "dark");
    const first = renderControl();
    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(document.documentElement.dataset.theme).toBe("dark");
    first.unmount();
    localStorage.setItem(THEME_KEY, "purple");
    renderControl();
    expect(screen.getByRole("radio", { name: "Match my device" })).toBeChecked();
  });

  test("storage that throws still works", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const reported = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const onError = vi.fn();
    window.addEventListener("error", onError);
    const user = userEvent.setup();
    renderControl();
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    window.removeEventListener("error", onError);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(onError).not.toHaveBeenCalled();
    expect(reported).not.toHaveBeenCalled();
  });

  test("works from the keyboard: Tab to the group, arrow keys change the choice", async () => {
    const user = userEvent.setup();
    renderControl();
    await user.tab();
    expect(screen.getByRole("radio", { name: "Match my device" })).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

describe("brand mark", () => {
  function mockSignedOut() {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "session_expired", message: "x", login_url: "/login" }), { status: 401 })),
    );
  }
  function renderLogin() {
    mockSignedOut();
    return render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );
  }

  test("login shows the light mark above the name, with 64 px source and 128 px 2x", async () => {
    setSystemDark(false);
    renderLogin();
    await screen.findByRole("button", { name: "Sign in" });
    const img = document.querySelector("img.brand-mark") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/brand/signal-harbor-mark-64.png");
    expect(img.getAttribute("srcset")).toBe("/brand/signal-harbor-mark-128.png 2x");
    expect(img.getAttribute("alt")).toBe(""); // the name is printed next to it
  });

  test("dark theme, explicit or from the device, uses the on-dark marks", async () => {
    setSystemDark(false);
    localStorage.setItem(THEME_KEY, "dark");
    const first = renderLogin();
    await screen.findByRole("button", { name: "Sign in" });
    let img = document.querySelector("img.brand-mark") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/brand/signal-harbor-mark-64-on-dark.png");
    expect(img.getAttribute("srcset")).toBe("/brand/signal-harbor-mark-128-on-dark.png 2x");
    first.unmount();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    setSystemDark(true);
    renderLogin();
    await screen.findByRole("button", { name: "Sign in" });
    img = document.querySelector("img.brand-mark") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/brand/signal-harbor-mark-64-on-dark.png");
  });

  test("an explicit Light choice beats a dark device", async () => {
    setSystemDark(true);
    localStorage.setItem(THEME_KEY, "light");
    renderLogin();
    await screen.findByRole("button", { name: "Sign in" });
    expect((document.querySelector("img.brand-mark") as HTMLImageElement).getAttribute("src")).toBe("/brand/signal-harbor-mark-64.png");
  });

  test("the login page carries the theme control; the signed-in top bar carries mark (named) and control", async () => {
    setSystemDark(false);
    const { unmount } = renderLogin();
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
    unmount();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const body = url === "/api/company" ? { company_id: "c", name: "Harbor Test Co", industry: "none" } : url === "/api/modules" ? [] : { display_name: "Ann", company_id: "c", roles: [] };
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/legacy"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByText("Harbor Test Co");
    expect(screen.getByRole("img", { name: "Signal Harbor" })).toHaveAttribute("src", "/brand/signal-harbor-mark-64.png");
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
  });
});

// IC-1a design tokens: dark on :root, light under the existing theme attribute and the device query.
const SH = readFileSync(`${SRC}/styles/legacy/sh.css`, "utf-8");
function block(selector: string): string {
  const start = SH.indexOf(`${selector} {`);
  return SH.slice(start, SH.indexOf("\n}", start));
}
function tokens(b: string): Record<string, string> {
  return Object.fromEntries([...b.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], (m[2] ?? "").trim()]));
}
function lum(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (c[0] ?? 0) + 0.7152 * (c[1] ?? 0) + 0.0722 * (c[2] ?? 0);
}
function ratio(a: string, b: string): number {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

describe("design tokens", () => {
  const dark = tokens(block(":root"));
  const light = tokens(block(':root[data-theme="light"]'));
  const device = tokens(block(':root:not([data-theme="dark"])'));

  test("dark is the default on :root; fonts are Manrope and JetBrains Mono", () => {
    expect(dark).toMatchObject({ "--bg": "#0B1014", "--card": "#121A20", "--bg2": "#0E161B", "--line": "#1E2A33", "--ink": "#EEF3F5", "--mute": "#B7C5CC", "--faint": "#7E9199", "--teal": "#2FBFB0", "--amber": "#F0A830", "--orange": "#F08A50", "--green": "#6CC28B", "--violet": "#C77DFF" });
    expect(dark["--font-sans"]).toMatch(/^'Manrope'/);
    expect(dark["--font-mono"]).toMatch(/^'JetBrains Mono'/);
  });

  test("the three toggle states set the expected values", async () => {
    const user = userEvent.setup();
    renderControl();
    const root = document.documentElement;
    await user.click(screen.getByRole("radio", { name: "Light" }));
    expect(root.dataset.theme).toBe("light"); // matches :root[data-theme="light"]
    expect(light).toMatchObject({ "--bg": "#F3F5F6", "--card": "#FFFFFF", "--line": "#D5DEE2", "--ink": "#14232B", "--mute": "#5E7079", "--teal": "#0F6B6B", "--amber": "#A35F00", "--orange": "#B4531A", "--green": "#2F7D4F" });
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    expect(root.dataset.theme).toBe("dark"); // no light rule matches: :root values apply
    await user.click(screen.getByRole("radio", { name: "Match my device" }));
    expect(root.hasAttribute("data-theme")).toBe(false); // the device query picks: light rule for a light device
    expect(device).toEqual(light);
  });

  test("body text holds 4.5:1 on its ground and surface in both themes", () => {
    for (const t of [dark, light]) {
      for (const text of ["--ink", "--mute"]) for (const ground of ["--bg", "--card"]) expect(ratio(t[text] ?? "", t[ground] ?? "")).toBeGreaterThanOrEqual(4.5);
    }
    expect(ratio(dark["--faint"] ?? "", dark["--bg"] ?? "")).toBeGreaterThanOrEqual(4.5);
  });
});
