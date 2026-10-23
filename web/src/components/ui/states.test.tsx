import { fireEvent, render, screen } from '@testing-library/react'
import { Loading, PageUnavailable, StaleNote, Unavailable } from './states'

describe('shared states', () => {
  it('words loading, unavailable and stale the same way everywhere', () => {
    render(
      <>
        <Loading what="the lights" />
        <Unavailable what="Calendars" plural detail="Try again later." />
        <StaleNote />
      </>,
    )
    expect(screen.getByText('Loading the lights…')).toBeInTheDocument()
    expect(screen.getByText(/^Calendars are not available right now\. Try again later\.$/)).toBeInTheDocument()
    expect(screen.getByText('Showing the last known figures.')).toHaveClass('text-warn')
  })

  it('offers a retry on a page that is not available', () => {
    const retry = vi.fn()
    render(<PageUnavailable what="The repo list" detail="It comes every 30 minutes." onRetry={retry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('The repo list is not available right now')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(retry).toHaveBeenCalled()
  })
})
