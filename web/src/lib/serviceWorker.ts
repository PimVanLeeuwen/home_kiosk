/**
 * Registers public/sw.js, which lets the installed app open without the hub
 * (plan.md M15). Browsers only allow service workers in a secure context, so
 * this runs on the Tailscale HTTPS address and is skipped on the plain LAN
 * address and in development.
 */
export function registerServiceWorker(
  env: { prod: boolean; secure: boolean } = { prod: import.meta.env.PROD, secure: window.isSecureContext },
): boolean {
  if (!env.prod || !env.secure || !('serviceWorker' in navigator)) return false
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      // Without it the app works as before, just not offline.
    })
  })
  return true
}
