import { createContext } from "react";

/** True inside the stepper: the Build rooms then leave their own tile switcher out, because the step rail is the switcher. */
export const InStepper = createContext(false);
