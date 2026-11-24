export type TaskStatus = 'running' | 'review' | 'approval' | 'done'
export type TaskTone = 'violet' | 'amber' | 'mint' | 'blue'

export interface Activity {
  id: string
  actor: 'agent' | 'human' | 'system'
  title: string
  body: string
  time: string
  kind?: 'note' | 'artifact' | 'decision' | 'tool'
}

export interface Task {
  id: string
  title: string
  project: string
  status: TaskStatus
  statusLabel: string
  summary: string
  goal: string
  agent: string
  agentMode: 'Controlled' | 'Delegate' | 'Observe'
  updatedAt: string
  progress: number
  tone: TaskTone
  decisionType?: '验收' | '授权' | '澄清'
  risk?: '低风险' | '中风险' | '高风险'
  artifact?: {
    name: string
    version: string
    changed: string
    lines: number
  }
  activities: Activity[]
}

export const tasks: Task[] = [
  {
    id: 'research',
    title: '整理 Agent 桌面产品参考',
    project: 'Dayline / 产品研究',
    status: 'running',
    statusLabel: '执行中',
    summary: '正在归纳 6 个产品的信息架构，重点比较任务恢复与人工介入方式。',
    goal: '形成一份可追溯的竞品研究摘要，并提炼不依赖具体厂商的设计原则。',
    agent: 'Atlas Research',
    agentMode: 'Delegate',
    updatedAt: '刚刚',
    progress: 68,
    tone: 'violet',
    decisionType: '澄清',
    activities: [
      {
        id: 'r1',
        actor: 'agent',
        title: '完成第一轮资料扫描',
        body: '已覆盖桌面工作区、审阅收件箱和连接管理三个方向，共保留 18 条来源记录。',
        time: '10:42',
        kind: 'tool',
      },
      {
        id: 'r2',
        actor: 'agent',
        title: '需要确认研究边界',
        body: '是否把团队协作产品纳入第一轮对比？这会增加约 35 分钟，但能补足交接视角。',
        time: '10:47',
        kind: 'decision',
      },
    ],
  },
  {
    id: 'readme',
    title: '更新项目说明与快速开始',
    project: 'Dayline / 文档',
    status: 'review',
    statusLabel: '待验收',
    summary: 'README v3 已生成，补充本地运行、能力边界和恢复语义，需要你审阅差异。',
    goal: '让首次访问仓库的人在 5 分钟内理解产品定位、边界并运行演示。',
    agent: 'Forge Local',
    agentMode: 'Controlled',
    updatedAt: '8 分钟前',
    progress: 100,
    tone: 'mint',
    decisionType: '验收',
    risk: '低风险',
    artifact: {
      name: 'README.md',
      version: 'v3',
      changed: '+42 −11',
      lines: 186,
    },
    activities: [
      {
        id: 'd1',
        actor: 'human',
        title: '你退回了 v2',
        body: '请明确区分“审批已通过”和“外部动作已完成”，不要把演示数据描述成真实连接。',
        time: '09:28',
        kind: 'note',
      },
      {
        id: 'd2',
        actor: 'agent',
        title: '已生成 README v3',
        body: '调整了状态术语，并新增“原型能力边界”章节。所有修改均已绑定到本次反馈。',
        time: '09:51',
        kind: 'artifact',
      },
    ],
  },
  {
    id: 'update',
    title: '准备本周项目更新',
    project: 'Dayline / 项目沟通',
    status: 'approval',
    statusLabel: '待授权',
    summary: '消息草稿已通过内容验收，等待批准发送到测试频道 #dayline-preview。',
    goal: '汇总本周产品决策与下周计划，经确认后发送到测试频道。',
    agent: 'Courier HTTP',
    agentMode: 'Controlled',
    updatedAt: '21 分钟前',
    progress: 100,
    tone: 'amber',
    decisionType: '授权',
    risk: '中风险',
    artifact: {
      name: 'weekly-update.md',
      version: 'v2 · 已验收',
      changed: '+18 −4',
      lines: 34,
    },
    activities: [
      {
        id: 'u1',
        actor: 'human',
        title: '内容验收通过',
        body: 'v2 内容已接受。接受产物不会自动批准发送。',
        time: '09:16',
        kind: 'decision',
      },
      {
        id: 'u2',
        actor: 'system',
        title: '创建一次性动作意图',
        body: 'message.publish → #dayline-preview，绑定 weekly-update.md v2，有效期至 12:30。',
        time: '09:17',
        kind: 'tool',
      },
    ],
  },
  {
    id: 'release',
    title: '检查 Windows 打包清单',
    project: 'Dayline / Release 0.1',
    status: 'done',
    statusLabel: '已完成',
    summary: '检查清单已验收，未执行签名、发布或上传操作。',
    goal: '检查桌面应用打包前的必要材料，不执行任何外部发布动作。',
    agent: 'Forge Local',
    agentMode: 'Delegate',
    updatedAt: '昨天',
    progress: 100,
    tone: 'blue',
    activities: [
      {
        id: 'p1',
        actor: 'system',
        title: '任务完成',
        body: '产物已验收并保存为私人记录；本任务没有外部动作。',
        time: '昨天 18:24',
        kind: 'decision',
      },
    ],
  },
]

export const inboxItems = [
  {
    id: 'approval-send',
    taskId: 'update',
    type: '授权',
    title: '允许发送本周项目更新？',
    description: '内容已验收；本次决定只授权向一个测试频道发送绑定版本。',
    time: '21 分钟前',
    risk: '中风险',
    accent: 'amber',
  },
  {
    id: 'review-readme',
    taskId: 'readme',
    type: '验收',
    title: 'README v3 已准备复查',
    description: 'Agent 声称已落实你对状态术语与演示边界的反馈。',
    time: '8 分钟前',
    risk: '低风险',
    accent: 'mint',
  },
  {
    id: 'clarify-research',
    taskId: 'research',
    type: '澄清',
    title: '研究范围需要你的选择',
    description: '是否把团队协作产品纳入第一轮对比？预计增加 35 分钟。',
    time: '刚刚',
    risk: '低风险',
    accent: 'violet',
  },
] as const
