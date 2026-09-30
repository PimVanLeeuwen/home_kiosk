import { fireEvent, render } from '@testing-library/react'
import { iconUrl } from '../lib/icons'
import { ServiceIcon } from './ServiceIcon'

describe('ServiceIcon', () => {
  it('shows the bundled icon', () => {
    const { container } = render(<ServiceIcon icon="jellyfin" label="Je" index={0} />)

    expect(container.querySelector('img')).toHaveAttribute('src', iconUrl('jellyfin'))
    expect(container).not.toHaveTextContent('Je')
  })

  it('falls back to letters for an unknown icon or none', () => {
    expect(render(<ServiceIcon icon="grafana" label="Gr" index={0} />).container).toHaveTextContent('Gr')
    expect(render(<ServiceIcon icon={null} label="Ab" index={1} />).container).toHaveTextContent('Ab')
  })

  it('falls back to letters when the image fails to load', () => {
    const { container } = render(<ServiceIcon icon="jellyfin" label="Je" index={0} />)

    fireEvent.error(container.querySelector('img')!)

    expect(container.querySelector('img')).toBeNull()
    expect(container).toHaveTextContent('Je')
  })
})
