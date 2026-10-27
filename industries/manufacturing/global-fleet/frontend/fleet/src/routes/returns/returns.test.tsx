import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FleetRoutes } from '../../App'
import type { ReturnCandidate, ReturnView } from './api'

const candidate: ReturnCandidate = {
  vehicleId: 7,
  registration: 'AB12 CDE',
  make: 'Example',
  model: 'Estate',
  assignmentId: 42,
  employeeNo: 'E123',
  firstName: 'Ada',
  lastName: 'Lovelace',
  startDate: '2026-03-01',
  lastOdometer: 1200,
  distanceUnit: 'MILE',
}

const returned: ReturnView = {
  returnId: 1,
  assignmentId: 42,
  vehicleId: 7,
  registration: 'AB12 CDE',
  employeeNo: 'E123',
  startDate: '2026-03-01',
  returnDate: '2026-10-27',
  odometer: 1300,
  distanceUnit: 'MILE',
  conditionNote: null,
}

function json(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  }))
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <FleetRoutes />
    </MemoryRouter>,
  )
}

function findCar(value: string, by: 'plate' | 'vehicleId' = 'plate') {
  fireEvent.change(screen.getByLabelText('Find by'), { target: { value: by } })
  fireEvent.change(screen.getByLabelText(by === 'plate' ? 'Plate' : 'Vehicle id'), { target: { value } })
  fireEvent.click(screen.getByRole('button', { name: 'Find car' }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('returns page', () => {
  it('GF18_returnFunctionIsReachable', () => {
    renderAt('/')
    fireEvent.click(screen.getByRole('link', { name: 'Returns' }))
    expect(screen.getByRole('heading', { name: 'Returns' })).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Find car' })).toBeInTheDocument()
  })

  it('looks a car up by plate and records the return', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => String(input).includes('/lookup')
      ? json(200, candidate)
      : json(201, returned))
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/returns')

    findCar(' ab12 cde ')
    expect(await screen.findByText(/Assigned to E123 \(Ada Lovelace\) since 2026-03-01/)).toBeInTheDocument()
    expect(screen.getByText('Last recorded odometer: 1200 miles')).toBeInTheDocument()
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/v1/returns/lookup?plate=ab12%20cde')

    fireEvent.change(screen.getByLabelText('Odometer (miles)'), { target: { value: '1300' } })
    fireEvent.click(screen.getByRole('button', { name: 'Return car' }))

    expect(await screen.findByRole('status')).toHaveTextContent('AB12 CDE returned on 2026-10-27 at 1300 miles')
    const [, init] = fetchMock.mock.calls[1] as unknown as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      vehicleId: 7,
      assignmentId: 42,
      returnDate: null,
      odometer: 1300,
      conditionNote: null,
    })
  })

  it('looks a car up by vehicle id and shows a first return without a previous reading', async () => {
    const fetchMock = vi.fn(() => json(200, { ...candidate, lastOdometer: null, distanceUnit: 'KM' }))
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/returns')

    findCar('7', 'vehicleId')
    expect(await screen.findByText('No previous odometer reading')).toBeInTheDocument()
    expect(screen.getByLabelText('Odometer (km)')).toBeInTheDocument()
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe('/api/v1/returns/lookup?vehicleId=7')
  })

  it('sends an all-digit plate as a plate, not a vehicle id', async () => {
    const fetchMock = vi.fn(() => json(200, candidate))
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/returns')

    findCar('1234')
    expect(await screen.findByRole('form', { name: 'Return car' })).toBeInTheDocument()
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe('/api/v1/returns/lookup?plate=1234')
  })

  it('rejects a non-numeric vehicle id without calling the service', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/returns')

    findCar('AB12', 'vehicleId')
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a vehicle id (digits only)')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the already-returned error from the service', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json(409, {
      code: 'ALREADY_RETURNED',
      message: 'Car AB12 CDE has no open assignment; it is already returned',
    })))
    renderAt('/returns')

    findCar('AB12 CDE')
    expect(await screen.findByRole('alert')).toHaveTextContent('already returned')
    expect(screen.queryByRole('form', { name: 'Return car' })).not.toBeInTheDocument()
  })

  it('keeps the form open when the service rejects the odometer', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input).includes('/lookup')
      ? json(200, candidate)
      : json(422, {
        code: 'ODOMETER_BELOW_LAST_READING',
        message: 'The odometer reading 1100 is below the car\'s last recorded reading of 1200 mile',
      })))
    renderAt('/returns')

    findCar('AB12 CDE')
    fireEvent.change(await screen.findByLabelText('Odometer (miles)'), { target: { value: '1100' } })
    // The input's min blocks this in a browser; submit directly to prove the service check is shown.
    fireEvent.submit(screen.getByRole('form', { name: 'Return car' }))

    await waitFor(() => { expect(screen.getByRole('alert')).toHaveTextContent('below the car') })
    expect(screen.getByRole('form', { name: 'Return car' })).toBeInTheDocument()
  })
})
