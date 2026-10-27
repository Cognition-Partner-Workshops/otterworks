import { useState, type FormEvent } from 'react'
import { Route, Routes, useNavigate } from 'react-router'
import AssignmentWizard from './request'
import EmployeeCar from './employee-car'

function AssignmentHome() {
  const navigate = useNavigate()
  const [employeeNo, setEmployeeNo] = useState('')
  const [currentCarEmployeeNo, setCurrentCarEmployeeNo] = useState('')

  function openRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (employeeNo.trim()) {
      navigate(`/assignment/request?employee=${encodeURIComponent(employeeNo.trim())}`)
    }
  }

  function openCurrentCar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (currentCarEmployeeNo.trim()) {
      navigate(`/assignment/${encodeURIComponent(currentCarEmployeeNo.trim())}`)
    }
  }

  return (
    <section>
      <h1>Assignment</h1>
      <form aria-label="Car request" onSubmit={openRequest}>
        <label>
          Employee number
          <input value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} />
        </label>
        <button type="submit">Request a car</button>
      </form>
      <form aria-label="Current car" onSubmit={openCurrentCar}>
        <label>
          Employee number for current car
          <input value={currentCarEmployeeNo} onChange={(event) => setCurrentCarEmployeeNo(event.target.value)} />
        </label>
        <button type="submit">View current car</button>
      </form>
    </section>
  )
}

export default function Assignment() {
  return (
    <Routes>
      <Route index element={<AssignmentHome />} />
      <Route path="request" element={<AssignmentWizard />} />
      <Route path=":employeeNo" element={<EmployeeCar />} />
    </Routes>
  )
}
