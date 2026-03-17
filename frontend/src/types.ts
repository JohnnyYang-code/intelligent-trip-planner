export type BudgetLevel = 'budget' | 'mid_range' | 'luxury'
export type TravelPace = 'relaxed' | 'moderate' | 'intensive'
export type POICategory =
  | 'history_culture'
  | 'nature_scenery'
  | 'food_dining'
  | 'shopping'
  | 'art_museum'
  | 'entertainment'
  | 'local_life'

export interface StructuredTripRequest {
  destination: string
  duration_days: number
  budget_level: BudgetLevel
  travel_pace: TravelPace
  preferred_categories?: POICategory[]
  free_text_preferences?: string
}

export interface NaturalLanguageTripRequest {
  raw_text: string
}

export interface ProviderStatus {
  name: string
  available: boolean
  mode: string
}

export interface HealthResponse {
  status: string
  providers: Record<string, ProviderStatus>
}

export interface DailyWeather {
  date: string
  condition: string
  temp_high_c: number
  temp_low_c: number
  humidity_pct: number
  precipitation_mm: number
  wind_speed_kmh: number
  uv_index: number
  travel_advisory: string
}

export interface POI {
  id: string
  name: string
  name_en?: string | null
  destination: string
  category: POICategory
  latitude: number
  longitude: number
  district: string
  popularity_score: number
  quality_score: number
  avg_cost_cny: number
  budget_tier: BudgetLevel
  duration_hours: number
  opening_hours?: string | null
  indoor: boolean
  child_friendly: boolean
  accessible: boolean
  tags: string[]
  description: string
  highlights: string[]
}

export interface ScheduledPOI {
  poi: POI
  visit_order: number
  suggested_start_time: string
  suggested_duration_hours: number
  recommendation_reason: string
}

export interface DayPlan {
  day_number: number
  date_label: string
  theme: string
  pois: ScheduledPOI[]
  weather?: DailyWeather | null
  narrative: string
  tips: string[]
}

export interface ItineraryResponse {
  request_id: string
  destination: string
  duration_days: number
  overview: string
  persona_summary: string
  days: DayPlan[]
  total_estimated_cost_cny: number
  generated_at: string
  planning_notes: string[]
}
