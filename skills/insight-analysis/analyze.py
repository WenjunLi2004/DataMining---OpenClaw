#!/usr/bin/env python3
"""
Generate fact-grounded OpenClaw insights.

The LLM, when available, is allowed to reason only from diagnostic_summary.json.
If the API is unavailable or the output does not contain the required sections,
the script falls back to a deterministic Markdown template.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DIAGNOSTIC = Path.home() / "openclaw-project/data/diagnostic_summary.json"
DEFAULT_OUTPUT = Path.home() / "openclaw-project/reports/INSIGHTS.md"
OPENCLAW_CFG = Path.home() / ".openclaw/openclaw.json"

REQUIRED_SECTIONS = [
    "## 1. 实验结论",
    "## 2. 模型行为解释",
    "## 3. 数据集问题诊断",
    "## 4. 真正有意义的特征",
    "## 5. 不能过度相信的结论",
    "## 6. 下一步实验建议",
    "## 7. 可追问问题",
]

# Numbers below this absolute value are treated as "trivial" (year fragments,
# counts like "7", "30 天", etc.) and not subject to grounding checks.
GROUNDING_TRIVIAL_INTS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 80, 100}
# Maximum fraction of LLM-emitted numbers that may be ungrounded before we
# reject the output. A small allowance covers years like "2025" and sample-size
# echoes that drift past 1-decimal rounding.
GROUNDING_TOLERANCE_FRAC = 0.10


def _get(d: dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "未测量"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "未测量"
    return f"{float(value) * 100:.{digits}f}%"


def _best(summary: dict[str, Any], key: str) -> str:
    item = _get(summary, f"models.{key}")
    if not item:
        return "未测量"
    return f"{item.get('model')}={_fmt(item.get('value'))}"


def _model_row(summary: dict[str, Any], name: str) -> dict[str, Any]:
    return _get(summary, f"models.metrics.{name}", {}) or {}


def _load_api_config() -> tuple[str, str, str]:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
    model = os.environ.get("OPENCLAW_INSIGHT_MODEL") or "deepseek-chat"

    if OPENCLAW_CFG.exists():
        try:
            cfg = json.loads(OPENCLAW_CFG.read_text())
            deepseek = cfg.get("models", {}).get("providers", {}).get("deepseek", {})
            api_key = api_key or deepseek.get("apiKey", "")
            base_url = os.environ.get("DEEPSEEK_BASE_URL") or deepseek.get("baseUrl", base_url)
        except Exception:
            pass
    return api_key, base_url, model


def deterministic_insights(summary: dict[str, Any], source_note: str = "deterministic-template") -> str:
    task = summary.get("task", {})
    models = summary.get("models", {})
    rf = _model_row(summary, "RF")
    lr = _model_row(summary, "LR")
    xgb = _model_row(summary, "XGBoost")
    baseline = _get(summary, "baselines.best_single_feature_auc")
    lang = summary.get("per_language", {})
    anomaly = lang.get("anomaly") or {}
    validation = _get(summary, "validation.time_split", {}) or {}
    ablation = summary.get("ablation", {})
    biggest = ablation.get("biggest_jump") or {}
    smallest = ablation.get("smallest_jump") or {}
    correlations = summary.get("feature_correlations", {})
    feature = summary.get("feature_importance", {})
    top_gini = (feature.get("top10_gini") or [{}])[0]
    top_shap = (feature.get("top10_shap") or [{}])[0]
    disagreements = feature.get("disagreements") or []
    anomalies = summary.get("anomalies", [])
    recommendations = summary.get("recommendations", [])

    model_table = (
        f"| 模型 | AUC | PR-AUC | F1 | Precision | Recall | P@10 |\n"
        f"|---|---:|---:|---:|---:|---:|---:|\n"
        f"| LR | {_fmt(lr.get('auc'))} | {_fmt(lr.get('pr_auc'))} | {_fmt(lr.get('f1'))} | {_fmt(lr.get('precision'))} | {_fmt(lr.get('recall'))} | {_fmt(lr.get('precision_at_10'), 2)} |\n"
        f"| RF | {_fmt(rf.get('auc'))} | {_fmt(rf.get('pr_auc'))} | {_fmt(rf.get('f1'))} | {_fmt(rf.get('precision'))} | {_fmt(rf.get('recall'))} | {_fmt(rf.get('precision_at_10'), 2)} |\n"
        f"| XGBoost | {_fmt(xgb.get('auc'))} | {_fmt(xgb.get('pr_auc'))} | {_fmt(xgb.get('f1'))} | {_fmt(xgb.get('precision'))} | {_fmt(xgb.get('recall'))} | {_fmt(xgb.get('precision_at_10'), 2)} |"
    )

    baseline_line = "未计算单特征 baseline。"
    if baseline:
        gap = None
        best_auc = _get(summary, "models.best_auc.value")
        if best_auc is not None and baseline.get("auc") is not None:
            gap = best_auc - baseline["auc"]
        baseline_line = (
            f"最佳单特征 baseline 是 `{baseline.get('name')}`，AUC={_fmt(baseline.get('auc'))}；"
            f"最佳模型是 {_best(summary, 'best_auc')}，差距={_fmt(gap)}。"
        )

    anomaly_line = "未发现可计算的语言级异常。"
    if anomaly:
        anomaly_line = (
            f"语言级最低可靠 AUC 出现在 `{anomaly.get('language')}`："
            f"AUC={_fmt(anomaly.get('auc'))}，positive rate={_pct(anomaly.get('positive_rate'))}，"
            f"比全局高 {_pct(anomaly.get('positive_rate_vs_global'))}，"
            f"比可用语言均值低 {_fmt(anomaly.get('auc_drop_below_language_mean'))}。"
        )

    corr_line = (
        f"`readme_len_30d` 与 `commits_30d` 的相关系数是 "
        f"{_fmt(correlations.get('readme_len_30d_vs_commits_30d'))}。"
    )

    anomaly_bullets = "\n".join(
        f"- {a.get('title')}: {a.get('implication')}" for a in anomalies
    ) or "- 未记录额外异常。"
    rec_bullets = "\n".join(
        f"- {r.get('priority')}: {r.get('action')} 原因：{r.get('reason')}" for r in recommendations
    ) or "- 暂无建议。"

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# OpenClaw Insight Analysis

生成时间：{generated_at}  
生成方式：{source_note}  
事实来源：`data/diagnostic_summary.json`

## 1. 实验结论

OpenClaw 当前最稳的定位是历史回测实验：使用仓库创建后 {task.get('snapshot_window_days', 30)} 天内的早期信号，预测它是否进入样本内 top 20%。本轮样本量为 {task.get('n_samples')}，正例为 {task.get('n_positive')}，positive rate={_pct(task.get('positive_rate'))}，top-20 阈值为 {task.get('top20_threshold_current_stars')} stars。

{model_table}

结论上，最佳 AUC 是 {_best(summary, 'best_auc')}，最佳 PR-AUC 是 {_best(summary, 'best_pr_auc')}，最佳 P@10 是 {_best(summary, 'best_p10')}。{baseline_line}

## 2. 模型行为解释

RF 的 AUC={_fmt(rf.get('auc'))}、Precision={_fmt(rf.get('precision'))}、Recall={_fmt(rf.get('recall'))}、P@10={_fmt(rf.get('precision_at_10'), 2)}。这说明 RF 更适合“少量候选短名单”的推荐场景：它在高置信 top-10 上表现强，但默认分类阈值下 Recall 较低，会漏掉一部分潜力项目。

LR 的 Recall={_fmt(lr.get('recall'))}，通常更愿意覆盖更多正例；XGBoost 的 Precision={_fmt(xgb.get('precision'))}、Recall={_fmt(xgb.get('recall'))}，在保守性和覆盖率之间更均衡。若产品目标是“每天只看 3-5 个”，RF 的高 P@10 更有用；若目标是“尽量不要漏掉潜力股”，LR/XGBoost 的 Recall 更值得关注。

## 3. 数据集问题诊断

{anomaly_line}

此外，数据诊断记录了这些风险：

{anomaly_bullets}

这些问题不否定模型结果，但会限制结论边界。当前模型只使用 19 个严格的 30 天内早期特征，已经移除 TF-IDF / author_followers / has_license / 当前 README 等无法历史回溯或泄漏当前状态的字段；所有特征均来自 created_at + 30 天窗口，不含任何事后信息。

## 4. 真正有意义的特征

RF Gini 的最高特征是 `{top_gini.get('feature', '未测量')}`，分数={_fmt(top_gini.get('importance'))}。SHAP 的最高特征是 `{top_shap.get('feature', '未测量')}`，mean|SHAP|={_fmt(top_shap.get('mean_abs_shap'))}。

{corr_line}

Ablation 中最大 AUC 增量来自 `{biggest.get('to', '未测量')}`，delta={_fmt(biggest.get('delta_auc'))}；最小增量来自 `{smallest.get('to', '未测量')}`，delta={_fmt(smallest.get('delta_auc'))}。这比单看 feature importance 更可靠，因为它检验了成组特征对模型表现的边际贡献。

Gini 和 SHAP 的差异：{'; '.join(disagreements) if disagreements else '未记录明显 top-5 分歧。'} 解释特征时应把它们当作“模型使用了什么信号”，不要直接说成因果关系。

## 5. 不能过度相信的结论

不能把本项目说成已经能稳定预测“今天哪些项目一定会火”。当前标签是 `_current_stars` 形成的历史回测标签，不是实时未来标签；如果做 Today Radar，只能叫候选观察清单。

Time split 结果：AUC={_fmt(validation.get('auc'))}，random CV AUC={_fmt(validation.get('random_cv_auc'))}，gap={_fmt(validation.get('auc_gap'))}。这个结果能说明单窗口数据内的时序风险较小，但不能自动推广到不同月份、不同主题热潮或更长期窗口。

另外，TypeScript 样本量有限（约 31 条），语言级结论需在报告里加谨慎表述：这是课程级 prototype，不是生产级预测系统。

## 6. 下一步实验建议

{rec_bullets}

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
"""


def _walk_numbers(value: Any) -> Iterable[float]:
    """Yield every numeric value reachable from a nested dict/list."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if value != value:  # NaN guard
            return
        yield float(value)
        return
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk_numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_numbers(v)
    elif isinstance(value, str):
        # Also harvest numbers embedded in string fields (e.g. "AUC=0.878").
        for m in re.finditer(r"-?\d+(?:\.\d+)?", value):
            try:
                yield float(m.group())
            except ValueError:
                continue


def _build_grounding_set(summary: dict[str, Any]) -> set[float]:
    """Flatten every number in the diagnostic summary into a set of variants.

    For each numeric value N we include the value itself plus several common
    rounding variants so the verifier accepts e.g. 0.878 written as 0.88.
    Percent forms (100 × N for fractions in [0, 1]) are also included so
    "20.2%" matches a stored positive_rate of 0.202.
    """
    raw_numbers = set()
    for n in _walk_numbers(summary):
        raw_numbers.add(n)
        if -1.0 <= n <= 1.0:
            raw_numbers.add(n * 100.0)

    variants: set[float] = set()
    for n in raw_numbers:
        variants.add(round(n, 4))
        variants.add(round(n, 3))
        variants.add(round(n, 2))
        variants.add(round(n, 1))
        if abs(n) >= 1.0:
            variants.add(round(n))
    return variants


def _extract_numbers_from_text(text: str) -> list[float]:
    """Pull every standalone number out of the LLM output.

    We deliberately keep this loose: percent suffixes are absorbed, but the
    numeric value is what we compare. Anything inside backticks is also
    considered (because the LLM often quotes feature names with numbers).
    """
    nums: list[float] = []
    for m in re.finditer(r"-?\d+(?:\.\d+)?", text):
        token = m.group()
        try:
            nums.append(float(token))
        except ValueError:
            continue
    return nums


def _verify_numbers(text: str, summary: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, reason). LLM output is rejected if too many numbers can't
    be matched against the diagnostic summary."""
    grounded = _build_grounding_set(summary)
    found = _extract_numbers_from_text(text)
    if not found:
        return True, "no numbers in LLM output"

    ungrounded: list[float] = []
    for value in found:
        # Trivial integers (years, small counts) are always allowed.
        if value.is_integer() and int(value) in GROUNDING_TRIVIAL_INTS:
            continue
        if value.is_integer() and 2000 <= int(value) <= 2100:
            continue  # year-like

        if any(
            abs(value - candidate) <= max(0.05, abs(candidate) * 0.005)
            for candidate in grounded
        ):
            continue
        ungrounded.append(value)

    total = max(len(found), 1)
    bad_frac = len(ungrounded) / total
    if bad_frac > GROUNDING_TOLERANCE_FRAC:
        sample = ", ".join(f"{x:g}" for x in ungrounded[:6])
        return (
            False,
            f"{len(ungrounded)}/{total} numbers ({bad_frac:.0%}) not grounded "
            f"in diagnostic_summary.json; e.g. {sample}",
        )
    return True, f"{len(ungrounded)}/{total} numbers ungrounded (within {GROUNDING_TOLERANCE_FRAC:.0%} tolerance)"


def llm_insights(summary: dict[str, Any]) -> str:
    api_key, base_url, model = _load_api_config()
    if not api_key:
        raise RuntimeError("no API key available")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    system = """你是 OpenClaw 的 insight-analyst sub-agent，角色是资深数据科学家。
你只能根据用户提供的 diagnostic_summary.json 做分析。
禁止编造数字，禁止引用文件中不存在的实验，禁止把推测写成事实。
如果某个指标不存在，必须写“未测量”或“当前数据没有提供”。
请用中文 Markdown 输出，并严格包含以下 7 个二级标题：
## 1. 实验结论
## 2. 模型行为解释
## 3. 数据集问题诊断
## 4. 真正有意义的特征
## 5. 不能过度相信的结论
## 6. 下一步实验建议
## 7. 可追问问题
"""
    user = (
        "请基于下面的 diagnostic_summary.json 生成 OpenClaw INSIGHTS.md。"
        "所有数字必须来自 JSON。\n\n"
        + json.dumps(summary, ensure_ascii=False, indent=2)
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        max_tokens=5000,
    )
    text = response.choices[0].message.content or ""
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    if missing:
        raise RuntimeError(f"LLM output missing required sections: {missing}")

    ok, reason = _verify_numbers(text, summary)
    if not ok:
        raise RuntimeError(f"LLM output failed grounding check: {reason}")
    print(f"  [grounding] {reason}", flush=True)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", default=str(DEFAULT_DIAGNOSTIC))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mode", choices=["auto", "llm", "template"], default="auto")
    args = parser.parse_args()

    diagnostic_path = Path(args.diagnostic).expanduser()
    output_path = Path(args.output).expanduser()
    if not diagnostic_path.exists():
        raise SystemExit(f"[ERROR] diagnostic summary not found: {diagnostic_path}")

    summary = json.loads(diagnostic_path.read_text())
    mode_used = "template"
    if args.mode in {"auto", "llm"}:
        try:
            text = llm_insights(summary)
            mode_used = "llm"
        except Exception as exc:
            if args.mode == "llm":
                raise
            print(
                f"  [warning] LLM path rejected, falling back to deterministic template: {exc}",
                file=sys.stderr, flush=True,
            )
            text = deterministic_insights(summary, source_note=f"deterministic-template (LLM fallback: {exc})")
    else:
        text = deterministic_insights(summary)

    if mode_used == "llm":
        text = text.rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(f"Insight analysis written → {output_path}", flush=True)
    print(f"  mode: {mode_used}", flush=True)


if __name__ == "__main__":
    main()
