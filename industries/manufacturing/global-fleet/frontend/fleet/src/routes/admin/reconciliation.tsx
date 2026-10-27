import { useMemo, useState } from 'react'
import reconciliationReport from './reconciliation-report.json'
import './reconciliation.css'

type TestResult = {
  name: string
  layer: string
  proves: string
  results: Record<string, string>
}

type ReconciliationRule = {
  id: string
  title: string
  verdict: string
  status: string
  decision: {
    status: string
    option: string | null
    decision: string | null
    decided_by: string | null
    decided_on: string | null
    open_items: string[]
  }
  expected_changes: Array<{ scope: string; count: number | null; total?: number | null }>
  tests: TestResult[]
  links: Array<{
    role: string
    pr?: number
    pr_url?: string
    title?: string
    session_url?: string
  }>
}

type Report = {
  generated_at?: string
  commit?: string
  rules: ReconciliationRule[]
}

const report = reconciliationReport as Report
const columns = [
  'rule_id',
  'title',
  'verdict',
  'status',
  'decision_status',
  'decision_option',
  'decision',
  'decided_by',
  'decided_on',
  'open_items',
  'tests',
  'latest_results',
  'pr_urls',
  'session_urls',
]

function latestResults(rule: ReconciliationRule) {
  return rule.tests.flatMap((test) =>
    Object.entries(test.results)
      .filter(([, result]) => result !== 'not-applicable')
      .map(([source, result]) => `${test.name} (${source}: ${result})`),
  )
}

function csvCell(value: string) {
  const safe = /^[=+\-@]/.test(value) ? `'${value}` : value
  return /[",\r\n]/.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe
}

export function buildReconciliationCsv(rules: ReconciliationRule[]) {
  const rows = rules.map((rule) => [
    rule.id,
    rule.title,
    rule.verdict,
    rule.status,
    rule.decision.status,
    rule.decision.option ?? '',
    rule.decision.decision ?? '',
    rule.decision.decided_by ?? '',
    rule.decision.decided_on ?? '',
    rule.decision.open_items.join(' | '),
    rule.tests.map((test) => `${test.name} (${test.layer})`).join(' | '),
    latestResults(rule).join(' | '),
    rule.links.map((link) => link.pr_url).filter(Boolean).join(' | '),
    rule.links.map((link) => link.session_url).filter(Boolean).join(' | '),
  ])
  return [columns, ...rows].map((row) => row.map((cell) => csvCell(String(cell))).join(',')).join('\r\n')
}

function downloadCsv(rules: ReconciliationRule[]) {
  const blob = new Blob([buildReconciliationCsv(rules)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'gf-reconciliation.csv'
  link.click()
  URL.revokeObjectURL(url)
}

function RuleStatus({ status }: { status: string }) {
  return <span className={`status-badge status-${status}`}>{status}</span>
}

export default function ReconciliationReport() {
  const [statusFilter, setStatusFilter] = useState('all')
  const rules = report.rules
  const visibleRules = useMemo(
    () => rules.filter((rule) => statusFilter === 'all' || rule.status === statusFilter),
    [rules, statusFilter],
  )
  const statusCounts = rules.reduce<Record<string, number>>((counts, rule) => {
    counts[rule.status] += 1
    return counts
  }, { covered: 0, partial: 0, failed: 0, missing: 0 })
  const verdictCounts = rules.reduce<Record<string, number>>((counts, rule) => {
    counts[rule.verdict] = (counts[rule.verdict] ?? 0) + 1
    return counts
  }, {})

  return (
    <main className="reconciliation-report">
      <h1>Reconciliation report</h1>
      <p className="report-meta">
        Latest test run {report.generated_at ?? 'unknown'} at commit {report.commit?.slice(0, 7) ?? 'unknown'}
      </p>
      <section className="report-summary" aria-label="Report summary">
        <div className="report-summary-card">
          <h2>Summary by status</h2>
          <ul className="report-counts">
            {Object.entries(statusCounts).map(([status, count]) => (
              <li key={status}><span className={`status-badge status-${status}`}>{status}</span>: {count}</li>
            ))}
          </ul>
        </div>
        <div className="report-summary-card">
          <h2>Summary by verdict</h2>
          <ul className="report-counts">
            {Object.entries(verdictCounts).map(([verdict, count]) => (
              <li key={verdict}>{verdict}: {count}</li>
            ))}
          </ul>
        </div>
      </section>
      <div className="report-toolbar">
        <div className="report-filter">
          <label htmlFor="status-filter">Filter by status</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            {['covered', 'partial', 'failed', 'missing'].map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </div>
        <button className="export-button" type="button" onClick={() => downloadCsv(visibleRules)}>Export CSV</button>
      </div>
      <div className="report-table-wrap">
        <table className="report-table">
          <thead>
            <tr>
              <th scope="col">Rule</th>
              <th scope="col">Verdict</th>
              <th scope="col">Status</th>
              <th scope="col">Decision</th>
              <th scope="col">Tests</th>
              <th scope="col">Latest result</th>
              <th scope="col">Links</th>
            </tr>
          </thead>
          <tbody>
            {visibleRules.length === 0 && (
              <tr>
                <td colSpan={7}>No rules have status {statusFilter}.</td>
              </tr>
            )}
            {visibleRules.map((rule) => (
              <tr key={rule.id}>
                <th scope="row">
                  <strong>{rule.id}</strong>
                  <br />
                  {rule.title}
                </th>
                <td>{rule.verdict}</td>
                <td><RuleStatus status={rule.status} /></td>
                <td>
                  <strong>{rule.decision.status}</strong>
                  {rule.decision.option && <div>Option {rule.decision.option}</div>}
                  {rule.decision.decision && <div>{rule.decision.decision}</div>}
                  <div>{rule.decision.decided_by ?? 'Unknown'} / {rule.decision.decided_on ?? 'Undated'}</div>
                  <div>Open items: {rule.decision.open_items.length ? rule.decision.open_items.join('; ') : 'None'}</div>
                </td>
                <td>
                  <ul>
                    {rule.tests.map((test) => (
                      <li key={`${test.layer}:${test.name}`}>{test.name} <small>({test.layer})</small></li>
                    ))}
                  </ul>
                </td>
                <td>
                  <ul>
                    {rule.tests.map((test) => (
                      <li key={`${test.layer}:${test.name}`}>
                        {Object.entries(test.results)
                          .filter(([, result]) => result !== 'not-applicable')
                          .map(([source, result]) => `${source}: ${result}`)
                          .join(' · ') || 'No applicable result'}
                      </li>
                    ))}
                  </ul>
                </td>
                <td>
                  <ul>
                    {rule.links.map((link, index) => (
                      <li key={`${link.role}:${link.pr ?? index}`}>
                        {link.pr_url && (
                          <a href={link.pr_url} target="_blank" rel="noopener noreferrer">
                            PR #{link.pr} {link.title}
                          </a>
                        )}
                        {link.session_url && (
                          <>
                            {link.pr_url && ' · '}
                            <a href={link.session_url} target="_blank" rel="noopener noreferrer">session</a>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
