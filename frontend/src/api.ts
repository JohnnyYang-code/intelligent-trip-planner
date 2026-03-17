import type {
  HealthResponse,
  ItineraryResponse,
  NaturalLanguageTripRequest,
  StructuredTripRequest,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function planTripStructured(
  payload: StructuredTripRequest,
): Promise<ItineraryResponse> {
  return request<ItineraryResponse>('/trips/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function planTripFromText(
  payload: NaturalLanguageTripRequest,
): Promise<ItineraryResponse> {
  return request<ItineraryResponse>('/trips/plan-from-text', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
