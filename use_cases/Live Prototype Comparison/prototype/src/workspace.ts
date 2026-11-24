import type { Task } from './data'

export type DecisionKind = 'accept' | 'revise' | 'approve' | 'reject' | 'clarify'
export type WorkFilter = 'attention' | 'running' | 'all'
export type BoardColumn = 'draft' | 'attention' | 'running' | 'handled'
export interface Decision {
  id: string
  taskId: string
  revision: number
  kind: DecisionKind
  note: string
  at: string
  receipt?: string
}
export interface Note { taskId: string; body: string; at: string }
export interface WorkspaceState {
  version: 2
  decisions: Decision[]
  notes: Note[]
  createdTasks: Task[]
  revisions: Record<string, number>
}

export function initialWorkspace(): WorkspaceState {
  return { version: 2, decisions: [], notes: [], createdTasks: [], revisions: {} }
}

export function revisionFor(state: WorkspaceState, task: Task) {
  return state.revisions[task.id] ?? (task.id === 'readme' ? 3 : task.id === 'update' ? 2 : 1)
}

export function decisionFor(state: WorkspaceState, task: Task) {
  return [...state.decisions].reverse().find(d => d.taskId === task.id && d.revision === revisionFor(state, task))
}

export function needsAttention(state: WorkspaceState, task: Task) {
  return Boolean(task.decisionType) && !decisionFor(state, task)
}

export function isRunning(state: WorkspaceState, task: Task) {
  if (task.id.startsWith('local-')) return false
  const decision = decisionFor(state, task)
  if (decision) return decision.kind === 'clarify' || decision.kind === 'revise' || (decision.kind === 'approve' && !decision.receipt)
  return task.status === 'running' && !task.decisionType
}

export function matchesFilter(state: WorkspaceState, task: Task, filter: WorkFilter) {
  return filter === 'all' || (filter === 'attention' ? needsAttention(state, task) : isRunning(state, task))
}

export function boardColumnFor(state: WorkspaceState, task: Task): BoardColumn {
  if (task.id.startsWith('local-')) return 'draft'
  if (needsAttention(state, task)) return 'attention'
  if (isRunning(state, task)) return 'running'
  return 'handled'
}

export function recordDecision(state: WorkspaceState, task: Task, kind: DecisionKind, note = ''): WorkspaceState {
  if (!needsAttention(state, task)) throw new Error('This decision has already been handled.')
  const allowed: Record<NonNullable<Task['decisionType']>, DecisionKind[]> = {
    验收: ['accept', 'revise'], 授权: ['approve', 'reject'], 澄清: ['clarify'],
  }
  if (!task.decisionType || !allowed[task.decisionType].includes(kind)) throw new Error('Invalid decision for this task.')
  if ((kind === 'revise' || kind === 'clarify') && !note.trim()) throw new Error('Feedback or a choice is required.')
  return {
    ...state,
    decisions: [...state.decisions, {
      id: crypto.randomUUID(), taskId: task.id, revision: revisionFor(state, task),
      kind, note: note.trim(), at: new Date().toISOString(),
    }],
  }
}

export function simulateReceipt(state: WorkspaceState, task: Task): WorkspaceState {
  const decision = decisionFor(state, task)
  if (!decision || decision.kind !== 'approve' || decision.receipt) throw new Error('No approved action is awaiting a receipt.')
  return { ...state, decisions: state.decisions.map(d => d.id === decision.id ? { ...d, receipt: `DEMO-${d.id.slice(0, 8)}` } : d) }
}

export function simulateRevision(state: WorkspaceState, task: Task): WorkspaceState {
  if (decisionFor(state, task)?.kind !== 'revise') throw new Error('No revision was requested.')
  return { ...state, revisions: { ...state.revisions, [task.id]: revisionFor(state, task) + 1 } }
}

// Validate browser storage before using it as application state.
export function parseWorkspace(raw: string): WorkspaceState {
  const value: unknown = JSON.parse(raw)
  const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
  const text = (v: unknown): v is string => typeof v === 'string'
  if (!object(value) || value.version !== 2 || !Array.isArray(value.decisions) || !Array.isArray(value.notes) ||
      !Array.isArray(value.createdTasks) || !object(value.revisions)) throw new Error('Unsupported workspace data.')
  const decisions: Decision[] = value.decisions.map(d => {
    if (!object(d) || !text(d.id) || !text(d.taskId) || !Number.isInteger(d.revision) || typeof d.revision !== 'number' || d.revision < 1 ||
        !['accept', 'revise', 'approve', 'reject', 'clarify'].includes(String(d.kind)) ||
        !text(d.note) || !text(d.at) || !Number.isFinite(Date.parse(d.at)) ||
        (d.receipt !== undefined && (!text(d.receipt) || d.kind !== 'approve'))) throw new Error('Invalid decision record.')
    return { id: d.id, taskId: d.taskId, revision: d.revision, kind: d.kind as DecisionKind, note: d.note, at: d.at, ...(typeof d.receipt === 'string' ? { receipt: d.receipt } : {}) }
  })
  const notes: Note[] = value.notes.map(n => {
    if (!object(n) || !text(n.taskId) || !text(n.body) || !text(n.at) || !Number.isFinite(Date.parse(n.at))) throw new Error('Invalid task note.')
    return { taskId: n.taskId, body: n.body, at: n.at }
  })
  const createdTasks: Task[] = value.createdTasks.map(t => {
    if (!object(t) || !text(t.id) || !t.id.startsWith('local-') || !text(t.title) || !text(t.goal) ||
        !text(t.agent) || !['Forge Local', 'Atlas Research', 'Courier HTTP'].includes(t.agent)) throw new Error('Invalid local task.')
    return createLocalTask(t.id, t.title, t.goal, t.agent)
  })
  const revisions: Record<string, number> = {}
  for (const [key, number] of Object.entries(value.revisions)) {
    if (!Number.isInteger(number) || typeof number !== 'number' || number < 1) throw new Error('Invalid artifact revision.')
    Object.defineProperty(revisions, key, { value: number, enumerable: true })
  }
  return { version: 2, decisions, notes, createdTasks, revisions }
}

export function createLocalTask(id: string, title: string, goal: string, agent: string): Task {
  return {
    id, title, goal, agent, project: 'Personal', status: 'running', statusLabel: '执行中',
    summary: goal, agentMode: 'Delegate', updatedAt: '刚刚', progress: 0, tone: 'blue', activities: [],
  }
}
