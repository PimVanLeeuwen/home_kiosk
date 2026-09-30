// Service icons bundled with the app, from homarr-labs/dashboard-icons
// (Apache-2.0, see src/assets/icons/LICENSE). Vite hashes each file, so they
// cache for good and nothing is fetched from a CDN.
const files = import.meta.glob<string>('../assets/icons/*.{svg,png}', {
  eager: true,
  query: '?url',
  import: 'default',
})

/** Icon name (file name without extension) to its URL. */
export const ICONS: Record<string, string> = Object.fromEntries(
  Object.entries(files).map(([path, url]) => [path.replace(/^.*\/|\.\w+$/g, ''), url]),
)

export const ICON_NAMES = Object.keys(ICONS).sort()

export const iconUrl = (name: string | null | undefined): string | undefined =>
  name ? ICONS[name] : undefined
