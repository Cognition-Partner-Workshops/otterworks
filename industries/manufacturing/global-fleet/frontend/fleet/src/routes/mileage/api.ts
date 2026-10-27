export type MileageStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface MileageClaimRequest {
  employeeNo: string
  journeyDate: string | null
  distance: number
  purpose: string
}

export interface MileageQuote {
  distance: number
  distanceUnit: string
  rate: number
  amount: number
  currency: string
}

export interface MileageClaim {
  id: number
  employeeNo: string
  employmentId: number
  journeyDate: string
  distance: number
  distanceUnit: string
  rate: number
  amount: number
  currency: string
  status: MileageStatus
  paidPeriod: string
  vehicleRegistration: string | null
  purpose: string | null
  submittedAt: string
  decidedAt: string | null
}

export interface MileageHistory {
  employeeNo: string
  from: string
  to: string
  claims: MileageClaim[]
}

export interface MileageReimbursement {
  employeeNo: string
  period: string
  claimCount: number
  distance: number
  amount: number
  currency: string
}

export class MileageApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'MileageApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/mileage${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const payload = await response.json() as Record<string, unknown>
  if (!response.ok) {
    throw new MileageApiError(
      String(payload.message ?? response.statusText),
      String(payload.code ?? 'MILEAGE_REQUEST_FAILED'),
      response.status,
    )
  }
  return payload as T
}

export function quoteMileage(distance: string | number): Promise<MileageQuote> {
  return request(`/quote?distance=${encodeURIComponent(String(distance))}`)
}

export function submitMileageClaim(claim: MileageClaimRequest): Promise<MileageClaim> {
  return request('/claims', { method: 'POST', body: JSON.stringify(claim) })
}

export function getPendingMileageClaims(): Promise<MileageClaim[]> {
  return request('/claims/pending')
}

export function approveMileageClaim(id: number): Promise<MileageClaim> {
  return request(`/claims/${id}/approve`, { method: 'POST' })
}

export function rejectMileageClaim(id: number): Promise<MileageClaim> {
  return request(`/claims/${id}/reject`, { method: 'POST' })
}

export function getMileageHistory(employeeNo: string): Promise<MileageHistory> {
  return request(`/employees/${encodeURIComponent(employeeNo)}/claims`)
}

export function getMileageReimbursement(
  employeeNo: string,
  period: string,
): Promise<MileageReimbursement> {
  return request(
    `/employees/${encodeURIComponent(employeeNo)}/reimbursement?period=${encodeURIComponent(period)}`,
  )
}
