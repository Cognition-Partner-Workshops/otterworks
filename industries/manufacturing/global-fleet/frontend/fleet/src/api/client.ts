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

export type EmploymentStatus = 'ACTIVE' | 'LEFT' | 'TRANSFERRED'
export type EligibilityReason =
  | 'EMPLOYEE_NUMBER_REQUIRED'
  | 'EMPLOYEE_NOT_FOUND'
  | 'NOT_ACTIVE'
  | 'GRADE_BELOW_THRESHOLD'
  | 'NO_EMPLOYMENT_ON_DATE'
  | 'CLAIM_AFTER_LEAVING_DATE'
export type CarRequestStep = 'EMPLOYEE' | 'VEHICLE' | 'CONFIRM'

export interface EligibilityDecision {
  allowed: boolean
  reason: EligibilityReason | null
  employeeNo: string | null
  employmentId: number | null
}

export interface EmployeeSummary {
  employeeNo: string
  lastName: string
  firstName: string
  grade: number | null
  status: EmploymentStatus | null
  currentCar: string | null
}

export interface EmploymentView {
  id: number
  grade: number | null
  status: EmploymentStatus
  hireDate: string
  leaveDate: string | null
}

export interface EmployeeInquiry {
  employeeNo: string
  lastName: string
  firstName: string
  currentCar: string | null
  current: EmploymentView | null
  employments: EmploymentView[]
  carRequest: EligibilityDecision
}

export interface BelowGradeHolder {
  employeeNo: string
  lastName: string
  firstName: string
  grade: number | null
  minGrade: number
  employmentId: number
  assignmentId: number
  registration: string
  startDate: string
  endDate: string | null
}

export interface ApiError {
  code: string
  message: string
  pool?: PoolVehicle[]
}

export class ApiFailure extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly payload: ApiError,
  ) {
    super(message)
    this.name = 'ApiFailure'
  }
}

export interface PoolVehicle {
  id: number
  registration: string
  make: string | null
  model: string | null
  listPrice: number | null
  co2: number | null
  fuel: string | null
}

export interface NewVehicleInput {
  plate: string
  make: string
  model: string
  listPrice: number | null
  co2: number | null
  fuel: string
  benefitPercent: number | null
}

export interface DraftVehicle {
  plate: string | null
  make: string | null
  model: string | null
  listPrice: number | null
  co2: number | null
  fuel: string | null
  benefitPercent: number | null
}

export interface DraftUpdateRequest {
  step: CarRequestStep
  vehicleChoice?: 'POOL' | 'NEW' | null
  poolVehicleId?: number | null
  newVehicle?: NewVehicleInput | null
  reason?: 'NC' | 'RP' | 'PL' | null
  startDate?: string | null
}

export interface CarRequestDraft {
  draftId: string
  employeeNo: string
  step: CarRequestStep
  vehicleChoice: 'POOL' | 'NEW' | null
  poolVehicleId: number | null
  newVehicle: DraftVehicle | null
  reason: 'NC' | 'RP' | 'PL' | null
  startDate: string | null
  eligibility: EligibilityDecision
  vehicleAvailable: boolean | null
  pool: PoolVehicle[]
}

export interface VehicleRulesResponse {
  requiredNewVehicleFields: string[]
}

export interface AssignmentView {
  id: number
  legacyRef: string | null
  registration: string
  make: string | null
  model: string | null
  startDate: string
  endDate: string | null
  reason: string | null
}

export interface EmployeeCarView {
  employeeNo: string
  current: AssignmentView | null
  history: AssignmentView[]
}

export interface SubmitRequest {
  draftId: string
}

export interface CarRequestResult {
  requestId: number
  assignmentId: number
  employeeNo: string
  registration: string
  reason: string
  startDate: string
  status: string
}

export interface DoubleHolderAssignment {
  legacyRef: string | null
  vehicleId: string
  startDate: string
  reason: string | null
}

export interface DoubleHolder {
  employeeNo: string
  employmentLegacyRef: string
  source: 'LEGACY_UNLOAD' | 'SERVICE'
  assignments: DoubleHolderAssignment[]
}

export interface ConfirmationRequest {
  assignmentLegacyRef: string
  returnDate: string
}

export interface ConfirmationResponse {
  employmentLegacyRef: string
  assignmentLegacyRef: string
  confirmedReturnDate: string
  confirmedAt: string
}

const apiBase = import.meta.env.VITE_API_BASE ?? ''

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = init
    ? await fetch(`${apiBase}${path}`, init)
    : await fetch(`${apiBase}${path}`)
  if (!response.ok) {
    let payload: ApiError = {
      code: 'REQUEST_FAILED',
      message: `Request failed with status ${response.status}`,
    }
    try {
      payload = await response.json() as ApiError
    } catch {
      // Keep a useful status-based message when no JSON response is available.
    }
    throw new ApiFailure(response.status, payload.code, payload.message, payload)
  }
  if (response.status === 204) return undefined as T
  return await response.json() as T
}

async function getProfile(): Promise<ProfileResponse> {
  return request<ProfileResponse>('/api/v1/profile')
}

async function searchEmployees(q: string = ''): Promise<EmployeeSummary[]> {
  return request<EmployeeSummary[]>(`/api/v1/employees?q=${encodeURIComponent(q)}`)
}

async function getEmployee(employeeNo: string): Promise<EmployeeInquiry> {
  try {
    return await request<EmployeeInquiry>(`/api/v1/employees/${encodeURIComponent(employeeNo)}`)
  } catch (cause) {
    if (cause instanceof ApiFailure && cause.status === 404) {
      throw new Error('Employee not found')
    }
    throw cause
  }
}

async function getDraft(employeeNo: string): Promise<CarRequestDraft> {
  return request<CarRequestDraft>(`/api/v1/car-requests/drafts/${encodeURIComponent(employeeNo)}`)
}

async function putDraft(employeeNo: string, draft: DraftUpdateRequest): Promise<CarRequestDraft> {
  return request<CarRequestDraft>(`/api/v1/car-requests/drafts/${encodeURIComponent(employeeNo)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(draft),
  })
}

async function deleteDraft(employeeNo: string): Promise<void> {
  return request<void>(`/api/v1/car-requests/drafts/${encodeURIComponent(employeeNo)}`, { method: 'DELETE' })
}

async function submitDraft(employeeNo: string, draftId: string): Promise<CarRequestResult> {
  return request<CarRequestResult>(
    `/api/v1/car-requests/drafts/${encodeURIComponent(employeeNo)}/submit`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draftId } satisfies SubmitRequest),
    },
  )
}

async function getPool(): Promise<PoolVehicle[]> {
  return request<PoolVehicle[]>('/api/v1/assignments/pool')
}

async function getVehicleRules(): Promise<VehicleRulesResponse> {
  return request<VehicleRulesResponse>('/api/v1/assignments/vehicle-rules')
}

async function getEmployeeCar(employeeNo: string): Promise<EmployeeCarView> {
  return request<EmployeeCarView>(`/api/v1/employees/${encodeURIComponent(employeeNo)}/car`)
}

async function getDoubleHolders(): Promise<DoubleHolder[]> {
  return request<DoubleHolder[]>('/api/v1/assignments/cutover/double-holders')
}

async function confirmDoubleHolder(
  employmentLegacyRef: string,
  confirmation: ConfirmationRequest,
): Promise<ConfirmationResponse> {
  return request<ConfirmationResponse>(
    `/api/v1/assignments/cutover/double-holders/${encodeURIComponent(employmentLegacyRef)}/confirmations`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(confirmation),
    },
  )
}

export const client = {
  getProfile,
  searchEmployees,
  getEmployee,
  getDraft,
  putDraft,
  deleteDraft,
  submitDraft,
  getPool,
  getVehicleRules,
  getEmployeeCar,
  getDoubleHolders,
  confirmDoubleHolder,
}
