import api from './client'
import type { Building, EnrichmentResult, PaginatedResponse, Person } from './types'

export const buildingsApi = {
  list: (search?: string) =>
    api.get<PaginatedResponse<Building>>('/buildings/', { params: search ? { search } : {} }),
  create: (data: Omit<Building, 'id' | 'created_at' | 'updated_at'>) =>
    api.post<Building>('/buildings/', data),
  update: (id: number, data: Partial<Omit<Building, 'id' | 'created_at' | 'updated_at'>>) =>
    api.patch<Building>(`/buildings/${id}/`, data),
  delete: (id: number) => api.delete(`/buildings/${id}/`),
}

export const personsApi = {
  list: (search?: string) =>
    api.get<PaginatedResponse<Person>>('/persons/', { params: search ? { search } : {} }),
  create: (data: Omit<Person, 'id' | 'building_detail' | 'has_enrichment' | 'latest_enrichment_id' | 'latest_enrichment_tier' | 'created_at' | 'updated_at'>) =>
    api.post<Person>('/persons/', data),
  update: (id: number, data: Partial<Omit<Person, 'id' | 'building_detail' | 'has_enrichment' | 'latest_enrichment_id' | 'latest_enrichment_tier' | 'created_at' | 'updated_at'>>) =>
    api.patch<Person>(`/persons/${id}/`, data),
  delete: (id: number) => api.delete(`/persons/${id}/`),
}

export const enrichmentsApi = {
  get: (id: number) => api.get<EnrichmentResult>(`/enrichments/${id}/`),
  run: (leadId: number) => api.post<EnrichmentResult>(`/enrich/${leadId}/`),
}
