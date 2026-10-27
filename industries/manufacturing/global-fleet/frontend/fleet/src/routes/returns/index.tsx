import { useState, type FormEvent } from 'react'
import { returnsApi, type DistanceUnit, type ReturnCandidate, type ReturnKey, type ReturnView } from './api'

const unitLabel: Record<DistanceUnit, string> = { MILE: 'miles', KM: 'km' }

function message(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback
}

function lookupKey(value: string): ReturnKey {
  const trimmed = value.trim()
  return /^\d+$/.test(trimmed) ? { vehicleId: Number(trimmed) } : { plate: trimmed }
}

export default function Returns() {
  const [search, setSearch] = useState('')
  const [candidate, setCandidate] = useState<ReturnCandidate | null>(null)
  const [returnDate, setReturnDate] = useState('')
  const [odometer, setOdometer] = useState('')
  const [note, setNote] = useState('')
  const [done, setDone] = useState<ReturnView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function find(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setDone(null)
    setCandidate(null)
    if (!search.trim()) {
      setError('Enter a plate or vehicle id')
      return
    }
    setBusy(true)
    try {
      setCandidate(await returnsApi.lookup(lookupKey(search)))
      setReturnDate('')
      setOdometer('')
      setNote('')
    } catch (cause) {
      setError(message(cause, 'Could not look up the car'))
    } finally {
      setBusy(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!candidate) return
    setError(null)
    setBusy(true)
    try {
      const reading = odometer.trim()
      setDone(await returnsApi.submit({
        vehicleId: candidate.vehicleId,
        assignmentId: candidate.assignmentId,
        returnDate: returnDate || null,
        odometer: reading === '' ? null : Number(reading),
        conditionNote: note.trim() || null,
      }))
      setCandidate(null)
    } catch (cause) {
      setError(message(cause, 'Could not record the return'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <h1>Returns</h1>
      <form aria-label="Find car" onSubmit={(event) => { void find(event) }}>
        <label>
          Plate or vehicle id
          <input value={search} onChange={(event) => { setSearch(event.target.value) }} />
        </label>
        <button type="submit" disabled={busy}>Find car</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {done && (
        <p role="status">
          {done.registration} returned on {done.returnDate} at {done.odometer} {unitLabel[done.distanceUnit]};
          the car is back in the pool.
        </p>
      )}
      {candidate && (
        <form aria-label="Return car" onSubmit={(event) => { void submit(event) }}>
          <h2>{candidate.registration} {candidate.make ?? ''} {candidate.model ?? ''}</h2>
          <p>
            Assigned to {candidate.employeeNo}
            {candidate.firstName || candidate.lastName
              ? ` (${[candidate.firstName, candidate.lastName].filter(Boolean).join(' ')})`
              : ''} since {candidate.startDate}
          </p>
          <p>
            {candidate.lastOdometer === null
              ? 'No previous odometer reading'
              : `Last recorded odometer: ${candidate.lastOdometer} ${unitLabel[candidate.distanceUnit]}`}
          </p>
          <label>
            Return date
            <input type="date" min={candidate.startDate} value={returnDate}
              onChange={(event) => { setReturnDate(event.target.value) }} />
          </label>
          <label>
            Odometer ({unitLabel[candidate.distanceUnit]})
            <input type="number" inputMode="numeric" step={1} min={candidate.lastOdometer ?? 0} required
              value={odometer} onChange={(event) => { setOdometer(event.target.value) }} />
          </label>
          <label>
            Condition note
            <textarea maxLength={200} value={note} onChange={(event) => { setNote(event.target.value) }} />
          </label>
          <button type="submit" disabled={busy}>Return car</button>
        </form>
      )}
    </section>
  )
}
