/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_DATA_SOURCE?: "live" | "snapshot";
  readonly VITE_API_URL?: string;
  readonly VITE_LIVE_ENDED?: string;
}
