import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { FleetRoutes } from '../../App'
import reconciliationReport from './reconciliation-report.json'
import { buildReconciliationCsv } from './reconciliation'

describe('admin reconciliation report', () => {
  it('renders every catalog rule with a visible status', () => {
    render(<MemoryRouter initialEntries={['/admin/reconciliation']}><FleetRoutes /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: 'Reconciliation report' })).toBeInTheDocument()
    const rows = within(screen.getByRole('table')).getAllByRole('row')
    expect(rows).toHaveLength(35)
    const summary = within(screen.getByRole('region', { name: 'Report summary' }))
    for (const status of ['partial', 'failed', 'missing']) {
      expect(summary.getByText(status, { exact: true }).parentElement).toHaveTextContent(`${status}: 0`)
    }
    for (const row of rows.slice(1)) {
      expect(within(row).getByText(/^(covered|partial|failed|missing)$/)).toBeInTheDocument()
    }
  })

  it('filters the table by status', () => {
    const chosenStatus = reconciliationReport.rules[0].status
    render(<MemoryRouter initialEntries={['/admin/reconciliation']}><FleetRoutes /></MemoryRouter>)

    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: chosenStatus } })

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows.length).toBeGreaterThan(0)
    expect(rows.every((row) => within(row).getByText(chosenStatus))).toBe(true)
  })

  it('shows an empty-state row when a status has no rules', () => {
    render(<MemoryRouter initialEntries={['/admin/reconciliation']}><FleetRoutes /></MemoryRouter>)

    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'missing' } })

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(1)
    expect(within(rows[0]).getByText('No rules have status missing.')).toBeInTheDocument()
    expect(within(rows[0]).getByRole('cell')).toHaveAttribute('colspan', '7')
  })

  it('builds RFC 4180 CSV with a rule row, quoting and formula neutralization', () => {
    const fullCsv = buildReconciliationCsv(reconciliationReport.rules)
    const lines = fullCsv.split('\r\n')
    expect(lines).toHaveLength(35)
    expect(lines[0]).toBe(
      'rule_id,title,verdict,status,decision_status,decision_option,decision,decided_by,decided_on,open_items,tests,latest_results,pr_urls,session_urls',
    )

    const rule = reconciliationReport.rules[0]
    const specialCsv = buildReconciliationCsv([{
      ...rule,
      title: 'title, with "quotes"\nand a newline',
      decision: { ...rule.decision, decision: '=SUM(A1:A2)' },
    }])
    expect(specialCsv).toContain('"title, with ""quotes""\nand a newline"')
    expect(specialCsv).toContain(",'=SUM(A1:A2),")
  })

  it('shows PR and session links with safe new-tab attributes', () => {
    render(<MemoryRouter initialEntries={['/admin/reconciliation']}><FleetRoutes /></MemoryRouter>)

    const firstRule = reconciliationReport.rules[0]
    const table = screen.getByRole('table')
    const row = within(table).getAllByRole('row')[1]
    expect(within(row).getByText(firstRule.id)).toBeInTheDocument()
    const prLink = within(row).getAllByRole('link', { name: /PR #\d+/ })[0]
    const sessionLink = within(row).getAllByRole('link', { name: 'session' })[0]
    expect(prLink).toHaveAttribute('target', '_blank')
    expect(prLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(sessionLink).toHaveAttribute('target', '_blank')
    expect(sessionLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('navigates to the report from the admin navigation item', () => {
    render(<MemoryRouter initialEntries={['/']}><FleetRoutes /></MemoryRouter>)

    fireEvent.click(screen.getByRole('link', { name: 'Admin' }))

    expect(screen.getByRole('heading', { name: 'Reconciliation report' })).toBeInTheDocument()
  })
})
