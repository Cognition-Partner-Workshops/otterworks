import { request, type ProfileResponse } from '../../api/client'

export type DistanceUnit = ProfileResponse['distanceUnit']

export interface ReturnCandidate {
  vehicleId: number
  registration: string
  make: string | null
  model: string | null
  assignmentId: number
  employeeNo: string
  firstName: string | null
  lastName: string | null
  startDate: string
  lastOdometer: number | null
  distanceUnit: DistanceUnit
}

export interface ReturnRequest {
  plate?: string
  vehicleId?: number
  assignmentId?: number
  returnDate: string | null
  odometer: number | null
  conditionNote: string | null
}

export interface ReturnView {
  returnId: number
  assignmentId: number
  vehicleId: number
  registration: string
  employeeNo: string
  startDate: string
  returnDate: string
  odometer: number
  distanceUnit: DistanceUnit
  conditionNote: string | null
}

export type ReturnKey = { plate: string } | { vehicleId: number }

export const returnsApi = {
  lookup: (key: ReturnKey) => {
    const query = 'plate' in key
      ? `plate=${encodeURIComponent(key.plate)}`
      : `vehicleId=${key.vehicleId}`
    return request<ReturnCandidate>(`/api/v1/returns/lookup?${query}`)
  },
  submit: (body: ReturnRequest) => request<ReturnView>('/api/v1/returns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }),
}
