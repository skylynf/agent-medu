# `evaluate/` — Medu-SPAgent 论文级分析库

面向 *Lancet Digital Health / npj Digital Medicine / JMIR Medical Education* 等顶刊投稿设计。
直接连接 Medu-SPAgent 平台运行时所用的 PostgreSQL，把 8 张原始表
（`users / training_sessions / messages / evaluation_snapshots / final_evaluations / ct_steps / survey_responses / prompts`）
**离线**拉取到 pandas，跑出 **CONSORT 队列流 → 人口学平衡 → 主结局 → 学习过程 → learning gain → checklist 逐项 → SUS/UES 信效度 → 相关矩阵 → 混合效应模型** 全套数值，并将结果同时**打印到命令行 + 落 CSV/JSON**。

> 默认不画图（满足你当前需求）。所有分析量都按可投稿的格式输出（n / mean (SD) / median [IQR] / 95% CI / Cohen's d / Hedges' g / Cliff's δ / η² / Cramér's V / Holm 与 Benjamini-Hochberg 校正 p）。

---

## 1. 实验设计假设

库按下列设计自动派生组别（无需手填映射）：

| 组 | 学习方法 (`training_sessions.method`) | 学习次数 | 考试 |
|---|---|---|---|
| **MA** | `multi_agent` | 2 | 1 (`exam`) |
| **SA** | `single_agent` | 2 | 1 (`exam`) |
| **CT** | `control` | 2 | 1 (`exam`) |

每个学生唯一组别 = 其全部学习会话采用的 `method`；若一名学生同时出现多种学习方法会被打成 `MIXED` 并在 *Cohort* 报告里高亮预警，方便你回到平台清理脏数据。

---

## 2. 安装

```powershell
cd E:\SPAgent
python -m venv .venv-eval
.\.venv-eval\Scripts\activate
pip install -r evaluate\requirements.txt
copy evaluate\.env.example evaluate\.env
notepad evaluate\.env   # 把 DATABASE_URL 填进去
```

> `DATABASE_URL` 用同步 psycopg2 串：
> `postgresql+psycopg2://USER:PASS@HOST:5432/DB?sslmode=require`
> 如果你贴的是 backend 用的 `postgresql+asyncpg://...`，库会自动改写成 psycopg2，但建议你显式填同步串。

---

## 3. 快速开始

```powershell
# 仅读取数据库 + 打印行数 + 字段类型
python -m evaluate inspect

# 把 8 张原始表落到 evaluate\output\raw\*.csv
python -m evaluate dump

# 跑全部分析（命令行打印 + 写 evaluate\output\）
python -m evaluate run

# 仅跑某几个 section
python -m evaluate run --section cohort --section exam --section mixed_models
```

可用 `--section` 取值：

| section | 说明 |
|---|---|
| `cohort` | CONSORT 队列流，pipeline 完整性，按 case 的样本分布，异常学生预警 |
| `demographics` | Table 1：role/institution/grade × group 卡方/Fisher，Cramér's V |
| `exam` | **主结局**：考试 OSCE 4 维 + final_score + checklist 加权分 + 诊断正误 在 MA/SA/CT 间的差异，含 Holm/BH 校正的 posthoc |
| `learning_process` | 学习阶段过程指标（duration / messages / completion / tutor 介入）每学生 2 次均值的组间比较 |
| `learning_gain` | session 1 → session 2 组内 paired 改善，以及 Δ 在三组间的差异 |
| `checklist_items` | 14 项 history-taking checklist 在考试场景的逐项 χ²，含校正 |
| `surveys` | SUS 总分、UES 总分 + 4 个分量表（FA/PU/AE/RW）的组间比较；逐题 mean (SD) by group |
| `reliability` | SUS / UES 的 Cronbach α（整体 + 分量表 + 分组） |
| `correlations` | 学习过程 ↔ 考试结局 ↔ 体验问卷 的 Spearman 矩阵（Holm/BH 校正） |
| `mixed_models` | 学习阶段 LMM `outcome ~ group × session_index + case + (1|user)`；考试 OLS / Logit `outcome ~ group + case` |
| `dialogue` | 对话级诊断：tutor 介入次数描述、学生消息平均字符数、响应延迟 |

---

## 4. 输出物

`run` 命令默认写到 `evaluate\output\`：

| 文件 | 说明 |
|---|---|
| `ds_students.csv` / `ds_learning.csv` / `ds_exams.csv` / `ds_checklist_long.csv` / `ds_surveys_wide.csv` | 派生宽表，可直接喂 SPSS / R / JASP |
| `<section>.json` | 该 section 的全部结构化结果（含描述 + 检验 + 效应量） |
| `<section>__*.csv` | 该 section 内部各表的扁平 CSV（嵌套字典自动展开为命名前缀） |
| `raw\raw_*.csv` | `dump` 命令落的 8 张原始表 |

---

## 5. 与已发表方法学的对齐

- **SUS** 标准计分（奇数 `score-1`、偶数 `5-score`，求和 ×2.5；满分 100）。仅当 10 题全部作答时给总分。
- **UES** 长版（O'Brien 2018）：反向题 6 − 原分；4 个分量表均分；Overall = 4 个分量表均分之和。
- **Cronbach α**：含整体 / 分量表 / 分组三种切片，便于在论文 *Methods → Reliability* 章节直接引用。
- **效应量**：连续型给 Cohen's d / Hedges' g / Cliff's δ；ANOVA 给 η² 与 ω²；Kruskal-Wallis 给 ε²；卡方给 Cramér's V。
- **多重比较校正**：Holm-Bonferroni 与 Benjamini-Hochberg FDR 同时输出。
- **正态性 / 方差齐性**：Shapiro-Wilk（n≤5000）/ D'Agostino's K²（n>5000）+ Levene；据此自动选择 Student-t / Welch-t / Mann-Whitney / 1-way ANOVA / Welch-ANOVA / Kruskal-Wallis。
- **混合效应**：学习阶段 `mixedlm(outcome ~ C(group) * C(session_index) + C(case_id), groups=user_id)`，REML=False（更利于嵌套模型 LR 检验）。考试阶段每学生 1 次 → OLS / Logit `outcome ~ C(group) + C(case_id)`，参考组固定 = `SA`。

---

## 6. 推荐论文呈现路径

1. **Figure 1 (CONSORT)**：用 `cohort` 的输出作底稿。
2. **Table 1 (Demographics)**：`demographics` 的 categorical_tables / categorical_tests 直接搬。
3. **Table 2 (Primary outcomes)**：`exam` 中的 `continuous` + `continuous_tests` + `binary`。
4. **Figure 2 (Learning curve)**：`learning_gain` 的 within_paired + between_delta。
5. **Table 3 (Per-item checklist)**：`checklist_items.item_tests`，已含校正 p。
6. **Table 4 (Experience)**：`surveys` + `reliability`（α 写正文，分量表写表）。
7. **Supplement**：`mixed_models` 的 `fixed_effects_text`、`correlations` 的相关矩阵。

---

## 7. 故障排查

| 现象 | 处理 |
|---|---|
| 报 `DATABASE_URL 未设置` | 检查 `evaluate\.env`；URL 必须是 `postgresql+psycopg2://...` |
| 某 section 报 `note: 样本不足` | 受试规模/缺失值导致；先跑 `cohort` 看是否有 MIXED / 缺学习/缺考试的脏样本 |
| Cronbach α 拒绝计算 | 题目方差为 0 或答完整问卷的人不足 2 人 |
| 混合模型 `拟合失败` | 通常是因为 `case_id` 在某组里只出现 1 次或 outcome 全部相等；可用 `--section mixed_models` 单跑读 raw 错误信息 |
