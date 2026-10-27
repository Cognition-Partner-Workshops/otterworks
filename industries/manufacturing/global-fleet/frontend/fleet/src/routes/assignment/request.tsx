import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import {
  ApiFailure,
  client,
  type CarRequestDraft,
  type CarRequestStep,
  type DraftUpdateRequest,
  type NewVehicleInput,
  type PoolVehicle,
  type VehicleRulesResponse,
} from '../../api/client'

type DraftState = Omit<CarRequestDraft, 'draftId'> & { draftId: string | null }

function blankVehicle(): NewVehicleInput {
  return {
    plate: '',
    make: '',
    model: '',
    listPrice: null,
    co2: null,
    fuel: 'D',
    benefitPercent: null,
  }
}

function vehicleForm(vehicle: CarRequestDraft['newVehicle']): NewVehicleInput {
  return {
    ...blankVehicle(),
    ...vehicle,
    plate: vehicle?.plate ?? '',
    make: vehicle?.make ?? '',
    model: vehicle?.model ?? '',
    fuel: vehicle?.fuel ?? 'D',
  }
}

function freshDraft(employeeNo: string, pool: PoolVehicle[]): DraftState {
  return {
    draftId: null,
    employeeNo,
    step: 'EMPLOYEE',
    vehicleChoice: null,
    poolVehicleId: null,
    newVehicle: null,
    reason: 'NC',
    startDate: null,
    eligibility: { allowed: true, reason: null, employeeNo, employmentId: null },
    vehicleAvailable: null,
    pool,
  }
}

export default function AssignmentWizard() {
  const [searchParams] = useSearchParams()
  const employeeNo = searchParams.get('employee')?.trim() ?? ''
  const navigate = useNavigate()
  const [draft, setDraft] = useState<DraftState | null>(null)
  const [rules, setRules] = useState<VehicleRulesResponse | null>(null)
  const [choice, setChoice] = useState<'POOL' | 'NEW'>('POOL')
  const [poolVehicleId, setPoolVehicleId] = useState('')
  const [newVehicle, setNewVehicle] = useState<NewVehicleInput>(blankVehicle())
  const [reason, setReason] = useState<'NC' | 'RP' | 'PL'>('NC')
  const [startDate, setStartDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [confirmationDirty, setConfirmationDirty] = useState(false)

  useEffect(() => {
    let active = true
    if (!employeeNo) {
      setError('Employee number is required')
      setLoading(false)
      return () => { active = false }
    }
    void Promise.all([
      client.getDraft(employeeNo).catch((cause: unknown) => {
        if (cause instanceof ApiFailure && cause.status === 404) return null
        throw cause
      }),
      client.getVehicleRules(),
      client.getPool(),
    ]).then(([saved, vehicleRules, pool]) => {
      if (!active) return
      setRules(vehicleRules)
      const initial: DraftState = saved
        ? { ...saved, draftId: saved.draftId, pool }
        : freshDraft(employeeNo, pool)
      setDraft(initial)
      setChoice(saved?.vehicleChoice ?? 'POOL')
      setPoolVehicleId(saved?.poolVehicleId?.toString() ?? '')
      setNewVehicle(vehicleForm(saved?.newVehicle ?? null))
      setReason(saved?.reason ?? 'NC')
      setStartDate(saved?.startDate ?? '')
      setLoading(false)
    }).catch((cause: unknown) => {
      if (!active) return
      setError(cause instanceof Error ? cause.message : 'Could not load car request')
      setLoading(false)
    })
    return () => { active = false }
  }, [employeeNo])

  async function persist(step: CarRequestStep): Promise<CarRequestDraft> {
    const update: DraftUpdateRequest = {
      step,
      vehicleChoice: choice,
      poolVehicleId: choice === 'POOL' && poolVehicleId ? Number(poolVehicleId) : null,
      newVehicle: choice === 'NEW' ? newVehicle : null,
      reason,
      startDate: startDate || null,
    }
    const saved = await client.putDraft(employeeNo, update)
    setDraft({ ...saved, draftId: saved.draftId })
    setChoice(saved.vehicleChoice ?? choice)
    setPoolVehicleId(saved.poolVehicleId?.toString() ?? '')
    setNewVehicle(vehicleForm(saved.newVehicle))
    setReason(saved.reason ?? 'NC')
    setStartDate(saved.startDate ?? '')
    setConfirmationDirty(false)
    return saved
  }

  async function continueToVehicle() {
    setError(null)
    try {
      const saved = await persist('VEHICLE')
      setDraft((current) => current ? { ...current, ...saved, step: 'VEHICLE' } : current)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save employee step')
    }
  }

  async function continueToConfirm() {
    setError(null)
    try {
      const saved = await persist('CONFIRM')
      setDraft((current) => current ? { ...current, ...saved, step: 'CONFIRM' } : current)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save vehicle')
    }
  }

  async function submit() {
    setError(null)
    try {
      const saved = confirmationDirty && draft
        ? await persist('CONFIRM')
        : draft as CarRequestDraft
      const result = await client.submitDraft(employeeNo, saved.draftId)
      navigate(`/assignment/${encodeURIComponent(result.employeeNo)}`)
    } catch (cause) {
      if (cause instanceof ApiFailure && cause.status === 409
          && cause.code === 'CAR_NO_LONGER_AVAILABLE') {
        setDraft((current) => current ? {
          ...current,
          step: 'VEHICLE',
          poolVehicleId: null,
          vehicleAvailable: false,
          pool: cause.payload.pool ?? [],
        } : current)
        setPoolVehicleId('')
        setError('Car no longer available')
        return
      }
      if (cause instanceof ApiFailure && cause.code === 'VEHICLE_NOT_AVAILABLE') {
        const updatedPool = await client.getPool().catch(() => [])
        setDraft((current) => current ? {
          ...current,
          step: 'VEHICLE',
          poolVehicleId: null,
          vehicleAvailable: false,
          pool: updatedPool,
        } : current)
        setPoolVehicleId('')
        setError('Car no longer available')
        return
      }
      setError(cause instanceof Error ? cause.message : 'Could not submit car request')
    }
  }

  async function discard() {
    setError(null)
    try {
      if (draft?.draftId) await client.deleteDraft(employeeNo)
      navigate('/assignment')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not discard draft')
    }
  }

  function updateNewVehicle(field: keyof NewVehicleInput, value: string) {
    setNewVehicle((current) => ({
      ...current,
      [field]: field === 'listPrice' || field === 'co2' || field === 'benefitPercent'
        ? value === '' ? null : Number(value)
        : value,
    }))
  }

  function required(field: string) {
    return rules?.requiredNewVehicleFields.includes(field) ?? true
  }

  if (loading) return <p>Loading car request…</p>
  if (!draft) return <p role="alert">{error ?? 'Could not load car request'}</p>

  return (
    <section>
      <h1>Request a company car</h1>
      <p>Employee: {employeeNo}</p>
      {error && <p role="alert">{error}</p>}
      {draft.step === 'EMPLOYEE' && (
        <div>
          <h2>Employee</h2>
          <p>{draft.eligibility.allowed ? 'Eligible to request a car' : draft.eligibility.reason}</p>
          <button type="button" onClick={() => void continueToVehicle()}>Continue</button>
        </div>
      )}
      {draft.step === 'VEHICLE' && (
        <div>
          <h2>Choose a vehicle</h2>
          <label>
            Vehicle type
            <select value={choice} onChange={(event) => setChoice(event.target.value as 'POOL' | 'NEW')}>
              <option value="POOL">Available pool car</option>
              <option value="NEW">New car</option>
            </select>
          </label>
          {choice === 'POOL' ? (
            <label>
              Pool vehicle
              <select value={poolVehicleId} onChange={(event) => setPoolVehicleId(event.target.value)}>
                <option value="">Select a car</option>
                {draft.pool.map((vehicle) => (
                  <option key={vehicle.id} value={vehicle.id}>
                    {vehicle.registration} — {vehicle.make ?? ''} {vehicle.model ?? ''}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <fieldset>
              <legend>New vehicle details</legend>
              <label>Registration<input required={required('plate')} value={newVehicle.plate} onChange={(event) => updateNewVehicle('plate', event.target.value)} /></label>
              <label>Make<input required={required('make')} value={newVehicle.make} onChange={(event) => updateNewVehicle('make', event.target.value)} /></label>
              <label>Model<input required={required('model')} value={newVehicle.model} onChange={(event) => updateNewVehicle('model', event.target.value)} /></label>
              <label>List price<input required={required('listPrice')} type="number" value={newVehicle.listPrice ?? ''} onChange={(event) => updateNewVehicle('listPrice', event.target.value)} /></label>
              <label>CO₂ g/km<input required={required('co2')} type="number" value={newVehicle.co2 ?? ''} onChange={(event) => updateNewVehicle('co2', event.target.value)} /></label>
              <label>Fuel
                <select required={required('fuel')} value={newVehicle.fuel} onChange={(event) => updateNewVehicle('fuel', event.target.value)}>
                  <option value="D">Diesel</option><option value="P">Petrol</option>
                  <option value="H">Hybrid</option><option value="E">Electric</option>
                </select>
              </label>
              {rules?.requiredNewVehicleFields.includes('benefitPercent') && (
                <label>Benefit percent
                  <input type="number" value={newVehicle.benefitPercent ?? ''}
                    onChange={(event) => updateNewVehicle('benefitPercent', event.target.value)} />
                </label>
              )}
            </fieldset>
          )}
          <button type="button" onClick={() => void continueToConfirm()}>Continue</button>
        </div>
      )}
      {draft.step === 'CONFIRM' && (
        <div>
          <h2>Confirm request</h2>
          <p>Vehicle: {choice === 'POOL'
            ? draft.pool.find((vehicle) => vehicle.id === Number(poolVehicleId))?.registration ?? 'Pool vehicle'
            : newVehicle.plate}</p>
          <label>Reason
            <select value={reason} onChange={(event) => {
              setReason(event.target.value as 'NC' | 'RP' | 'PL')
              setConfirmationDirty(true)
            }}>
              <option value="NC">New car</option><option value="RP">Replacement</option><option value="PL">Pool loan</option>
            </select>
          </label>
          <div>
            <label htmlFor="assignment-start-date">Start date</label>
            <input id="assignment-start-date" type="date" value={startDate}
              aria-describedby="assignment-start-date-hint"
              onChange={(event) => {
                setStartDate(event.target.value)
                setConfirmationDirty(true)
              }} />
            <small id="assignment-start-date-hint">Leave blank to start today</small>
          </div>
          <button type="button" onClick={() => void submit()}>Submit request</button>
        </div>
      )}
      <button type="button" onClick={() => void discard()}>Discard</button>
    </section>
  )
}
