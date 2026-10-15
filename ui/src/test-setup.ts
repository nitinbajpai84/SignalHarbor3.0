import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// The full suite runs ~20 jsdom workers at once; waitFor's default second is too short under that load.
configure({ asyncUtilTimeout: 5000 });
