import { Route, Routes } from 'react-router'
import EmployeeInquiry from './inquiry'
import EmployeeSearch from './search'

export default function Eligibility() {
  return (
    <>
      <h1>Eligibility</h1>
      <Routes>
        <Route index element={<EmployeeSearch />} />
        <Route path="employees/:employeeNo" element={<EmployeeInquiry />} />
      </Routes>
    </>
  )
}
