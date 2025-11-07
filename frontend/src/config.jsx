// Expose API and WS URLs from environment. Accept Vite-style VITE_* env names.
export const API_BASE = import.meta.env.VITE_API_BASE || '';
export const WS_URL = import.meta.env.VITE_WS_URL || '';
