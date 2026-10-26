import { expect, test } from '@playwright/test'

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

  // In the sidebar under Home, and on the More page on a phone.
  if (isMobile) {
    await page.locator('nav.fixed').getByRole('link', { name: 'More' }).click()
    await page.getByRole('main').getByRole('link', { name: /Lights/ }).click()
  } else {
    await page.locator('aside').getByRole('link', { name: 'Lights' }).click()
  }

  const kitchen = page.getByRole('region', { name: 'Kitchen spots' })
  await expect(page.getByText('5 of 5 on')).toBeVisible()
  await kitchen.getByRole('button', { pressed: true }).click()
  await expect(kitchen.getByRole('button', { pressed: false })).toContainText('Off')
  await expect(page.getByText('2 of 5 on')).toBeVisible()

  await kitchen.getByRole('radio', { name: '2700 K' }).click()
  await expect.poll(() => sent).toEqual([{ on: false }, { kelvin: 2700 }])
})

test('The floor plan is placed in Settings and finds a group on the Lights page', async ({ page }) => {
  let plan = { aspect: 1.7, lights: {}, furniture: [{ kind: 'sofa', x: 0.7, y: 0.7, w: 0.26, h: 0.2 }] }
  const saved: unknown[] = []
  await page.route('**/api/lights', (route) => route.fulfill({ json: lights(true) }))
  await page.route('**/api/lights/plan', (route) => {
    if (route.request().method() === 'PUT') {
      plan = route.request().postDataJSON()
      saved.push(plan)
    }
    return route.fulfill({ json: plan })
  })

  await page.goto('/settings/lights')
  const editor = page.getByRole('group', { name: /The living room from above/ })
  const bank = editor.getByRole('button', { name: /^Plafondlamp Bank:/ })
  await bank.focus()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowDown')
  await page.getByRole('button', { name: 'Save the plan' }).click()
  await expect(page.getByRole('status')).toContainText('Saved')
  expect(saved).toHaveLength(1)

  await page.goto('/lights')
  const room = page.getByRole('group', { name: /The living room from above/ })
  await room.getByRole('button', { name: 'Ceiling lamps, Plafondlamp Bank: on at 55%' }).click()
  await expect(page.getByRole('region', { name: 'Ceiling lamps' })).toHaveAttribute('data-selected', 'true')
})
