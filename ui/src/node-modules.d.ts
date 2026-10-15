// Just enough of Node's fs for the tests that read source files from disk (no @types/node dependency).
declare module "node:fs" {
  export function readFileSync(path: string, encoding: "utf-8"): string;
  export function readdirSync(path: string): string[];
  export function statSync(path: string): { isDirectory(): boolean };
}
declare const process: { cwd(): string };
