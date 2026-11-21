import { expect, test } from '@playwright/test'
import { Shell } from './shell'

const light = (id: string, name: string, on: boolean, brightness: number, kelvin: number | null) => ({ id, name, on, brightness, kelvin, reachable: true })

function lights(spotsOn: boolean, as_of = new Date().toISOString()) {
  return {
    as_of, stale: false, room: 'Living room', kelvins: [2200, 2700, 3500, 4500, 6500],
    groups: [
      { id: 'kitchen', name: 'Kitchen spots', kind: 'ambiance', on: spotsOn, brightness: 77, kelvin: 4500,
        lights: ['Keuken 1', 'Keuken 2', 'Keuken 3'].map((n, i) => light(`s${i}`, n, spotsOn, 77, 4500)) },
      { id: 'ceiling', name: 'Ceiling lamps', kind: 'white', on: true, brightness: 55, kelvin: null,
        lights: [light('b1', 'Plafondlamp Bank', true, 55, null), light('b2', 'Plafondlamp Tafel', true, 55, null)] },
    ],
  }
}

test('Lights switches the kitchen spots and picks a white', async ({ page, isMobile }) => {
  const sent: unknown[] = []
  let spotsOn = true
  await page.route('**/api/lights', (route) => route.fulfill({ json: lights(spotsOn) }))
  await page.route('**/api/lights/kitchen', (route) => {
    const body = route.request().postDataJSON()
    sent.push(body)
    if ('on' in body) spotsOn = body.on
    return route.fulfill({ json: lights(spotsOn, new Date(Date.now() + 1000).toISOString()) })
  })
  await page.goto('/')

  // The Home space opens on Lights, on desktop and on a phone.
  await new Shell(page).open('Home', undefined, isMobile)

  const kitchen = page.getByRole('region', { name: 'Kitchen spots' })
  await expect(page.getByText('5 of 5 on')).toBeVisible()
  await kitchen.getByRole('button', { pressed: true }).click()
  await expect(kitchen.getByRole('button', { pressed: false })).toContainText('Off')
  await expect(page.getByText('2 of 5 on')).toBeVisible()

  await kitchen.getByRole('radio', { name: '2700 K' }).click()
  await expect.poll(() => sent).toEqual([{ on: false }, { kelvin: 2700 }])
})
