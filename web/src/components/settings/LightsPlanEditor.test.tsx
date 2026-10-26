import { fireEvent, render, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { LightsPlan } from '../../lib/lightsPlan'
import { sentBody, stubApi } from '../../test/stubApi'
import { LightsPlanEditor } from './LightsPlanEditor'

const LIGHTS = {
  as_of: new Date().toISOString(), stale: false, room: 'Living room', kelvins: [2700],
  groups: [{ id: 'g', name: 'Ceiling lamps', kind: 'white', on: true, brightness: 60, kelvin: null,
    lights: [{ id: 'b1', name: 'Bank', on: true, brightness: 60, kelvin: null, reachable: true }] }],
}
const PLAN: LightsPlan = {
  aspect: 1.7, lights: { b1: { x: 0.5, y: 0.5 } },
  furniture: [{ kind: 'sofa', x: 0.5, y: 0.7, w: 0.3, h: 0.2 }, { kind: 'tv', x: 0.5, y: 0.95, w: 0.2, h: 0.04 }],
}

describe('LightsPlanEditor', () => {
  it('moves lights and furniture, turns and removes pieces, and saves the plan', async () => {
    const fetchMock = stubApi({ '/api/lights': LIGHTS, '/api/lights/plan': PLAN, 'PUT /api/lights/plan': (body: unknown) => body })
    render(<LightsPlanEditor />)

    const plan = await screen.findByRole('group', { name: /The living room from above/ })
    const save = screen.getByRole('button', { name: 'Save the plan' })
    expect(save).toBeDisabled()
    fireEvent.keyDown(within(plan).getByRole('button', { name: /^Bank:/ }), { key: 'ArrowRight' })
    fireEvent.keyDown(within(plan).getByRole('button', { name: /^Sofa:/ }), { key: 'ArrowUp' })
    fireEvent.click(screen.getByRole('button', { name: 'Turn sofa' }))
    fireEvent.click(screen.getByRole('button', { name: 'TV', pressed: true }))
    fireEvent.click(save)

    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'PUT', '/api/lights/plan')).toEqual({
        aspect: 1.7,
        lights: { b1: { x: 0.51, y: 0.5 } },
        furniture: [{ kind: 'sofa', x: 0.5, y: 0.69, w: 0.2, h: 0.3 }],
      }),
    )
    expect(await screen.findByRole('status')).toHaveTextContent('Saved')
  })
})
