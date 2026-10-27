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

const apiBase = import.meta.env.VITE_API_BASE ?? ''

async function getProfile(): Promise<ProfileResponse> {
  const response = await fetch(`${apiBase}/api/v1/profile`)
  if (!response.ok) {
    throw new Error(`Profile request failed with status ${response.status}`)
  }
  return (await response.json()) as ProfileResponse
}

async function searchEmployees(q: string = ''): Promise<EmployeeSummary[]> {
  const response = await fetch(`${apiBase}/api/v1/employees?q=${encodeURIComponent(q)}`)
  if (!response.ok) {
    throw new Error(`Employee search failed with status ${response.status}`)
  }
  return (await response.json()) as EmployeeSummary[]
}

async function getEmployee(employeeNo: string): Promise<EmployeeInquiry> {
  const response = await fetch(`${apiBase}/api/v1/employees/${encodeURIComponent(employeeNo)}`)
  if (response.status === 404) {
    throw new Error('Employee not found')
  }
  if (!response.ok) {
    throw new Error(`Employee request failed with status ${response.status}`)
  }
  return (await response.json()) as EmployeeInquiry
}

export const client = { getProfile, searchEmployees, getEmployee }
