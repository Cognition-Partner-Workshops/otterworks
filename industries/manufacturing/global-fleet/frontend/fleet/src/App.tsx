import { Component, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router'
import { client, type ProfileResponse } from './api/client'
import { ErrorAlert, Loading, errorText } from './components/status'
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

class RouteErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return <ErrorAlert>Something went wrong. Use Home to start again.</ErrorAlert>
    }
    return this.props.children
  }
}

function ProfileBanner() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    client.getProfile().then((result) => {
      if (active) setProfile(result)
    }).catch((cause: unknown) => {
      if (active) setError(errorText(cause, 'Could not load profile'))
    })
    return () => { active = false }
  }, [])

  if (error) return <ErrorAlert>Profile unavailable: {error}</ErrorAlert>
  if (!profile) return <Loading>Loading profile…</Loading>
  return (
    <p>
      Profile: {profile.sourceApp} · {profile.currency} · distances in {profile.distanceUnit === 'KM' ? 'km' : 'miles'}
    </p>
  )
}

export function FleetRoutes({ showProfile = false }: { showProfile?: boolean }) {
  return (
    <>
      {showProfile && <ProfileBanner />}
      <nav aria-label="Fleet functions">
        <NavLink to="/">Home</NavLink>
        {routes.map(({ path, label }) => (
          <NavLink key={path} to={path}>{label}</NavLink>
        ))}
      </nav>
      <RouteErrorBoundary>
        <Routes>
          <Route path="/" element={<Home />} />
          {routes.map(({ path, component: RouteComponent }) => (
            <Route key={path} path={`${path}/*`} element={<RouteComponent />} />
          ))}
        </Routes>
      </RouteErrorBoundary>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <FleetRoutes showProfile />
    </BrowserRouter>
  )
}
