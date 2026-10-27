import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EmployeeCarView, EmployeeInquiry, EmployeeSummary, PoolVehicle, ProfileResponse } from './api/client'
import App, { FleetRoutes } from './App'

const routeRenderState = vi.hoisted(() => ({ returnsThrows: false }))

vi.mock('./routes/returns', async () => {
  const actual = await vi.importActual<typeof import('./routes/returns')>('./routes/returns')
  return {
    default: function MockReturns() {
      if (routeRenderState.returnsThrows) throw new Error('Test render failure')
      const ActualReturns = actual.default
      return <ActualReturns />
    },
  }
})

describe('fleet application', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    routeRenderState.returnsThrows = false
  })

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

  const ukProfile: ProfileResponse = {
    sourceApp: 'gf-mainframe-idms',
    currency: 'GBP',
    distanceUnit: 'MILE',
    minGrade: 7,
    benefitPercentSource: 'VEHICLE',
    benefitPercent: null,
    commutePercentPerUnit: '0',
    employeeContribution: 'EMPLOYEE',
    benefitRounding: 'DOWN',
    mileageRate: '0.445',
    mileageRounding: 'HALF_UP',
    claimLookbackMonths: 3,
    maxClaimDistance: 1500,
    claimHistoryMonths: 6,
    payrollFile: true,
  }
  const deProfile: ProfileResponse = {
    sourceApp: 'gf-jsf-portal',
    currency: 'EUR',
    distanceUnit: 'KM',
    minGrade: 6,
    benefitPercentSource: 'PROFILE',
    benefitPercent: '1.00',
    commutePercentPerUnit: '0.030',
    employeeContribution: 'NONE',
    benefitRounding: 'HALF_UP',
    mileageRate: '0.305',
    mileageRounding: 'HALF_UP',
    claimLookbackMonths: 2,
    maxClaimDistance: 2500,
    claimHistoryMonths: 6,
    payrollFile: false,
  }

  it.each([['uk', ukProfile], ['de', deProfile]] as const)(
    'GF32_navigationReachesEveryFunction(%s)',
    async (_country, profile) => {
      const employee: EmployeeSummary = {
        employeeNo: 'E123',
        lastName: 'Lovelace',
        firstName: 'Ada',
        grade: 9,
        status: 'ACTIVE',
        currentCar: 'CAR-123',
      }
      const inquiry: EmployeeInquiry = {
        employeeNo: 'E123',
        lastName: 'Lovelace',
        firstName: 'Ada',
        currentCar: 'CAR-123',
        current: { id: 4, grade: 9, status: 'ACTIVE', hireDate: '2020-01-01', leaveDate: null },
        employments: [{ id: 4, grade: 9, status: 'ACTIVE', hireDate: '2020-01-01', leaveDate: null }],
        carRequest: { allowed: true, reason: null, employeeNo: 'E123', employmentId: 4 },
      }
      const car: EmployeeCarView = {
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
      const pool: PoolVehicle[] = [{
        id: 10,
        registration: 'POOL-10',
        make: 'Example',
        model: 'Estate',
        listPrice: 22000,
        co2: 120,
        fuel: 'D',
      }]
      vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url === '/api/v1/profile') return Response.json(profile)
        if (url === '/api/v1/employees?q=') return Response.json([employee])
        if (url === '/api/v1/employees/E123/car') return Response.json(car)
        if (url === '/api/v1/employees/E123') return Response.json(inquiry)
        if (url === '/api/v1/car-requests/drafts/E123') {
          return Response.json({ code: 'NO_DRAFT', message: 'No draft' }, { status: 404 })
        }
        if (url === '/api/v1/assignments/vehicle-rules') {
          return Response.json({ requiredNewVehicleFields: ['plate', 'make', 'model', 'listPrice', 'co2', 'fuel'] })
        }
        if (url === '/api/v1/assignments/pool') return Response.json(pool)
        if (url === '/api/v1/benefit/periods') {
          return Response.json([{
            period: '202610',
            startDate: '2026-10-01',
            endDate: '2026-10-31',
            status: 'OPEN',
            mileageRate: 0.305,
            recordCount: null,
            totalTaxable: null,
            totalMileage: null,
          }])
        }
        return Response.json([])
      }))
      render(
        <MemoryRouter initialEntries={['/']}>
          <FleetRoutes showProfile />
        </MemoryRouter>,
      )

      expect(await screen.findByText(new RegExp(`Profile: .* · ${profile.currency} · distances in`))).toBeInTheDocument()
      fireEvent.click(screen.getByRole('link', { name: 'Employee search' }))
      expect(await screen.findByRole('heading', { name: 'Employees' })).toBeInTheDocument()
      fireEvent.click(await screen.findByRole('link', { name: 'E123' }))
      expect(await screen.findByRole('heading', { name: 'E123' })).toBeInTheDocument()

      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      fireEvent.click(screen.getByRole('link', { name: 'Car request' }))
      fireEvent.change(screen.getByLabelText('Employee number'), { target: { value: 'E123' } })
      fireEvent.click(screen.getByRole('button', { name: 'Request a car' }))
      expect(await screen.findByRole('heading', { name: 'Request a company car' })).toBeInTheDocument()

      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      fireEvent.click(screen.getByRole('link', { name: 'Current car and history' }))
      fireEvent.change(screen.getByLabelText('Employee number for current car'), { target: { value: 'E123' } })
      fireEvent.click(screen.getByRole('button', { name: 'View current car' }))
      expect(await screen.findByRole('heading', { name: 'Current car' })).toBeInTheDocument()

      fireEvent.click(screen.getByRole('link', { name: 'Returns' }))
      expect(screen.getByRole('form', { name: 'Find car' })).toBeInTheDocument()

      fireEvent.click(screen.getByRole('link', { name: 'Mileage' }))
      expect(screen.getByRole('heading', { name: 'Submit mileage claim' })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('link', { name: 'Mileage approvals' }))
      expect(await screen.findByRole('heading', { name: 'Mileage approvals' })).toBeInTheDocument()

      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      fireEvent.click(screen.getByRole('link', { name: 'Benefit inquiry' }))
      expect(await screen.findByRole('heading', { name: 'Benefit inquiry' })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      fireEvent.click(screen.getByRole('link', { name: 'Benefit statement' }))
      expect(await screen.findByRole('heading', { name: 'Benefit statement' })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      fireEvent.click(screen.getByRole('link', { name: 'Period close' }))
      expect(await screen.findByRole('heading', { name: 'Benefit periods' })).toBeInTheDocument()
      expect(await screen.findByRole('button', { name: 'Close period' })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      expect(screen.getByRole('heading', { name: 'Global Fleet' })).toBeInTheDocument()
    },
  )

  it('GF32_routeErrorClearsOnNavigation', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      render(
        <MemoryRouter initialEntries={['/']}>
          <FleetRoutes />
        </MemoryRouter>,
      )

      routeRenderState.returnsThrows = true
      fireEvent.click(screen.getByRole('link', { name: 'Returns' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')

      routeRenderState.returnsThrows = false
      fireEvent.click(screen.getByRole('link', { name: 'Home' }))
      expect(await screen.findByRole('heading', { name: 'Global Fleet' })).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    } finally {
      consoleError.mockRestore()
    }
  })
})
