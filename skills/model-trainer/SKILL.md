---
name: model-trainer
description: Train LR / RF / XGBoost on features.csv for GitHub star prediction. Runs 5-fold stratified CV, outputs metrics (AUC, F1, Precision, Recall, Accuracy) and top-10 feature importances to model_results.json.
metadata: { "openclaw": { "emoji": "🤖", "requires": { "bins": ["python3"], "env": [] } } }
---

# Model Trainer

Trains three classifiers on `features.csv` and outputs evaluation results.

## Models

| Model | Notes |
|-------|-------|
| LR | Logistic Regression + StandardScaler, class_weight=balanced |
| RF | Random Forest 200 trees, class_weight=balanced |
| XGBoost | 200 estimators, scale_pos_weight=4 for imbalanced classes |

## Usage

```bash
python3 ~/.openclaw/workspace/skills/model-trainer/train.py
# or with explicit paths:
python3 ~/.openclaw/workspace/skills/model-trainer/train.py \
  --input ~/openclaw-project/data/features.csv \
  --output ~/openclaw-project/data/model_results.json
```

## Output schema (model_results.json)

```json
{
  "models": {
    "LR":      { "auc": {"mean": 0.85, "std": 0.03}, "f1": {...}, ... },
    "RF":      { ... },
    "XGBoost": { ... }
  },
  "feature_importance": {
    "RF":      [{"feature": "commits_30d", "importance": 0.12}, ...],
    "XGBoost": [...],
    "LR":      [...]
  },
  "meta": { "n_samples": 500, "n_features": 38, ... }
}
```
