import { expect, test, type Page } from '@playwright/test'

const column = (page: Page, id: string) => page.locator(`.board-column[data-column="${id}"]`)
const card = (page: Page, id: string) => page.locator(`.task-row[data-task-id="${id}"]`)
const openTask = (page: Page, id: string) => card(page, id).click()
const back = (page: Page) => page.getByRole('button', { name: 'Back to board', exact: true }).click()

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('dayline-design')) localStorage.setItem('dayline-design', 'd')
  })
})

test('D opens three work columns without reserving space for drafts', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/?design=d')
  await expect(page.locator('.desktop-app')).toHaveAttribute('data-design', 'd')
  await expect(page.locator('.desktop-app')).toHaveAttribute('data-prototype-ready', 'true')
  await expect(page.getByRole('button', { name: 'Prototype D', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('region', { name: 'Task board', exact: true })).toBeVisible()
  await expect(page.locator('.task-detail')).toHaveCount(0)
  await expect(page.locator('.board-column')).toHaveCount(3)
  await expect(column(page, 'draft')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Local drafts', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'New task', exact: true })).toBeVisible()
  for (const [id, count] of [['attention', 3], ['running', 1], ['handled', 1]] as const) {
    await expect(column(page, id).locator('.task-row')).toHaveCount(count)
    await expect(column(page, id).locator('.board-column-count')).toHaveText(String(count))
  }
  await expect(page.locator('.task-row')).toHaveCount(5)
  const layout = await page.locator('.board-column').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().toJSON()))
  expect(new Set(layout.map(box => box.top)).size).toBe(1)
  const lanes = await page.locator('.kanban-lanes').boundingBox()
  expect(lanes).not.toBeNull()
  expect(layout[0].left).toBe(lanes!.x)
  expect(layout[2].right).toBeLessThanOrEqual(lanes!.x + lanes!.width)
  for (let index = 1; index < layout.length; index++) expect(layout[index].left).toBeGreaterThan(layout[index - 1].right)
  expect(await page.locator('.task-row').evaluateAll(elements => elements.every(element => !element.hasAttribute('draggable')))).toBe(true)
  expect(errors).toEqual([])
})

test('accepting moves one card to handled, keeps the panel open and persists', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'readme')
  await expect(page.getByRole('region', { name: 'Task detail panel', exact: true })).toBeVisible()
  const board = await page.locator('.board-surface').boundingBox()
  const panel = await page.locator('.task-detail').boundingBox()
  expect(board).not.toBeNull()
  expect(panel).not.toBeNull()
  expect(panel!.x).toBeGreaterThanOrEqual(board!.x + board!.width)
  await page.getByRole('button', { name: 'Accept v3', exact: true }).click()
  await expect(column(page, 'handled').locator('[data-task-id="readme"]')).toHaveCount(1)
  await expect(column(page, 'attention').locator('.board-column-count')).toHaveText('2')
  await expect(page.locator('.resolution-card')).toContainText('Artifact accepted')
  await expect(page.locator('.task-detail')).toHaveAttribute('data-task-id', 'readme')
  await expect(page.locator('.nav-count')).toHaveText('2')
  await back(page)
  await expect(card(page, 'readme')).toBeFocused()
  await page.reload()
  await expect(column(page, 'handled').locator('[data-task-id="readme"]')).toHaveCount(1)
  await openTask(page, 'update')
  await expect(page.getByRole('button', { name: 'Authorize once', exact: true })).toBeEnabled()
})

test('revision requests move to running and returned revisions need review again', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'readme')
  await page.getByRole('button', { name: 'Request changes', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Send revision request', exact: true })).toBeDisabled()
  await page.getByLabel('What needs to change?').fill('Explain authorization separately from delivery.')
  await page.getByRole('button', { name: 'Send revision request', exact: true }).click()
  await expect(column(page, 'running').locator('[data-task-id="readme"]')).toContainText('Revision requested')
  await page.getByRole('button', { name: 'Demo: return a new revision', exact: true }).click()
  await expect(column(page, 'attention').locator('[data-task-id="readme"]')).toContainText('README.md · v4')
  await page.getByRole('combobox', { name: 'Artifact version', exact: true }).selectOption('3')
  await expect(page.getByRole('button', { name: 'Accept v4', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'View latest revision', exact: true }).click()
  await page.getByRole('button', { name: 'Accept v4', exact: true }).click()
  await expect(column(page, 'handled').locator('[data-task-id="readme"]')).toHaveCount(1)
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await expect(page.locator('.timeline')).toContainText('Changes requested · v3')
  await expect(page.locator('.timeline')).toContainText('Artifact accepted · v4')
})

test('authorization waits in running until a simulated receipt arrives', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'update')
  await expect(page.locator('.action-scope')).toContainText('#dayline-preview')
  await expect(page.locator('.action-scope')).toContainText('weekly-update.md · v2')
  await expect(page.locator('.scope-warning')).toBeVisible()
  await page.getByRole('button', { name: 'Authorize once', exact: true }).click()
  await expect(column(page, 'running').locator('[data-task-id="update"]')).toContainText('Authorized · awaiting receipt')
  await expect(column(page, 'handled').locator('[data-task-id="update"]')).toHaveCount(0)
  await expect(page.locator('.resolution-card')).toContainText('no execution receipt yet')
  await expect(page.locator('.resolution-card code')).toHaveCount(0)
  await page.getByRole('button', { name: 'Demo: generate simulated receipt', exact: true }).click()
  await expect(column(page, 'handled').locator('[data-task-id="update"]')).toContainText('Delivered · simulated')
  await expect(page.locator('.resolution-card code')).toContainText('DEMO-')
})

test('declining a send is handled, not delivered; scope confirmation continues running', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'update')
  await page.getByRole('button', { name: 'Decline', exact: true }).click()
  await expect(column(page, 'handled').locator('[data-task-id="update"]')).toContainText('Send declined')
  await expect(page.getByRole('button', { name: 'Demo: generate simulated receipt', exact: true })).toHaveCount(0)
  await back(page)
  await openTask(page, 'research')
  await page.getByRole('radio', { name: /Include team collaboration/ }).check()
  await page.getByRole('button', { name: 'Confirm scope', exact: true }).click()
  await expect(column(page, 'running').locator('[data-task-id="research"]')).toContainText('Continuing · demo')
  await expect(page.locator('.resolution-card blockquote')).toHaveText('Include team collaboration products')
})

test('closing and reopening retains feedback, task tabs and notes, with keyboard focus restored', async ({ page }) => {
  await page.goto('/')
  await card(page, 'readme').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Back to board', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Request changes', exact: true }).click()
  await page.getByLabel('What needs to change?').fill('Keep my unsubmitted board feedback.')
  await page.keyboard.press('Escape')
  await expect(page.locator('.task-detail')).toHaveCount(0)
  await expect(card(page, 'readme')).toBeFocused()
  await openTask(page, 'update')
  await back(page)
  await openTask(page, 'readme')
  await expect(page.getByLabel('What needs to change?')).toHaveValue('Keep my unsubmitted board feedback.')
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.locator('.detail-scroll').evaluate(element => { element.scrollTop = 150 })
  const scroll = await page.locator('.detail-scroll').evaluate(element => element.scrollTop)
  expect(scroll).toBeGreaterThan(0)
  await back(page)
  await openTask(page, 'readme')
  await expect.poll(() => page.locator('.detail-scroll').evaluate(element => element.scrollTop)).toBe(scroll)
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await page.getByLabel('Task note', { exact: true }).fill('A note draft stays in the board.')
  await back(page)
  await openTask(page, 'readme')
  await expect(page.getByRole('tab', { name: /Workstream/ })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByLabel('Task note', { exact: true })).toHaveValue('A note draft stays in the board.')
  await page.getByRole('button', { name: 'Search tasks', exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('.task-detail')).toBeVisible()
})

test('search filters across all columns without losing the open task', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'readme')
  await page.getByRole('textbox', { name: 'Filter work', exact: true }).fill('Courier')
  await expect(page.locator('.task-row')).toHaveCount(1)
  await expect(card(page, 'update')).toBeVisible()
  await expect(page.locator('.task-detail')).toHaveAttribute('data-task-id', 'readme')
  await page.getByRole('textbox', { name: 'Filter work', exact: true }).fill('no-such-task')
  await expect(page.getByRole('status')).toContainText('No matching work')
  await expect(page.locator('.task-row')).toHaveCount(0)
  await back(page)
  await expect(page.getByRole('textbox', { name: 'Filter work', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Clear search', exact: true }).click()
  await expect(page.locator('.task-row')).toHaveCount(5)
  for (const id of ['attention', 'running', 'handled']) await expect(column(page, id)).toBeVisible()
})

test('new tasks remain local drafts and are searchable after refresh', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'New task', exact: true }).click()
  await page.getByLabel('Task name', { exact: true }).fill('私人的 board draft')
  await page.getByLabel('Goal & acceptance criteria', { exact: true }).fill('Do not start a real agent.')
  await page.getByRole('button', { name: 'Create draft', exact: true }).click()
  await expect(page.locator('.board-column')).toHaveCount(3)
  await expect(column(page, 'draft')).toHaveCount(0)
  const drafts = page.getByRole('button', { name: 'Local drafts', exact: true })
  await expect(drafts).toContainText('1')
  await expect(page.getByText('This is a local demo draft. No task has been sent to an agent.')).toBeVisible()
  await back(page)
  await expect(drafts).toBeFocused()
  await drafts.click()
  const popover = page.getByRole('region', { name: 'Local drafts', exact: true })
  await expect(popover).toContainText('私人的 board draft')
  await popover.locator('.task-row').click()
  await expect(popover).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '私人的 board draft', exact: true })).toBeVisible()
  await back(page)
  await page.reload()
  await expect(drafts).toContainText('1')
  await expect(page.locator('.board-column')).toHaveCount(3)
  await page.getByRole('button', { name: 'Search tasks', exact: true }).click()
  await page.getByRole('dialog').getByRole('textbox').fill('私人的')
  await page.locator('.search-results button').click()
  await expect(page.getByRole('heading', { name: '私人的 board draft', exact: true })).toBeVisible()
})

test('board labels are bilingual without translating saved user text', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'readme')
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await page.getByLabel('Task note', { exact: true }).fill('原文 stays unchanged')
  await page.getByRole('button', { name: 'Save note', exact: true }).click()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByRole('button', { name: /简体中文/ }).click()
  await page.getByRole('button', { name: '完成', exact: true }).click()
  await expect(page.getByRole('button', { name: '原型 D', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.user-text')).toHaveText('原文 stays unchanged')
  await page.getByRole('button', { name: '返回看板', exact: true }).click()
  await expect(page.getByRole('region', { name: '任务看板', exact: true })).toBeVisible()
  for (const label of ['需要你', '执行中', '已处理']) {
    await expect(page.locator('.board-column-heading h2').filter({ hasText: label })).toHaveCount(1)
  }
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN')
})

for (const width of [1440, 1024, 820, 390]) {
  test(`board scrolling, feedback and decision controls work at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    const board = await page.locator('.kanban-lanes').evaluate(element => ({ content: element.scrollWidth, visible: element.clientWidth }))
    if (width <= 820) expect(board.content).toBeGreaterThan(board.visible)
    await openTask(page, 'readme')
    await expect(page.getByRole('button', { name: 'Accept v3', exact: true })).toBeInViewport()
    await page.getByRole('button', { name: 'Request changes', exact: true }).click()
    await expect(page.getByLabel('What needs to change?')).toBeInViewport()
    await page.getByLabel('What needs to change?').fill('Keep this feedback reachable.')
    await expect(page.getByRole('button', { name: 'Send revision request', exact: true })).toBeInViewport()
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    await back(page)
    await openTask(page, 'update')
    await expect(page.locator('.action-scope')).toContainText('#dayline-preview')
    await expect(page.getByRole('button', { name: 'Authorize once', exact: true })).toBeInViewport()
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    await back(page)
    await openTask(page, 'release')
    await expect(page.locator('.task-detail')).toHaveAttribute('data-task-id', 'release')
    await back(page)
    await expect(card(page, 'release')).toBeInViewport()
  })
}

test('unreadable storage remains explicit and is not overwritten in board view', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('dayline-workbench-v2', '{"corrupted":true}'))
  await page.goto('/?design=d')
  await expect(page.getByRole('alert')).toContainText('Local data could not be loaded or saved')
  expect(await page.evaluate(() => localStorage.getItem('dayline-workbench-v2'))).toBe('{"corrupted":true}')
})

test('board and inspector text meet readable contrast thresholds', async ({ page }) => {
  await page.goto('/')
  await openTask(page, 'readme')
  await page.getByRole('textbox', { name: 'Filter work', exact: true }).fill('quick start')
  const ratios = await page.evaluate(() => {
    const luminance = (color: string) => {
      const values = (color.match(/[\d.]+/g) ?? []).slice(0, 3).map(value => {
        const n = Number(value) / 255
        return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4
      })
      return values[0] * .2126 + values[1] * .7152 + values[2] * .0722
    }
    return [
      '.board-kicker', '.board-column-heading h2', '.board-column-heading p', '.board-column-count',
      '.task-row.selected > strong', '.task-row.selected > p', '.task-row.selected .board-card-meta',
      '.board-column-empty', '.board-note', '.board-detail-toolbar > span', '.task-goal',
      '.decision-buttons .primary', '.document-body p',
    ].map(selector => {
      const element = document.querySelector(selector)
      if (!element) throw new Error(`Missing text: ${selector}`)
      let parent: Element | null = element
      let background = 'rgb(255, 255, 255)'
      while (parent) {
        const color = getComputedStyle(parent).backgroundColor
        if (color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') { background = color; break }
        parent = parent.parentElement
      }
      const foreground = getComputedStyle(element).color
      const a = luminance(foreground)
      const b = luminance(background)
      return { selector, ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) }
    })
  })
  for (const value of ratios) expect.soft(value.ratio, value.selector).toBeGreaterThanOrEqual(4.5)
})

for (const width of [1440, 390]) {
  test(`existing drafts use a compact entry, not a board column, at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => localStorage.setItem('dayline-workbench-v2', JSON.stringify({
      version: 2, decisions: [], notes: [], revisions: {},
      createdTasks: [{ id: 'local-compact', title: 'Compact draft', goal: 'Keep this unsent.', agent: 'Forge Local' }],
    })))
    await page.goto('/')
    await expect(page.locator('.board-column')).toHaveCount(3)
    await expect(column(page, 'draft')).toHaveCount(0)
    await expect(page.locator('.kanban-lanes .task-row')).toHaveCount(5)
    const drafts = page.getByRole('button', { name: 'Local drafts', exact: true })
    const entry = await drafts.boundingBox()
    expect(entry).not.toBeNull()
    expect(entry!.width).toBeLessThanOrEqual(160)
    expect(entry!.height).toBeLessThanOrEqual(40)
    await drafts.click()
    const popover = page.getByRole('region', { name: 'Local drafts', exact: true })
    await expect(popover.locator('.task-row')).toHaveCount(1)
    const popup = await popover.boundingBox()
    expect(popup).not.toBeNull()
    expect(popup!.width).toBeLessThanOrEqual(300)
    expect(popup!.height).toBeLessThanOrEqual(360)
    expect(popup!.x).toBeGreaterThanOrEqual(0)
    expect(popup!.x + popup!.width).toBeLessThanOrEqual(width)
    await page.keyboard.press('Escape')
    await expect(popover).toHaveCount(0)
    await expect(drafts).toBeFocused()
    await drafts.click()
    await popover.locator('.task-row').click()
    await expect(page.getByRole('heading', { name: 'Compact draft', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Back to board', exact: true })).toBeFocused()
    await back(page)
    await expect(drafts).toBeFocused()
    await expect(page.locator('.board-column')).toHaveCount(3)
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
  })
}
