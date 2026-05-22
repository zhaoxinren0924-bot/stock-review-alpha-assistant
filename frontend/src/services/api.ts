export async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return res.json()
}
