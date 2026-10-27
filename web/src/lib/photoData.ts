/** The longest side a phone photo is sent with; the hub keeps 900 px of it. */
export const PHOTO_LONGEST = 1800

/**
 * A photo from the phone as a JPEG data URL, at most PHOTO_LONGEST px, turned the right way up.
 * Sent as JSON, so the hub's write guard stays as it is.
 */
export async function photoData(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  const scale = Math.min(1, PHOTO_LONGEST / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return canvas.toDataURL('image/jpeg', 0.85)
}
