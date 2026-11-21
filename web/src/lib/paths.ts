/**
 * Every page's address (plan.md M38: spaces). A page lives under its space (`/house/nas`);
 * links in the hub take their address from here. Today, Now's first tab, stays at `/`.
 */
export const PATHS = {
  today: '/',
  weather: '/now/weather',
  running: '/now/running',
  reminders: '/now/reminders',
  todos: '/now/todos',
  lights: '/home/lights',
  music: '/home/music',
  nas: '/house/nas',
  docker: '/house/docker',
  services: '/house/services',
  backups: '/house/backups',
  media: '/house/media',
  network: '/house/network',
  repos: '/house/repos',
  alerts: '/house/alerts',
  news: '/read/news',
  saved: '/read/saved',
  portfolio: '/money/portfolio',
  recipes: '/kitchen/recipes',
  ask: '/ask',
  settings: '/settings',
} as const

export const alertPath = (id: number | string) => `${PATHS.alerts}/${id}`
export const recipePath = (id: string) => `${PATHS.recipes}/${encodeURIComponent(id)}`
export const cookPath = (id: string) => `${recipePath(id)}/cook`

/**
 * Where each page was before the spaces: the address and everything under it moves, its
 * query and hash kept, so ntfy taps (`/alerts/<id>`), alert pages' onward links, the
 * collector's links and bookmarks keep working.
 */
export const MOVED: Record<string, string> = {
  '/weather': PATHS.weather,
  '/running': PATHS.running,
  '/reminders': PATHS.reminders,
  '/todos': PATHS.todos,
  '/lights': PATHS.lights,
  '/music': PATHS.music,
  '/nas': PATHS.nas,
  '/docker': PATHS.docker,
  '/services': PATHS.services,
  '/backups': PATHS.backups,
  '/media': PATHS.media,
  '/tailscale': PATHS.network,
  '/repos': PATHS.repos,
  '/alerts': PATHS.alerts,
  '/news': PATHS.news,
  '/saved': PATHS.saved,
  '/portfolio': PATHS.portfolio,
  '/recipes': PATHS.recipes,
}

/** An address from before the spaces at its new place (others as they are): for links the collector sends. */
export function movedPath(path: string): string {
  const from = Object.keys(MOVED).find((old) => path === old || (path.startsWith(old) && /^[/?#]/.test(path.slice(old.length))))
  return from ? MOVED[from] + path.slice(from.length) : path
}
