import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { client, type EmployeeSummary } from '../../api/client'

export default function EmployeeSearch() {
  const [term, setTerm] = useState('')
  const [employees, setEmployees] = useState<EmployeeSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  async function search(value: string) {
    try {
      setError(null)
      setEmployees(await client.searchEmployees(value))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Employee search failed')
    }
  }

  useEffect(() => {
    void search('')
  }, [])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void search(term)
  }

  return (
    <section>
      <h2>Employees</h2>
      <form onSubmit={submit}>
        <label htmlFor="employee-search">Search employees</label>
        <input
          id="employee-search"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
        />
        <button type="submit">Search</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>Employee no</th>
            <th>Last name</th>
            <th>First name</th>
            <th>Grade</th>
            <th>Status</th>
            <th>Current car</th>
          </tr>
        </thead>
        <tbody>
          {employees.map((employee) => (
            <tr key={employee.employeeNo}>
              <td>
                <Link to={`/eligibility/employees/${encodeURIComponent(employee.employeeNo)}`}>
                  {employee.employeeNo}
                </Link>
              </td>
              <td>{employee.lastName}</td>
              <td>{employee.firstName}</td>
              <td>{employee.grade ?? '—'}</td>
              <td>{employee.status ?? '—'}</td>
              <td>{employee.currentCar ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
