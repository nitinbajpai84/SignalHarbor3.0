// All screen wording lives here (rule: plain words, one sentence per error, say what to do next).
export const copy = {
  product: "Signal Harbor",
  login: {
    title: "Sign in",
    email: "Email",
    password: "Password",
    button: "Sign in",
    busy: "Signing in...",
    mismatch: "That email and password did not match. Try again.",
    unavailable: "We could not sign you in right now. Try again in a moment.",
  },
  home: {
    heading: "Your modules",
    signOut: "Sign out",
    emptyModules: "No modules are switched on for your company yet. Ask your administrator.",
    guidedBy: "Guided by",
  },
  module: {
    placeholder: "This module opens in a later release.",
    back: "Back to your modules",
  },
  states: {
    loading: "Loading...",
    empty: "Nothing here yet.",
    error: "Something went wrong. Try again in a moment.",
    refused: "This module is not part of your plan. Ask your administrator.",
    noAccess: "You do not have access to this. Ask your administrator.",
    refusedHeading: "This module is not available",
    retry: "Try again",
  },
  notFound: { message: "We could not find that page.", home: "Go to your modules" },
  errors: {
    network: "We could not reach the service. Check your connection and try again.",
    server: "Something went wrong on our side. Try again in a moment.",
    sessionEnded: "Your session has ended. Please sign in again.",
  },
  theme: { legend: "Theme", light: "Light", dark: "Dark", system: "Match my device" },
  wizard: { back: "Back", next: "Next", suggestion: "Suggestion", steps: "Steps" },
} as const;
