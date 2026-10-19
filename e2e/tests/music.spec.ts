import { expect, test } from '@playwright/test'

const device = (id: string, name: string, active = false) => ({ id, name, type: 'tv', active, volume: 60, restricted: false })

function music(playing: boolean) {
  return {
    as_of: Date.now() / 1000, stale: false, connected: true, default_device: 'Apple TV Living Room', last: null,
    devices: [device('atv', 'Apple TV Living Room', playing), device('mac', 'MacBook Pro')],
    favourites: [{ position: 0, id: 'p1', name: 'Discover Weekly', cover: null, colour: null }],
    playing: playing
      ? { kind: 'track', title: 'Midnight City', subtitle: 'M83', duration_ms: 243000, cover: null, colour: '#e85c8c',
          state: 'playing', progress_ms: 97000, device: device('atv', 'Apple TV Living Room', true) }
      : null,
  }
}

test('Music starts a favourite on the Apple TV and shows it on Home', async ({ page, isMobile }) => {
  let playing = false
  const started: string[] = []
  await page.route('**/api/music', (route) => route.fulfill({ json: music(playing) }))
  await page.route('**/api/music/favourites/0/play', (route) => {
    started.push(route.request().method())
    playing = true
    return route.fulfill({ json: { ok: true, device_id: 'atv', seconds: 4.2 } })
  })
  await page.goto('/')

  // Nothing plays yet: no Now Playing card on Home.
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Now playing' })).toHaveCount(0)

  if (isMobile) {
    await page.locator('nav.fixed').getByRole('link', { name: 'More' }).click()
    await page.getByRole('main').getByRole('link', { name: /Music/ }).click()
  } else {
    await page.locator('aside').getByRole('link', { name: 'Music' }).click()
  }
  await expect(page.getByRole('heading', { name: 'Nothing playing' })).toBeVisible()
  await page.getByRole('button', { name: 'Play Discover Weekly' }).click()
  await expect(page.getByRole('heading', { name: 'Midnight City' })).toBeVisible()
  expect(started).toEqual(['POST'])

  await page.goto('/')
  const card = page.getByRole('region', { name: 'Now playing' })
  await expect(card).toContainText('Midnight City')
  await expect(card).toContainText('On Apple TV Living Room')
})
