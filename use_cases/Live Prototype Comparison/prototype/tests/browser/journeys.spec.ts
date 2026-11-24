import { expect, test, type Page } from '@playwright/test'

const selectTask = (page: Page, id: string) => page.locator(`.task-row[data-task-id="${id}"]`).click()
const detail = (page: Page) => page.locator('.task-detail')

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.project.name === 'design-b' || testInfo.project.name === 'design-c') {
    await page.addInitScript(design => {
      if (!localStorage.getItem('dayline-design')) localStorage.setItem('dayline-design', design)
    }, testInfo.project.name === 'design-c' ? 'c' : 'b')
  }
})

test('continuous work: selection, filters, read position and feedback drafts stay in place', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.goto('/')
  await expect(detail(page)).toHaveAttribute('data-task-id', 'readme')
  await expect(page.getByRole('button', { name: /Open.*workspace/i })).toHaveCount(0)
  await page.locator('.detail-scroll').evaluate(el => { el.scrollTop = 180 })
  const scroll = await page.locator('.detail-scroll').evaluate(el => el.scrollTop)
  await page.getByRole('button', { name: 'Request changes', exact: true }).click()
  await page.getByLabel('What needs to change?').fill('Keep this draft while I check the other task.')
  await selectTask(page, 'update')
  await expect(page.getByRole('button', { name: 'Needs you 3', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('navigation').getByRole('button', { name: 'Work 3', exact: true })).toHaveAttribute('aria-current', 'page')
  await selectTask(page, 'readme')
  await expect(page.getByLabel('What needs to change?')).toHaveValue('Keep this draft while I check the other task.')
  // Closing the editor restores room for the original reading position.
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect.poll(() => page.locator('.detail-scroll').evaluate(el => el.scrollTop)).toBeGreaterThanOrEqual(Math.min(scroll, 100))
  await page.getByRole('button', { name: 'In progress', exact: true }).click()
  await expect(detail(page)).toHaveAttribute('data-task-id', 'readme')
  await expect(page.locator('.task-row[data-task-id="checks"]')).toBeVisible()
  await selectTask(page, 'checks')
  await page.getByRole('tab', { name: 'Context', exact: true }).click()
  await expect(page.getByText('Observe only. No pause, cancel, or enforcement controls.')).toBeVisible()
  expect(errors).toEqual([])
})

test('acceptance stays inline, removes the pending flag, persists and cannot authorize a send', async ({ page }) => {
  await page.goto('/')
  await page.locator('.detail-scroll').evaluate(el => { el.scrollTop = el.scrollHeight })
  await page.getByRole('button', { name: 'Accept v3', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(detail(page)).toHaveAttribute('data-task-id', 'readme')
  await expect(page.locator('.resolution-card')).toContainText('Artifact accepted')
  await expect(page.locator('.resolution-card')).toBeInViewport()
  await expect(page.locator('.nav-count')).toHaveText('2')
  await expect(page.locator('.task-row.selected')).toContainText('Accepted')
  await expect(page.getByRole('button', { name: 'Accept v3', exact: true })).toHaveCount(0)
  await page.reload()
  await expect(page.locator('.resolution-card')).toContainText('Artifact accepted')
  await expect(page.locator('.nav-count')).toHaveText('2')
  await selectTask(page, 'update')
  await expect(page.getByRole('button', { name: 'Authorize once' })).toBeEnabled()
})

test('revision feedback and new versions retain their history', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Request changes', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Send revision request' })).toBeDisabled()
  await page.getByLabel('What needs to change?').fill('Explain what happens after authorization.')
  await page.getByRole('button', { name: 'Send revision request' }).click()
  await expect(page.locator('.resolution-card')).toContainText('Explain what happens after authorization.')
  await page.getByRole('button', { name: 'Demo: return a new revision' }).click()
  await expect(page.getByRole('button', { name: 'Accept v4' })).toBeEnabled()
  await expect(page.locator('.feedback-note')).toContainText('Explain what happens after authorization.')
  await page.getByRole('combobox', { name: 'Artifact version' }).selectOption('3')
  await expect(page.getByRole('button', { name: 'Accept v4' })).toHaveCount(0)
  await page.getByRole('button', { name: 'View latest revision' }).click()
  await page.getByRole('button', { name: 'Accept v4' }).click()
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await expect(page.locator('.timeline')).toContainText('Changes requested · v3')
  await expect(page.locator('.timeline')).toContainText('Artifact accepted · v4')
})

test('authorization is not delivery, scope can be answered, all-clear keeps the task open', async ({ page }) => {
  await page.goto('/')
  await selectTask(page, 'update')
  await expect(page.locator('.action-scope')).toContainText('#dayline-preview')
  await expect(page.locator('.action-scope')).toContainText('weekly-update.md · v2')
  await page.getByRole('button', { name: 'Authorize once' }).click()
  await expect(page.locator('.resolution-card')).toContainText('no execution receipt yet')
  await expect(page.locator('.resolution-card code')).toHaveCount(0)
  await page.getByRole('button', { name: 'Demo: generate simulated receipt' }).click()
  await expect(page.locator('.resolution-card code')).toContainText('DEMO-')
  await selectTask(page, 'research')
  await page.getByRole('radio', { name: /Include team collaboration/ }).check()
  await page.getByRole('button', { name: 'Confirm scope' }).click()
  await expect(page.locator('.resolution-card blockquote')).toHaveText('Include team collaboration products')
  await page.reload()
  await page.getByRole('button', { name: 'All', exact: true }).click()
  await selectTask(page, 'research')
  await expect(page.getByRole('radio', { name: /Include team collaboration/ })).toBeChecked()
  await page.getByRole('button', { name: 'Needs you 1', exact: true }).click()
  await selectTask(page, 'readme')
  await page.getByRole('button', { name: 'Accept v3', exact: true }).click()
  await expect(page.locator('.nav-count')).toHaveText('0')
  await expect(page.locator('.list-empty')).toContainText('All clear here')
  await expect(detail(page)).toHaveAttribute('data-task-id', 'readme')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('language switching is reactive and never translates user content', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await page.getByLabel('Task note').fill('任务已完成 — this is my original text')
  await page.getByRole('button', { name: 'Save note' }).click()
  await page.getByRole('button', { name: /Settings/ }).click()
  await page.getByRole('button', { name: /简体中文/ }).click()
  await page.getByRole('button', { name: '完成', exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN')
  await expect(page.getByRole('heading', { name: '更新项目说明与快速开始' })).toBeVisible()
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByRole('button', { name: 'EN English English' }).click()
  await page.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(page.locator('.user-text')).toHaveText('任务已完成 — this is my original text')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await expect(page.locator('.user-text')).toHaveText('任务已完成 — this is my original text')
})

test('new drafts and search open concrete tasks without starting an agent', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'New task', exact: true }).click()
  await page.getByLabel('Task name').fill('Research laptop setup')
  await page.getByLabel('Goal & acceptance criteria').fill('Collect setup notes. Do not run commands.')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.getByRole('heading', { name: 'Research laptop setup', exact: true })).toBeVisible()
  await expect(page.getByText('This is a local demo draft. No task has been sent to an agent.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'All', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.reload()
  await page.getByRole('button', { name: 'Search tasks', exact: true }).click()
  await page.getByRole('dialog').getByRole('textbox').fill('laptop')
  await page.locator('.search-results button').click()
  await expect(page.getByRole('heading', { name: 'Research laptop setup', exact: true })).toBeVisible()
})

for (const width of [1440, 1024, 820, 390]) {
  test(`layout at ${width}px preserves decision controls and destination`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await selectTask(page, 'update')
    await expect(page.locator('.action-scope')).toContainText('#dayline-preview')
    await expect(page.getByRole('button', { name: 'Authorize once' })).toBeVisible()
    const layout = await page.evaluate(() => {
      const button = document.querySelector('.decision-buttons .primary')?.getBoundingClientRect()
      return { scrollWidth: document.body.scrollWidth, width: innerWidth, height: innerHeight, button: button?.toJSON() }
    })
    expect(layout.scrollWidth).toBeLessThanOrEqual(width)
    expect(layout.button?.right).toBeLessThanOrEqual(width)
    expect(layout.button?.bottom).toBeLessThanOrEqual(layout.height)
    if (width < 721) {
      await page.getByRole('button', { name: 'Work list', exact: true }).click()
      await expect(page.locator('.task-row.selected')).toHaveAttribute('data-task-id', 'update')
    }
  })
}

test('unreadable storage produces an explicit warning without overwriting data', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('dayline-workbench-v2', '{"corrupted": true}'))
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Local data could not be loaded or saved')
  expect(await page.evaluate(() => localStorage.getItem('dayline-workbench-v2'))).toBe('{"corrupted": true}')
})

test('all designs keep key reading text legible without decorative gradients', async ({ page }, testInfo) => {
  await page.goto('/')
  const appearance = await page.evaluate(() => {
    const luminance = (color: string) => {
      const channels = (color.match(/[\d.]+/g) ?? []).slice(0, 3).map(n => Number(n) / 255)
      const linear = channels.map(n => n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4)
      return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722
    }
    const contrast = (selector: string) => {
      const element = document.querySelector(selector)
      if (!element) throw new Error(`Missing reading surface: ${selector}`)
      let parent: Element | null = element
      let background = 'rgb(255, 255, 255)'
      while (parent) {
        const color = getComputedStyle(parent).backgroundColor
        if (color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') {
          background = color
          break
        }
        parent = parent.parentElement
      }
      const foreground = getComputedStyle(element).color
      const light = luminance(foreground)
      const dark = luminance(background)
      return { selector, foreground, background, ratio: (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05) }
    }
    const selectors = [
      '.work-heading p', '.task-goal', '.task-row.selected > strong', '.task-row.selected > p',
      '.task-row.selected .row-meta > span:last-child', '.nav-item.active',
      '.decision-buttons .primary', '.document-body p', '.diff-block.addition p',
      '.diff-block.deletion p', '.section-kicker', '.app-status > span',
    ]
    if (document.querySelector('.desktop-app')?.getAttribute('data-design') === 'c') {
      selectors.push(
        '.control-room-label', '.overview-card[aria-pressed="true"] > strong',
        '.overview-card[aria-pressed="true"] > span', '.overview-card:not([aria-pressed="true"]) > span',
        '.global-sidebar .nav-item:not(.active)', '.global-sidebar .brand-symbol',
      )
    }
    return {
      text: selectors.map(contrast),
      gradients: ['.global-sidebar', '.main-surface', '.brand-symbol', '.decision-buttons .primary'].map(selector => {
        const element = document.querySelector(selector)
        if (!element) throw new Error(`Missing surface: ${selector}`)
        return getComputedStyle(element).backgroundImage
      }),
      headingFont: getComputedStyle(document.querySelector('h1')!).fontFamily,
    }
  })
  for (const text of appearance.text) expect.soft(text.ratio, `${text.selector}: ${text.foreground} on ${text.background}`).toBeGreaterThanOrEqual(4.5)
  expect(appearance.gradients).toEqual(['none', 'none', 'none', 'none'])
  expect(appearance.headingFont).toContain(testInfo.project.name === 'design-c' ? 'Segoe UI' : 'Georgia')
})

test('A/B/C/D are presentations of the same task, tab, draft and decision', async ({ page }) => {
  await page.goto('/?design=a')
  await page.getByRole('button', { name: 'Request changes', exact: true }).click()
  await page.getByLabel('What needs to change?').fill('Do not lose my feedback when comparing designs.')
  await page.getByRole('button', { name: 'Prototype B', exact: true }).click()
  await expect(page.locator('.desktop-app')).toHaveAttribute('data-design', 'b')
  await expect(page.getByRole('button', { name: 'Needs you 3', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(detail(page)).toHaveAttribute('data-task-id', 'readme')
  await expect(page.getByLabel('What needs to change?')).toHaveValue('Do not lose my feedback when comparing designs.')
  for (const design of ['C', 'D', 'A']) {
    await page.getByRole('button', { name: `Prototype ${design}`, exact: true }).click()
    await expect(page.locator('.desktop-app')).toHaveAttribute('data-design', design.toLowerCase())
    await expect(page.getByLabel('What needs to change?')).toHaveValue('Do not lose my feedback when comparing designs.')
  }
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.getByRole('tab', { name: /Workstream/ }).click()
  await page.getByLabel('Task note').fill('Another draft stays in this task.')
  for (const design of ['B', 'C', 'D']) {
    await page.getByRole('button', { name: `Prototype ${design}`, exact: true }).click()
    await expect(page.getByRole('tab', { name: /Workstream/ })).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByLabel('Task note')).toHaveValue('Another draft stays in this task.')
  }
  await page.getByRole('tab', { name: 'Result', exact: true }).click()
  await page.getByRole('button', { name: 'Accept v3', exact: true }).click()
  await page.getByRole('button', { name: 'Prototype A', exact: true }).click()
  await expect(page.locator('.resolution-card')).toContainText('Artifact accepted')
  await expect(page.locator('.nav-count')).toHaveText('2')
  await expect(page.getByRole('button', { name: 'Accept v3', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Prototype D', exact: true }).click()
  await page.reload()
  await expect(page.locator('.desktop-app')).toHaveAttribute('data-design', 'd')
  await selectTask(page, 'readme')
  await expect(page.locator('.resolution-card')).toContainText('Artifact accepted')
})

test('research mode fixes the requested design and hides study navigation', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('dayline-design', 'b'))
  for (const design of ['a', 'b', 'c', 'd']) {
    await page.goto(`/?design=${design}&research=1`)
    await expect(page.locator('.desktop-app')).toHaveAttribute('data-design', design)
    await expect(page.locator('.desktop-app')).toHaveAttribute('data-prototype-ready', 'true')
    await expect(page.locator('.desktop-app')).toHaveAttribute('data-research', 'true')
    await expect(page.getByRole('group', { name: 'Compare UI designs' })).toHaveCount(0)
    await expect(page.getByText('Demo User', { exact: true })).toHaveCount(1)
    await page.reload()
    await expect(page.locator('.desktop-app')).toHaveAttribute('data-design', design)
  }
})

test('B changes component dimensions and action placement, not the review path', async ({ page }) => {
  await page.goto('/?design=a')
  const a = await page.evaluate(() => {
    const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().toJSON()
    return { list: box('.work-list'), content: box('.detail-scroll'), actions: box('.decision-footer-wrap') }
  })
  await page.getByRole('button', { name: 'Prototype B', exact: true }).click()
  await expect(page.locator('.task-row.selected > p')).toBeHidden()
  await page.getByRole('button', { name: 'Show summaries', exact: true }).click()
  await expect(page.locator('.task-row.selected > p')).toBeVisible()
  await page.getByRole('button', { name: 'Show summaries', exact: true }).click()
  const b = await page.evaluate(() => {
    const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().toJSON()
    return { list: box('.work-list'), content: box('.detail-scroll'), actions: box('.decision-footer-wrap') }
  })
  expect(b.list.width).toBeLessThan(a.list.width)
  expect(b.content.height).toBeGreaterThan(a.content.height)
  expect(b.actions.left).toBeGreaterThanOrEqual(b.content.right - 1)
  expect(a.actions.top).toBeGreaterThanOrEqual(a.content.bottom - 1)
  await expect(page.locator('.decision-side-summary')).toContainText('README.md · v3')
  await expect(page.locator('.desktop-app')).toHaveAttribute('data-summaries', 'compact')
  await selectTask(page, 'update')
  await expect(page.locator('.decision-side-summary')).toContainText('#dayline-preview')
  await expect(page.locator('.action-scope')).toContainText('weekly-update.md · v2')
  await expect(page.locator('.scope-warning')).toBeVisible()
})

test('design selection is bilingual and preserves the current artifact revision', async ({ page }) => {
  await page.goto('/?design=b')
  await page.getByRole('combobox', { name: 'Artifact version' }).selectOption('2')
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByRole('button', { name: /简体中文/ }).click()
  await page.getByRole('button', { name: '完成', exact: true }).click()
  await expect(page.getByRole('button', { name: '原型 B', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: '原型 A', exact: true }).click()
  await expect(page.getByRole('combobox', { name: '产物版本' })).toHaveValue('2')
  await expect(page.getByRole('button', { name: '接受 v3', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '原型 D', exact: true }).click()
  await expect(page.getByRole('button', { name: '原型 D', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('combobox', { name: '产物版本' })).toHaveValue('2')
  await expect(page.getByRole('button', { name: '接受 v3', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '原型 C', exact: true }).click()
  await expect(page.getByRole('button', { name: '原型 C', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('group', { name: '工作概览', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '查看需要你的工作', exact: true })).toContainText('3')
  await expect(page.getByRole('combobox', { name: '产物版本' })).toHaveValue('2')
  await expect(page.getByRole('button', { name: '接受 v3', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '原型 B', exact: true }).click()
  await page.getByRole('button', { name: '查看最新版本', exact: true }).click()
  await expect(page.getByRole('button', { name: '接受 v3', exact: true })).toBeVisible()
})

test('B keeps side actions reachable at its narrowest wide-screen breakpoint', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.goto('/?design=b')
  const accept = page.getByRole('button', { name: 'Accept v3', exact: true })
  await expect(accept).toBeInViewport()
  await page.getByRole('button', { name: 'Request changes', exact: true }).click()
  await expect(page.getByLabel('What needs to change?')).toBeInViewport()
  await page.getByLabel('What needs to change?').fill('Test feedback at the side-panel breakpoint.')
  await expect(page.getByRole('button', { name: 'Send revision request' })).toBeInViewport()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await selectTask(page, 'update')
  const authorize = await page.getByRole('button', { name: 'Authorize once', exact: true }).boundingBox()
  expect(authorize).not.toBeNull()
  expect(authorize!.y + authorize!.height).toBeLessThanOrEqual(720)
  await expect(page.locator('.decision-side-summary')).toContainText('#dayline-preview')
})

test('C changes navigation, task cards and action placement without changing decisions', async ({ page }) => {
  const boxes = () => page.evaluate(() => {
    const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().toJSON()
    return { nav: box('.global-sidebar'), list: box('.work-list'), content: box('.detail-scroll'), actions: box('.decision-footer-wrap') }
  })
  await page.goto('/?design=a')
  const a = await boxes()
  await page.getByRole('button', { name: 'Prototype B', exact: true }).click()
  const b = await boxes()
  await page.getByRole('button', { name: 'Prototype C', exact: true }).click()
  const c = await boxes()
  expect(c.nav.width).toBe(1440)
  expect(c.nav.bottom).toBeLessThan(c.list.top)
  expect(c.list.width).toBeGreaterThan(a.list.width)
  expect(c.list.width).toBeGreaterThan(b.list.width)
  expect(c.actions.bottom).toBeLessThanOrEqual(c.content.top + 1)
  await expect(page.locator('.task-row.selected > p')).toBeVisible()
  await expect(page.getByRole('group', { name: 'Work overview' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Show items needing you', exact: true })).toContainText('3')
  await page.getByRole('button', { name: 'Show in-progress work', exact: true }).click()
  await expect(page.getByRole('button', { name: 'In progress', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(detail(page)).toHaveAttribute('data-task-id', 'readme')
  await expect(page.locator('.task-row[data-task-id="checks"]')).toBeVisible()
  await page.getByRole('button', { name: 'Show all work', exact: true }).click()
  await expect(page.locator('.task-row')).toHaveCount(5)
  await page.getByRole('button', { name: 'Show items needing you', exact: true }).click()
  await page.getByRole('button', { name: 'Accept v3', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Show items needing you', exact: true })).toContainText('2')
  await expect(page.locator('.resolution-card')).toContainText('Artifact accepted')
  await selectTask(page, 'update')
  await expect(page.locator('.action-scope')).toContainText('#dayline-preview')
  await expect(page.locator('.scope-warning')).toBeVisible()
})

for (const viewport of [{ width: 1280, height: 720 }, { width: 820, height: 720 }, { width: 390, height: 800 }]) {
  test(`C keeps feedback and authorization reachable at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/?design=c')
    if (viewport.width < 721) await selectTask(page, 'readme')
    await expect(page.getByRole('button', { name: 'Accept v3', exact: true })).toBeInViewport()
    await page.getByRole('button', { name: 'Request changes', exact: true }).click()
    await expect(page.getByLabel('What needs to change?')).toBeInViewport()
    await page.getByLabel('What needs to change?').fill('Keep feedback reachable in the control room.')
    await expect(page.getByRole('button', { name: 'Send revision request' })).toBeInViewport()
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    if (viewport.width < 721) await page.getByRole('button', { name: 'Work list', exact: true }).click()
    await selectTask(page, 'update')
    await expect(page.getByRole('button', { name: 'Authorize once', exact: true })).toBeInViewport()
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(viewport.width)
  })
}
