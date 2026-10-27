import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FleetRoutes } from '../../App'
import type { MileageClaim, MileageHistory } from './api'

function claim(overrides: Partial<MileageClaim> = {}): MileageClaim {
  return {
    id: 42,
    employeeNo: 'E-42',
    employmentId: 4,
    journeyDate: '2026-10-20',
    distance: 20,
    distanceUnit: 'KM',
    rate: 0.305,
    amount: 6.10,
    currency: 'EUR',
    status: 'PENDING',
    paidPeriod: '202610',
    vehicleRegistration: null,
    purpose: 'Client visit',
    submittedAt: '2026-10-27T12:00:00Z',
    decidedAt: null,
    ...overrides,
  }
}

describe('mileage routes', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('GF19_blankJourneyDateIsSentAsNull', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('POST')
      return Response.json(claim())
    })
    vi.stubGlobal('fetch', fetchMock)
    render(
      <MemoryRouter initialEntries={['/mileage']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('Employee number'), { target: { value: 'E-42' } })
    fireEvent.change(screen.getByLabelText('Distance'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Purpose'), { target: { value: 'Client visit' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit claim' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as Record<string, unknown>
    expect(body).toMatchObject({
      employeeNo: 'E-42',
      journeyDate: null,
      distance: 20,
      purpose: 'Client visit',
    })
    expect(await screen.findByRole('heading', { name: 'Claim submitted' })).toBeInTheDocument()
  })

  it('GF22_approvalPageApprovesPendingClaim', async () => {
    const pending = claim()
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/claims/pending')) return Response.json([pending])
      return Response.json({ ...pending, status: 'APPROVED', decidedAt: '2026-10-27T12:00:00Z' })
    })
    vi.stubGlobal('fetch', fetchMock)
    render(
      <MemoryRouter initialEntries={['/mileage/approvals']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    expect(await screen.findByText('Status: APPROVED')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/mileage/claims/42/approve',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('GF24_historyPageListsNewestFirst', async () => {
    const history: MileageHistory = {
      employeeNo: 'E-42',
      from: '2026-04-27',
      to: '2026-10-27',
      claims: [
        claim({ id: 2, journeyDate: '2026-10-20', status: 'APPROVED', vehicleRegistration: 'CAR-2' }),
        claim({ id: 1, journeyDate: '2026-04-27', status: 'REJECTED', vehicleRegistration: null }),
      ],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(history)))
    render(
      <MemoryRouter initialEntries={['/mileage/E-42']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(within(rows[1]).getByText('2026-10-20')).toBeInTheDocument()
    expect(within(rows[1]).getByText('CAR-2')).toBeInTheDocument()
    expect(within(rows[2]).getByText('2026-04-27')).toBeInTheDocument()
    expect(within(rows[2]).getByText('—')).toBeInTheDocument()
  })
})
