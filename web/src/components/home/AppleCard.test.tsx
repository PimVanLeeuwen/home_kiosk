import { render, screen, waitFor, within } from '@testing-library/react'
import type { AppleDevices, ApplePlaying } from '../../lib/types'
import { stubApi } from '../../test/stubApi'
import { AppleCard } from './AppleCard'
import { useApi } from '../../lib/useApi'

/** The card as Home gives it its data. */
function Fetched() {
  const { data } = useApi<AppleDevices>('/api/apple')
  return <AppleCard data={data} />
}

const dev = (id: string, kind: 'tv' | 'homepod' | 'homepod_mini', thread: boolean | null, over = {}) => ({
  id,
  name: id,
  kind,
  online: true,
  offline_since: null,
  thread,
  ...over,
})
const show: ApplePlaying = { state: 'playing', media: 'video', title: 'Severance', subtitle: 'S2 E7', app: 'Jellyfin', device: 'w1', artwork: false }

function house(over: { living?: ApplePlaying | null; bath?: ApplePlaying | null; bathOnline?: boolean; stale?: boolean } = {}): AppleDevices {
  return {
    as_of: new Date().toISOString(),
    stale: over.stale ?? false,
    rooms: [
      { id: 'living-room', name: 'Living room', devices: [dev('w1', 'homepod', true), dev('tv1', 'tv', true), dev('w2', 'homepod', true)], playing: over.living ?? null },
      { id: 'bedroom', name: 'Bedroom', devices: [dev('tv2', 'tv', null), dev('mini1', 'homepod_mini', true)], playing: null },
      {
        id: 'bathroom',
        name: 'Bathroom',
        devices: [dev('mini2', 'homepod_mini', true, { online: over.bathOnline ?? true })],
        playing: over.bath ?? null,
      },
    ],
  }
}

const card = () => screen.findByRole('region', { name: 'Apple devices' })

describe('AppleCard', () => {
  it('draws every device and the Thread network, all online', async () => {
    stubApi({ '/api/apple': house() })
    render(<Fetched />)

    const c = await card()
    expect(within(c).getByText('All online')).toBeInTheDocument()
    expect(c.querySelectorAll('[data-device]')).toHaveLength(6)
    expect(c.querySelectorAll('[data-link="up"]')).toHaveLength(5)
    expect(within(c).getByText('Thread · 5 of 5 border routers')).toBeInTheDocument()
    expect(c).toHaveTextContent('6 of 6 online')
    expect(within(c).queryByRole('list', { name: 'Playing' })).not.toBeInTheDocument()
  })

  it('lights the room that plays and says what plays there', async () => {
    stubApi({ '/api/apple': house({ living: show }) })
    render(<Fetched />)

    const c = await card()
    expect(within(c).getByText('Playing in Living room')).toBeInTheDocument()
    expect(c.querySelector('[data-room="living-room"]')).toHaveAttribute('data-playing', 'playing')
    // Video: the Apple TV and both HomePods of the pair send out ripples.
    for (const id of ['w1', 'tv1', 'w2']) expect(c.querySelectorAll(`[data-device="${id}"] .motion-safe\\:animate-ripple`)).toHaveLength(2)
    expect(c.querySelectorAll('[data-device="mini1"] .motion-safe\\:animate-ripple')).toHaveLength(0)
    const bar = within(within(c).getByRole('list', { name: 'Playing' })).getByRole('listitem')
    expect(bar).toHaveTextContent('Severance')
    expect(bar).toHaveTextContent('S2 E7 · Jellyfin · Living room')
  })

  it('shows artwork through the hub and a paused item without ripples', async () => {
    const paused: ApplePlaying = { ...show, state: 'paused', media: 'music', title: 'Nightcall', artwork: true, device: 'mini2' }
    stubApi({ '/api/apple': house({ bath: paused, living: show }) })
    render(<Fetched />)

    const c = await card()
    expect(within(c).getByText('Playing in Living room')).toBeInTheDocument()
    const bars = within(within(c).getByRole('list', { name: 'Playing' })).getAllByRole('listitem')
    expect(bars[1]).toHaveAttribute('data-state', 'paused')
    expect(bars[1]).toHaveTextContent('Paused · S2 E7')
    expect(bars[1].querySelector('img')).toHaveAttribute('src', '/api/apple/artwork/bathroom')
    expect(c.querySelectorAll('[data-device="mini2"] .motion-safe\\:animate-ripple')).toHaveLength(0)
  })

  it('marks an offline device and breaks its Thread links', async () => {
    stubApi({ '/api/apple': house({ bathOnline: false, living: show }) })
    render(<Fetched />)

    const c = await card()
    expect(within(c).getByText('1 offline')).toBeInTheDocument()
    expect(c.querySelector('[data-device="mini2"]')).toHaveAttribute('data-online', 'false')
    expect(c.querySelectorAll('[data-link="broken"]')).toHaveLength(2)
    expect(within(c).getByText('Thread · 4 of 5 border routers')).toBeInTheDocument()
    expect(within(c).getByRole('img')).toHaveAccessibleName(expect.stringContaining('Bathroom: 1 device, mini2 offline'))
  })

  it('notes a stale answer', async () => {
    stubApi({ '/api/apple': house({ stale: true }) })
    render(<Fetched />)

    expect(await screen.findByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('stays away until the first answer', async () => {
    const fetchMock = stubApi({})
    const { container } = render(<Fetched />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
