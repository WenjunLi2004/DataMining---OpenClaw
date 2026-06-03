# OpenClaw Insight Analysis

生成时间：2026-06-03 11:00 UTC  
生成方式：deterministic-template  
事实来源：`data/diagnostic_summary.json`

## 1. 实验结论

OpenClaw 当前最稳的定位是历史回测实验：使用仓库创建后 30 天内的早期信号，预测它是否进入样本内 top 20%。本轮样本量为 500，正例为 102，positive rate=20.4%，top-20 阈值为 49 stars。

| 模型 | AUC | PR-AUC | F1 | Precision | Recall | P@10 |
|---|---:|---:|---:|---:|---:|---:|
| LR | 0.8830 | 0.6243 | 0.6330 | 0.5135 | 0.8419 | 0.80 |
| RF | 0.8812 | 0.6617 | 0.5402 | 0.6320 | 0.4890 | 0.70 |
| XGBoost | 0.8759 | 0.6339 | 0.5994 | 0.5517 | 0.6843 | 0.80 |

结论上，最佳 AUC 是 LR=0.8830，最佳 PR-AUC 是 RF=0.6617，最佳 P@10 是 LR=0.8000。最佳单特征 baseline 是 `issues_30d`，AUC=0.6628；最佳模型是 LR=0.8830，差距=0.2201。

## 2. 模型行为解释

RF 的 AUC=0.8812、Precision=0.6320、Recall=0.4890、P@10=0.70。这说明 RF 更适合“少量候选短名单”的推荐场景：它在高置信 top-10 上表现强，但默认分类阈值下 Recall 较低，会漏掉一部分潜力项目。

LR 的 Recall=0.8419，通常更愿意覆盖更多正例；XGBoost 的 Precision=0.5517、Recall=0.6843，在保守性和覆盖率之间更均衡。若产品目标是“每天只看 3-5 个”，RF 的高 P@10 更有用；若目标是“尽量不要漏掉潜力股”，LR/XGBoost 的 Recall 更值得关注。

## 3. 数据集问题诊断

语言级最低可靠 AUC 出现在 `Go`：AUC=0.6641，positive rate=22.2%，比全局高 1.8%，比可用语言均值低 0.0661。

此外，数据诊断记录了这些风险：

- Python subset has much higher positive rate than global: Per-language Python AUC may be depressed by class distribution shift and within-language homogeneity.
- Some features are strongly correlated: Feature importance should be interpreted as model attribution, not causal attribution.

这些问题不否定模型结果，但会限制结论边界。当前模型只使用 19 个严格的 30 天内早期特征，已经移除 TF-IDF / author_followers / has_license / 当前 README 等无法历史回溯或泄漏当前状态的字段；所有特征均来自 created_at + 30 天窗口，不含任何事后信息。

## 4. 真正有意义的特征

RF Gini 的最高特征是 `lang_Python`，分数=0.1611。SHAP 的最高特征是 `lang_Python`，mean|SHAP|=0.1440。

`readme_len_30d` 与 `commits_30d` 的相关系数是 0.2150。

Ablation 中最大 AUC 增量来自 `C_readme`，delta=0.0186；最小增量来自 `D_all`，delta=-0.0072。这比单看 feature importance 更可靠，因为它检验了成组特征对模型表现的边际贡献。

Gini 和 SHAP 的差异：RF Gini top-5 only: commits_30d, lang_JavaScript; SHAP top-5 only: issues_30d, lang_TypeScript 解释特征时应把它们当作“模型使用了什么信号”，不要直接说成因果关系。

## 5. 不能过度相信的结论

不能把本项目说成已经能稳定预测“今天哪些项目一定会火”。当前标签是 `_current_stars` 形成的历史回测标签，不是实时未来标签；如果做 Today Radar，只能叫候选观察清单。

Time split 结果：AUC=0.8816，random CV AUC=0.8812，gap=0.0004。这个结果能说明单窗口数据内的时序风险较小，但不能自动推广到不同月份、不同主题热潮或更长期窗口。

另外，TypeScript 样本量有限（约 31 条），语言级结论需在报告里加谨慎表述：这是课程级 prototype，不是生产级预测系统。

## 6. 下一步实验建议

- P0: Keep the default experiment as a fixed historical backtest. 原因：It avoids unstable live labels and makes course evaluation reproducible.
- P0: Present Today Radar, if used, as a candidate shortlist rather than verified prediction. 原因：Recent repositories do not yet have future labels.
- P1: Compare model ranking against simple single-feature baselines. 原因：This shows whether the ML pipeline beats simple heuristics.
- P1: Verify that raw data was collected with the strict-30d collector (v2+). 原因：The 19-feature model assumes all features are bounded to the first 30 days; approximate values reduce model validity.
- P2: Treat TypeScript and per-language results as caveated unless more samples are collected. 原因：N500 TypeScript count is small.

最优先的工程动作是：保留固定历史回测作为主线；把 Today Radar 降级成”近期候选项目 shortlist”；继续做单特征 baseline 对比展示；确认原始数据由 strict-30d collector（v2+）采集，确保 19 个特征全部严格锁定在 30 天窗口内。

## 7. 可追问问题

- 为什么 RF 的 AUC 高，但 Recall 明显低？
- 如果只看 P@10，RF 是否比 XGBoost 更适合推荐场景？
- 最佳模型相比最佳单特征 baseline 到底多赢了多少？
- Python 子集为什么更难预测，是样本分布问题还是特征同质化问题？
- 去掉 `contributors_30d` 后 AUC 会下降多少？
- `readme_len_30d` 是真实质量信号，还是项目成熟度/曝光度的代理变量？
- TypeScript 样本不足会不会影响整体模型？
- 如果用固定 star 阈值代替样本内 top 20%，结论会不会变？
- Today Radar 应该输出预测结论，还是候选观察清单？
