import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FleetRoutes } from '../../App'
import type {
  CarRequestDraft,
  DraftUpdateRequest,
  EmployeeCarView,
  PoolVehicle,
  VehicleRulesResponse,
} from '../../api/client'

const pool: PoolVehicle[] = [{
  id: 10,
  registration: 'POOL-10',
  make: 'Example',
  model: 'Estate',
  listPrice: 22000,
  co2: 120,
  fuel: 'D',
}]

const rules: VehicleRulesResponse = {
  requiredNewVehicleFields: ['plate', 'make', 'model', 'listPrice', 'co2', 'fuel'],
}

function savedDraft(): CarRequestDraft {
  return {
    draftId: 'draft-123',
    employeeNo: 'E123',
    step: 'CONFIRM',
    vehicleChoice: 'NEW',
    poolVehicleId: null,
    newVehicle: {
      plate: 'AB12 CDE',
      make: 'Example Motors',
      model: 'Tourer',
      listPrice: 25000,
      co2: 0,
      fuel: 'E',
      benefitPercent: null,
    },
    reason: 'RP',
    startDate: '2026-10-20',
    eligibility: { allowed: true, reason: null, employeeNo: 'E123', employmentId: 4 },
    vehicleAvailable: null,
    pool,
  }
}

function routeFetch(
  draft: CarRequestDraft | null = savedDraft(),
  overrides: Record<string, (init?: RequestInit) => Response | Promise<Response>> = {},
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const override = overrides[`${method} ${url}`]
    if (override) return await override(init)
    if (url.endsWith('/car-requests/drafts/E123') && method === 'GET') {
      return draft
        ? Response.json(draft)
        : new Response(JSON.stringify({ code: 'NO_DRAFT', message: 'No draft' }), { status: 404 })
    }
    if (url.endsWith('/car-requests/drafts/E123') && method === 'PUT') {
      const update = JSON.parse(String(init?.body)) as DraftUpdateRequest
      return Response.json({
        ...(draft ?? savedDraft()),
        ...update,
        draftId: draft?.draftId ?? 'draft-123',
        employeeNo: 'E123',
        startDate: update.startDate ?? null,
      })
    }
    if (url.endsWith('/assignments/vehicle-rules')) return Response.json(rules)
    if (url.endsWith('/assignments/pool')) return Response.json(pool)
    return Response.json({})
  })
}

describe('assignment routes', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('GF09_startDateDefaultsToServerToday', async () => {
    const fetchMock = routeFetch(null)
    vi.stubGlobal('fetch', fetchMock)
    render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))
    expect(await screen.findByRole('heading', { name: 'Choose a vehicle' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByRole('heading', { name: 'Confirm request' })).toBeInTheDocument()
    expect(screen.getByLabelText('Start date')).toHaveValue('')

    const putBodies = fetchMock.mock.calls
      .filter(([, init]) => init?.method === 'PUT')
      .map(([, init]) => JSON.parse(String(init?.body)) as DraftUpdateRequest)
    expect(putBodies).toHaveLength(2)
    expect(putBodies[1]).toMatchObject({ step: 'CONFIRM', startDate: null })
  })

  it('GF34_refreshReturnsToSavedDraft', async () => {
    const fetchMock = routeFetch()
    vi.stubGlobal('fetch', fetchMock)
    const first = render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Confirm request' })).toBeInTheDocument()
    expect(screen.getByLabelText('Reason')).toHaveValue('RP')
    expect(screen.getByLabelText('Start date')).toHaveValue('2026-10-20')
    expect(screen.getByText(/Vehicle: AB12 CDE/)).toBeInTheDocument()
    first.unmount()

    const second = render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Confirm request' })).toBeInTheDocument()
    expect(screen.getByLabelText('Reason')).toHaveValue('RP')
    expect(screen.getByText(/Vehicle: AB12 CDE/)).toBeInTheDocument()
    second.unmount()

    const freshFetch = routeFetch(null)
    vi.stubGlobal('fetch', freshFetch)
    render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))
    await waitFor(() => {
      expect(freshFetch).toHaveBeenCalledWith(
        expect.stringContaining('/car-requests/drafts/E123'),
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"step":"VEHICLE"'),
        }),
      )
    })
  })

  it('GF34_newTabResumesSameDraft', async () => {
    const fetchMock = routeFetch()
    vi.stubGlobal('fetch', fetchMock)
    const first = render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Confirm request' })).toBeInTheDocument()
    first.unmount()
    render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Confirm request' })).toBeInTheDocument()
    expect(screen.getByLabelText('Start date')).toHaveValue('2026-10-20')
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/car-requests/drafts/E123'))).toHaveLength(2)
  })

  it('GF07_staleSubmitReturnsToVehicleChoice', async () => {
    const draft = {
      ...savedDraft(),
      step: 'CONFIRM' as const,
      vehicleChoice: 'POOL' as const,
      poolVehicleId: 10,
    }
    const fetchMock = routeFetch(draft, {
      'POST /api/v1/car-requests/drafts/E123/submit': () => Response.json({
        code: 'CAR_NO_LONGER_AVAILABLE',
        message: 'Car no longer available',
        pool: [],
      }, { status: 409 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    render(
      <MemoryRouter initialEntries={['/assignment/request?employee=E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Submit request' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Car no longer available')
    expect(await screen.findByRole('heading', { name: 'Choose a vehicle' })).toBeInTheDocument()
  })

  it('GF13_currentCarPageShowsOpenAssignment', async () => {
    const currentCar: EmployeeCarView = {
      employeeNo: 'E123',
      current: {
        id: 7,
        legacyRef: null,
        registration: 'CAR-123',
        make: 'Example',
        model: 'Estate',
        startDate: '2025-02-01',
        endDate: null,
        reason: 'NC',
      },
      history: [],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(currentCar)))
    render(
      <MemoryRouter initialEntries={['/assignment/E123']}>
        <FleetRoutes />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/CAR-123/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Assignment history' })).toBeInTheDocument()
  })
})
