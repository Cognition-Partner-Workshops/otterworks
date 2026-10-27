import { BrowserRouter, NavLink, Route, Routes } from 'react-router'
import Assignment from './routes/assignment'
import Benefit from './routes/benefit'
import Eligibility from './routes/eligibility'
import Home from './routes/home'
import Mileage from './routes/mileage'
import Returns from './routes/returns'

const routes = [
  { path: '/eligibility', label: 'Eligibility', component: Eligibility },
  { path: '/assignment', label: 'Assignment', component: Assignment },
  { path: '/returns', label: 'Returns', component: Returns },
  { path: '/mileage', label: 'Mileage', component: Mileage },
  { path: '/benefit', label: 'Benefit', component: Benefit },
]

export function FleetRoutes() {
  return (
    <>
      <nav aria-label="Fleet functions">
        <NavLink to="/">Home</NavLink>
        {routes.map(({ path, label }) => (
          <NavLink key={path} to={path}>{label}</NavLink>
        ))}
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        {routes.map(({ path, component: Component }) => (
          <Route key={path} path={path} element={<Component />} />
        ))}
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <FleetRoutes />
    </BrowserRouter>
  )
}
