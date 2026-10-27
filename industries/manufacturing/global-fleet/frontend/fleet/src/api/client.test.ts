import { afterEach, describe, expect, it, vi } from 'vitest'
import { client, type EmployeeInquiry, type EmployeeSummary, type ProfileResponse } from './client'

const profile: ProfileResponse = {
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

describe('fleet API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses the profile JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => profile,
    }))

    await expect(client.getProfile()).resolves.toEqual(profile)
    expect(fetch).toHaveBeenCalledWith('/api/v1/profile')
  })

  it('searches employees with an encoded query', async () => {
    const employees: EmployeeSummary[] = [{
      employeeNo: 'E123',
      lastName: 'Example',
      firstName: 'Erin',
      grade: 7,
      status: 'ACTIVE',
      currentCar: 'CAR-1',
    }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => employees,
    }))

    await expect(client.searchEmployees('ACME & Co')).resolves.toEqual(employees)
    expect(fetch).toHaveBeenCalledWith('/api/v1/employees?q=ACME%20%26%20Co')
  })

  it('gets an employee using an encoded employee number', async () => {
    const employee: EmployeeInquiry = {
      employeeNo: 'A/B 1',
      lastName: 'Example',
      firstName: 'Erin',
      currentCar: null,
      current: null,
      employments: [],
      carRequest: {
        allowed: false,
        reason: 'NOT_ACTIVE',
        employeeNo: 'A/B 1',
        employmentId: null,
      },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => employee,
    }))

    await expect(client.getEmployee('A/B 1')).resolves.toEqual(employee)
    expect(fetch).toHaveBeenCalledWith('/api/v1/employees/A%2FB%201')
  })

  it('turns an employee 404 into a readable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    await expect(client.getEmployee('UNKNOWN')).rejects.toThrow('Employee not found')
  })
})
