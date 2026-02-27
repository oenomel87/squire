import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'
import {
  addLocalReview,
  addRepo,
  getPull,
  getPullComments,
  getPullDiff,
  getPullFiles,
  getPullGitHubReviews,
  listLocalReviews,
  listPulls,
  listRepos,
  removeRepo,
  syncRepo,
  updateReviewStatus,
} from './api'
import type {
  GitHubComment,
  GitHubReview,
  PullDetail,
  PullFile,
  PullSummary,
  Repo,
} from './api'

type ReviewStatus = 'pending' | 'in-progress' | 'done'
type DetailTab = 'local-reviews' | 'files' | 'diff' | 'comments' | 'github-reviews'

function App() {
  const [repos, setRepos] = useState<Repo[]>([])
  const [selectedRepo, setSelectedRepo] = useState('')
  const [pullState, setPullState] = useState<'open' | 'closed' | 'all'>('open')
  const [pulls, setPulls] = useState<PullSummary[]>([])
  const [selectedPullNumber, setSelectedPullNumber] = useState<number | null>(null)
  const [pullDetail, setPullDetail] = useState<PullDetail | null>(null)
  const [pullFiles, setPullFiles] = useState<PullFile[]>([])

  const [localReviewStatus, setLocalReviewStatus] = useState<ReviewStatus>('pending')
  const [localReviews, setLocalReviews] = useState<
    Array<{
      id: number
      file_path: string | null
      line_number: number | null
      severity: 'info' | 'warning' | 'error'
      body: string
      agent: string
      created_at: string
    }>
  >([])

  const [detailTab, setDetailTab] = useState<DetailTab>('local-reviews')
  const [diffText, setDiffText] = useState('')
  const [diffTargetFile, setDiffTargetFile] = useState('')
  const [githubComments, setGithubComments] = useState<GitHubComment[]>([])
  const [githubReviews, setGithubReviews] = useState<GitHubReview[]>([])
  const [tabLoading, setTabLoading] = useState(false)
  const [tabLoaded, setTabLoaded] = useState({
    diff: false,
    comments: false,
    githubReviews: false,
  })

  const [repoInput, setRepoInput] = useState('')
  const [repoFullSync, setRepoFullSync] = useState(false)
  const [repoGitHubToken, setRepoGitHubToken] = useState('')
  const [repoGitHubBaseUrl, setRepoGitHubBaseUrl] = useState('')
  const [reviewBody, setReviewBody] = useState('')
  const [reviewFile, setReviewFile] = useState('')
  const [reviewLine, setReviewLine] = useState('')
  const [reviewSeverity, setReviewSeverity] = useState<'info' | 'warning' | 'error'>('info')
  const [reviewAgent, setReviewAgent] = useState('codex')
  const [busy, setBusy] = useState(false)
  const [errorText, setErrorText] = useState('')
  const [noticeText, setNoticeText] = useState('')

  const selectedPull = useMemo(
    () => pulls.find((pull) => pull.number === selectedPullNumber) ?? null,
    [pulls, selectedPullNumber],
  )
  const selectedRepoRecord = useMemo(
    () => repos.find((repo) => repo.full_name === selectedRepo) ?? null,
    [repos, selectedRepo],
  )

  const setError = (message: string) => {
    setErrorText(message)
    setNoticeText('')
  }

  const setNotice = (message: string) => {
    setNoticeText(message)
    setErrorText('')
  }

  const parseError = (error: unknown): string => {
    if (error instanceof Error) {
      const trimmed = error.message.trim()
      if (trimmed.startsWith('{')) {
        try {
          const parsed = JSON.parse(trimmed) as { detail?: string }
          if (parsed.detail) {
            return parsed.detail
          }
        } catch {
          return trimmed
        }
      }
      return trimmed
    }
    return '요청 처리 중 알 수 없는 오류가 발생했습니다.'
  }

  const resetTabData = () => {
    setDetailTab('local-reviews')
    setDiffText('')
    setDiffTargetFile('')
    setGithubComments([])
    setGithubReviews([])
    setTabLoaded({
      diff: false,
      comments: false,
      githubReviews: false,
    })
  }

  const reloadRepos = async (preferRepo?: string) => {
    const loaded = await listRepos()
    setRepos(loaded)

    const preferred = preferRepo?.trim()
    if (preferred && loaded.some((repo) => repo.full_name === preferred)) {
      setSelectedRepo(preferred)
      return
    }

    if (!loaded.length) {
      setSelectedRepo('')
      return
    }

    setSelectedRepo((current) => {
      if (current && loaded.some((repo) => repo.full_name === current)) {
        return current
      }
      return loaded[0].full_name
    })
  }

  const reloadPulls = async (repo: string, state: 'open' | 'closed' | 'all') => {
    const loaded = await listPulls(repo, state)
    setPulls(loaded)
    if (!loaded.some((pull) => pull.number === selectedPullNumber)) {
      setSelectedPullNumber(loaded[0]?.number ?? null)
    }
  }

  const reloadPullDetail = async (repo: string, number: number) => {
    const [detail, reviews, files] = await Promise.all([
      getPull(repo, number),
      listLocalReviews(repo, number),
      getPullFiles(repo, number),
    ])
    setPullDetail(detail)
    setLocalReviewStatus(reviews.review_status)
    setLocalReviews(reviews.items)
    setPullFiles(files)
  }

  const loadDiff = async (repo: string, number: number, filePath: string) => {
    setTabLoading(true)
    try {
      const text = await getPullDiff(repo, number, filePath || undefined)
      setDiffText(text)
      setTabLoaded((current) => ({ ...current, diff: true }))
    } catch (error) {
      setError(parseError(error))
    } finally {
      setTabLoading(false)
    }
  }

  const loadGitHubComments = async (repo: string, number: number) => {
    setTabLoading(true)
    try {
      const data = await getPullComments(repo, number)
      setGithubComments(data)
      setTabLoaded((current) => ({ ...current, comments: true }))
    } catch (error) {
      setError(parseError(error))
    } finally {
      setTabLoading(false)
    }
  }

  const loadGitHubReviews = async (repo: string, number: number) => {
    setTabLoading(true)
    try {
      const data = await getPullGitHubReviews(repo, number)
      setGithubReviews(data)
      setTabLoaded((current) => ({ ...current, githubReviews: true }))
    } catch (error) {
      setError(parseError(error))
    } finally {
      setTabLoading(false)
    }
  }

  const loadDetailTab = (tab: DetailTab, repo: string, number: number) => {
    if (tab === 'diff') {
      if (!tabLoaded.diff) {
        void loadDiff(repo, number, diffTargetFile)
      }
      return
    }
    if (tab === 'comments') {
      if (!tabLoaded.comments) {
        void loadGitHubComments(repo, number)
      }
      return
    }
    if (tab === 'github-reviews') {
      if (!tabLoaded.githubReviews) {
        void loadGitHubReviews(repo, number)
      }
    }
  }

  const handleSelectDetailTab = (tab: DetailTab) => {
    setDetailTab(tab)
    if (!selectedRepo || selectedPullNumber === null) {
      return
    }
    loadDetailTab(tab, selectedRepo, selectedPullNumber)
  }

  useEffect(() => {
    ;(async () => {
      try {
        await reloadRepos()
      } catch (error) {
        setError(parseError(error))
      }
    })()
  }, [])

  useEffect(() => {
    if (!selectedRepo) {
      setPulls([])
      setSelectedPullNumber(null)
      setPullDetail(null)
      setPullFiles([])
      setLocalReviews([])
      setLocalReviewStatus('pending')
      resetTabData()
      return
    }

    ;(async () => {
      try {
        await reloadPulls(selectedRepo, pullState)
      } catch (error) {
        setError(parseError(error))
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepo, pullState])

  useEffect(() => {
    if (!selectedRepo || selectedPullNumber === null) {
      setPullDetail(null)
      setPullFiles([])
      setLocalReviews([])
      setLocalReviewStatus('pending')
      resetTabData()
      return
    }

    resetTabData()
    ;(async () => {
      try {
        await reloadPullDetail(selectedRepo, selectedPullNumber)
      } catch (error) {
        setError(parseError(error))
      }
    })()
  }, [selectedRepo, selectedPullNumber])

  const handleAddRepo = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const targetRepo = repoInput.trim()
    if (!targetRepo) {
      setError('저장소를 owner/repo 형식으로 입력하세요.')
      return
    }

    setBusy(true)
    try {
      const githubToken = repoGitHubToken.trim()
      const githubBaseUrl = repoGitHubBaseUrl.trim()
      await addRepo(targetRepo, repoFullSync, {
        githubToken: githubToken || undefined,
        githubBaseUrl: githubBaseUrl || undefined,
      })
      await reloadRepos(targetRepo)
      await reloadPulls(targetRepo, pullState)
      setRepoInput('')
      setRepoGitHubToken('')
      setRepoGitHubBaseUrl('')
      setNotice(`저장소 ${targetRepo} 등록 및 동기화를 완료했습니다.`)
    } catch (error) {
      setError(parseError(error))
    } finally {
      setBusy(false)
    }
  }

  const handleRemoveRepo = async () => {
    if (!selectedRepo) {
      return
    }

    if (!window.confirm(`${selectedRepo} 저장소를 등록 해제할까요?`)) {
      return
    }

    setBusy(true)
    try {
      await removeRepo(selectedRepo)
      await reloadRepos()
      setNotice(`저장소 ${selectedRepo} 등록을 해제했습니다.`)
    } catch (error) {
      setError(parseError(error))
    } finally {
      setBusy(false)
    }
  }

  const handleSync = async (full: boolean) => {
    if (!selectedRepo) {
      setError('동기화할 저장소를 먼저 선택하세요.')
      return
    }

    setBusy(true)
    try {
      await syncRepo(selectedRepo, full)
      await reloadRepos(selectedRepo)
      await reloadPulls(selectedRepo, pullState)
      if (selectedPullNumber !== null) {
        await reloadPullDetail(selectedRepo, selectedPullNumber)
      }
      setNotice(full ? '전체 동기화를 완료했습니다.' : '증분 동기화를 완료했습니다.')
    } catch (error) {
      setError(parseError(error))
    } finally {
      setBusy(false)
    }
  }

  const handleSetReviewStatus = async (nextStatus: ReviewStatus) => {
    if (!selectedRepo || selectedPullNumber === null) {
      return
    }

    setBusy(true)
    try {
      await updateReviewStatus(selectedRepo, selectedPullNumber, nextStatus)
      await reloadPulls(selectedRepo, pullState)
      await reloadPullDetail(selectedRepo, selectedPullNumber)
      setNotice(`리뷰 상태를 ${nextStatus}로 변경했습니다.`)
    } catch (error) {
      setError(parseError(error))
    } finally {
      setBusy(false)
    }
  }

  const handleCreateReview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedRepo || selectedPullNumber === null) {
      setError('리뷰를 작성할 PR을 선택하세요.')
      return
    }

    const body = reviewBody.trim()
    if (!body) {
      setError('리뷰 본문을 입력하세요.')
      return
    }

    const lineNumber = reviewLine.trim() ? Number(reviewLine.trim()) : null
    if (lineNumber !== null && Number.isNaN(lineNumber)) {
      setError('라인 번호는 숫자여야 합니다.')
      return
    }

    setBusy(true)
    try {
      await addLocalReview(selectedRepo, selectedPullNumber, {
        body,
        severity: reviewSeverity,
        file_path: reviewFile.trim() || null,
        line_number: lineNumber,
        agent: reviewAgent.trim() || 'codex',
      })
      await reloadPulls(selectedRepo, pullState)
      await reloadPullDetail(selectedRepo, selectedPullNumber)
      setReviewBody('')
      setReviewFile('')
      setReviewLine('')
      setNotice('로컬 리뷰 코멘트를 추가했습니다.')
    } catch (error) {
      setError(parseError(error))
    } finally {
      setBusy(false)
    }
  }

  const handleReloadDiff = async () => {
    if (!selectedRepo || selectedPullNumber === null) {
      return
    }
    await loadDiff(selectedRepo, selectedPullNumber, diffTargetFile)
  }

  const handleReloadComments = async () => {
    if (!selectedRepo || selectedPullNumber === null) {
      return
    }
    await loadGitHubComments(selectedRepo, selectedPullNumber)
  }

  const handleReloadGitHubReviews = async () => {
    if (!selectedRepo || selectedPullNumber === null) {
      return
    }
    await loadGitHubReviews(selectedRepo, selectedPullNumber)
  }

  const formatDate = (value: string | null) => {
    if (!value) {
      return '-'
    }
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
      return value
    }
    return parsed.toLocaleString()
  }

  return (
    <div className="page">
      <header className="app-header reveal">
        <p className="eyebrow">Local PR Proxy</p>
        <h1>Squire Dashboard</h1>
        <p className="subtitle">
          저장소 등록, 동기화, PR 상세 확인, 로컬 리뷰 상태 변경을 한 화면에서 처리합니다.
        </p>
      </header>

      {errorText && <div className="alert alert-error reveal">{errorText}</div>}
      {noticeText && <div className="alert alert-notice reveal">{noticeText}</div>}

      <div className="layout">
        <aside className="panel left reveal">
          <section className="section">
            <h2>저장소 관리</h2>
            <form className="repo-form" onSubmit={handleAddRepo}>
              <div className="row">
                <input
                  value={repoInput}
                  onChange={(event) => setRepoInput(event.target.value)}
                  placeholder="owner/repo"
                />
                <button type="submit" disabled={busy}>
                  add
                </button>
              </div>
              <input
                type="password"
                value={repoGitHubToken}
                onChange={(event) => setRepoGitHubToken(event.target.value)}
                placeholder="프로젝트 전용 GitHub token (optional)"
              />
              <input
                value={repoGitHubBaseUrl}
                onChange={(event) => setRepoGitHubBaseUrl(event.target.value)}
                placeholder="프로젝트 전용 GitHub base URL (optional)"
              />
            </form>
            <p className="small">프로젝트 토큰은 macOS Keychain에 저장되며 DB에는 평문 저장하지 않습니다.</p>
            <label className="check">
              <input
                type="checkbox"
                checked={repoFullSync}
                onChange={(event) => setRepoFullSync(event.target.checked)}
              />
              추가 시 전체 동기화 강제 실행
            </label>
          </section>

          <section className="section">
            <h2>활성 저장소</h2>
            <div className="row">
              <select
                value={selectedRepo}
                onChange={(event) => setSelectedRepo(event.target.value)}
                disabled={!repos.length || busy}
              >
                <option value="">선택하세요</option>
                {repos.map((repo) => (
                  <option key={repo.id} value={repo.full_name}>
                    {repo.full_name}
                  </option>
                ))}
              </select>
              <button type="button" className="danger" onClick={handleRemoveRepo} disabled={busy}>
                remove
              </button>
            </div>
            <p className="small">
              last_synced:{' '}
              {selectedRepoRecord?.last_synced_at ? formatDate(selectedRepoRecord.last_synced_at) : '-'}
            </p>
            <p className="small">
              github config: token{' '}
              {selectedRepoRecord?.has_custom_github_token ? 'project' : 'global'} · base_url{' '}
              {selectedRepoRecord?.github_base_url || '<global>'}
            </p>
            <div className="row">
              <button type="button" onClick={() => handleSync(false)} disabled={!selectedRepo || busy}>
                증분 sync
              </button>
              <button
                type="button"
                className="accent"
                onClick={() => handleSync(true)}
                disabled={!selectedRepo || busy}
              >
                전체 sync
              </button>
            </div>
          </section>

          <section className="section">
            <h2>PR 목록</h2>
            <div className="segment">
              {(['open', 'closed', 'all'] as const).map((state) => (
                <button
                  key={state}
                  type="button"
                  className={pullState === state ? 'active' : ''}
                  onClick={() => setPullState(state)}
                  disabled={busy}
                >
                  {state}
                </button>
              ))}
            </div>
            <div className="list">
              {!pulls.length && <p className="empty">표시할 PR이 없습니다.</p>}
              {pulls.map((pull) => (
                <button
                  type="button"
                  key={pull.id}
                  className={`list-item ${selectedPullNumber === pull.number ? 'selected' : ''}`}
                  onClick={() => setSelectedPullNumber(pull.number)}
                >
                  <div className="list-top">
                    <strong>#{pull.number}</strong>
                    <span className={`badge ${pull.state}`}>{pull.state}</span>
                  </div>
                  <p className="title">{pull.title}</p>
                  <p className="meta">
                    by {pull.author} · files {pull.changed_files} · review {pull.review_status}
                  </p>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <main className="panel right reveal">
          {!selectedRepo && <p className="empty">좌측에서 저장소를 선택하세요.</p>}
          {selectedRepo && !selectedPull && <p className="empty">PR을 선택하세요.</p>}
          {selectedRepo && selectedPull && pullDetail && (
            <>
              <section className="section">
                <div className="detail-head">
                  <h2>
                    #{pullDetail.number} {pullDetail.title}
                  </h2>
                  <span className={`badge ${pullDetail.state}`}>{pullDetail.state}</span>
                </div>
                <p className="meta">
                  {pullDetail.head_branch} → {pullDetail.base_branch} · by {pullDetail.author}
                </p>
                <p className="meta">
                  changed files {pullDetail.changed_files} · synced {formatDate(pullDetail.synced_at)}
                </p>
                {pullDetail.body && <pre className="body">{pullDetail.body}</pre>}
              </section>

              <section className="section">
                <h2>로컬 리뷰 상태</h2>
                <div className="row">
                  {(['pending', 'in-progress', 'done'] as const).map((status) => (
                    <button
                      type="button"
                      key={status}
                      className={localReviewStatus === status ? 'active' : ''}
                      onClick={() => handleSetReviewStatus(status)}
                      disabled={busy}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </section>

              <section className="section">
                <h2>PR 데이터</h2>
                <div className="segment detail-tabs">
                  <button
                    type="button"
                    className={detailTab === 'local-reviews' ? 'active' : ''}
                    onClick={() => handleSelectDetailTab('local-reviews')}
                  >
                    local reviews
                  </button>
                  <button
                    type="button"
                    className={detailTab === 'files' ? 'active' : ''}
                    onClick={() => handleSelectDetailTab('files')}
                  >
                    files
                  </button>
                  <button
                    type="button"
                    className={detailTab === 'diff' ? 'active' : ''}
                    onClick={() => handleSelectDetailTab('diff')}
                  >
                    diff
                  </button>
                  <button
                    type="button"
                    className={detailTab === 'comments' ? 'active' : ''}
                    onClick={() => handleSelectDetailTab('comments')}
                  >
                    comments
                  </button>
                  <button
                    type="button"
                    className={detailTab === 'github-reviews' ? 'active' : ''}
                    onClick={() => handleSelectDetailTab('github-reviews')}
                  >
                    github reviews
                  </button>
                </div>

                {detailTab === 'local-reviews' && (
                  <>
                    {!localReviews.length && <p className="empty">등록된 로컬 리뷰가 없습니다.</p>}
                    <div className="review-list">
                      {localReviews.map((review) => (
                        <article key={review.id} className={`review-card ${review.severity}`}>
                          <p className="review-head">
                            [{review.severity}]{' '}
                            {review.file_path ? `${review.file_path}:${review.line_number ?? '-'}` : 'PR'}
                          </p>
                          <p>{review.body}</p>
                          <p className="meta">
                            agent {review.agent} · {formatDate(review.created_at)}
                          </p>
                        </article>
                      ))}
                    </div>

                    <form className="review-form" onSubmit={handleCreateReview}>
                      <textarea
                        placeholder="리뷰 의견을 입력하세요"
                        value={reviewBody}
                        onChange={(event) => setReviewBody(event.target.value)}
                        rows={4}
                      />
                      <div className="review-grid">
                        <select
                          value={reviewSeverity}
                          onChange={(event) =>
                            setReviewSeverity(event.target.value as 'info' | 'warning' | 'error')
                          }
                        >
                          <option value="info">info</option>
                          <option value="warning">warning</option>
                          <option value="error">error</option>
                        </select>
                        <input
                          value={reviewFile}
                          onChange={(event) => setReviewFile(event.target.value)}
                          placeholder="file path (optional)"
                        />
                        <input
                          value={reviewLine}
                          onChange={(event) => setReviewLine(event.target.value)}
                          placeholder="line (optional)"
                        />
                        <input
                          value={reviewAgent}
                          onChange={(event) => setReviewAgent(event.target.value)}
                          placeholder="agent"
                        />
                      </div>
                      <button type="submit" className="accent" disabled={busy}>
                        리뷰 코멘트 추가
                      </button>
                    </form>
                  </>
                )}

                {detailTab === 'files' && (
                  <>
                    {!pullFiles.length && <p className="empty">변경 파일이 없습니다.</p>}
                    <div className="file-list">
                      {pullFiles.map((file) => (
                        <article key={file.filename} className="file-item">
                          <p className="file-name">{file.filename}</p>
                          <p className="meta">
                            {file.status} · +{file.additions} -{file.deletions} (Δ{file.changes})
                          </p>
                        </article>
                      ))}
                    </div>
                  </>
                )}

                {detailTab === 'diff' && (
                  <>
                    <div className="row diff-toolbar">
                      <select
                        value={diffTargetFile}
                        onChange={(event) => {
                          setDiffTargetFile(event.target.value)
                          setTabLoaded((current) => ({ ...current, diff: false }))
                          setDiffText('')
                        }}
                      >
                        <option value="">PR 전체 diff</option>
                        {pullFiles.map((file) => (
                          <option key={file.filename} value={file.filename}>
                            {file.filename}
                          </option>
                        ))}
                      </select>
                      <button type="button" onClick={handleReloadDiff} disabled={tabLoading}>
                        diff reload
                      </button>
                    </div>
                    {tabLoading && <p className="small">diff 로딩 중...</p>}
                    {!tabLoading && !diffText && <p className="empty">표시할 diff가 없습니다.</p>}
                    {!!diffText && <pre className="diff-view">{diffText}</pre>}
                  </>
                )}

                {detailTab === 'comments' && (
                  <>
                    <div className="row">
                      <button type="button" onClick={handleReloadComments} disabled={tabLoading}>
                        comments refresh
                      </button>
                    </div>
                    {!githubComments.length && <p className="empty">GitHub 코멘트가 없습니다.</p>}
                    <div className="activity-list">
                      {githubComments.map((comment) => (
                        <article key={comment.id} className="activity-card">
                          <p className="review-head">
                            {comment.user?.login || 'unknown'} · {formatDate(comment.created_at)}
                          </p>
                          <p>{comment.body || '(empty)'}</p>
                          <a
                            href={comment.html_url}
                            target="_blank"
                            rel="noreferrer"
                            className="meta link"
                          >
                            open on github
                          </a>
                        </article>
                      ))}
                    </div>
                  </>
                )}

                {detailTab === 'github-reviews' && (
                  <>
                    <div className="row">
                      <button type="button" onClick={handleReloadGitHubReviews} disabled={tabLoading}>
                        reviews refresh
                      </button>
                    </div>
                    {!githubReviews.length && <p className="empty">GitHub 리뷰 이벤트가 없습니다.</p>}
                    <div className="activity-list">
                      {githubReviews.map((review) => (
                        <article key={review.id} className="activity-card">
                          <p className="review-head">
                            {review.user?.login || 'unknown'} · {review.state} ·{' '}
                            {formatDate(review.submitted_at)}
                          </p>
                          <p>{review.body || '(empty)'}</p>
                          <a
                            href={review.html_url}
                            target="_blank"
                            rel="noreferrer"
                            className="meta link"
                          >
                            open on github
                          </a>
                        </article>
                      ))}
                    </div>
                  </>
                )}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
