// G5: the installable app. Registers the service worker (public/sw.js), remembers the browser's "install" offer and handles Web Push.
// Everything here fails quietly into "not available": a browser without these features just has no Install or Notifications choice.
import { apiGet, apiSend } from "./api/client";

interface InstallEvent extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> }
let offer: InstallEvent | null = null;
const listeners = new Set<() => void>();
const tell = () => listeners.forEach((l) => l());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); offer = e as InstallEvent; tell(); });
  window.addEventListener("appinstalled", () => { offer = null; tell(); });
}

export function registerServiceWorker(): void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator) || !import.meta.env.PROD) return; // the dev server has no built shell to keep
  window.addEventListener("load", () => { navigator.serviceWorker.register("/sw.js").catch(() => undefined); });
}

export const isStandalone = (): boolean =>
  typeof window !== "undefined" && (window.matchMedia?.("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);
export const isIos = (): boolean => typeof navigator !== "undefined" && /iphone|ipad|ipod/i.test(navigator.userAgent);

/** What the Install button can do now: `prompt` (the browser offered), `ios` (Share, then Add to Home Screen), or none. */
export function installKind(): "prompt" | "ios" | null {
  if (isStandalone()) return null;
  if (offer) return "prompt";
  return isIos() ? "ios" : null;
}
export async function install(): Promise<boolean> {
  if (!offer) return false;
  const o = offer;
  await o.prompt();
  const { outcome } = await o.userChoice;
  if (outcome === "accepted") offer = null;
  tell();
  return outcome === "accepted";
}
export function onInstallChange(fn: () => void): () => void { listeners.add(fn); return () => { listeners.delete(fn); }; }

// ---- Web Push ----
export interface PushConfig { enabled: boolean; public_key: string | null; subscribed: boolean }
export const pushSupported = (): boolean =>
  typeof navigator !== "undefined" && "serviceWorker" in navigator && typeof window !== "undefined" && "PushManager" in window && "Notification" in window;
export const getPushConfig = () => apiGet<PushConfig>("/api/v3/push/config");

const keyBytes = (b64: string): Uint8Array => {
  const raw = atob(b64.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(b64.length / 4) * 4, "="));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};

/** Ask permission, subscribe this device and tell the server. Throws a plain sentence when it cannot. */
export async function enablePush(publicKey: string): Promise<void> {
  if (!pushSupported()) throw new Error("This browser cannot show notifications.");
  if ((await Notification.requestPermission()) !== "granted") throw new Error("Notifications are blocked for this site. Allow them in the browser settings.");
  const reg = await navigator.serviceWorker.ready;
  const sub = (await reg.pushManager.getSubscription()) ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) as BufferSource }));
  await apiSend("POST", "/api/v3/push/subscribe", { subscription: sub.toJSON() });
}

export async function disablePush(): Promise<void> {
  let endpoint = "";
  if (pushSupported()) {
    const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription();
    endpoint = sub?.endpoint ?? "";
    await sub?.unsubscribe().catch(() => false);
  }
  await apiSend("POST", "/api/v3/push/unsubscribe", endpoint ? { endpoint } : {});
}
