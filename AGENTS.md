# openclaw-project

课程级 ML 数据挖掘与 multi-agent 实验项目。目标：用 GitHub 仓库创建后 30 天内的早期信号，做历史回测，预测仓库当前 star 是否进入样本内 top 20%，并自动生成可解释实验分析报告。

> 定位边界：OpenClaw 默认使用固定历史快照，保证课程实验可复现；它不是生产级“每天预测谁一定会火”的系统。若后续加入 Today Radar，只应表述为“近期候选项目观察清单”，不是已验证预测。

## 用户偏好记忆

- 后续新增或更新记忆时，必须同步到 Claude-facing 和 Codex-facing 的说明/记忆文件，不要只写一边。
- 生成或重构 HTML walkthrough / report / explanation 页面时，默认加入左侧导航栏，方便按板块浏览。

---

## 已完成的 Skills

### `repo-collector`
路径：`~/.openclaw/workspace/skills/repo-collector/`

采集 GitHub 仓库历史数据，核心脚本 `collect.py`，支持：
- `--target N` 指定采集数量（默认 20，测试用）
- `--start / --end` 指定创建时间范围
- `--out-dir / --out-file` 指定输出路径

```bash
# 快速测试（20 个）
python3 ~/.openclaw/workspace/skills/repo-collector/collect.py --target 20

# 完整采集
python3 ~/.openclaw/workspace/skills/repo-collector/collect.py --target 500
```

---

## 数据文件

| 文件 | 描述 |
|------|------|
| `data/repos_raw_500_strict.jsonl` | **正式数据**：500 条 strict-30d 记录（2026-05-30 采集，created 2025-03-01..2025-04-30，batch=strict_30d_1y_2025_03_04） |
| `data/repos_raw_500.jsonl` | 本地旧版历史备份（2026-05-18 采集，created 2025-05-01..2025-06-30）——**不含 30d 字段，已从仓库排除，不再作为主数据源** |
| `data/repos_raw.jsonl` | 20 条 strict-30d 样例记录（快速测试 / schema 查看用） |
| `data/summary.md` | 最近一次采集的统计报告 |
| `data/collect_500_strict.log` | strict 采集的本地完整运行日志（`.gitignore` 排除，不随仓库提交） |
| `data/collect_500.log` | 旧版本地采集日志（历史存档，不随仓库提交） |

### 数据规模（strict-30d，2026-05-30）
- 采集成功：500 / 500，失败：0
- 创建日期：2025-03-01 .. 2025-04-30（满足“30 天观察窗 + 完整一年标签窗口”）
- 语言分布：Python 100 · JavaScript 100 · Go 99 · Rust 99 · TypeScript 99 · unknown 3
- Star 分布（当前）：0–9 占 283 · 10–49 占 121 · 50–199 占 61 · 200–999 占 19 · 1000+ 占 16

### JSONL 记录结构

```json
{
  "snapshot": {
    "name", "full_name", "language", "topics", "description", "license",
    // strict-30d 模型特征
    "has_readme_30d", "readme_len_30d", "readme_has_image_30d", "readme_has_demo_url_30d",
    "readme_ref_sha",
    "commits_30d", "contributors_30d", "issues_30d", "prs_30d",
    // 旧的当前态字段保留为 metadata，不进模型
    "has_readme", "readme_len", "readme_has_image", "readme_has_demo_url",
    "contributors", "author_followers", "author_public_repos", "author_type",
    "window_since", "window_until"
  },
  "labels": {
    "current_stars", "current_forks", "created_at", "last_commit_at"
  }
}
```

---

## 关键设计决策

**防 leakage 设计（strict-30d v3，2026-05-30 升级）**
最终模型使用 19 个更严格的早期特征：30 天开发活跃度、30 天历史 README、语言和 owner 类型。无法历史回溯的当前态字段已移出模型，以降低后验信息泄漏：
- commits / issues / PRs 均使用 `since` + `until` 参数过滤
- `contributors_30d`：基于前 30 天 commits 内不同 commit-author 标识（login → email → name）去重计数，**不再使用** GitHub 当前 `/contributors` endpoint
- 历史 README：通过 `/commits?until=cutoff` 拿到 `created_at + 30 天`前最近一次 commit SHA，再用 `/readme?ref=SHA` 拉取该 SHA 对应的 README，输出 `readme_len_30d / has_readme_30d / readme_has_image_30d / readme_has_demo_url_30d / readme_ref_sha`
- 当前态字段 `author_followers / author_public_repos / has_license / 当前 README / 当前 contributors / TF-IDF(topics+description)` 仍写到 JSONL 中作为 audit metadata，但 feature-extractor **不会**把它们送进模型
- `current_stars` / `current_forks` 明确放入 `labels`，不混入 snapshot

**语言覆盖策略**
搜索时对每种语言设置硬性 quota（`ceil(target / 5)`），防止 Python 独占结果。
strict-30d 重采后语言分布更均衡：Python 100、JavaScript 100、Go 99、Rust 99、TypeScript 99、unknown 3。

**搜索多样性**
使用 5 语言 × 20 个 AI/CS 关键词的组合搜索，按 stars 降序取结果，去重后截取 target 数量。

**Rate limit 处理**
- Search API：每次请求后 sleep 1.2s（≤30 req/min）
- Core API：`X-RateLimit-Remaining < 5` 时自动等待到 reset
- 遇 403/5xx 指数退避重试，最多 5 次

---

## Sub-agent Pipeline（2026-05-18 实现，2026-05-24 增强）

Orchestrator + 执行型子任务 + 分析型子任务，用户说"开始分析"即自动跑完整流程。

### 启动方式

```bash
export DEEPSEEK_API_KEY=sk-...
openclaw agent --agent pipeline-orchestrator --message "开始分析"
```

`pipeline-orchestrator` skill 入口会自动启动并打开 OpenClaw Console：
`http://localhost:8080/dashboard/`。

底层脚本仍可直接运行：

```bash
python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py "开始分析"
python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py --no-open-dashboard "开始分析"
```

### 复现 pipeline vs 强制重跑

复现 pipeline 的推荐命令仍然是：

```bash
openclaw agent --agent pipeline-orchestrator --message "开始分析"
```

这条命令并不等于强制所有步骤重跑——`skip` 是 agent 在 `run_inspect_pipeline_state` 之后根据
文件时间戳作出的调度决策。如果你想让某些步骤真的重新执行，更推荐的做法是删除对应的产物
文件（例如 `data/diagnostic_summary.json`），让 orchestrator 根据 missing/stale 状态自动恢复。

#### --force-local：演示用强制重算

仅强制重算本地分析链路，**不**重采 GitHub 数据。canonical `data/repos_raw_500_strict.jsonl` 完全
保持不变：

```bash
python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py --force-local "开始分析"
```

执行顺序：`feature-extractor → model-trainer → diagnostic-builder → insight-analysis → report-generator`。
适合展示时确保所有步骤都看得到状态变化。

#### --force-full：高风险，**不推荐展示使用**

```bash
python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py --force-full "开始分析"
```

默认行为已收紧：新采集的数据会写到 `data/repos_raw_500_strict_force_<timestamp>.jsonl`，**canonical
historical snapshot 仍然保留**。下游步骤仍然消费 canonical 文件，因此默认 `--force-full`
对实验结果等价于 `--force-local` 加上一次重采集示例。

只有在 explicitly 通过 `--force-full-overwrite` 时才会真的覆盖 canonical：

```bash
python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py \
  --force-full --force-full-overwrite "开始分析"
```

GitHub Search API 结果不是确定性的：一旦覆盖，过往的课程实验就无法严格复现。脚本会在终端
打印醒目警告 + rollback 命令，但展示场景下应该避免使用该参数。

#### 自然语言强制触发已删除

为避免 `"请强制按规则执行"` 这类普通表述被误识别成 force 模式，orchestrator 不再扫描用户
消息中的关键字。`force-local` / `force-full` 只能通过 CLI flag 或环境变量
`OPENCLAW_FORCE_LOCAL=1` / `OPENCLAW_FORCE_FULL=1` 触发。

### 架构

```
orchestrator.py  (DeepSeek Chat + Tool Use)
├── run_repo_collector      → ~/.openclaw/workspace/skills/repo-collector/collect.py
├── run_feature_extractor   → ~/.openclaw/workspace/skills/feature-extractor/extract.py
├── run_model_trainer       → ~/.openclaw/workspace/skills/model-trainer/train.py
├── run_diagnostic_builder  → ~/.openclaw/workspace/skills/diagnostic-builder/diagnose.py
├── run_insight_analysis    → ~/.openclaw/workspace/skills/insight-analysis/analyze.py
├── run_report_generator    → ~/.openclaw/workspace/skills/report-generator/generate.py
└── run_today_radar         → ~/.openclaw/workspace/skills/today-radar/radar.py  (用户明确请求时)
```

### 调度策略

- 默认不再按文件年龄自动重采集数据；`data/repos_raw_500_strict.jsonl` 是固定历史回测快照。
- 缺少 raw data 时才采集；用户明确要求 force refresh 时才重采。
- features / model_results / diagnostic_summary / INSIGHTS 按依赖时间戳判断是否需要刷新。
- HTML report 每次都重新生成，用来记录本次决策和最新 insight。
- Today Radar 是可选应用模式，仅在用户明确要求“今日雷达 / Today Radar / 近期项目”时运行。

### 中间产物

| 文件 | 描述 |
|------|------|
| `data/features.csv` | 500×19 strict-30d 特征矩阵 + metadata + is_top20 标签（单 batch 时使用全局 p80） |
| `data/model_results.json` | LR/RF/XGBoost 5-fold CV 指标 + 特征重要性 |
| `data/diagnostic_summary.json` | 事实诊断摘要：baseline、模型权衡、语言异常、相关性、ablation、caveats |
| `reports/INSIGHTS.md` | 基于 diagnostic_summary 的可解释分析，含 7 个章节（fact-grounded） |
| `reports/insights.html` | INSIGHTS.md 的 HTML 渲染版，dashboard 洞察分析 tab 直接消费 |
| `reports/YYYY-MM-DD_final.html` | HTML 评估报告，嵌入 Insight Analysis |
| `reports/latest_final.html` | 最新 HTML 评估报告的稳定入口，供 Console iframe 使用 |
| `data/model_artifacts/` | 可复用 RF 模型 + feature/model schema（feature_schema.json 锁定 19 个特征；旧 TF-IDF vectorizer 已废弃，新版 extractor 会主动清理） |
| `reports/today_radar.json` | Today Radar 候选项目清单（可选应用模式） |
| `reports/today_radar.html` | Today Radar HTML 报告 |
| `dashboard/index.html` / `reports.html` | 统一 OpenClaw Console：pipeline 状态 + backtest report + Today Radar |

### 特征设计（strict-30d v3，共 19 个）

- Language one-hot (6)：lang_Python · lang_JavaScript · lang_Go · lang_Rust · lang_TypeScript · lang_Other
- Owner type (1)：is_org
- Early activity (4)：commits_30d · issues_30d · prs_30d · contributors_30d
- Historical README (4)：has_readme_30d · readme_len_30d · readme_has_image_30d · readme_has_demo_url_30d
- Derived activity (4)：activity_total_30d · commits_per_contributor_30d · prs_per_issue_30d · has_pr_activity_30d

> **不再进模型的字段**（与 v2 的差异）：TF-IDF(topics + description bigrams)、author_followers、author_public_repos、has_license、旧 readme_len/has_readme/readme_has_image/readme_has_demo_url、旧 contributors（无时间过滤）。它们仍可能出现在 JSONL audit metadata 中。

---

## Dashboard (OpenClaw 控制台)

`dashboard/index.html` 展示 6 个 worker 步骤的实时状态，与 SKILL.md 的执行顺序一一对应：

```
数据采集 → 特征工程 → 模型训练 → 事实诊断 → 洞察分析 → 报告生成
```

数据源：

- `data/pipeline_status.jsonl`：流水线事件（agent_start / agent_completed / agent_failed / pipeline_start / pipeline_complete）；
  通过 `agents/orchestrator.py` 的 `_run()` 自动写入，每个 subprocess 步骤都会留事件。
- `data/diagnostic_summary.json`：右侧"历史回测摘要"卡片的指标来源。
- `reports/today_radar.json`：右侧"今日雷达"候选清单来源。

报告 tabs：

| Tab | 文件 |
|---|---|
| 历史回测报告 | `reports/latest_final.html` |
| 今日雷达 | `reports/today_radar.html` |
| 洞察分析 | `reports/insights.html`（由 `report-generator` 把 `INSIGHTS.md` 渲染成 HTML） |

启动方式：

```bash
cd ~/openclaw-project
python3 -m http.server 8080 --bind 127.0.0.1
# 然后浏览器打开 http://127.0.0.1:8080/dashboard/
```

`run.py` 启动 pipeline 时会自动起这个 server 并打开浏览器。

## 下一步计划

- [x] **strict-30d 特征工程**：去除 TF-IDF / author_followers / public_repos / has_license / 当前 README / 当前 contributors，保留 19 个严格 30 天内特征（2026-05-30）
- [x] **strict raw data 重采**：新增 `data/repos_raw_500_strict.jsonl`，500 条记录均含 `contributors_30d` 与历史 README 30d 字段；`feature_provenance.all_strict_30d = true`
- [ ] **baseline 展示增强**：在报告中更显式对比 commits_30d / readme_len_30d / contributors_30d 等简单排序规则
- [x] **TypeScript 补充采集**：strict 数据中 TypeScript 已提升到 99 条，可进行更稳定的语言级分析
- [ ] **Embedding 特征（未来扩展）**：DeepSeek embedding 可在保证 30 天历史可用的前提下作为新增信号尝试
- [ ] **Today Radar live run**：配置 GITHUB_TOKEN 后扫描创建于 30-45 天前的近期仓库；当前已支持离线冒烟测试
