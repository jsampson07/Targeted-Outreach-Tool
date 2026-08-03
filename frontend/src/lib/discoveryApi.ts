import { request } from './apiClient'
import type {
  CompanySearchResponse,
  ContactDiscoveryResponse,
} from './discoveryTypes'

export function searchCompanies(query: string): Promise<CompanySearchResponse> {
  return request<CompanySearchResponse>('/companies/search', {
    method: 'POST',
    body: { query },
  })
}

export function discoverContact(
  company_domain: string,
  role_title: string,
): Promise<ContactDiscoveryResponse> {
  return request<ContactDiscoveryResponse>('/contacts/discover', {
    method: 'POST',
    body: { company_domain, role_title },
  })
}
