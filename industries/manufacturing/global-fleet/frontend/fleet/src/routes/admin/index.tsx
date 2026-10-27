import { Navigate, Route, Routes } from 'react-router'
import ReconciliationReport from './reconciliation'

export default function Admin() {
  return (
    <Routes>
      <Route index element={<Navigate to="reconciliation" replace />} />
      <Route path="reconciliation" element={<ReconciliationReport />} />
    </Routes>
  )
}
