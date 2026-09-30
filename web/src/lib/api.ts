/** GET a JSON endpoint on the hub API. Relative, so it works on every host. */
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error(`${path} answered ${response.status}`)
  return (await response.json()) as T
}
