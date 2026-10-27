import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { client, type EmployeeCarView } from '../../api/client'
import { ErrorAlert, Loading, errorText } from '../../components/status'

export default function EmployeeCar() {
  const { employeeNo = '' } = useParams()
  const [result, setResult] = useState<EmployeeCarView | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void client.getEmployeeCar(employeeNo)
      .then((car) => {
        if (active) setResult(car)
      })
      .catch((cause: unknown) => {
        if (active) setError(errorText(cause, 'Could not load current car'))
      })
    return () => { active = false }
  }, [employeeNo])

  if (error) return <ErrorAlert>{error}</ErrorAlert>
  if (!result) return <Loading>Loading car history…</Loading>

  return (
    <section>
      <h1>{result.employeeNo}</h1>
      <h2>Current car</h2>
      {result.current
        ? <p>{result.current.registration} — {result.current.make ?? ''} {result.current.model ?? ''}</p>
        : <p>No company car</p>}
      <h2>Assignment history</h2>
      {result.history.length === 0 ? <p>No assignment history</p> : (
        <table>
          <thead>
            <tr><th>Registration</th><th>Start date</th><th>End date</th><th>Reason</th><th>Assignment ID</th></tr>
          </thead>
          <tbody>
            {result.history.map((assignment) => (
              <tr key={assignment.id}>
                <td>{assignment.registration}</td>
                <td>{assignment.startDate}</td>
                <td>{assignment.endDate ?? 'Open'}</td>
                <td>{assignment.reason ?? '—'}</td>
                <td>{assignment.legacyRef ?? assignment.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
