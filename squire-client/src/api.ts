export type Repo = {
  id: number
  full_name: string
  is_active: boolean
  created_at: string
  updated_at: string
  last_synced_at: string | null
  has_custom_github_token: boolean
  github_base_url: string | null
}

export type PullSummary = {
  id: number
  repo: string
  number: number
  title: string
  author: string
  state: 'open' | 'closed' | 'merged'
  changed_files: number
  updated_at: string
  review_status: 'pending' | 'in-progress' | 'done'
}

export type PullDetail = {
  id: number
  repo: string
  number: number
  title: string
  body: string | null
  author: string
  state: 'open' | 'closed' | 'merged'
  head_branch: string
  base_branch: string
  changed_files: number
  reviewers: string[]
  created_at: string
  updated_at: string
  synced_at: string
  review_status: 'pending' | 'in-progress' | 'done'
}

export type PullFile = {
  filename: string
  status: string
  additions: number
  deletions: number
  changes: number
}

export type LocalReview = {
  id: number
  file_path: string | null
  line_number: number | null
  severity: 'info' | 'warning' | 'error'
  body: string
  agent: string
  created_at: string
}

export type LocalReviewList = {
  review_status: 'pending' | 'in-progress' | 'done'
  items: LocalReview[]
}

export type GitHubComment = {
  id: number
  body: string | null
  created_at: string
  updated_at: string
  html_url: string
  user?: {
    login?: string
  }
}

export type GitHubReview = {
  id: number
  state: string
  body: string | null
  submitted_at: string | null
  html_url: string
  user?: {
    login?: string
  }
}

const API_BASE_URL =
  import.meta.env.VITE_SQUIRE_API_BASE_URL?.trim() || 'http://127.0.0.1:8484'

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `API request failed: ${response.status}`)
  }

  return (await response.json()) as T
}

async function requestText(path: string, options: RequestOptions = {}): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  const text = await response.text()
  if (!response.ok) {
    throw new Error(text || `API request failed: ${response.status}`)
  }

  return text
}

export async function listRepos(): Promise<Repo[]> {
  return request<Repo[]>('/repos')
}

export async function addRepo(
  fullName: string,
  fullSync: boolean,
  options?: {
    githubToken?: string
    githubBaseUrl?: string
  },
): Promise<void> {
  await request('/repos', {
    method: 'POST',
    body: {
      full_name: fullName,
      full_sync: fullSync,
      github_token: options?.githubToken,
      github_base_url: options?.githubBaseUrl,
    },
  })
}

export async function removeRepo(fullName: string): Promise<void> {
  await request(`/repos/${encodeURIComponent(fullName)}`, {
    method: 'DELETE',
  })
}

export async function syncRepo(repo: string, full: boolean): Promise<void> {
  await request(`/sync?repo=${encodeURIComponent(repo)}&full=${full ? 'true' : 'false'}`, {
    method: 'POST',
  })
}

export async function listPulls(
  repo: string,
  state: 'open' | 'closed' | 'all',
): Promise<PullSummary[]> {
  return request<PullSummary[]>(
    `/pulls?repo=${encodeURIComponent(repo)}&state=${encodeURIComponent(state)}`,
  )
}

export async function getPull(repo: string, number: number): Promise<PullDetail> {
  return request<PullDetail>(`/pulls/${number}?repo=${encodeURIComponent(repo)}`)
}

export async function getPullFiles(repo: string, number: number): Promise<PullFile[]> {
  return request<PullFile[]>(`/pulls/${number}/files?repo=${encodeURIComponent(repo)}`)
}

export async function getPullDiff(
  repo: string,
  number: number,
  filePath?: string,
): Promise<string> {
  const query = filePath
    ? `?repo=${encodeURIComponent(repo)}&file=${encodeURIComponent(filePath)}`
    : `?repo=${encodeURIComponent(repo)}`
  return requestText(`/pulls/${number}/diff${query}`)
}

export async function getPullComments(repo: string, number: number): Promise<GitHubComment[]> {
  return request<GitHubComment[]>(`/pulls/${number}/comments?repo=${encodeURIComponent(repo)}`)
}

export async function getPullGitHubReviews(
  repo: string,
  number: number,
): Promise<GitHubReview[]> {
  return request<GitHubReview[]>(
    `/pulls/${number}/github-reviews?repo=${encodeURIComponent(repo)}`,
  )
}

export async function listLocalReviews(repo: string, number: number): Promise<LocalReviewList> {
  return request<LocalReviewList>(`/pulls/${number}/local-reviews?repo=${encodeURIComponent(repo)}`)
}

export async function addLocalReview(
  repo: string,
  number: number,
  payload: {
    body: string
    severity: 'info' | 'warning' | 'error'
    file_path?: string | null
    line_number?: number | null
    agent?: string
  },
): Promise<void> {
  await request(`/pulls/${number}/local-reviews?repo=${encodeURIComponent(repo)}`, {
    method: 'POST',
    body: payload,
  })
}

export async function updateReviewStatus(
  repo: string,
  number: number,
  status: 'pending' | 'in-progress' | 'done',
): Promise<void> {
  await request(`/pulls/${number}/review-status?repo=${encodeURIComponent(repo)}`, {
    method: 'PUT',
    body: { status },
  })
}
