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

  const selectedCategoryShorts = useMemo(
    () =>
      categoryOptions
        .filter((category) => structuredForm.preferred_categories?.includes(category.value))
        .map((category) => category.short),
    [structuredForm.preferred_categories],
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
      <header className="travel-hero">
        <nav className="topbar">
          <div className="brand-mark">
            <span className="brand-logo">✈</span>
            <div>
              <strong>TripTailor</strong>
              <p>Smart itinerary planning</p>
            </div>
          </div>
          <div className="topbar-badges">
            <span className="product-badge">Personalized itineraries</span>
            <span className={`status-dot ${healthLoading ? 'loading' : 'ok'}`}>
              {healthLoading ? 'Checking backend' : health?.status ?? 'Unavailable'}
            </span>
          </div>
        </nav>

        <div className="hero-content">
          <div className="hero-copy-block">
            <p className="eyebrow light">Plan smarter trips</p>
            <h1>Build a personalized itinerary in minutes</h1>
            <p className="hero-copy light-copy">
              Discover a cleaner way to plan city trips with tailored pacing, category-based
              preferences, and day-by-day recommendations that feel like a real travel product.
            </p>

            <div className="hero-pills">
              <span>Food, culture, local life</span>
              <span>Natural-language trip requests</span>
              <span>Day-by-day itineraries</span>
            </div>
          </div>

          <section className="search-card panel input-panel">
            <div className="search-card-header">
              <div>
                <p className="eyebrow">Trip planner</p>
                <h2>Where would you like to go?</h2>
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
                  Describe it
                </button>
              </div>
            </div>

            {mode === 'structured' ? (
              <div className="form-stack compact-stack">
                <label>
                  Destination
                  <input
                    value={structuredForm.destination}
                    onChange={(event) => handleStructuredChange('destination', event.target.value)}
                    placeholder="Brisbane"
                  />
                </label>

                <div className="three-column-grid">
                  <label>
                    Days
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
                    Budget
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

                  <label>
                    Pace
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
                </div>

                <div>
                  <span className="field-label">What are you into?</span>
                  <div className="chip-grid travel-chip-grid">
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
                  Trip vibe or preferences
                  <textarea
                    rows={4}
                    value={structuredForm.free_text_preferences ?? ''}
                    onChange={(event) =>
                      handleStructuredChange('free_text_preferences', event.target.value)
                    }
                    placeholder="I like relaxed neighborhoods, local food, and places that are less crowded."
                  />
                </label>
              </div>
            ) : (
              <div className="form-stack compact-stack">
                <label>
                  Describe your trip
                  <textarea
                    rows={6}
                    value={rawText}
                    onChange={(event) => setRawText(event.target.value)}
                    placeholder="I'd like to spend three days in Brisbane, focusing mainly on food."
                  />
                </label>
                <div className="example-callout travel-example">
                  <strong>Example</strong>
                  <p>{naturalExample}</p>
                </div>
              </div>
            )}

            <div className="action-row search-actions">
              <button className="secondary" onClick={fillExample}>
                Use sample trip
              </button>
              <button className="secondary" onClick={resetAll}>
                Clear
              </button>
              <button className="primary large-cta" disabled={!canSubmit || loading} onClick={handleSubmit}>
                {loading ? 'Planning your trip…' : 'Generate itinerary'}
              </button>
            </div>
          </section>
        </div>
      </header>

      <section className="quick-glance-grid">
        <div className="quick-card">
          <span className="quick-label">Input modes</span>
          <strong>Structured + natural language</strong>
          <p>Choose a classic travel form or just describe the trip you want.</p>
        </div>
        <div className="quick-card">
          <span className="quick-label">Trip style</span>
          <strong>
            {selectedCategoryShorts.length > 0 ? selectedCategoryShorts.join(' · ') : 'Flexible'}
          </strong>
          <p>Mix categories like food, history, nature, and local life.</p>
        </div>
        <div className="quick-card">
          <span className="quick-label">Planner status</span>
          <strong>{healthLoading ? 'Connecting…' : health?.status ?? 'Offline'}</strong>
          <p>
            {providerEntries.length > 0
              ? providerEntries.map(([name, provider]) => `${name}: ${provider.mode}`).join(' · ')
              : 'Backend health and provider modes appear here.'}
          </p>
        </div>
      </section>

      <main className="results-layout">
        <section className="results-main panel result-panel">
          <div className="section-heading result-heading product-heading">
            <div>
              <p className="eyebrow">Suggested itinerary</p>
              <h2>Your trip plan</h2>
            </div>
            {result && (
              <div className="result-badges">
                <span>{result.duration_days} days</span>
                <span>{totalPois} stops</span>
                <span>From ¥{Math.round(result.total_estimated_cost_cny)}</span>
              </div>
            )}
          </div>

          {error && <div className="message error">{error}</div>}
          {loading && <div className="message loading">Building your itinerary…</div>}

          {!loading && !result && !error && (
            <div className="empty-state travel-empty">
              <h3>Start with a destination</h3>
              <p>
                Search for a city, choose your travel style, and we&apos;ll generate a complete
                day-by-day itinerary with recommendations and timing.
              </p>
            </div>
          )}

          {result && (
            <div className="result-stack">
              <div className="destination-hero-card">
                <div>
                  <p className="eyebrow">Recommended for {result.destination}</p>
                  <h3>{result.destination}</h3>
                  <p className="destination-overview">
                    {result.overview || 'A personalized itinerary generated from your travel preferences.'}
                  </p>
                </div>
                <div className="destination-stats">
                  <div>
                    <span>Trip length</span>
                    <strong>{result.duration_days} days</strong>
                  </div>
                  <div>
                    <span>Total stops</span>
                    <strong>{totalPois}</strong>
                  </div>
                  <div>
                    <span>Estimated total</span>
                    <strong>¥{Math.round(result.total_estimated_cost_cny)}</strong>
                  </div>
                </div>
              </div>

              <div className="summary-grid product-summary-grid">
                <div className="summary-block feature-block product-card">
                  <h4>Why this trip fits you</h4>
                  <p>{result.persona_summary}</p>
                </div>

                <div className="summary-block feature-block product-card soft-card">
                  <h4>Good to know</h4>
                  <p>
                    Powered by structured itinerary planning with LLM-supported input parsing and
                    recommendation copy.
                  </p>
                </div>
              </div>

              {result.planning_notes.length > 0 && (
                <div className="summary-block notes-block product-card">
                  <h4>Trip notes</h4>
                  <ul>
                    {result.planning_notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}

              {result.days.map((day) => (
                <article key={day.day_number} className="day-card itinerary-day-card">
                  <div className="day-header product-day-header">
                    <div>
                      <p className="eyebrow">{day.date_label}</p>
                      <h3>{day.theme || `Day ${day.day_number}`}</h3>
                    </div>
                    <div className="day-header-side">
                      <span className="day-poi-count">{day.pois.length} activities</span>
                      {day.weather && (
                        <div className="weather-badge product-weather">
                          <strong>{day.weather.condition}</strong>
                          <span>
                            {Math.round(day.weather.temp_low_c)}–
                            {Math.round(day.weather.temp_high_c)}°C
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {(day.narrative || day.weather?.travel_advisory) && (
                    <div className="day-meta-grid product-day-meta">
                      {day.narrative && (
                        <div className="day-meta-card narrative-card product-card-lite">
                          <span className="meta-label">Day overview</span>
                          <p>{day.narrative}</p>
                        </div>
                      )}
                      {day.weather?.travel_advisory && (
                        <div className="day-meta-card product-card-lite">
                          <span className="meta-label">Weather note</span>
                          <p>{day.weather.travel_advisory}</p>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="product-poi-grid">
                    {day.pois.map((scheduledPoi) => (
                      <div key={`${day.day_number}-${scheduledPoi.poi.id}`} className="poi-card product-poi-card">
                        <div className="poi-image-placeholder">
                          <span>{scheduledPoi.suggested_start_time}</span>
                          <small>{scheduledPoi.suggested_duration_hours}h stay</small>
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

                          <div className="poi-meta-row product-meta-row">
                            <span>From ¥{Math.round(scheduledPoi.poi.avg_cost_cny)}</span>
                            <span>{scheduledPoi.poi.budget_tier}</span>
                            {scheduledPoi.poi.opening_hours && (
                              <span>{scheduledPoi.poi.opening_hours}</span>
                            )}
                          </div>

                          {scheduledPoi.recommendation_reason && (
                            <p className="poi-reason highlighted-reason product-highlight">
                              {scheduledPoi.recommendation_reason}
                            </p>
                          )}

                          {scheduledPoi.poi.description && (
                            <p className="poi-description">{scheduledPoi.poi.description}</p>
                          )}

                          {scheduledPoi.poi.highlights.length > 0 && (
                            <div className="inline-tags product-tags">
                              {scheduledPoi.poi.highlights.slice(0, 3).map((highlight) => (
                                <span key={highlight}>{highlight}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              ))}

              <p className="meta-text booking-meta">
                Request ID: {result.request_id} · Generated at{' '}
                {new Date(result.generated_at).toLocaleString()}
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
