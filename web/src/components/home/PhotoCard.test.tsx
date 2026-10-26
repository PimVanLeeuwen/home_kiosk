import { fireEvent, render, screen } from '@testing-library/react'
import type { PhotoOfTheDay } from '../../lib/pieceTypes'
import { agoLine } from '../../lib/photo'
import { PhotoCard } from './PhotoCard'

const PHOTO: PhotoOfTheDay = {
  as_of: new Date(2026, 9, 26, 6, 5).toISOString(), stale: false,
  asset: 'a1', taken: '2019-10-26', years: 7, people: ['Anna', 'Bob'],
}

describe('PhotoCard', () => {
  it('shows the picture with how long ago and who is in it', () => {
    render(<PhotoCard data={PHOTO} />)

    expect(screen.getByRole('region', { name: 'Photo of the day' })).toBeInTheDocument()
    const img = screen.getByRole('img', { name: 'The photo of the day, from 26 October 2019 · Anna, Bob' })
    expect(img).toHaveAttribute('src', '/api/photo/picture?asset=a1')
    expect(screen.getByText('7 years ago today')).toBeInTheDocument()
    expect(screen.getByText('26 October 2019 · Anna, Bob')).toBeInTheDocument()
  })

  it('leaves out who when nobody is named, and goes when the picture fails', () => {
    render(<PhotoCard data={{ ...PHOTO, people: [] }} />)

    expect(screen.getByText('26 October 2019')).toBeInTheDocument()
    fireEvent.error(screen.getByRole('img'))
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })

  it('shows nothing on a day without a memory', () => {
    const { container } = render(<PhotoCard data={{ ...PHOTO, asset: null, taken: null, years: null }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('words the years', () => {
    expect([agoLine(1), agoLine(7), agoLine(0)]).toEqual(['1 year ago today', '7 years ago today', 'Today'])
  })
})
