/**
 * Puts text on the clipboard. The text may still be on its way (a fetch): Safari only allows a
 * copy inside the tap, so a ClipboardItem with a promise is tried first, then writeText, then
 * the old way for plain http (the Tailscale IP), which has no clipboard API.
 */
export async function copyText(text: string | Promise<string>): Promise<void> {
  const clip = navigator.clipboard
  if (clip?.write && typeof ClipboardItem !== 'undefined') {
    try {
      const blob = Promise.resolve(text).then((t) => new Blob([t], { type: 'text/plain' }))
      await clip.write([new ClipboardItem({ 'text/plain': blob })])
      return
    } catch {
      // Not allowed or not supported this way: try the others.
    }
  }
  const value = await text
  if (clip?.writeText) {
    try {
      await clip.writeText(value)
      return
    } catch {
      // Fall through to the old way.
    }
  }
  const area = document.createElement('textarea')
  area.value = value
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.append(area)
  area.select()
  const copied = document.execCommand?.('copy') ?? false
  area.remove()
  if (!copied) throw new Error('The browser did not allow copying.')
}
