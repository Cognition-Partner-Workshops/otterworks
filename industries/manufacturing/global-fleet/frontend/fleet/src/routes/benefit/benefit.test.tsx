import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FleetRoutes } from '../../App'

const inquiry = {
  employeeNo: 'E123',
  period: '202610',
  status: 'CLOSED' as const,
  lines: [{
    registration: 'HH-VS 7629',
    from: '2026-10-27',
    to: '2026-10-31',
    days: 5,
    monthlyBenefit: 654.43,
    benefit: 105.55,
  }],
  carDays: 5,
  taxableBenefit: 105.55,
  distance: 0,
  mileageAmount: 0,
  leaverFlag: null,
  currency: 'EUR',
}

describe('benefit routes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GF27_inquiryShowsRunFigure', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => inquiry,
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/benefit']}><FleetRoutes /></MemoryRouter>)

    fireEvent.change(screen.getByLabelText('Employee number'), { target: { value: 'E123' } })
    fireEvent.change(screen.getByLabelText('Period'), { target: { value: '2026-10' } })
    fireEvent.click(screen.getByRole('button', { name: 'View benefit' }))

    expect(await screen.findByText('Taxable benefit: 105.55 EUR')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/benefit/employees/E123?period=202610')
    expect(screen.getByText('HH-VS 7629')).toBeInTheDocument()
    expect(screen.getByText('2026-10-27')).toBeInTheDocument()
    expect(screen.getByText('2026-10-31')).toBeInTheDocument()
  })

  it('GF27_statementShowsProfileAndCalculation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...inquiry,
        firstName: 'Priya',
        lastName: 'Raman',
        fullName: 'Priya Raman',
        commuteDistance: 33,
        ruleText: '1.00% list price plus commute',
      }),
    }))
    render(<MemoryRouter initialEntries={['/benefit']}><FleetRoutes /></MemoryRouter>)

    fireEvent.click(screen.getByRole('button', { name: 'Statement' }))
    fireEvent.change(screen.getByLabelText('Employee number'), { target: { value: 'E123' } })
    fireEvent.change(screen.getByLabelText('Period'), { target: { value: '2026-10' } })
    fireEvent.click(screen.getByRole('button', { name: 'View statement' }))

    expect(await screen.findByRole('heading', { name: 'Priya Raman' })).toBeInTheDocument()
    expect(screen.getByText('1.00% list price plus commute')).toBeInTheDocument()
    expect(screen.getByText('Taxable benefit: 105.55 EUR')).toBeInTheDocument()
  })

  it('GF26_periodsCanBeOpenedAndClosed', async () => {
    const open = {
      period: '202610',
      startDate: '2026-10-01',
      endDate: '2026-10-31',
      status: 'OPEN',
      mileageRate: 0.305,
      recordCount: null,
      totalTaxable: null,
      totalMileage: null,
    }
    const closed = { ...open, status: 'CLOSED', recordCount: 1, totalTaxable: 105.55, totalMileage: 0 }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [open] })
      .mockResolvedValueOnce({ ok: true, json: async () => closed })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/benefit']}><FleetRoutes /></MemoryRouter>)

    fireEvent.click(screen.getByRole('button', { name: 'Periods' }))
    expect(await screen.findByText('202610')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close period' }))
    expect(await screen.findByText('CLOSED')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/v1/benefit/periods/202610/close', {
      method: 'POST',
    })
  })
})
