import { afterEach, describe, expect, it, vi } from 'vitest'
import { client, type ProfileResponse } from './client'

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
})
