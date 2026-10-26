/** "7 years ago today" for the photo of the day; "Today" for one taken this year. */
export function agoLine(years: number | null): string {
  if (!years) return 'Today'
  return `${years} year${years === 1 ? '' : 's'} ago today`
}
