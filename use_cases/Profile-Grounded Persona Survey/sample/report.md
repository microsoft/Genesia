# AI Task Delegation Survey [SIMULATED]

[Study scope and provenance](README.md) | [研究范围与来源](README_CN.md) | [Question distributions / 逐题分布](distributions.json)

Reviewed publication of one new completed profile-only survey using openai/gpt-6.1-terra at temperature1 via OpenRouter. No product was used. All answers and initial intents were generated anew; recommendations are hypotheses for validation, not observed defects.

Merged finding support/counter counts describe unions of cited answers. They do not establish that every cited Persona agrees with every clause; members may overlap across questions. These are synthetic results, not human-participant evidence, adoption rates or population estimates.

**阅读说明：** 20个合成Persona全部选择条件性考虑，并不代表真人采用率或独立共识；模型倾向、画像及共同问卷都可能促成趋同。不能只据此决定默认权限。本轮删除文件有1人不委托，其余19人每次确认，不沿用旧版“全部审批相同”的描述。每题百分比以该题已回答人数为分母，条件跳过不是缺失或拒绝。审批信息多选不是排序，未选某项不是反对；重要性量表与分类审批矩阵也不能混作自主性分数。费用、支持、来源核验和实际复核负担仍需分别验证，不是实测收益。

**人数范围：** 委派立场的解释中3/20提出屏幕阅读器或可访问控制条件；下一步验证题中4/20明确提出辅助技术核验，包含放大和键盘需求。两者按不同问题计数，不是两个互斥群体或额外参与者。

## Summary

这组合成样本倾向于从范围明确的小任务开始委托，同时保留对发送、修改和删除等行动的控制。下一步应优先验证分级授权、批准前信息和不确定结果的处理，而不是将任务兴趣视为自动执行授权。

- 20人均接受在明确限制内免逐次确认地创建未发送或发布的草稿，但发送和修改均需逐次确认；1人不愿委托删除文件。
- 批准前，20人均希望看到具体内容、目的地、权限范围和恢复选项。对于不确定输出，17人选择审阅草稿，3人选择先暂停询问。
- 所有人都考虑委托至少一项任务，但任务相关性、行动授权与实际使用是不同问题。
- 参与者愿意投入一定时间复核；无障碍、数据访问、费用和协作条件也值得在真实场景中验证。
- Synthetic Persona feedback, not research with real participants or a population estimate.

### Decision Snapshot
- **Relevant Tasks:** Drafting or revising text: 18 (90.0%) · Finding and comparing information: 20 (100.0%) · Organizing schedules or reminders: 20 (100.0%) · Organizing digital files: 10 (50.0%) · Summarizing documents or messages: 14 (70.0%)
- **Delegation Position:** Would consider delegating at least one task: 20 (100.0%)
- **Uncertain Output:** Provide an uncertain draft for me to review: 17 (85.0%) · Stop and ask me before continuing: 3 (15.0%)
- **Approval Information:** Exact content or change: 20 (100.0%) · Recipient or destination: 20 (100.0%) · Permission scope and limits: 20 (100.0%) · Reasons and supporting sources: 13 (65.0%) · Changes since the previous version: 18 (90.0%) · Undo or recovery options: 20 (100.0%)
- **Use Context:** Personal tasks: 7 (35.0%) · Work tasks: 11 (55.0%) · Both personal and work tasks: 2 (10.0%)

## Next actions

Prioritized from the evidence; ranking is decision support, not measured impact.


### 1. 在真实参与者研究中，用任务授权和行动确认原型测试分级控制：草稿可在明确限制内生成，发送、修改和删除需逐次确认，并允许选择不委托删除。
- **Target:** This study
- 这能检验关键行动边界及删除上的少数意见，同时保留参与者对受限草稿的开放态度；现有证据尚未验证具体限制如何设置。
Based on: [f1](#finding-f1), [f8](#finding-f8)

### 2. 测试批准前预览界面，展示具体内容或更改、目的地、权限范围和恢复选项，并检验版本变化及来源信息的呈现方式。
- **Target:** This study
- 四类信息获得一致选择，版本变化和来源的选择则有差异；测试应保留完整审阅，同时避免假定所有信息同等重要。
Based on: [f2](#finding-f2), [f6](#finding-f6)

### 3. 在不确定结果界面测试标注不确定草稿与暂停询问两种路径，并观察参与者如何核查后再决定是否行动。
- **Target:** This study
- 多数人希望先审阅草稿，但3人希望先暂停；两条路径可避免用单一处理方式覆盖不同边界。
Based on: [f3](#finding-f3), [f8](#finding-f8)

### 4. 在权限设置流程中测试访问范围和信息分享限制的说明与选择，包含共享设备情境。
- **Target:** This study
- 参与者重视隐私，并担心不必要的数据使用；应验证可理解的控制方式，而非假定已有泄露或缺陷。
Based on: [f4](#finding-f4), [f8](#finding-f8)

### 5. 用工作和个人场景中的提醒、信息比较及草稿任务开展实任务研究，记录核查过程和时间投入。
- **Target:** This study
- 这些任务在样本中相关，但兴趣不等于实际委托或收益；研究应保留人工复核，同时检验其时间成本。
Based on: [f5](#finding-f5), [f6](#finding-f6), [f8](#finding-f8)

### 6. 在后续原型研究中单独测试屏幕阅读器、键盘和放大操作，并纳入低带宽、共享设备及同事记录情境。
- **Target:** This study
- 少数参与者提出的使用条件可能影响适用性；这些是待验证条件，不是已证实的产品缺陷。
Based on: [f7](#finding-f7)

## Findings



<a id="finding-f1"></a>

### 草稿与有后果行动应分开授权
20人均偏好在明确限制内创建不发送或发布的草稿，无需逐次确认；修改现有文档和向他人发送消息则均要求逐次确认。删除文件时，19人要求每次确认，1人选择不委托。个别回答还限制付款、联系他人或敏感信息分享，说明任务委托不等于后续行动授权。20人均将执行控制评为极其重要，将撤销或恢复评为非常重要。

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 20人均偏好在明确限制内创建不发送或发布的草稿，无需逐次确认；同样20人均偏好修改现有文档和向他人发送消息时逐次确认。 (supporting answers: 20; counter answers: 0)
- 删除数字文件时，19人偏好每次执行前确认，1人选择不委托；无人选择在限制内免逐次确认。 (supporting answers: 19; counter answers: 1)
- 除审阅结果外，个别回答还提出不授权付款或联系他人、少分享个人或敏感信息，以及涉及同事记录时先与同事讨论。另一回答希望核对日程摘要后自己决定是否需要变更。这些条件说明任务委托与行动授权可以分开。 (supporting answers: 5; counter answers: 0)
- 全部20份回答将对执行内容的控制评为极其重要，并将撤销或恢复能力评为非常重要。 (supporting answers: 20; counter answers: 0)
- To validate: 明确限制的具体内容和不委托删除的原因尚不清楚；这些均为假设偏好。

</details>

<a id="finding-f2"></a>

### 批准前需要看清具体行动
20人均选择在批准前了解具体内容或更改、接收方或目的地、权限范围与限制，以及撤销或恢复选项。18人还选择查看相对上一版本的变化；13人选择理由与支持来源，7人未选择，但仍选择了前述四类信息。

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 20人均选择希望在批准前了解具体内容或更改、接收方或目的地、权限范围与限制，以及撤销或恢复选项。 (supporting answers: 20; counter answers: 0)
- 20人中有18人选择了自上一版本以来的变化；另有2人未选择该项，但都选择了具体内容或更改。 (supporting answers: 18; counter answers: 2)
- 20人中有13人选择理由与支持来源，7人未选择；后者仍全部选择了四类一致选择的信息。 (supporting answers: 13; counter answers: 7)
- To validate: 未选择某项不等于反对，也不能据此确定信息的相对重要性。

</details>

<a id="finding-f3"></a>

### 不确定结果需要两条处理路径
17人选择先获取不确定草稿供审阅，3人选择暂停并询问。草稿支持者常希望标出不确定内容，以便使用或分享前核查；部分人提到对照可信来源或自己的标准。多位回答者也担心结果出错，并希望在依赖或分享前检查。

Evidence contributors: 18 from cited supporting answers; 3 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 17个回答选择提供不确定草稿供审阅，希望先看到建议和不确定之处，再自行核查或决定；3个回答选择暂停询问，更希望在继续前掌握细节并决定下一步。 (supporting answers: 17; counter answers: 3)
- 草稿支持者常希望明确标出不确定内容，以便在使用或分享前核查；部分回答提到对照可信来源、日程或自身标准。多项回答还将审阅草稿与发送、更改或其他有后果的行动区分开，要求先自行决定或确认。 (supporting answers: 16; counter answers: 0)
- 多位回答者担心摘要、日程、比较或面向他人的材料出现错误，希望在依赖或分享结果前检查；其中有人特别希望核查来源。 (supporting answers: 15; counter answers: 0)
- To validate: 对错误的担忧并非错误已经发生，也未证明助手具备标注或提供来源的能力。

</details>

<a id="finding-f4"></a>

### 准确性和信息边界都重要
20人均将准确性和隐私评为至少非常重要，其中分别有16人和12人评为极其重要。多位回答者担心不必要地使用或分享个人、敏感或财务信息，希望知道或限制助手可访问的内容；共享设备也被特别提及。

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 20份回答均将准确性和隐私评为至少非常重要。其中准确性有16份评为极其重要、4份评为非常重要；隐私有12份评为极其重要、8份评为非常重要。 (supporting answers: 20; counter answers: 0)
- 多位回答者担心不必要地使用或分享个人、敏感或财务信息，也希望知道或限制助手可访问的内容；共享设备被特别提及。 (supporting answers: 16; counter answers: 0)
- 多条回答愿意付出复核或设置时间，但不愿放弃对发送、变更、重要行动或分享内容的控制；部分回答进一步限制不必要的个人信息、敏感细节或安全码。 (supporting answers: 18; counter answers: 0)
- To validate: 这些评分和担忧不是对实际准确性、权限设置或信息保护效果的评价。

</details>

<a id="finding-f5"></a>

### 从小任务入手，但场景和任务各异
20人均认为查找与比较信息、整理日程或提醒相关，18人选择文字撰写或修改，14人选择摘要，10人选择整理数字文件。全部20人会考虑委托至少一项任务；首选包括提醒、整理、规划和草稿，部分人希望在使用或发送前自行核对。场景选择为工作任务11人、个人任务7人、两者皆有2人。任务相关不代表授权后续行动。

Evidence contributors: 20 from cited supporting answers; 9 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 20人均选择查找与比较信息、整理日程或提醒；18人选择撰写或修改文字，另有2人未选择文字任务。 (supporting answers: 20; counter answers: 0)
- 14人选择总结文档或消息，6人未选择该任务。 (supporting answers: 14; counter answers: 6)
- 10人选择整理数字文件，10人未选择，表明该任务在本样本中的相关性并不一致。 (supporting answers: 10; counter answers: 10)
- 全部20名回答者都选择会考虑委托至少一项任务；理由集中在提醒、资料整理、草稿、清单或日程等起始任务。部分回答者强调要自行检查结果或依据可信来源核对。 (supporting answers: 20; counter answers: 0)
- 15条回答选择提醒、清单、摘要、资料整理、报告比较或学习规划等任务。理由包括任务简单或范围明确，以及能在使用前自行核对；任务相关性并不意味着愿意授权助手采取后续行动。 (supporting answers: 15; counter answers: 0)
- 5条回答选择起草会议跟进、团队更新、排程消息或教学材料。参与者希望在发送、分享或使用前检查措辞、细节或事实；其中有人明确由自己发送，或先决定是否发送。 (supporting answers: 5; counter answers: 0)
- 11人选择工作任务，7人选择个人任务，2人同时选择个人和工作任务。这是对假设性助手的场景偏好，不代表实际使用或委派意愿。 (supporting answers: 11; counter answers: 9)
- To validate: 这些选择未展示产品，也不代表实际委托、使用效果或持续使用。

</details>

<a id="finding-f6"></a>

### 愿意复核，但时间投入仍有差异
全部20条回答愿意投入一定时间检查结果、设置权限或确认变更。对本人所需时间，14人评为中等重要，6人评为非常重要。少数人希望总体节省时间，也有人即使节省较少仍愿意检查；因此不能把接受复核理解为对耗时没有限制。

Evidence contributors: 20 from cited supporting answers; 6 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 14份回答将本人所需时间评为中等重要，6份评为非常重要；后者表明时间投入对部分回答者也是重要的使用决策因素。 (supporting answers: 14; counter answers: 6)
- 全部 20 条回答都愿意投入一定时间检查结果、设置权限或确认变更；部分回答明确将此与完全自动化作对比。参与者意在用一定的时间和参与换取合适的协助或控制，而非表明已经使用过该助手。 (supporting answers: 20; counter answers: 0)
- 少数回答提出更具体的条件：有人希望总体节省时间，也有人即使节省时间较少仍愿意检查；另有人愿意接受更少的功能以换取权限控制和最少数据分享，或要求价格清晰、可核查来源。 (supporting answers: 6; counter answers: 0)
- To validate: 尚未测量复核耗时，也不能确定可接受的具体时间。

</details>

<a id="finding-f7"></a>

### 无障碍与使用条件可能影响适用性
3名回答者提出屏幕阅读器兼容或可访问控制等无障碍条件。后续验证建议还涉及放大、键盘操作、低带宽或有限数据量、共享设备保护、费用和支持；涉及同事记录时，个别回答希望先征求同事意见。

Evidence contributors: 17 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 三名回答者希望先看到演示；两名提及了解成本，其中一名还提及可获得的支持。另有三名提出无障碍条件，包括与屏幕阅读器兼容或可访问的控制方式。 (supporting answers: 7; counter answers: 0)
- 部分回答提出验证屏幕阅读器、放大或键盘操作，以及有限数据量或低带宽下的使用；另有回答关注共享设备上的信息保护、费用和支持。涉及工作或同事记录时，个别回答希望先征求同事意见；一份希望与信任的人一起练习。 (supporting answers: 17; counter answers: 0)
- To validate: 未提及这些条件不代表其他人不在意；没有产品展示或群体资料可用于判断缺陷或群体差异。

</details>

<a id="finding-f8"></a>

### 用具体任务验证控制与结果
多份回答希望先看演示或尝试排班、交接摘要、教学材料、提醒等小任务，再核对结果。回答也普遍希望了解所需信息或权限并验证能否限制行动；部分人还提出核对来源、不确定性、审核效率、确认或恢复方式。

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- 多份回答希望先看演示或尝试小任务，再核对结果；任务包括排班、交接摘要、教学材料和提醒等。部分回答特别提出核对来源、标注不确定性或检查结果是否便于快速审核。 (supporting answers: 19; counter answers: 0)
- 回答普遍希望了解所需信息或权限，并验证可否限制行动；多份回答还要求发送或修改前审核确认，或能够撤销和恢复。具体要求从审阅草稿到确认外部行动、恢复原始记录不等。 (supporting answers: 20; counter answers: 0)
- To validate: 提出试用不等于愿意持续委托，也不证明准确性或可用性。

</details>

## Limitations

研究基于20名合成参与者的假设性回答，未展示或使用产品，也未观察实际委托、操作结果或耗时。计数仅描述该样本，不支持总体推断；拒绝原因题因所有人均考虑至少一项委托而全部跳过。
