import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, AudioLines, Bot, Check, CheckCheck,
  ChevronDown, ChevronRight, CircleDot, Clock3, Columns3, Command, FileCheck2, FileText, Folder,
  GitCompareArrows, History, Layers3, Laptop, ListFilter, LockKeyhole, MessageSquare,
  Minus, Monitor, Plus, Search, Send, Settings2, ShieldCheck, Sparkles, Square, X,
} from 'lucide-react'
import { tasks as seedTasks, type Task } from './data'
import { useLocale } from './i18n/LocaleProvider'
import {
  boardColumnFor, createLocalTask, decisionFor, initialWorkspace, isRunning, matchesFilter, needsAttention,
  parseWorkspace, recordDecision, revisionFor, simulateReceipt, simulateRevision,
  type Decision, type DecisionKind, type WorkFilter, type WorkspaceState,
} from './workspace'

type Page = 'work' | 'agents' | 'history'
type Tab = 'result' | 'activity' | 'context'
type Modal = 'settings' | 'new' | 'search' | null
type Translator = ReturnType<typeof useLocale>['t']
type Design = 'a' | 'b' | 'c' | 'd'
const STORAGE_KEY = 'dayline-workbench-v2'
const taskNumbers: Record<string, string> = { readme: '011', update: '012', research: '014', release: '015', checks: '016' }

const monitorTask: Task = {
  id: 'checks', title: '运行桌面兼容性检查', project: 'Dayline / QA', status: 'running',
  statusLabel: '执行中', summary: '检查窗口缩放、键盘导航和本地存储。', goal: '验证桌面工作台在常见窗口尺寸下的可用性。',
  agent: 'Sentinel', agentMode: 'Observe', updatedAt: '刚刚', progress: 42, tone: 'blue',
  activities: [{ id: 'check-1', actor: 'agent', title: '窗口检查进行中', body: '已检查 1440px 视口。下一步检查较小窗口。', time: '10:52', kind: 'tool' }],
}

function fixture(task: Task, value: string, t: Translator) {
  return task.id.startsWith('local-') ? value : t(value)
}

function matchesQuery(task: Task, query: string, t: Translator) {
  return `${fixture(task, task.title, t)} ${task.agent} ${task.project}`.toLowerCase().includes(query.toLowerCase())
}

function statusText(task: Task, state: WorkspaceState, t: Translator) {
  const decision = decisionFor(state, task)
  if (decision) {
    switch (decision.kind) {
      case 'accept': return t('已验收', 'Accepted')
      case 'revise': return t('等待新版本', 'Revision requested')
      case 'reject': return t('已拒绝发送', 'Send declined')
      case 'clarify': return t('继续执行 · 演示', 'Continuing · demo')
      case 'approve': return decision.receipt ? t('模拟交付完成', 'Delivered · simulated') : t('已授权 · 等待回执', 'Authorized · awaiting receipt')
    }
  }
  if (task.id.startsWith('local-')) return t('本地草稿', 'Local draft')
  if (task.decisionType === '验收') return t('待验收', 'Ready for review')
  if (task.decisionType === '授权') return t('待授权', 'Needs authorization')
  if (task.decisionType === '澄清') return t('等待你的回答', 'Needs your input')
  return task.status === 'done' ? t('已完成', 'Completed') : t('执行中', 'In progress')
}

function decisionTitle(decision: Decision, t: Translator) {
  const titles: Record<DecisionKind, string> = {
    accept: t('产物已验收', 'Artifact accepted'),
    revise: t('已提交修改要求', 'Changes requested'),
    approve: decision.receipt ? t('已收到模拟回执', 'Simulated receipt received') : t('单次授权已记录', 'One-time authorization recorded'),
    reject: t('本次发送已拒绝', 'Send request declined'),
    clarify: t('研究范围已确认', 'Research scope confirmed'),
  }
  return titles[decision.kind]
}

export default function App() {
  const { t, language } = useLocale()
  const researchMode = new URLSearchParams(window.location.search).get('research') === '1'
  const [appearance] = useState<{ design: Design; error: boolean }>(() => {
    const requested = new URLSearchParams(window.location.search).get('design')
    try {
      const saved = localStorage.getItem('dayline-design')
      const selected = requested ?? saved ?? 'a'
      if (selected !== 'a' && selected !== 'b' && selected !== 'c' && selected !== 'd') throw new Error('Unsupported design preference')
      return { design: selected, error: false }
    } catch (error) {
      console.error('Unable to load design preference', error)
      return { design: requested === 'b' || requested === 'c' || requested === 'd' ? requested : 'a', error: true }
    }
  })
  const [design, setDesign] = useState<Design>(appearance.design)
  const [appearanceError, setAppearanceError] = useState(appearance.error)
  const [showSummaries, setShowSummaries] = useState(false)
  const [loaded] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return { state: raw ? parseWorkspace(raw) : initialWorkspace(), error: false }
    } catch (error) {
      console.error('Unable to load demo workspace; stored data was left untouched', error)
      return { state: initialWorkspace(), error: true }
    }
  })
  const [state, setState] = useState(loaded.state)
  const [storageError, setStorageError] = useState(loaded.error)
  const [actionError, setActionError] = useState('')
  const [page, setPage] = useState<Page>('work')
  const [filter, setFilter] = useState<WorkFilter>('attention')
  const [selectedId, setSelectedId] = useState('readme')
  const [query, setQuery] = useState('')
  const [modal, setModal] = useState<Modal>(null)
  const [views, setViews] = useState<Record<string, Tab>>({})
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [feedbackOpen, setFeedbackOpen] = useState<Record<string, boolean>>({})
  const [choices, setChoices] = useState<Record<string, string>>({})
  const [revisionViews, setRevisionViews] = useState<Record<string, number>>({})
  const [mobileDetail, setMobileDetail] = useState(false)
  const [boardDetailOpen, setBoardDetailOpen] = useState(false)
  const detailRef = useRef<HTMLDivElement>(null)
  const boardRef = useRef<HTMLDivElement>(null)
  const boardCloseRef = useRef<HTMLButtonElement>(null)
  const boardReturnFocus = useRef(false)
  const scrollPositions = useRef<Record<string, number>>({})
  const taskList = [...seedTasks, monitorTask, ...state.createdTasks]
  const selected = taskList.find(task => task.id === selectedId) ?? taskList[0]
  const pending = taskList.filter(task => needsAttention(state, task))
  const running = taskList.filter(task => isRunning(state, task))
  const completed = state.decisions.length
  const tab = views[selected.id] ?? 'result'
  const currentRevision = revisionFor(state, selected)
  const viewedRevision = revisionViews[selected.id] ?? currentRevision
  const resolution = decisionFor(state, selected)
  const visibleTasks = taskList.filter(task => matchesFilter(state, task, filter) && matchesQuery(task, query, t))
  const pinned = !visibleTasks.some(task => task.id === selected.id) &&
    !query && !matchesFilter(state, selected, filter)

  useEffect(() => {
    if (loaded.error) return
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) }
    catch (error) {
      console.error('Unable to persist demo workspace', error)
      setStorageError(true)
    }
  }, [state, loaded.error])

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setModal(current => current === 'search' ? null : 'search')
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  useEffect(() => {
    if (detailRef.current) detailRef.current.scrollTop = scrollPositions.current[`${selected.id}:${tab}`] ?? 0
  }, [selected.id, tab, page, design, boardDetailOpen])

  const changeDesign = (next: Design) => {
    setDesign(next)
    if (next === 'd') setBoardDetailOpen(true)
    try {
      const url = new URL(window.location.href)
      url.searchParams.set('design', next)
      window.history.replaceState(null, '', url)
      localStorage.setItem('dayline-design', next)
      setAppearanceError(false)
    } catch (error) {
      console.error('Unable to save design preference', error)
      setAppearanceError(true)
    }
  }

  const update = (change: (previous: WorkspaceState) => WorkspaceState) => {
    try {
      const next = change(state)
      setState(next)
      setActionError('')
      return true
    } catch (error) {
      console.error('Demo action failed', error)
      setActionError(t('操作未完成，请检查任务当前状态后重试。', 'The action was not completed. Check the current task state and try again.'))
      return false
    }
  }
  const selectTask = (task: Task) => {
    setSelectedId(task.id)
    setMobileDetail(true)
    setBoardDetailOpen(true)
    if (design === 'd' && boardDetailOpen) boardCloseRef.current?.focus()
    setActionError('')
  }
  const setTab = (next: Tab) => setViews(previous => ({ ...previous, [selected.id]: next }))
  const nextTask = () => {
    const next = pending.find(task => task.id !== selected.id)
    if (next) selectTask(next)
  }
  const resolve = (kind: DecisionKind, note = '') => {
    if (update(previous => recordDecision(previous, selected, kind, note))) {
      setFeedbackOpen(previous => ({ ...previous, [selected.id]: false }))
      setDrafts(previous => ({ ...previous, [`review:${selected.id}`]: '' }))
      scrollPositions.current[`${selected.id}:${tab}`] = 0
      detailRef.current?.scrollTo({ top: 0 })
    }
  }
  const showTask = (task: Task) => {
    setPage('work')
    setFilter('all')
    setQuery('')
    selectTask(task)
    setModal(null)
  }

  const closeBoardDetail = () => {
    boardReturnFocus.current = true
    setBoardDetailOpen(false)
  }

  useEffect(() => {
    if (design !== 'd' || page !== 'work') return
    if (boardDetailOpen) boardCloseRef.current?.focus()
    else if (boardReturnFocus.current) {
      const target = boardRef.current?.querySelector<HTMLButtonElement>(`[data-task-id="${CSS.escape(selected.id)}"]`)
      if (target) target.focus()
      else if (selected.id.startsWith('local-')) boardRef.current?.querySelector<HTMLButtonElement>('.board-drafts-trigger')?.focus()
      else boardRef.current?.querySelector<HTMLInputElement>('input')?.focus()
      boardReturnFocus.current = false
    }
  }, [design, boardDetailOpen, selected.id, page])

  useEffect(() => {
    if (design !== 'd' || page !== 'work' || !boardDetailOpen || modal) return
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) {
        event.preventDefault()
        boardReturnFocus.current = true
        setBoardDetailOpen(false)
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [design, page, boardDetailOpen, modal])

  return (
    <div
      className="desktop-app"
      data-design={design}
      data-prototype-ready="true"
      data-research={researchMode ? 'true' : 'false'}
      data-summaries={showSummaries ? 'expanded' : 'compact'}
    >
      <header className="window-bar">
        <span><span className="mini-brand"><AudioLines size={14} /></span> Dayline <span className="window-channel">Preview</span></span>
        <span className="window-center"><LockKeyhole size={11} /> {t('个人工作空间', 'Personal workspace')}</span>
        <div className="window-controls" aria-hidden="true"><Minus size={14} /><Square size={11} /><X size={15} /></div>
      </header>
      <div className="app-frame">
        <aside className="global-sidebar">
          <div className="wordmark"><span className="brand-symbol"><AudioLines size={25} /></span><span className="wordmark-label">Dayline</span></div>
          <div className="workspace-identity"><span className="workspace-avatar">K</span><div><strong>{t('我的工作空间', 'My workspace')}</strong><small>{t('个人 · 本地', 'Personal · Local')}</small></div><LockKeyhole size={13} /></div>
          <span className="nav-caption">{t('工作空间', 'WORKSPACE')}</span>
          <nav aria-label={t('主导航', 'Main navigation')}>
            <button className={page === 'work' ? 'nav-item active' : 'nav-item'} title={t('工作', 'Work')} onClick={() => setPage('work')} aria-current={page === 'work' ? 'page' : undefined}><Layers3 size={18} />{t('工作', 'Work')}<span className="nav-count">{pending.length}</span></button>
            <button className={page === 'agents' ? 'nav-item active' : 'nav-item'} title={t('Agents 与连接', 'Agents')} onClick={() => setPage('agents')} aria-current={page === 'agents' ? 'page' : undefined}><Bot size={18} />{t('Agents 与连接', 'Agents')}</button>
            <button className={page === 'history' ? 'nav-item active' : 'nav-item'} title={t('工作记录', 'Activity')} onClick={() => setPage('history')} aria-current={page === 'history' ? 'page' : undefined}><History size={18} />{t('工作记录', 'Activity')}<span className="quiet-count">{completed || ''}</span></button>
          </nav>
          <div className="sidebar-spacer" />
          <div className="local-note"><LockKeyhole size={13} /><span>{t('本地演示环境', 'Local demo environment')}</span></div>
          <button className="nav-item settings-link" title={t('设置', 'Settings')} aria-label={t('设置', 'Settings')} onClick={() => setModal('settings')}><Settings2 size={17} />{t('设置', 'Settings')}<span className="language-hint" aria-hidden="true">{language === 'en' ? 'EN' : '中文'}</span></button>
          <div className="profile"><span className="profile-avatar">DU</span><div><strong>{t('演示用户', 'Demo User')}</strong><small>{t('个人工作空间', 'Personal workspace')}</small></div></div>
        </aside>
        <main className="main-surface">
          <header className="main-toolbar">
            <div className="breadcrumb"><span>{t('工作空间', 'Workspace')}</span><ChevronRight size={13} /><strong>{page === 'work' ? t('工作', 'Work') : page === 'agents' ? 'Agents' : t('工作记录', 'Activity')}</strong></div>
            <div className="toolbar-actions">
              {!researchMode && <div className="design-switch" role="group" aria-label={t('界面设计对比', 'Compare UI designs')}>
                <span className="design-switch-label">{t('设计', 'Design')}</span>
                <button type="button" aria-label={t('原型 A', 'Prototype A')} aria-pressed={design === 'a'} onClick={() => changeDesign('a')} title={t('A · 舒展列表，底部操作', 'A · Spacious list, bottom actions')}>A</button>
                <button type="button" aria-label={t('原型 B', 'Prototype B')} aria-pressed={design === 'b'} onClick={() => changeDesign('b')} title={t('B · 紧凑列表，侧边操作', 'B · Compact list, side actions')}>B</button>
                <button type="button" aria-label={t('原型 C', 'Prototype C')} aria-pressed={design === 'c'} onClick={() => changeDesign('c')} title={t('C · 控制中心，顶部决策', 'C · Control room, top actions')}>C</button>
                <button type="button" aria-label={t('原型 D', 'Prototype D')} aria-pressed={design === 'd'} onClick={() => changeDesign('d')} title={t('D · 状态看板，侧边详情', 'D · Kanban board, side details')}>D</button>
              </div>}
              <button className="command-button" onClick={() => setModal('search')} aria-label={t('搜索任务', 'Search tasks')}><Search size={15} /><span>{t('搜索任务', 'Search tasks')}</span><kbd>Ctrl K</kbd></button>
              <button className="primary small" onClick={() => setModal('new')}><Plus size={15} />{t('新建任务', 'New task')}</button>
            </div>
          </header>
          {(storageError || loaded.error) && <div className="error-banner" role="alert">{t('本地数据无法读取或保存。当前为临时会话；原有数据未被覆盖。', 'Local data could not be loaded or saved. This is a temporary session; existing data has not been overwritten.')}</div>}
          {appearanceError && <div className="error-banner" role="alert">{t('无法读取或保存界面偏好；当前仍可切换设计，任务数据不受影响。', 'The design preference could not be loaded or saved. You can still switch designs; task data is unaffected.')}</div>}
          {page === 'work' && <>
            <section className="work-heading">
              <div>
                {design === 'c' && <span className="control-room-label"><CircleDot size={12} />{t('控制中心 / 本地演示', 'CONTROL ROOM / LOCAL DEMO')}</span>}
                {design === 'd' && <span className="board-kicker"><Columns3 size={13} />{t('工作看板', 'WORK BOARD')}</span>}
                <h1>{design === 'd' ? t('让进展一目了然。', 'See the work flow.') : design === 'c' ? t('下一步，由你掌舵。', 'Make the next move.') : t('工作，井然有序。', 'A clearer view of your work.')}</h1>
                <p>{pending.length ? t(`有 ${pending.length} 项工作需要你的判断，其余正在有序推进。`, `${pending.length} things need your attention. The rest is moving along.`) : t('需要你的决定都已处理，可以继续查看进展。', 'Your decisions are taken care of. Keep an eye on what comes next.')}</p>
              </div>
              {design === 'c' ? <div className="control-room-stats" role="group" aria-label={t('工作概览', 'Work overview')}>
                <button className="overview-card attention-card" aria-label={t('查看需要你的工作', 'Show items needing you')} aria-pressed={filter === 'attention'} onClick={() => setFilter('attention')}><MessageSquare size={16} /><strong>{pending.length}</strong><span>{t('需要你', 'Needs you')}</span><ArrowUpRight size={14} /></button>
                <button className="overview-card" aria-label={t('查看执行中的工作', 'Show in-progress work')} aria-pressed={filter === 'running'} onClick={() => setFilter('running')}><Activity size={16} /><strong>{running.length}</strong><span>{t('执行中', 'In progress')}</span><ArrowUpRight size={14} /></button>
                <button className="overview-card" aria-label={t('查看全部工作', 'Show all work')} aria-pressed={filter === 'all'} onClick={() => setFilter('all')}><Layers3 size={16} /><strong>{taskList.length}</strong><span>{t('全部工作', 'All work')}</span><ArrowUpRight size={14} /></button>
              </div> : <span className="running-summary"><Activity size={14} /><strong>{running.length}</strong>{t('执行中', 'in progress')}</span>}
            </section>
            <div className={`workbench ${mobileDetail ? 'show-detail' : ''} ${design === 'd' && boardDetailOpen ? 'board-detail-open' : ''}`}>
              {design === 'd' ? <div className="board-surface" ref={boardRef}>
                <TaskBoard tasks={taskList} state={state} activeId={boardDetailOpen ? selected.id : undefined} query={query} onQuery={setQuery} onSelect={selectTask} />
              </div> : <section className="work-list" aria-label={t('工作列表', 'Work list')}>
                <div className="list-top"><h2>{t('我的工作', 'Your work')}</h2><span>{taskList.length}</span><ListFilter size={15} /></div>
                {design === 'b' && <div className="density-control"><span>{t('列表显示', 'List detail')}</span><button className="density-button" aria-pressed={showSummaries} onClick={() => setShowSummaries(value => !value)}>{t('显示摘要', 'Show summaries')}<span aria-hidden="true" className="density-toggle" /></button></div>}
                <div className="filter-tabs" aria-label={t('工作筛选', 'Work filters')}>
                  {(['attention', 'running', 'all'] as const).map(value => <button key={value} aria-pressed={filter === value} className={filter === value ? 'selected' : ''} onClick={() => setFilter(value)}>{value === 'attention' ? t('需要你', 'Needs you') : value === 'running' ? t('执行中', 'In progress') : t('全部', 'All')} {value === 'attention' && <span>{pending.length}</span>}</button>)}
                </div>
                <div className="list-search"><Search size={14} /><input aria-label={t('筛选工作', 'Filter work')} placeholder={t('按任务或 Agent 筛选…', 'Filter tasks or agents…')} value={query} onChange={event => setQuery(event.target.value)} />{query && <button className="icon-button" aria-label={t('清空搜索', 'Clear search')} onClick={() => setQuery('')}><X size={13} /></button>}</div>
                <div className="task-list-scroll">
                  <p className="list-section-label">{filter === 'attention' ? t('等待你的决定', 'WAITING FOR YOUR DECISION') : filter === 'running' ? t('正在推进', 'MOVING FORWARD') : t('所有工作', 'ALL WORK')}</p>
                  {visibleTasks.map(task => <TaskRow key={task.id} task={task} selected={selected.id === task.id} state={state} onClick={() => selectTask(task)} />)}
                  {!visibleTasks.length && <div className="list-empty"><CheckCheck size={25} /><strong>{query ? t('没有匹配的工作', 'No matching work') : t('这里都处理好了', 'All clear here')}</strong><p>{t('切换筛选，查看其他工作。', 'Choose another filter to see more work.')}</p></div>}
                  {pinned && <><p className="list-section-label">{resolution ? t('刚刚处理 · 保留当前结果', 'JUST HANDLED · RESULT KEPT OPEN') : t('当前任务 · 不在此筛选中', 'OPEN TASK · OUTSIDE THIS FILTER')}</p><TaskRow task={selected} selected state={state} onClick={() => selectTask(selected)} /></>}
                </div>
                <div className="list-footer"><LockKeyhole size={12} />{t('选择任务，不离开当前视图', 'One workspace. No context switching.')}</div>
              </section>}
              {(design !== 'd' || boardDetailOpen) && <section className="task-detail" data-task-id={selected.id} id={design === 'd' ? 'board-detail' : undefined} aria-label={design === 'd' ? t('任务详情面板', 'Task detail panel') : undefined}>
                {design === 'd' && <div className="board-detail-toolbar"><span><FileCheck2 size={14} />{t('任务详情', 'TASK DETAILS')}</span><button className="text-button" ref={boardCloseRef} onClick={closeBoardDetail} aria-label={t('返回看板', 'Back to board')}>{t('返回看板', 'Back to board')}<X size={16} /></button></div>}
                <div className="task-detail-header">
                  <button className="mobile-back text-button" onClick={() => setMobileDetail(false)}><ArrowDownLeft size={14} />{t('工作列表', 'Work list')}</button>
                  <div className="task-overline"><span className="task-id">{selected.id.startsWith('local-') ? 'LOCAL' : `DL-${taskNumbers[selected.id]}`}</span><ChevronRight size={12} /><span>{fixture(selected, selected.project, t)}</span><span className={`status-badge ${needsAttention(state, selected) ? 'attention' : 'neutral'}`}><CircleDot size={11} />{statusText(selected, state, t)}</span></div>
                  <h2>{fixture(selected, selected.title, t)}</h2>
                  <p className="task-goal">{fixture(selected, selected.goal, t)}</p>
                  <div className="task-byline"><span className={`agent-icon ${selected.tone}`}><Bot size={13} /></span><strong>{selected.agent}</strong><span className="byline-divider" /><Monitor size={12} /><span>{selected.agent.includes('HTTP') ? 'Remote / HTTP' : 'Windows / Local'}</span><span className="byline-divider" /><span>{t('演示任务', 'Demo task')}</span></div>
                </div>
                <div className="detail-tabs" role="tablist" aria-label={t('任务详情', 'Task details')}>
                  {(['result', 'activity', 'context'] as const).map(value => <button key={value} role="tab" id={`tab-${value}`} aria-selected={tab === value} aria-controls="detail-content" onClick={() => setTab(value)} className={tab === value ? 'active' : ''}>{value === 'result' ? <FileCheck2 size={15} /> : value === 'activity' ? <Activity size={15} /> : <Folder size={15} />}{value === 'result' ? t('工作成果', 'Result') : value === 'activity' ? t('执行过程', 'Workstream') : t('任务背景', 'Context')}{value === 'activity' && <span>{selected.activities.length + state.decisions.filter(d => d.taskId === selected.id).length + state.notes.filter(n => n.taskId === selected.id).length}</span>}</button>)}
                  <span className="detail-scope"><LockKeyhole size={11} />{t('仅此任务', 'This task only')}</span>
                </div>
                <div className="detail-scroll" id="detail-content" role="tabpanel" aria-labelledby={`tab-${tab}`} ref={detailRef} onScroll={event => { scrollPositions.current[`${selected.id}:${tab}`] = event.currentTarget.scrollTop }}>
                  {actionError && <div className="error-banner" role="alert">{actionError}</div>}
                  {resolution && <ResolutionCard decision={resolution} hasNext={pending.some(task => task.id !== selected.id)} onNext={nextTask} onReceipt={() => update(s => simulateReceipt(s, selected))} onRevision={() => {
                    if (update(s => simulateRevision(s, selected))) {
                      setRevisionViews(v => ({ ...v, [selected.id]: currentRevision + 1 }))
                      setTab('result')
                    }
                  }} />}
                  {tab === 'result' && <TaskResult task={selected} state={state} viewedRevision={viewedRevision} onRevisionChange={revision => setRevisionViews(v => ({ ...v, [selected.id]: revision }))} choice={resolution?.kind === 'clarify' ? resolution.note : choices[selected.id] ?? 'focused'} onChoice={choice => setChoices(v => ({ ...v, [selected.id]: choice }))} onContext={() => setTab('context')} />}
                  {tab === 'activity' && <Workstream task={selected} state={state} draft={drafts[`note:${selected.id}`] ?? ''} onDraft={body => setDrafts(v => ({ ...v, [`note:${selected.id}`]: body }))} onSend={() => {
                    const body = drafts[`note:${selected.id}`]?.trim()
                    if (!body) return
                    update(s => ({ ...s, notes: [...s.notes, { taskId: selected.id, body, at: new Date().toISOString() }] }))
                    setDrafts(v => ({ ...v, [`note:${selected.id}`]: '' }))
                  }} />}
                  {tab === 'context' && <TaskContext task={selected} />}
                </div>
                {needsAttention(state, selected) ? <DecisionBar task={selected} currentRevision={currentRevision} viewedRevision={viewedRevision} showCurrent={() => { setRevisionViews(v => ({ ...v, [selected.id]: currentRevision })); setTab('result') }} tab={tab} onReview={() => setTab('result')} feedbackOpen={feedbackOpen[selected.id] ?? false} onFeedbackOpen={open => setFeedbackOpen(v => ({ ...v, [selected.id]: open }))} feedback={drafts[`review:${selected.id}`] ?? ''} onFeedback={body => setDrafts(v => ({ ...v, [`review:${selected.id}`]: body }))} choice={choices[selected.id] ?? 'focused'} onResolve={resolve} /> :
                  <div className="settled-footer"><CheckCheck size={15} /><span>{resolution ? t('决定已记录。你仍在同一个任务中。', 'Decision saved. You are still in the same task.') : t('当前无需决定', 'No decision needed right now')}</span>{pending.some(task => task.id !== selected.id) && <button className="text-button" onClick={nextTask}>{t('下一项', 'Next item')}<ArrowRight size={14} /></button>}</div>}
              </section>}
            </div>
          </>}
          {page === 'agents' && <AgentsPage />}
          {page === 'history' && <HistoryPage state={state} tasks={taskList} onTask={showTask} />}
          <footer className="app-status"><span><span className="blue-dot" />{t('M0 演示 · 合成数据，无真实 Agent 连接', 'M0 preview · Synthetic data, no live agent connections')}</span><span><LockKeyhole size={11} />{storageError ? t('临时会话', 'Temporary session') : t('保存在此浏览器', 'Saved in this browser')}</span></footer>
        </main>
      </div>
      {modal === 'settings' && <SettingsDialog onClose={() => setModal(null)} />}
      {modal === 'new' && <NewTaskDialog onClose={() => setModal(null)} onCreate={(title, goal, agent) => {
        const task = createLocalTask(`local-${crypto.randomUUID()}`, title, goal, agent)
        update(s => ({ ...s, createdTasks: [...s.createdTasks, task] }))
        showTask(task)
      }} />}
      {modal === 'search' && <SearchDialog tasks={taskList} onClose={() => setModal(null)} onSelect={showTask} />}
    </div>
  )
}

function TaskBoard({ tasks, state, activeId, query, onQuery, onSelect }: {
  tasks: Task[]; state: WorkspaceState; activeId?: string; query: string
  onQuery: (query: string) => void; onSelect: (task: Task) => void
}) {
  const { t } = useLocale()
  const [draftsOpen, setDraftsOpen] = useState(false)
  const draftsRef = useRef<HTMLDivElement>(null)
  const draftsButtonRef = useRef<HTMLButtonElement>(null)
  const drafts = tasks.filter(task => boardColumnFor(state, task) === 'draft')
  const matching = tasks.filter(task => boardColumnFor(state, task) !== 'draft' && matchesQuery(task, query, t))
  useEffect(() => {
    if (!draftsOpen) return
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !draftsRef.current?.contains(event.target)) setDraftsOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [draftsOpen])
  const columns = [
    { id: 'attention', label: t('需要你', 'Needs you'), description: t('验收、授权或确认范围', 'Review, authorize or clarify') },
    { id: 'running', label: t('执行中', 'In progress'), description: t('正在推进或等待回应', 'Working or awaiting a response') },
    { id: 'handled', label: t('已处理', 'Handled'), description: t('已验收、已拒绝或已完成', 'Accepted, declined or completed') },
  ] as const
  return <>
    <div className="board-toolbar">
      <div className="board-view-label"><Columns3 size={16} /><strong>{t('状态看板', 'Status board')}</strong><span>{t(`${matching.length} 项工作`, `${matching.length} items`)}</span></div>
      <div className="board-toolbar-actions">
        {drafts.length > 0 && <div className="board-drafts" ref={draftsRef} onKeyDown={event => {
          if (event.key === 'Escape' && draftsOpen) {
            event.preventDefault()
            event.stopPropagation()
            setDraftsOpen(false)
            draftsButtonRef.current?.focus()
          }
        }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setDraftsOpen(false) }}>
          <button className="board-drafts-trigger" ref={draftsButtonRef} aria-label={t('本地草稿', 'Local drafts')} aria-expanded={draftsOpen} aria-controls={draftsOpen ? 'board-drafts' : undefined} onClick={() => setDraftsOpen(open => !open)}><FileText size={14} />{t('草稿', 'Drafts')}<span>{drafts.length}</span><ChevronDown size={12} /></button>
          {draftsOpen && <section className="board-draft-popover" id="board-drafts" aria-label={t('本地草稿', 'Local drafts')}>
            <p>{t('尚未发送给 Agent', 'Not sent to an agent')}</p>
            {drafts.map(task => <TaskRow task={task} selected={activeId === task.id} state={state} onClick={() => { setDraftsOpen(false); onSelect(task) }} board expanded={activeId === task.id} key={task.id} />)}
          </section>}
        </div>}
        <div className="list-search"><Search size={14} /><input aria-label={t('筛选工作', 'Filter work')} placeholder={t('按任务或 Agent 筛选…', 'Filter tasks or agents…')} value={query} onChange={event => onQuery(event.target.value)} />{query && <button className="icon-button" aria-label={t('清空搜索', 'Clear search')} onClick={() => onQuery('')}><X size={13} /></button>}</div>
      </div>
    </div>
    {query && !matching.length && <p className="board-no-results" role="status">{t('没有匹配的工作，清空搜索可查看全部卡片。', 'No matching work. Clear search to see all cards.')}</p>}
    <div className="kanban-lanes" role="region" aria-label={t('任务看板', 'Task board')} tabIndex={0}>
      {columns.map(column => {
        const items = matching.filter(task => boardColumnFor(state, task) === column.id)
        return <section className={`board-column column-${column.id}`} data-column={column.id} key={column.id} aria-labelledby={`board-column-${column.id}`}>
          <header className="board-column-heading"><h2 id={`board-column-${column.id}`}><span className="board-dot" aria-hidden="true" />{column.label}<span className="board-column-count">{items.length}</span></h2><p>{column.description}</p></header>
          <div className="board-column-cards">
            {items.map(task => <TaskRow task={task} selected={activeId === task.id} state={state} onClick={() => onSelect(task)} board expanded={activeId === task.id} key={task.id} />)}
            {!items.length && <div className="board-column-empty"><Columns3 size={20} /><span>{t('暂无工作', 'No items here')}</span></div>}
          </div>
        </section>
      })}
    </div>
    <p className="board-note"><ShieldCheck size={13} />{t('卡片随任务进展与决定自动流转，不支持拖拽跳过审批。', 'Cards move with progress and decisions. No drag-to-approve.')}</p>
  </>
}

function TaskRow({ task, selected, state, onClick, board = false, expanded }: {
  task: Task; selected: boolean; state: WorkspaceState; onClick: () => void; board?: boolean; expanded?: boolean
}) {
  const { t } = useLocale()
  const pending = needsAttention(state, task)
  return <button className={`task-row ${selected ? 'selected' : ''}`} onClick={onClick} aria-pressed={selected} data-task-id={task.id} aria-expanded={expanded} aria-controls={board && expanded ? 'board-detail' : undefined}>
    <div className="row-meta"><span className={`row-type ${task.tone}`}>{task.decisionType === '验收' ? <GitCompareArrows size={13} /> : task.decisionType === '授权' ? <ShieldCheck size={13} /> : task.decisionType === '澄清' ? <MessageSquare size={13} /> : <Activity size={13} />}{pending ? t(task.decisionType ?? '') : statusText(task, state, t)}</span><span>{t(task.updatedAt)}</span></div>
    <strong>{fixture(task, task.title, t)}</strong>
    {board && <span className="board-card-meta">{fixture(task, task.project, t)}{task.artifact && <span>{task.artifact.name} · v{revisionFor(state, task)}</span>}</span>}
    <p>{pending ? task.decisionType === '验收' ? t('新版本已准备好，查看修改与反馈。', 'A new version is ready. Review the changes.') : task.decisionType === '授权' ? t('发送前，核对内容与接收对象。', 'Check the message and destination before sending.') : t('确定研究范围，让工作继续。', 'Set the scope so the work can continue.') : statusText(task, state, t)}</p>
    <div className="row-agent"><span className={`agent-icon ${task.tone}`}><Bot size={12} /></span>{task.agent}{pending ? <span className="row-indicator" /> : board && isRunning(state, task) ? <Clock3 size={12} /> : board && task.id.startsWith('local-') ? <FileText size={12} /> : <Check size={12} />}</div>
  </button>
}

function TaskResult({ task, state, viewedRevision, onRevisionChange, choice, onChoice, onContext }: {
  task: Task; state: WorkspaceState; viewedRevision: number; onRevisionChange: (revision: number) => void
  choice: string; onChoice: (choice: string) => void; onContext: () => void
}) {
  const { t } = useLocale()
  const revision = revisionFor(state, task)
  const feedback = [...state.decisions].reverse().find(d => d.taskId === task.id && d.kind === 'revise' && d.revision < viewedRevision)
  if (task.id === 'readme') return <>
    <div className="decision-intro"><span className="section-kicker">{t('产物验收', 'ARTIFACT REVIEW')}</span><h3>{t('更清晰的边界。等你确认。', 'A clearer story. Ready for your review.')}</h3><p>{t('核对这次修改是否回应了你的反馈。接受不会触发发布。', 'Check that this revision addresses your feedback. Accepting does not publish anything.')}</p></div>
    <div className="feedback-note"><span className="note-icon"><MessageSquare size={16} /></span><div><div className="note-heading"><strong>{t('你的上次反馈', 'Your last feedback')}</strong><span>{feedback ? t(`关联 v${feedback.revision} → v${viewedRevision}`, `Linked to v${feedback.revision} → v${viewedRevision}`) : t('关联 v2 → v3', 'Linked to v2 → v3')}</span></div><p>{feedback ? feedback.note : t('请明确区分“审批已通过”和“外部动作已完成”，不要把演示数据描述成真实连接。')}</p></div></div>
    {revision > 3 && <div className="sample-note"><InfoDot />{t('这是模拟返回的新版本，示例正文没有自动落实任意修改要求。请再次核对。', 'This is a simulated new revision. The sample text has not automatically implemented arbitrary feedback. Review it again.')}</div>}
    <article className="artifact-card">
      <header className="artifact-heading"><span className="file-emblem"><FileText size={19} /></span><div><strong>README.md</strong><span>{t('版本化产物 · 合成示例', 'Versioned artifact · Synthetic sample')}</span></div><label className="version-picker"><span className="sr-only">{t('产物版本', 'Artifact version')}</span><select value={viewedRevision} onChange={event => onRevisionChange(Number(event.target.value))}>{Array.from({ length: revision - 1 }, (_, i) => revision - i).map(v => <option key={v} value={v}>v{v}{v === revision ? t(' · 最新', ' · Latest') : ''}</option>)}</select><ChevronDown size={12} /></label></header>
      <div className="artifact-subbar"><span><GitCompareArrows size={13} />{viewedRevision >= 3 ? t('修改前后', 'Before & after') : t('历史版本', 'Previous version')}</span><span className="diff-stat">{viewedRevision >= 3 ? t('2 处关键修改', '2 key changes') : 'v2'}</span></div>
      <div className="document-body"><div className="document-brand"><AudioLines size={24} /><span>Dayline</span></div><p className="document-lead">{t('一个面向个人的 Agent 工作监督台。')}</p><h4>{t('为什么做 Dayline')}</h4><p>{t('当多个 Agent 同时工作时，真正稀缺的不是更多对话，而是人的注意力。')}</p>
        {viewedRevision >= 3 && <div className="diff-block addition"><span>+</span><p>{t('本仓库当前提供交互原型，不代表已接入真实 Agent 或安全执行通道。')}</p></div>}
        <h4>{t('状态如何解释')}</h4><div className={`diff-block ${viewedRevision >= 3 ? 'deletion' : ''}`}><span>{viewedRevision >= 3 ? '−' : '·'}</span><p>{t('批准后，消息将被成功发送。')}</p></div>
        {viewedRevision >= 3 && <div className="diff-block addition"><span>+</span><p>{t('批准仅代表授权；外部动作是否成功以执行回执为准。')}</p></div>}
        <div className="document-end"><span />{t('预览示例结束', 'END OF SAMPLE')}<span /></div>
      </div>
    </article>
    <div className="evidence-strip"><span><ShieldCheck size={15} />{t('人工验收，不等于事实验证', 'Human review, not proof of correctness')}</span><button className="text-button" onClick={onContext}>{t('查看来源与范围', 'Sources & scope')}<ArrowUpRight size={13} /></button></div>
  </>
  if (task.id === 'update') return <>
    <div className="decision-intro"><span className="section-kicker">{t('单次动作授权', 'ONE-TIME AUTHORIZATION')}</span><h3>{t('发送之前，最后确认。', 'One last look before it goes out.')}</h3><p>{t('内容已验收；现在只决定是否向指定测试频道发送 v2。', 'The content is accepted. Decide only whether to send v2 to the specified test channel.')}</p></div>
    <section className="action-scope"><div className="scope-title"><ShieldCheck size={17} /><strong>{t('本次授权范围', 'Exactly what you authorize')}</strong><span className="risk-tag">{t('中风险', 'Medium risk')}</span></div><dl><div><dt>{t('动作', 'Action')}</dt><dd>message.publish</dd></div><div><dt>{t('接收对象', 'Destination')}</dt><dd>#dayline-preview <small>{t('测试工作区 · 12 位成员', 'Test workspace · 12 members')}</small></dd></div><div><dt>{t('绑定内容', 'Bound content')}</dt><dd>weekly-update.md · v2<small>{t('不含附件', 'No attachments')}</small></dd></div><div><dt>{t('授权边界', 'Permission boundary')}</dt><dd>{t('仅此版本、此对象、这一次', 'This version, this destination, once')}<small>{t('内容或对象改变需重新授权', 'Changed content or destination requires new authorization')}</small></dd></div></dl><p className="scope-warning">{t('发送后接收方可能已经阅读；保留本地旧版本不能撤回消息。', 'Recipients may read a sent message. Keeping an older local version cannot recall it.')}</p></section>
    <article className="artifact-card message-artifact"><header className="artifact-heading"><span className="file-emblem violet"><Send size={18} /></span><div><strong>weekly-update.md</strong><span>v2 · {t('已验收', 'Accepted')}</span></div><span className="private-label"><LockKeyhole size={12} />{t('尚未发送', 'Not sent')}</span></header><div className="message-document"><div className="destination"><span>#</span><div><strong>dayline-preview</strong><small>{t('模拟发送预览', 'Simulated message preview')}</small></div></div><h4>{t('Dayline 本周进展')}</h4><p>{t('大家好，本周我们完成了产品边界与第一阶段原型方向的收敛。')}</p><h5>{t('本周已完成')}</h5><ul><li>{t('明确以“人的注意力与决定”为核心组织工作')}</li><li>{t('区分执行完成、产物验收和外部动作成功')}</li><li>{t('确定两个原型研究方向')}</li></ul><p className="message-signature">— Dayline</p></div></article>
    <div className="sample-note"><InfoDot />{t('原型不会发送消息。授权和执行回执将分别显示。', 'This prototype will not send a message. Authorization and execution receipts are shown separately.')}</div>
  </>
  if (task.id === 'research') return <>
    <div className="decision-intro"><span className="section-kicker">{t('范围澄清', 'A QUESTION OF SCOPE')}</span><h3>{t('往深处走，还是先聚焦？', 'Go broader, or stay focused?')}</h3><p>{t('是否把团队协作产品纳入第一轮对比？预计增加 35 分钟。')}</p></div>
    <div className="research-summary"><Search size={23} /><div><strong>{t('第一轮资料已就绪', 'The first research pass is ready')}</strong><p>{t('6 个产品 · 18 条模拟来源记录 · 尚无最终结论', '6 products · 18 simulated source records · No final conclusion yet')}</p></div></div>
    <fieldset className="scope-choices" disabled={!needsAttention(state, task)}><legend>{t('研究范围', 'Research scope')}</legend>{[
      { id: 'focused', title: t('保持个人工具范围'), body: t('先完成当前 6 个产品，避免第一轮研究过宽。'), time: t('预计 18 分钟完成'), recommended: true },
      { id: 'include', title: t('纳入团队协作产品'), body: t('增加交接、共享验收和角色边界的对比。'), time: t('预计增加 35 分钟'), recommended: false },
    ].map(option => <label key={option.id} className={`scope-choice ${choice === option.id ? 'selected' : ''}`}><input type="radio" name="research-scope" value={option.id} checked={choice === option.id} onChange={() => onChoice(option.id)} /><div><strong>{option.title}{option.recommended && <span>{t('建议', 'Suggested')}</span>}</strong><p>{option.body}</p><small><Clock3 size={12} />{option.time}</small></div></label>)}</fieldset>
    <div className="sample-note"><InfoDot />{t('这是范围选择，不是对外部动作的授权。', 'This is a scope decision, not authorization for an external action.')}</div>
  </>
  return <div className="progress-result"><span className="progress-orbit">{task.status === 'done' ? <CheckCheck size={30} /> : <Activity size={30} />}</span><span className="section-kicker">{t('任务进展', 'TASK PROGRESS')}</span><h3>{task.status === 'done' ? t('检查清单已验收', 'Checklist accepted') : task.id.startsWith('local-') ? t('任务已保存在本地', 'Your task is saved locally') : t('工作正在推进', 'Work is moving forward')}</h3><p>{task.id.startsWith('local-') ? t('这是本地演示草稿，没有向任何 Agent 发送任务。', 'This is a local demo draft. No task has been sent to an agent.') : fixture(task, task.summary, t)}</p>{task.id === 'checks' && <div className="run-progress"><div><span>{t('模拟检查进度', 'Simulated check progress')}</span><strong>42%</strong></div><span><i style={{ width: '42%' }} /></span></div>}<div className="sample-note"><LockKeyhole size={14} />{t('没有真实执行或外部写入', 'No live execution or external writes')}</div></div>
}

function InfoDot() { return <CircleDot size={15} /> }

function DecisionBar({ task, currentRevision, viewedRevision, showCurrent, tab, onReview, feedbackOpen, onFeedbackOpen, feedback, onFeedback, choice, onResolve }: {
  task: Task; currentRevision: number; viewedRevision: number; showCurrent: () => void; tab: Tab; onReview: () => void
  feedbackOpen: boolean; onFeedbackOpen: (open: boolean) => void; feedback: string; onFeedback: (value: string) => void
  choice: string; onResolve: (kind: DecisionKind, note?: string) => void
}) {
  const { t } = useLocale()
  if (task.id === 'readme' && viewedRevision !== currentRevision) return <div className="decision-footer"><span>{t('历史版本只读，请审阅最新版本。', 'Previous version is read-only. Review the latest version.')}</span><button className="primary" onClick={showCurrent}>{t('查看最新版本', 'View latest revision')}<ArrowRight size={14} /></button></div>
  if (tab !== 'result') return <div className="decision-footer"><div className="footer-hint"><CircleDot size={15} />{t('决定前先检查工作成果', 'Review the result before deciding')}</div><button className="primary" onClick={onReview}>{t('查看工作成果', 'Review result')}<ArrowRight size={15} /></button></div>
  return <div className="decision-footer-wrap">
    <div className="decision-side-summary">
      <span className="section-kicker">{t('当前决定', 'YOUR DECISION')}</span>
      <h3>{task.decisionType === '验收' ? t('验收此版本', 'Review this revision') : task.decisionType === '授权' ? t('单次授权', 'Authorize once') : t('确认范围', 'Confirm the scope')}</h3>
      <dl>
        <div><dt>{t('对应任务', 'Task')}</dt><dd>{task.id.startsWith('local-') ? 'LOCAL' : `DL-${taskNumbers[task.id]}`}</dd></div>
        {task.artifact && <div><dt>{t('产物', 'Artifact')}</dt><dd>{task.artifact.name} · v{currentRevision}</dd></div>}
        {task.decisionType === '授权' && <div><dt>{t('接收对象', 'Destination')}</dt><dd>#dayline-preview</dd></div>}
      </dl>
      <p>{t('只决定当前这件事。完整内容与依据在左侧。', 'Decide on this item only. Review the full content and evidence alongside.')}</p>
    </div>
    {feedbackOpen && <form className="revision-form" onSubmit={event => { event.preventDefault(); if (feedback.trim()) onResolve('revise', feedback) }}><label htmlFor="revision-feedback">{t('需要修改什么？', 'What needs to change?')}</label><textarea id="revision-feedback" value={feedback} onChange={event => onFeedback(event.target.value)} placeholder={t('指出具体段落、问题或验收条件…', 'Name the section, issue, or acceptance criteria…')} required rows={3} /><div><button type="button" className="secondary" onClick={() => onFeedbackOpen(false)}>{t('取消', 'Cancel')}</button><button className="primary" disabled={!feedback.trim()}>{t('提交修改要求', 'Send revision request')}<Send size={14} /></button></div></form>}
    {!feedbackOpen && <div className="decision-footer"><div className="footer-hint"><ShieldCheck size={17} /><span>{task.decisionType === '验收' ? t('仅验收产物，不会发布', 'Accept the artifact. Nothing is published.') : task.decisionType === '授权' ? t('一次授权，不等于发送成功', 'Authorization is not a delivery receipt.') : t('只调整本任务的研究范围', 'Only changes the scope of this task.')}</span></div><div className="decision-buttons">
      {task.decisionType === '验收' && <><button className="secondary" onClick={() => onFeedbackOpen(true)}>{t('要求修改', 'Request changes')}</button><button className="primary" onClick={() => onResolve('accept')}><Check size={16} />{t(`接受 v${currentRevision}`, `Accept v${currentRevision}`)}</button></>}
      {task.decisionType === '授权' && <><button className="secondary" onClick={() => onResolve('reject')}>{t('拒绝', 'Decline')}</button><button className="primary" onClick={() => onResolve('approve')}><ShieldCheck size={16} />{t('仅授权这一次', 'Authorize once')}</button></>}
      {task.decisionType === '澄清' && <button className="primary" onClick={() => onResolve('clarify', choice)}>{t('确认范围', 'Confirm scope')}<ArrowRight size={15} /></button>}
    </div></div>}
  </div>
}

function ResolutionCard({ decision, hasNext, onNext, onReceipt, onRevision }: { decision: Decision; hasNext: boolean; onNext: () => void; onReceipt: () => void; onRevision: () => void }) {
  const { t } = useLocale()
  return <section className="resolution-card" role="status"><span className="resolution-icon"><Check size={18} /></span><div><strong>{decisionTitle(decision, t)}</strong><p>{decision.kind === 'approve' ? decision.receipt ? t('这是模拟回执，没有真实发送。', 'This is a simulated receipt. Nothing was actually sent.') : t('授权已保存，但尚未收到执行回执。不要重复发送。', 'Authorization is saved, but there is no execution receipt yet. Do not send again.') :
    decision.kind === 'accept' ? t('只接受了此版本，没有批准任何后续发布动作。', 'This version is accepted. No subsequent publishing action was authorized.') :
    decision.kind === 'revise' ? t('反馈已关联到此版本，等待 Agent 返回新版本。', 'Your feedback is linked to this revision. Waiting for a new version.') :
    decision.kind === 'reject' ? t('消息仍为私人产物，没有发送。', 'The message remains a private artifact and has not been sent.') :
    t('选择已记录。演示中的研究任务可以继续。', 'Your choice is recorded. The simulated research task can continue.')}</p>
    {decision.note && <blockquote>{decision.kind === 'clarify' ? decision.note === 'focused' ? t('保持个人工具范围') : t('纳入团队协作产品') : decision.note}</blockquote>}
    {decision.receipt && <code>{decision.receipt}</code>}
    <div className="resolution-links">{decision.kind === 'approve' && !decision.receipt && <button className="text-button" onClick={onReceipt}>{t('演示：生成模拟回执', 'Demo: generate simulated receipt')}<ArrowUpRight size={12} /></button>}{decision.kind === 'revise' && <button className="text-button" onClick={onRevision}>{t('演示：返回新版本', 'Demo: return a new revision')}<ArrowUpRight size={12} /></button>}{hasNext && <button className="text-button" onClick={onNext}>{t('处理下一项', 'Next item')}<ArrowRight size={13} /></button>}</div></div></section>
}

function Workstream({ task, state, draft, onDraft, onSend }: { task: Task; state: WorkspaceState; draft: string; onDraft: (value: string) => void; onSend: () => void }) {
  const { t, language } = useLocale()
  const history = [
    ...state.decisions.filter(d => d.taskId === task.id).map(d => ({ at: d.at, title: decisionTitle(d, t), body: d.kind === 'clarify' ? d.note === 'focused' ? t('保持个人工具范围') : t('纳入团队协作产品') : d.note, revision: d.revision })),
    ...state.notes.filter(n => n.taskId === task.id).map(n => ({ at: n.at, title: t('你的补充说明 · 仅本地', 'Your note · local only'), body: n.body, revision: null })),
  ].sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
  return <div className="stream-content"><div className="decision-intro"><span className="section-kicker">{t('上下文始终在这里', 'THE CONTEXT IS ALWAYS HERE')}</span><h3>{t('这件工作，如何走到现在。', 'How this work got here.')}</h3><p>{t('执行记录、你的反馈与每一次决定，都属于同一个任务。', 'Progress, feedback, and every decision belong to this task.')}</p></div><div className="timeline">
    {task.activities.map(activity => <article key={activity.id}><span className={`timeline-icon ${activity.actor === 'human' ? 'human' : ''}`}>{activity.actor === 'human' ? <MessageSquare size={14} /> : <Bot size={14} />}</span><div><div className="timeline-title"><strong>{t(activity.title)}</strong><time>{t(activity.time)}</time></div><p>{t(activity.body)}</p>{activity.kind === 'artifact' && <span className="timeline-artifact"><FileText size={13} />README.md · v3</span>}</div></article>)}
    {history.map((entry, i) => <article key={`${entry.at}-${i}`}><span className="timeline-icon human"><Check size={14} /></span><div><div className="timeline-title"><strong>{entry.title}{entry.revision && ` · v${entry.revision}`}</strong><time>{new Date(entry.at).toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit' })}</time></div>{entry.body && <p className="user-text">{entry.body}</p>}</div></article>)}
    {!task.activities.length && !history.length && <p className="sample-note">{t('本地任务已创建，没有真实执行记录。', 'Local task created. No live execution records yet.')}</p>}
  </div><form className="composer" onSubmit={event => { event.preventDefault(); onSend() }}><label className="sr-only" htmlFor="task-note">{t('补充说明', 'Task note')}</label><textarea id="task-note" value={draft} onChange={event => onDraft(event.target.value)} placeholder={t('补充要求或记录想法…', 'Add direction or leave a note…')} rows={3} /><div><span><LockKeyhole size={12} />{t('仅保存在本地，不会发送给 Agent', 'Saved locally. Not sent to an agent.')}</span><button className="primary small" disabled={!draft.trim()}>{t('保存说明', 'Save note')}<ArrowRight size={14} /></button></div></form></div>
}

function TaskContext({ task }: { task: Task }) {
  const { t } = useLocale()
  return <div className="context-content"><div className="decision-intro"><span className="section-kicker">{t('任务背景', 'CONTEXT & BOUNDARIES')}</span><h3>{t('目标清楚，边界明确。', 'A clear goal. Clear boundaries.')}</h3></div><section className="context-section"><h4>{t('任务目标', 'The goal')}</h4><p>{fixture(task, task.goal, t)}</p></section><section className="context-section"><h4>{t('完成条件', 'Definition of done')}</h4><ul><li>{t('产物可以检查，修改与反馈对应。', 'An inspectable artifact with changes linked to feedback.')}</li><li>{t('人工验收与外部动作授权分别记录。', 'Human acceptance and external authorization are separate.')}</li><li>{t('需要发送时，以目标端回执确认结果。', 'Where delivery is required, a destination receipt confirms the outcome.')}</li></ul></section><section className="context-section"><h4>{t('参考材料', 'Reference materials')}</h4><div className="source-item"><FileText size={18} /><div><strong>{task.id === 'readme' ? 'Product brief / README v2' : 'Project brief / Weekly notes'}</strong><span>{t('仅为合成示例引用，不是可打开的真实文件', 'Synthetic reference labels, not live files')}</span></div><span className="demo-chip">DEMO</span></div></section><section className="context-section"><h4>{t('执行身份与能力', 'Agent & capabilities')}</h4><dl className="context-facts"><div><dt>Agent</dt><dd>{task.agent}</dd></div><div><dt>{t('演示能力等级', 'Illustrated capability')}</dt><dd>{task.agentMode}</dd></div><div><dt>{t('真实连接状态', 'Live connection')}</dt><dd>{t('未连接', 'Not connected')}</dd></div></dl><p className="sample-note">{task.agentMode === 'Observe' ? t('只读观察，不提供暂停、取消或阻止执行能力。', 'Observe only. No pause, cancel, or enforcement controls.') : t('界面演示能力不代表实际安全边界；真实接入需要适配器确认。', 'Illustrated capabilities are not enforced security guarantees. A live adapter must verify them.')}</p></section></div>
}

function AgentsPage() {
  const { t } = useLocale()
  return <section className="utility-page"><span className="section-kicker">{t('连接你的工作', 'CONNECT YOUR WORK')}</span><h1>{t('Agent 与连接', 'Your agents, together.')}</h1><p>{t('先定义能力，再建立连接。当前全部为演示配置。', 'Capabilities before connections. These are all demo configurations.')}</p><div className="agent-cards">{[
    ['Forge Local', 'Local runner', 'Delegate / Controlled', 'mint'],
    ['Atlas Research', 'Local runner', 'Delegate', 'violet'],
    ['Courier HTTP', 'HTTP adapter', 'Controlled', 'amber'],
    ['Sentinel', 'Event stream', 'Observe', 'blue'],
  ].map(([name, adapter, mode, tone]) => <article className="agent-card" key={name}><span className={`agent-large ${tone}`}><Bot size={24} /></span><h3>{name}</h3><p>{adapter}</p><span className="capability-chip">{mode}</span><footer><span className="muted-dot" />{t('演示配置 · 未连接', 'Demo configuration · Not connected')}</footer></article>)}</div><div className="sample-note"><LockKeyhole size={17} />{t('此阶段不收集凭据，不自动发现其他电脑，也不启动任何 Agent。', 'This phase collects no credentials, discovers no other computers, and starts no agents.')}</div></section>
}

function HistoryPage({ state, tasks, onTask }: { state: WorkspaceState; tasks: Task[]; onTask: (task: Task) => void }) {
  const { t, language } = useLocale()
  return <section className="utility-page"><span className="section-kicker">{t('每个决定，有迹可循', 'A RECORD OF YOUR DECISIONS')}</span><h1>{t('工作记录', 'Nothing gets lost.')}</h1><p>{t('决定、反馈和模拟回执保存在本地，不会重放任何动作。', 'Decisions, feedback, and simulated receipts stay local. Opening them never replays an action.')}</p><div className="history-list">{[...state.decisions].reverse().map(decision => {
    const task = tasks.find(item => item.id === decision.taskId)
    return <article key={decision.id}><span className="timeline-icon"><Check size={15} /></span><div><strong>{decisionTitle(decision, t)} · v{decision.revision}</strong><p>{task ? fixture(task, task.title, t) : decision.taskId}</p><small>{new Date(decision.at).toLocaleString(language)}</small></div>{task && <button className="secondary small" onClick={() => onTask(task)}>{t('查看任务', 'View task')}<ArrowUpRight size={13} /></button>}</article>
  })}{!state.decisions.length && <div className="utility-empty"><History size={30} /><h3>{t('你的决定将显示在这里', 'Your decisions will appear here')}</h3><p>{t('先从工作列表中处理一个事项。', 'Start with an item in your work list.')}</p></div>}</div></section>
}

function ModalFrame({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const { t } = useLocale()
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    const previousFocus = document.activeElement
    element?.showModal()
    return () => { element?.close(); if (previousFocus instanceof HTMLElement) previousFocus.focus() }
  }, [])
  return <dialog ref={dialog} className={`dialog ${wide ? 'wide' : ''}`} onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose() } }} aria-labelledby="dialog-title"><header><span className="dialog-symbol"><Sparkles size={18} /></span><h2 id="dialog-title">{title}</h2><button className="icon-button" onClick={onClose} aria-label={t('关闭', 'Close')}><X size={18} /></button></header>{children}</dialog>
}

function SettingsDialog({ onClose }: { onClose: () => void }) {
  const { t, language, setLanguage, storageError } = useLocale()
  return <ModalFrame title={t('设置', 'Settings')} onClose={onClose}><div className="dialog-body"><span className="section-kicker">{t('界面语言', 'INTERFACE LANGUAGE')}</span><p>{t('切换即时生效，不会丢失当前任务与反馈草稿。', 'Applies immediately, without losing your task or feedback draft.')}</p><div className="language-options"><button aria-pressed={language === 'en'} onClick={() => setLanguage('en')} className={language === 'en' ? 'selected' : ''}><span>EN</span><div><strong>English</strong><small>English</small></div>{language === 'en' && <Check size={17} />}</button><button aria-pressed={language === 'zh'} onClick={() => setLanguage('zh')} className={language === 'zh' ? 'selected' : ''}><span>中</span><div><strong>简体中文</strong><small>Simplified Chinese</small></div>{language === 'zh' && <Check size={17} />}</button></div>{storageError && <p className="error-banner" role="alert">{t('无法保存语言设置。', 'The language preference could not be saved.')}</p>}<div className="settings-info"><Laptop size={17} /><p>{t('任务与决定只存储在此浏览器中，未同步到其他电脑。', 'Tasks and decisions are stored in this browser only, not synced to other computers.')}</p></div></div><footer><span>{t('本地演示环境', 'Local demo environment')}</span><button className="primary" onClick={onClose}>{t('完成', 'Done')}</button></footer></ModalFrame>
}

function NewTaskDialog({ onClose, onCreate }: { onClose: () => void; onCreate: (title: string, goal: string, agent: string) => void }) {
  const { t } = useLocale()
  const [title, setTitle] = useState('')
  const [goal, setGoal] = useState('')
  const [agent, setAgent] = useState('Forge Local')
  return <ModalFrame title={t('委派新任务', 'Delegate a new task')} onClose={onClose}><form onSubmit={event => { event.preventDefault(); if (title.trim() && goal.trim()) onCreate(title.trim(), goal.trim(), agent) }}><div className="dialog-body form-fields"><label>{t('任务名称', 'Task name')}<input autoFocus value={title} onChange={event => setTitle(event.target.value)} required placeholder={t('例如：准备发布说明', 'e.g. Prepare release notes')} maxLength={140} /></label><label>{t('目标与完成条件', 'Goal & acceptance criteria')}<textarea value={goal} onChange={event => setGoal(event.target.value)} required rows={4} placeholder={t('期望的结果，以及不应执行的动作…', 'What good looks like, and what not to do…')} /></label><label>Agent<select value={agent} onChange={event => setAgent(event.target.value)}><option>Forge Local</option><option>Atlas Research</option><option>Courier HTTP</option></select></label><div className="sample-note"><ShieldCheck size={16} />{t('仅创建本地草稿。不会启动 Agent，也不会访问文件。', 'Creates a local draft only. No agent starts and no files are accessed.')}</div></div><footer><button type="button" className="secondary" onClick={onClose}>{t('取消', 'Cancel')}</button><button className="primary" disabled={!title.trim() || !goal.trim()}>{t('创建草稿', 'Create draft')}<ArrowRight size={14} /></button></footer></form></ModalFrame>
}

function SearchDialog({ tasks, onClose, onSelect }: { tasks: Task[]; onClose: () => void; onSelect: (task: Task) => void }) {
  const { t } = useLocale()
  const [query, setQuery] = useState('')
  const matches = tasks.filter(task => `${fixture(task, task.title, t)} ${task.agent}`.toLowerCase().includes(query.toLowerCase()))
  return <ModalFrame title={t('搜索工作', 'Find your work')} onClose={onClose} wide><div className="search-dialog-input"><Search size={18} /><input autoFocus value={query} onChange={event => setQuery(event.target.value)} aria-label={t('搜索任务', 'Search tasks')} placeholder={t('按任务名称或 Agent 搜索…', 'Search by task or agent…')} /></div><div className="search-results">{matches.map(task => <button key={task.id} onClick={() => onSelect(task)}><FileText size={18} /><div><strong>{fixture(task, task.title, t)}</strong><span>{task.agent}</span></div><ArrowUpRight size={15} /></button>)}{!matches.length && <p>{t('没有匹配的任务', 'No matching tasks')}</p>}</div><footer><span><Command size={12} /> {t('搜索只改变选中任务，不创建新工作空间。', 'Search opens a task, not a new workspace.')}</span></footer></ModalFrame>
}
