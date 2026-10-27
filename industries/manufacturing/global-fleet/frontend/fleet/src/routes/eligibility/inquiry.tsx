import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { client, type EmployeeInquiry as EmployeeInquiryData } from '../../api/client'

export default function EmployeeInquiry() {
  const { employeeNo = '' } = useParams()
  const [employee, setEmployee] = useState<EmployeeInquiryData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void client.getEmployee(employeeNo)
      .then((data) => {
        if (active) setEmployee(data)
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Employee request failed')
      })
    return () => {
      active = false
    }
  }, [employeeNo])

  if (error) {
    return <p role="alert">{error}</p>
  }
  if (!employee) {
    return <p>Loading employee…</p>
  }

  return (
    <section>
      <h2>{employee.employeeNo}</h2>
      <dl>
        <dt>Last name</dt>
        <dd>{employee.lastName}</dd>
        <dt>First name</dt>
        <dd>{employee.firstName}</dd>
        <dt>Current car</dt>
        <dd>{employee.currentCar ?? '—'}</dd>
        <dt>Car request eligibility</dt>
        <dd>{employee.carRequest.allowed ? 'Eligible' : employee.carRequest.reason}</dd>
      </dl>
      <h3>Employment history</h3>
      <table>
        <thead>
          <tr>
            <th>Grade</th>
            <th>Status</th>
            <th>Hire date</th>
            <th>Leave date</th>
          </tr>
        </thead>
        <tbody>
          {employee.employments.map((employment) => (
            <tr key={employment.id}>
              <td>{employment.grade ?? '—'}</td>
              <td>{employment.status}</td>
              <td>{employment.hireDate}</td>
              <td>{employment.leaveDate ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
