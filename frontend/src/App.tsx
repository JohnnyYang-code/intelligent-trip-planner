import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { getHealth, planTripFromText, planTripStructured } from './api'
import type {
  HealthResponse,
  ItineraryResponse,
  POICategory,
  StructuredTripRequest,
} from './types'

type InputMode = 'structured' | 'natural'

const categoryOptions: { value: POICategory; label: string }[] = [
  { value: 'history_culture', label: 'History & Culture' },
  { value: 'nature_scenery', label: 'Nature & Scenery' },
  { value: 'food_dining', label: 'Food & Dining' },
  { value: 'shopping', label: 'Shopping' },
  { value: 'art_museum', label: 'Art & Museum' },
  { value: 'entertainment', label: 'Entertainment' },
  { value: 'local_life', label: 'Local Life' },
]

const structuredExample: StructuredTripRequest = {
  destination: 'brisbane',
  duration_days: 3,
  budget_level: 'mid_range',
  travel_pace: 'moderate',
  preferred_categories: ['food_dining', 'local_life'],
  free_text_preferences:
    'I prefer walkable local neighborhoods, relaxed meal stops, and less crowded places.',
}

const naturalExample =
  "I'd like to spend three days in Brisbane, focusing mainly on food, local neighborhoods, and a relaxed pace."

function App() {
  const [mode, setMode] = useState<InputMode>('structured')
  const [structuredForm, setStructuredForm] =
    useState<StructuredTripRequest>(structuredExample)
  const [rawText, setRawText] = useState(naturalExample)
  const [result, setResult] = useState<ItineraryResponse | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [healthLoading, setHealthLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadHealth = async () => {
      try {
        const response = await getHealth()
        setHealth(response)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load health status.'
        setError(message)
      } finally {
        setHealthLoading(false)
      }
    }

    void loadHealth()
  }, [])

  const providerEntries = useMemo(() => {
    if (!health) return []
    return Object.entries(health.providers)
  }, [health])

  const handleStructuredChange = <K extends keyof StructuredTripRequest>(
    key: K,
    value: StructuredTripRequest[K],
  ) => {
    setStructuredForm((current) => ({ ...current, [key]: value }))
  }

  const handleCategoryToggle = (category: POICategory) => {
    const current = structuredForm.preferred_categories ?? []
    const next = current.includes(category)
      ? current.filter((item) => item !== category)
      : [...current, category]

    handleStructuredChange('preferred_categories', next)
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response =
        mode === 'structured'
          ? await planTripStructured({
              ...structuredForm,
              preferred_categories:
                structuredForm.preferred_categories?.length
                  ? structuredForm.preferred_categories
                  : undefined,
              free_text_preferences: structuredForm.free_text_preferences?.trim() || undefined,
            })
          : await planTripFromText({ raw_text: rawText.trim() })

      setResult(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate itinerary.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const canSubmit =
    mode === 'structured'
      ? structuredForm.destination.trim().length > 0 && structuredForm.duration_days >= 1
      : rawText.trim().length >= 10

  return (
    <div className="app-shell">
      <header className="hero-panel">
        <div>
          <p className="eyebrow">Thesis Demo Frontend</p>
          <h1>Intelligent Trip Planning Assistant</h1>
          <p className="hero-copy">
            A lightweight interface for demonstrating a hybrid trip planning system:
            deterministic itinerary generation with LLM-based explanation and natural-language
            input parsing.
          </p>
        </div>
        <div className="health-card">
          <div className="health-header">
            <h2>Backend Health</h2>
            <span className={`status-pill ${healthLoading ? 'muted' : 'ok'}`}>
              {healthLoading ? 'Checking…' : health?.status ?? 'Unavailable'}
            </span>
          </div>
          <div className="provider-grid">
            {providerEntries.map(([key, provider]) => (
              <div key={key} className="provider-row">
                <span className="provider-name">{key}</span>
                <span className={`provider-state ${provider.available ? 'ok' : 'down'}`}>
                  {provider.mode}
                </span>
              </div>
            ))}
            {!providerEntries.length && !healthLoading && (
              <p className="muted-text">Health endpoint unavailable.</p>
            )}
          </div>
        </div>
      </header>

      <main className="main-grid">
        <section className="panel input-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Input</p>
              <h2>Plan a trip</h2>
            </div>
            <div className="mode-toggle" role="tablist" aria-label="Input modes">
              <button
                className={mode === 'structured' ? 'active' : ''}
                onClick={() => setMode('structured')}
              >
                Structured
              </button>
              <button
                className={mode === 'natural' ? 'active' : ''}
                onClick={() => setMode('natural')}
              >
                Natural language
              </button>
            </div>
          </div>

          {mode === 'structured' ? (
            <div className="form-stack">
              <label>
                Destination
                <input
                  value={structuredForm.destination}
                  onChange={(event) => handleStructuredChange('destination', event.target.value)}
                  placeholder="e.g. brisbane"
                />
              </label>

              <div className="two-column-grid">
                <label>
                  Duration (days)
                  <input
                    type="number"
                    min={1}
                    max={14}
                    value={structuredForm.duration_days}
                    onChange={(event) =>
                      handleStructuredChange('duration_days', Number(event.target.value) || 1)
                    }
                  />
                </label>

                <label>
                  Budget level
                  <select
                    value={structuredForm.budget_level}
                    onChange={(event) =>
                      handleStructuredChange('budget_level', event.target.value as StructuredTripRequest['budget_level'])
                    }
                  >
                    <option value="budget">Budget</option>
                    <option value="mid_range">Mid-range</option>
                    <option value="luxury">Luxury</option>
                  </select>
                </label>
              </div>

              <label>
                Travel pace
                <select
                  value={structuredForm.travel_pace}
                  onChange={(event) =>
                    handleStructuredChange('travel_pace', event.target.value as StructuredTripRequest['travel_pace'])
                  }
                >
                  <option value="relaxed">Relaxed</option>
                  <option value="moderate">Moderate</option>
                  <option value="intensive">Intensive</option>
                </select>
              </label>

              <div>
                <span className="field-label">Preferred categories</span>
                <div className="chip-grid">
                  {categoryOptions.map((category) => {
                    const selected = structuredForm.preferred_categories?.includes(category.value)
                    return (
                      <button
                        key={category.value}
                        type="button"
                        className={`chip ${selected ? 'selected' : ''}`}
                        onClick={() => handleCategoryToggle(category.value)}
                      >
                        {category.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              <label>
                Free-text preferences
                <textarea
                  rows={5}
                  value={structuredForm.free_text_preferences ?? ''}
                  onChange={(event) =>
                    handleStructuredChange('free_text_preferences', event.target.value)
                  }
                  placeholder="Optional: mention soft preferences like food, crowd tolerance, walking preference, or atmosphere."
                />
              </label>
            </div>
          ) : (
            <div className="form-stack">
              <label>
                Trip description
                <textarea
                  rows={10}
                  value={rawText}
                  onChange={(event) => setRawText(event.target.value)}
                  placeholder="I'd like to spend three days in Brisbane, focusing mainly on food."
                />
              </label>
              <p className="muted-text">
                The backend will parse this into structured fields, then run the same itinerary
                planning pipeline.
              </p>
            </div>
          )}

          <div className="action-row">
            <button className="secondary" onClick={() => {
              setStructuredForm(structuredExample)
              setRawText(naturalExample)
            }}>
              Fill example
            </button>
            <button className="secondary" onClick={() => {
              setStructuredForm({
                destination: '',
                duration_days: 3,
                budget_level: 'mid_range',
                travel_pace: 'moderate',
                preferred_categories: [],
                free_text_preferences: '',
              })
              setRawText('')
              setResult(null)
              setError(null)
            }}>
              Reset
            </button>
            <button className="primary" disabled={!canSubmit || loading} onClick={handleSubmit}>
              {loading ? 'Generating…' : 'Generate itinerary'}
            </button>
          </div>
        </section>

        <section className="panel result-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Output</p>
              <h2>Itinerary result</h2>
            </div>
          </div>

          {error && <div className="message error">{error}</div>}
          {loading && <div className="message loading">Calling backend and assembling itinerary…</div>}

          {!loading && !result && !error && (
            <div className="empty-state">
              <h3>Ready for demo</h3>
              <p>
                Submit either a structured request or a natural-language description to display
                the generated itinerary here.
              </p>
            </div>
          )}

          {result && (
            <div className="result-stack">
              <div className="summary-card">
                <div className="summary-topline">
                  <div>
                    <p className="eyebrow">Destination</p>
                    <h3>{result.destination}</h3>
                  </div>
                  <div className="summary-metrics">
                    <div>
                      <span>Days</span>
                      <strong>{result.duration_days}</strong>
                    </div>
                    <div>
                      <span>Estimated cost</span>
                      <strong>¥{Math.round(result.total_estimated_cost_cny)}</strong>
                    </div>
                  </div>
                </div>

                <div className="summary-block">
                  <h4>Persona summary</h4>
                  <p>{result.persona_summary}</p>
                </div>

                {result.overview && (
                  <div className="summary-block">
                    <h4>Overview</h4>
                    <p>{result.overview}</p>
                  </div>
                )}

                {result.planning_notes.length > 0 && (
                  <div className="summary-block">
                    <h4>Planning notes</h4>
                    <ul>
                      {result.planning_notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="meta-text">
                  Request ID: {result.request_id} · Generated at{' '}
                  {new Date(result.generated_at).toLocaleString()}
                </p>
              </div>

              {result.days.map((day) => (
                <article key={day.day_number} className="day-card">
                  <div className="day-header">
                    <div>
                      <p className="eyebrow">{day.date_label}</p>
                      <h3>{day.theme || `Day ${day.day_number}`}</h3>
                    </div>
                    {day.weather && (
                      <div className="weather-badge">
                        <strong>{day.weather.condition}</strong>
                        <span>
                          {Math.round(day.weather.temp_low_c)}–{Math.round(day.weather.temp_high_c)}°C
                        </span>
                      </div>
                    )}
                  </div>

                  {day.weather?.travel_advisory && (
                    <p className="weather-note">{day.weather.travel_advisory}</p>
                  )}

                  {day.narrative && <p className="narrative">{day.narrative}</p>}

                  <div className="poi-list">
                    {day.pois.map((scheduledPoi) => (
                      <div key={`${day.day_number}-${scheduledPoi.poi.id}`} className="poi-card">
                        <div className="poi-time">
                          <span>{scheduledPoi.suggested_start_time}</span>
                          <small>{scheduledPoi.suggested_duration_hours}h</small>
                        </div>
                        <div className="poi-content">
                          <div className="poi-heading">
                            <h4>{scheduledPoi.poi.name}</h4>
                            <span className="category-tag">
                              {scheduledPoi.poi.category.replaceAll('_', ' ')}
                            </span>
                          </div>
                          <p className="poi-meta">
                            {scheduledPoi.poi.district} · ¥{Math.round(scheduledPoi.poi.avg_cost_cny)}
                            {scheduledPoi.poi.opening_hours
                              ? ` · ${scheduledPoi.poi.opening_hours}`
                              : ''}
                          </p>
                          {scheduledPoi.recommendation_reason && (
                            <p className="poi-reason">{scheduledPoi.recommendation_reason}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
