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

const categoryOptions: { value: POICategory; label: string; short: string }[] = [
  { value: 'history_culture', label: 'History & Culture', short: 'History' },
  { value: 'nature_scenery', label: 'Nature & Scenery', short: 'Nature' },
  { value: 'food_dining', label: 'Food & Dining', short: 'Food' },
  { value: 'shopping', label: 'Shopping', short: 'Shopping' },
  { value: 'art_museum', label: 'Art & Museum', short: 'Museum' },
  { value: 'entertainment', label: 'Entertainment', short: 'Fun' },
  { value: 'local_life', label: 'Local Life', short: 'Local' },
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

function formatCategory(value: string) {
  return value.replaceAll('_', ' ')
}

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

  const totalPois = useMemo(
    () => result?.days.reduce((sum, day) => sum + day.pois.length, 0) ?? 0,
    [result],
  )

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

  const resetAll = () => {
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
  }

  const fillExample = () => {
    setStructuredForm(structuredExample)
    setRawText(naturalExample)
    setError(null)
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
        <div className="hero-copy-block">
          <p className="eyebrow">Thesis Demo Frontend</p>
          <h1>Intelligent Trip Planning Assistant</h1>
          <p className="hero-copy">
            A lightweight demo interface for a hybrid trip planning system. The structured
            pipeline generates the itinerary; the LLM only supports natural-language parsing and
            explanatory text.
          </p>

          <div className="hero-pills">
            <span>Structured planning</span>
            <span>Natural-language input parsing</span>
            <span>LLM-generated explanation</span>
          </div>
        </div>

        <div className="hero-side-stack">
          <div className="mini-thesis-card">
            <p className="eyebrow">System framing</p>
            <div className="framing-flow">
              <div>
                <strong>Input layer</strong>
                <span>Structured form or raw natural language</span>
              </div>
              <div>
                <strong>Planning core</strong>
                <span>Persona → scoring → allocation → route ordering</span>
              </div>
              <div>
                <strong>Explanation layer</strong>
                <span>Overview, narratives, recommendation reasons</span>
              </div>
            </div>
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

          <div className="input-mode-note">
            {mode === 'structured'
              ? 'Use a compact research-demo form that maps directly to the backend request schema.'
              : 'Enter one sentence; the backend parses it into structured fields before running the same planning pipeline.'}
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
                      handleStructuredChange(
                        'budget_level',
                        event.target.value as StructuredTripRequest['budget_level'],
                      )
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
                    handleStructuredChange(
                      'travel_pace',
                      event.target.value as StructuredTripRequest['travel_pace'],
                    )
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
                  placeholder="Optional: mention crowd tolerance, walking preference, food style, atmosphere, or soft constraints."
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
              <div className="example-callout">
                <strong>Example prompt</strong>
                <p>{naturalExample}</p>
              </div>
            </div>
          )}

          <div className="action-row">
            <button className="secondary" onClick={fillExample}>
              Fill example
            </button>
            <button className="secondary" onClick={resetAll}>
              Reset
            </button>
            <button className="primary" disabled={!canSubmit || loading} onClick={handleSubmit}>
              {loading ? 'Generating…' : 'Generate itinerary'}
            </button>
          </div>
        </section>

        <section className="panel result-panel">
          <div className="section-heading result-heading">
            <div>
              <p className="eyebrow">Output</p>
              <h2>Planner result</h2>
            </div>
            {result && (
              <div className="result-badges">
                <span>{result.duration_days} days</span>
                <span>{totalPois} POIs</span>
                <span>¥{Math.round(result.total_estimated_cost_cny)}</span>
              </div>
            )}
          </div>

          {error && <div className="message error">{error}</div>}
          {loading && (
            <div className="message loading">Calling backend and assembling itinerary…</div>
          )}

          {!loading && !result && !error && (
            <div className="empty-state">
              <h3>Ready for demo</h3>
              <p>
                Submit either a structured request or a natural-language description to display
                the generated itinerary, persona summary, overview, and day-by-day schedule here.
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
                      <span>Total POIs</span>
                      <strong>{totalPois}</strong>
                    </div>
                    <div>
                      <span>Estimated cost</span>
                      <strong>¥{Math.round(result.total_estimated_cost_cny)}</strong>
                    </div>
                  </div>
                </div>

                <div className="summary-grid">
                  <div className="summary-block feature-block">
                    <h4>Planner persona</h4>
                    <p>{result.persona_summary}</p>
                  </div>

                  <div className="summary-block feature-block accent-block">
                    <h4>LLM-generated overview</h4>
                    <p>{result.overview || 'No overview returned for this run.'}</p>
                  </div>
                </div>

                {result.planning_notes.length > 0 && (
                  <div className="summary-block notes-block">
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
                    <div className="day-header-side">
                      <span className="day-poi-count">{day.pois.length} stops</span>
                      {day.weather && (
                        <div className="weather-badge">
                          <strong>{day.weather.condition}</strong>
                          <span>
                            {Math.round(day.weather.temp_low_c)}–
                            {Math.round(day.weather.temp_high_c)}°C
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="day-meta-grid">
                    {day.weather?.travel_advisory && (
                      <div className="day-meta-card">
                        <span className="meta-label">Weather advisory</span>
                        <p>{day.weather.travel_advisory}</p>
                      </div>
                    )}
                    {day.narrative && (
                      <div className="day-meta-card narrative-card">
                        <span className="meta-label">Narrative</span>
                        <p>{day.narrative}</p>
                      </div>
                    )}
                  </div>

                  <div className="timeline">
                    {day.pois.map((scheduledPoi, index) => (
                      <div key={`${day.day_number}-${scheduledPoi.poi.id}`} className="timeline-row">
                        <div className="timeline-rail">
                          <div className="timeline-dot" />
                          {index !== day.pois.length - 1 && <div className="timeline-line" />}
                        </div>

                        <div className="poi-card timeline-card">
                          <div className="poi-time-card">
                            <span className="time-main">{scheduledPoi.suggested_start_time}</span>
                            <small>{scheduledPoi.suggested_duration_hours}h</small>
                          </div>

                          <div className="poi-content">
                            <div className="poi-heading">
                              <div>
                                <h4>{scheduledPoi.poi.name}</h4>
                                <p className="poi-subtitle">{scheduledPoi.poi.district}</p>
                              </div>
                              <span className="category-tag">
                                {formatCategory(scheduledPoi.poi.category)}
                              </span>
                            </div>

                            <div className="poi-meta-row">
                              <span>¥{Math.round(scheduledPoi.poi.avg_cost_cny)}</span>
                              <span>{scheduledPoi.poi.budget_tier}</span>
                              {scheduledPoi.poi.opening_hours && (
                                <span>{scheduledPoi.poi.opening_hours}</span>
                              )}
                            </div>

                            {scheduledPoi.recommendation_reason && (
                              <p className="poi-reason highlighted-reason">
                                {scheduledPoi.recommendation_reason}
                              </p>
                            )}

                            {(scheduledPoi.poi.description || scheduledPoi.poi.highlights.length > 0) && (
                              <div className="poi-extra">
                                {scheduledPoi.poi.description && (
                                  <p className="poi-description">{scheduledPoi.poi.description}</p>
                                )}
                                {scheduledPoi.poi.highlights.length > 0 && (
                                  <div className="inline-tags">
                                    {scheduledPoi.poi.highlights.slice(0, 3).map((highlight) => (
                                      <span key={highlight}>{highlight}</span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
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

      <section className="footer-note panel">
        <p>
          This frontend is intentionally minimal: one page, two input modes, and a clear display
          of how structured planning output differs from LLM-generated explanation.
        </p>
      </section>
    </div>
  )
}

export default App
