import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

async function loadTypeScript(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}
const model = await loadTypeScript('../src/workspace.ts')
const { tasks } = await loadTypeScript('../src/data.ts')
const task = id => tasks.find(t => t.id === id)

test('three independent decisions share the same task model', () => {
  const state = model.initialWorkspace()
  assert.deepEqual(tasks.filter(t => model.needsAttention(state, t)).map(t => t.id), ['research', 'readme', 'update'])
})

test('board columns place each task once and keep unsent local drafts separate', () => {
  const state = model.initialWorkspace()
  const draft = model.createLocalTask('local-board', 'Draft', 'Not started', 'Forge Local')
  const running = { ...task('research'), id: 'checks', decisionType: undefined }
  assert.deepEqual(tasks.map(t => [t.id, model.boardColumnFor(state, t)]), [
    ['research', 'attention'], ['readme', 'attention'], ['update', 'attention'], ['release', 'handled'],
  ])
  assert.equal(model.boardColumnFor(state, draft), 'draft')
  assert.equal(model.boardColumnFor(state, running), 'running')
  assert.deepEqual(state, model.initialWorkspace())
})

test('board authorization stays running until a receipt, while declined sends are handled', () => {
  const initial = model.initialWorkspace()
  const approved = model.recordDecision(initial, task('update'), 'approve')
  assert.equal(model.boardColumnFor(approved, task('update')), 'running')
  const delivered = model.simulateReceipt(approved, task('update'))
  assert.equal(model.boardColumnFor(delivered, task('update')), 'handled')
  const declined = model.recordDecision(initial, task('update'), 'reject')
  assert.equal(model.boardColumnFor(declined, task('update')), 'handled')
  assert.equal(model.decisionFor(declined, task('update')).receipt, undefined)
})

test('board revisions return to attention and confirmations continue in progress', () => {
  const initial = model.initialWorkspace()
  const revised = model.recordDecision(initial, task('readme'), 'revise', 'Clarify the boundary.')
  assert.equal(model.boardColumnFor(revised, task('readme')), 'running')
  const returned = model.simulateRevision(revised, task('readme'))
  assert.equal(model.boardColumnFor(returned, task('readme')), 'attention')
  const accepted = model.recordDecision(returned, task('readme'), 'accept')
  assert.equal(model.boardColumnFor(accepted, task('readme')), 'handled')
  const confirmed = model.recordDecision(initial, task('research'), 'clarify', 'focused')
  assert.equal(model.boardColumnFor(confirmed, task('research')), 'running')
  const restored = model.parseWorkspace(JSON.stringify(accepted))
  assert.equal(model.boardColumnFor(restored, task('readme')), 'handled')
})

test('acceptance resolves only the selected task; it never authorizes a send', () => {
  const state = model.recordDecision(model.initialWorkspace(), task('readme'), 'accept')
  assert.equal(model.needsAttention(state, task('readme')), false)
  assert.equal(model.needsAttention(state, task('update')), true)
  assert.equal(model.needsAttention(state, task('research')), true)
  assert.equal(state.decisions[0].kind, 'accept')
  assert.equal(state.decisions[0].receipt, undefined)
})

test('duplicate submissions cannot create duplicate decisions', () => {
  const state = model.recordDecision(model.initialWorkspace(), task('update'), 'approve')
  assert.throws(() => model.recordDecision(state, task('update'), 'approve'), /already been handled/)
  assert.equal(state.decisions.length, 1)
})

test('approval and simulated receipt are separate transitions', () => {
  const initial = model.initialWorkspace()
  assert.throws(() => model.simulateReceipt(initial, task('update')), /No approved action/)
  const approved = model.recordDecision(initial, task('update'), 'approve')
  assert.equal(model.decisionFor(approved, task('update')).receipt, undefined)
  assert.equal(model.isRunning(approved, task('update')), true)
  const delivered = model.simulateReceipt(approved, task('update'))
  assert.match(model.decisionFor(delivered, task('update')).receipt, /^DEMO-/)
  assert.equal(model.isRunning(delivered, task('update')), false)
  assert.throws(() => model.simulateReceipt(delivered, task('update')), /No approved action/)
  assert.equal(model.decisionFor(approved, task('update')).receipt, undefined)
})

test('declined actions cannot generate receipts', () => {
  const state = model.recordDecision(model.initialWorkspace(), task('update'), 'reject')
  assert.throws(() => model.simulateReceipt(state, task('update')), /No approved action/)
})

test('feedback is required and linked to the exact revision', () => {
  const initial = model.initialWorkspace()
  assert.throws(() => model.recordDecision(initial, task('readme'), 'revise', '  '), /required/)
  const state = model.recordDecision(initial, task('readme'), 'revise', '  Clarify the scope.  ')
  assert.equal(state.decisions[0].note, 'Clarify the scope.')
  assert.equal(state.decisions[0].revision, 3)
  assert.equal(model.isRunning(state, task('readme')), true)
})

test('a simulated revision restores review without deleting prior decisions', () => {
  const first = model.recordDecision(model.initialWorkspace(), task('readme'), 'revise', 'Clarify')
  const revised = model.simulateRevision(first, task('readme'))
  assert.equal(model.revisionFor(revised, task('readme')), 4)
  assert.equal(model.needsAttention(revised, task('readme')), true)
  assert.equal(revised.decisions.length, 1)
  const accepted = model.recordDecision(revised, task('readme'), 'accept')
  assert.deepEqual(accepted.decisions.map(d => [d.kind, d.revision]), [['revise', 3], ['accept', 4]])
  assert.throws(() => model.simulateRevision(accepted, task('readme')), /No revision/)
})

test('scope responses are required; handled research moves to in-progress', () => {
  assert.throws(() => model.recordDecision(model.initialWorkspace(), task('research'), 'clarify'), /required/)
  const state = model.recordDecision(model.initialWorkspace(), task('research'), 'clarify', 'focused')
  assert.equal(model.matchesFilter(state, task('research'), 'attention'), false)
  assert.equal(model.matchesFilter(state, task('research'), 'running'), true)
  assert.equal(model.matchesFilter(state, task('research'), 'all'), true)
})

test('decision types cannot be applied to the wrong task', () => {
  assert.throws(() => model.recordDecision(model.initialWorkspace(), task('readme'), 'approve'), /Invalid decision/)
})

test('refresh persistence keeps user text, history, and revisions', () => {
  let state = model.recordDecision(model.initialWorkspace(), task('readme'), 'revise', '保留这句中文')
  state = model.simulateRevision(state, task('readme'))
  state.createdTasks.push(model.createLocalTask('local-test', '私人的 title', '<script>not code</script>', 'Forge Local'))
  state.notes.push({ taskId: 'readme', body: '原始输入', at: new Date().toISOString() })
  assert.deepEqual(model.parseWorkspace(JSON.stringify(state)), state)
  assert.equal(model.isRunning(state, state.createdTasks[0]), false)
})

test('corrupt or unsupported storage is rejected explicitly', () => {
  assert.throws(() => model.parseWorkspace('{'), SyntaxError)
  assert.throws(() => model.parseWorkspace('{"version":1}'), /Unsupported/)
  assert.throws(() => model.parseWorkspace(JSON.stringify({ ...model.initialWorkspace(), decisions: [{}] })), /Invalid decision/)
  assert.throws(() => model.parseWorkspace(JSON.stringify({ ...model.initialWorkspace(), revisions: { readme: -1 } })), /Invalid artifact/)
})
