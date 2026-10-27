import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FleetRoutes } from '../../App'
import type { EmployeeInquiry, EmployeeSummary } from '../../api/client'

describe('eligibility routes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GF33_searchPageListsEmployeesWithCurrentCar', async () => {
    const employees: EmployeeSummary[] = [{
      employeeNo: 'E123',
      lastName: 'Example',
      firstName: 'Erin',
      grade: 7,
      status: 'ACTIVE',
      currentCar: 'CAR-123',
    }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => employees,
    }))

    render(
      <MemoryRouter initialEntries={['/eligibility']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'E123' })).toBeInTheDocument()
    expect(screen.getByText('CAR-123')).toBeInTheDocument()
    expect(screen.getByText('Example')).toBeInTheDocument()
  })

  it('GF03_inquiryPageShowsLeaver', async () => {
    const employee: EmployeeInquiry = {
      employeeNo: 'E124',
      lastName: 'Leaver',
      firstName: 'Leslie',
      currentCar: null,
      current: {
        id: 7,
        grade: 7,
        status: 'LEFT',
        hireDate: '2019-01-01',
        leaveDate: '2024-05-31',
      },
      employments: [{
        id: 7,
        grade: 7,
        status: 'LEFT',
        hireDate: '2019-01-01',
        leaveDate: '2024-05-31',
      }],
      carRequest: {
        allowed: false,
        reason: 'NOT_ACTIVE',
        employeeNo: 'E124',
        employmentId: 7,
      },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => employee,
    }))

    render(
      <MemoryRouter initialEntries={['/eligibility/employees/E124']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'E124' })).toBeInTheDocument()
    expect(screen.getByText('LEFT')).toBeInTheDocument()
    expect(screen.getByText('NOT_ACTIVE')).toBeInTheDocument()
  })

  it('GF03_inquiryPageShowsNotFound', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))

    render(
      <MemoryRouter initialEntries={['/eligibility/employees/UNKNOWN']}>
        <FleetRoutes />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Employee not found')
  })
})
