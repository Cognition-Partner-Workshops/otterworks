export interface ProfileResponse {
  sourceApp: string
  currency: string
  distanceUnit: 'MILE' | 'KM'
  minGrade: number
  benefitPercentSource: 'VEHICLE' | 'PROFILE'
  benefitPercent: string | null
  commutePercentPerUnit: string
  employeeContribution: 'EMPLOYEE' | 'NONE'
  benefitRounding: RoundingMode
  mileageRate: string
  mileageRounding: RoundingMode
  claimLookbackMonths: number
  maxClaimDistance: number
  claimHistoryMonths: number
  payrollFile: boolean
}

export type RoundingMode =
  | 'UP'
  | 'DOWN'
  | 'CEILING'
  | 'FLOOR'
  | 'HALF_UP'
  | 'HALF_DOWN'
  | 'HALF_EVEN'
  | 'UNNECESSARY'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

async function getProfile(): Promise<ProfileResponse> {
  const response = await fetch(`${apiBase}/api/v1/profile`)
  if (!response.ok) {
    throw new Error(`Profile request failed with status ${response.status}`)
  }
  return (await response.json()) as ProfileResponse
}

export const client = { getProfile }
