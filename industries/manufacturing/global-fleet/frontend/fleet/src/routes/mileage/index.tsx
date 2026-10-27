import { useEffect, useState, type FormEvent } from 'react'
import { Link, Route, Routes, useParams } from 'react-router'
import {
  approveMileageClaim,
  getMileageHistory,
  getPendingMileageClaims,
  MileageApiError,
  quoteMileage,
  rejectMileageClaim,
  submitMileageClaim,
  type MileageClaim,
  type MileageHistory,
  type MileageQuote,
} from './api'

function errorMessage(error: unknown): string {
  if (error instanceof MileageApiError) return `${error.code}: ${error.message}`
  return error instanceof Error ? error.message : 'Mileage request failed'
}

function ClaimEntry() {
  const [employeeNo, setEmployeeNo] = useState('')
  const [journeyDate, setJourneyDate] = useState('')
  const [distance, setDistance] = useState('')
  const [purpose, setPurpose] = useState('')
  const [quote, setQuote] = useState<MileageQuote | null>(null)
  const [claim, setClaim] = useState<MileageClaim | null>(null)
  const [error, setError] = useState('')

  async function calculate() {
    setError('')
    try {
      setQuote(await quoteMileage(distance))
    } catch (cause) {
      setError(errorMessage(cause))
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      setClaim(await submitMileageClaim({
        employeeNo,
        journeyDate: journeyDate || null,
        distance: Number(distance),
        purpose,
      }))
    } catch (cause) {
      setError(errorMessage(cause))
    }
  }

  return (
    <section>
      <h1>Mileage</h1>
      <h2>Submit mileage claim</h2>
      <form onSubmit={submit}>
        <label>
          Employee number
          <input
            required
            value={employeeNo}
            onChange={(event) => setEmployeeNo(event.target.value)}
          />
        </label>
        <label>
          Journey date
          <input
            type="date"
            value={journeyDate}
            onChange={(event) => setJourneyDate(event.target.value)}
          />
        </label>
        <label>
          Distance
          <input
            required
            type="number"
            step="any"
            value={distance}
            onChange={(event) => setDistance(event.target.value)}
          />
        </label>
        <label>
          Purpose
          <input value={purpose} onChange={(event) => setPurpose(event.target.value)} />
        </label>
        <button type="button" onClick={() => void calculate()}>Calculate</button>
        <button type="submit">Submit claim</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {quote && (
        <p aria-label="Mileage quote">
          Quote: {quote.distance} {quote.distanceUnit} at {quote.rate} = {quote.amount} {quote.currency}
        </p>
      )}
      {claim && (
        <section aria-label="Submitted claim">
          <h2>Claim submitted</h2>
          <p>{claim.status}: {claim.amount} {claim.currency} for {claim.distance} {claim.distanceUnit}</p>
          <Link to={encodeURIComponent(employeeNo)}>Claim history</Link>
        </section>
      )}
      <p><Link to="approvals">Mileage approvals</Link></p>
    </section>
  )
}

function Approvals() {
  const [claims, setClaims] = useState<MileageClaim[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getPendingMileageClaims()
      .then((pending) => {
        if (active) setClaims(pending)
      })
      .catch((cause: unknown) => {
        if (active) setError(errorMessage(cause))
      })
    return () => { active = false }
  }, [])

  async function decide(id: number, decision: 'approve' | 'reject') {
    setError('')
    try {
      const updated = decision === 'approve'
        ? await approveMileageClaim(id)
        : await rejectMileageClaim(id)
      setClaims((current) => current.map((claim) => claim.id === id ? updated : claim))
    } catch (cause) {
      setError(errorMessage(cause))
    }
  }

  return (
    <section>
      <h1>Mileage approvals</h1>
      {error && <p role="alert">{error}</p>}
      {claims.length === 0
        ? <p>No pending mileage claims.</p>
        : (
          <ul>
            {claims.map((claim) => (
              <li key={claim.id}>
                <p>
                  {claim.employeeNo} · {claim.journeyDate} · {claim.distance} {claim.distanceUnit}
                  · {claim.amount} {claim.currency} · {claim.purpose}
                </p>
                <p>Status: {claim.status}</p>
                {claim.status === 'PENDING' && (
                  <>
                    <button onClick={() => void decide(claim.id, 'approve')}>Approve</button>
                    <button onClick={() => void decide(claim.id, 'reject')}>Reject</button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      <Link to="../">Mileage claims</Link>
    </section>
  )
}

function ClaimHistory() {
  const { employeeNo = '' } = useParams()
  const [history, setHistory] = useState<MileageHistory | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getMileageHistory(employeeNo)
      .then((result) => {
        if (active) setHistory(result)
      })
      .catch((cause: unknown) => {
        if (active) setError(errorMessage(cause))
      })
    return () => { active = false }
  }, [employeeNo])

  return (
    <section>
      <h1>Mileage claim history: {employeeNo}</h1>
      {error && <p role="alert">{error}</p>}
      {history && (
        <>
          <p>Journey dates: {history.from} to {history.to}</p>
          <table>
            <thead>
              <tr>
                <th>Journey date</th>
                <th>Distance</th>
                <th>Vehicle</th>
                <th>Amount</th>
                <th>Paid period</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {history.claims.map((claim) => (
                <tr key={claim.id}>
                  <td>{claim.journeyDate}</td>
                  <td>{claim.distance} {claim.distanceUnit}</td>
                  <td>{claim.vehicleRegistration ?? '—'}</td>
                  <td>{claim.amount} {claim.currency}</td>
                  <td>{claim.paidPeriod}</td>
                  <td>{claim.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <Link to="../">Mileage claims</Link>
    </section>
  )
}

export default function Mileage() {
  return (
    <Routes>
      <Route index element={<ClaimEntry />} />
      <Route path="approvals" element={<Approvals />} />
      <Route path=":employeeNo" element={<ClaimHistory />} />
    </Routes>
  )
}
