import type { ReactNode } from 'react'
import { ApiFailure } from '../api/client'

export function Loading({ children }: { children: ReactNode }) {
  return <p aria-busy="true">{children}</p>
}

export function ErrorAlert({ children }: { children: ReactNode }) {
  if (!children) return null
  return <p role="alert">{children}</p>
}

export function errorText(cause: unknown, fallback: string): string {
  if (cause instanceof ApiFailure) return cause.message
  if (cause instanceof Error) return cause.message
  return fallback
}
