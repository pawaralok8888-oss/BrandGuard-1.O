/**
 * Demo-only controls such as "Simulate load error" and "Preview empty state".
 * They are hidden unless VITE_SHOW_DEV_TOOLS=true is set when the frontend is built or run.
 */
export const SHOW_DEV_TOOLS = import.meta.env.VITE_SHOW_DEV_TOOLS === "true";
