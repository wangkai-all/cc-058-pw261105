const API_BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  listBoxes: () => request('/api/box-types'),
  createBox: (data) => request('/api/box-types', { method: 'POST', body: JSON.stringify(data) }),
  listPlans: () => request('/api/freight-plans'),
  createPlan: (data) => request('/api/freight-plans', { method: 'POST', body: JSON.stringify(data) }),
  solve: (data) => request('/api/solve', { method: 'POST', body: JSON.stringify(data) }),
}
