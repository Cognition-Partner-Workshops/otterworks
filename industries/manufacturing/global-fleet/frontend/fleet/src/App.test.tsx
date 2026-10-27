import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App, { FleetRoutes } from './App'

describe('fleet application', () => {
  it('renders the home page and navigation', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Global Fleet' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Fleet functions' })).toBeInTheDocument()
  })

  it.each([
    ['/', 'Global Fleet'],
    ['/eligibility', 'Eligibility'],
    ['/assignment', 'Assignment'],
    ['/returns', 'Returns'],
    ['/mileage', 'Mileage'],
    ['/benefit', 'Benefit'],
  ])('renders route %s', (path, heading) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
  })
})
