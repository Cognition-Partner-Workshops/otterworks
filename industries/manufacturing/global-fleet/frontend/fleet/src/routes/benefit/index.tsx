import { useEffect, useState, type FormEvent } from 'react'
import {
  client,
  type BenefitInquiry,
  type BenefitPeriod,
  type BenefitStatement,
} from '../../api/client'

type View = 'inquiry' | 'statement' | 'periods'

function periodKey(period: string): string {
  return period.replace('-', '')
}

function currentPeriod(): string {
  return new Date().toISOString().slice(0, 7)
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Benefit request failed'
}

export default function Benefit() {
  const [view, setView] = useState<View>('inquiry')
  const [employeeNo, setEmployeeNo] = useState('')
  const [period, setPeriod] = useState(currentPeriod())
  const [inquiry, setInquiry] = useState<BenefitInquiry | null>(null)
  const [statement, setStatement] = useState<BenefitStatement | null>(null)
  const [periods, setPeriods] = useState<BenefitPeriod[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (view !== 'periods') return
    let active = true
    setError('')
    client.getBenefitPeriods()
      .then((result) => {
        if (active) setPeriods(result)
      })
      .catch((cause: unknown) => {
        if (active) setError(errorText(cause))
      })
    return () => { active = false }
  }, [view])

  async function submitInquiry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await client.getBenefitInquiry(employeeNo, periodKey(period))
      setInquiry(result)
    } catch (cause) {
      setError(errorText(cause))
    } finally {
      setLoading(false)
    }
  }

  async function submitStatement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await client.getBenefitStatement(employeeNo, periodKey(period))
      setStatement(result)
    } catch (cause) {
      setError(errorText(cause))
    } finally {
      setLoading(false)
    }
  }

  async function openPeriod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      const opened = await client.openBenefitPeriod(periodKey(period))
      setPeriods((current) => [opened, ...current.filter((item) => item.period !== opened.period)])
    } catch (cause) {
      setError(errorText(cause))
    }
  }

  async function closePeriod(month: string) {
    setError('')
    try {
      const closed = await client.closeBenefitPeriod(month)
      setPeriods((current) => current.map((item) => item.period === closed.period ? closed : item))
    } catch (cause) {
      setError(errorText(cause))
    }
  }

  return (
    <section>
      <h1>Benefit</h1>
      <nav aria-label="Benefit functions">
        <button type="button" onClick={() => setView('inquiry')}>Inquiry</button>
        <button type="button" onClick={() => setView('statement')}>Statement</button>
        <button type="button" onClick={() => setView('periods')}>Periods</button>
      </nav>
      {error && <p role="alert">{error}</p>}

      {view === 'inquiry' && (
        <section>
          <h2>Benefit inquiry</h2>
          <form onSubmit={submitInquiry}>
            <label>
              Employee number
              <input required value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} />
            </label>
            <label>
              Period
              <input required type="month" value={period} onChange={(event) => setPeriod(event.target.value)} />
            </label>
            <button type="submit" disabled={loading}>View benefit</button>
          </form>
          {inquiry && <InquiryResult result={inquiry} />}
        </section>
      )}

      {view === 'statement' && (
        <section>
          <h2>Benefit statement</h2>
          <form onSubmit={submitStatement}>
            <label>
              Employee number
              <input required value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} />
            </label>
            <label>
              Period
              <input required type="month" value={period} onChange={(event) => setPeriod(event.target.value)} />
            </label>
            <button type="submit" disabled={loading}>View statement</button>
          </form>
          {statement && (
            <section aria-label="Benefit statement details">
              <h3>{statement.fullName}</h3>
              <p>{statement.period} · {statement.status} · Commute distance: {statement.commuteDistance}</p>
              <p>{statement.ruleText}</p>
              <InquiryResult result={statement} />
            </section>
          )}
        </section>
      )}

      {view === 'periods' && (
        <section>
          <h2>Benefit periods</h2>
          <form onSubmit={openPeriod}>
            <label>
              Period to open
              <input required type="month" value={period} onChange={(event) => setPeriod(event.target.value)} />
            </label>
            <button type="submit">Open period</button>
          </form>
          {periods.length === 0
            ? <p>No benefit periods.</p>
            : (
              <table>
                <thead>
                  <tr><th>Period</th><th>Status</th><th>Records</th><th>Taxable total</th><th>Mileage total</th><th /></tr>
                </thead>
                <tbody>
                  {periods.map((item) => (
                    <tr key={item.period}>
                      <td>{item.period}</td>
                      <td>{item.status}</td>
                      <td>{item.recordCount ?? '—'}</td>
                      <td>{item.totalTaxable ?? '—'}</td>
                      <td>{item.totalMileage ?? '—'}</td>
                      <td>
                        {item.status === 'OPEN' && (
                          <button type="button" onClick={() => void closePeriod(item.period)}>Close period</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </section>
      )}
    </section>
  )
}

function InquiryResult({ result }: { result: BenefitInquiry }) {
  return (
    <section aria-label="Benefit calculation">
      <p>{result.employeeNo} · {result.period} · {result.status}</p>
      <table>
        <thead>
          <tr><th>Registration</th><th>From</th><th>To</th><th>Days</th><th>Monthly benefit</th><th>Benefit</th></tr>
        </thead>
        <tbody>
          {result.lines.map((line, index) => (
            <tr key={`${line.registration}-${line.from}-${index}`}>
              <td>{line.registration || '—'}</td>
              <td>{line.from}</td>
              <td>{line.to}</td>
              <td>{line.days}</td>
              <td>{line.monthlyBenefit} {result.currency}</td>
              <td>{line.benefit} {result.currency}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>Car days: {result.carDays}</p>
      <p>Taxable benefit: {result.taxableBenefit} {result.currency}</p>
      <p>Mileage: {result.distance} · Reimbursement: {result.mileageAmount} {result.currency}</p>
      {result.leaverFlag && <p>Leaver flag: {result.leaverFlag}</p>}
    </section>
  )
}
