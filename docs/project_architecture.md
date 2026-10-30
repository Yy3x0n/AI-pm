# 项目架构说明

> 阶段 0 交付物。本文件记录项目定位、分析范围、数据流、目录职责、技术选型与阶段验收标准。
> 所有字段结论均来自阶段 0 对 CSV 表头的实际查证，未行查证的推断已明确标注。

---

## 1. 项目定位

| 项目 | 内容 |
|---|---|
| 名称 | AI SaaS 产品增长与运营数据分析 / AI SaaS Product Growth & Operations Analytics |
| 性质 | 个人求职作品集项目，本地可运行的数据分析项目 |
| 分析视角 | B2B SaaS。分析粒度为 `account_id`（组织客户）与 `subscription_id`（订阅），不称"个人用户" |
| 目标岗位 | AI 业务数据分析、AI 产品数据分析、产品数据分析、数据分析、数据运营、商业化运营 |
| 不做的事 | 前端、后端服务、登录系统、在线 SaaS、Flask/FastAPI/Streamlit/Docker/Spark、机器学习模型、Agent 系统 |

---

## 2. 核心业务问题

1. 不同获客渠道带来的组织客户数量与质量是否存在差异？
2. 注册组织是否进入订阅、是否开始使用功能？激活漏斗在哪一环流失最多？
3. 不同注册月份的客户后续活跃留存情况如何？
4. 哪些组织客户使用频率高、订阅价值高、或存在流失风险？
5. 不同套餐的收入、升级、降级、流失表现如何？
6. 客服响应与解决时长是否与流失存在关联（相关，非因果）？
7. 新手引导优化实验是否提升激活率？7 日留存护栏是否受损？
8. 核心指标是否出现异常？异常集中在哪些维度？
9. 如何把已算出的数字转写成简短、可核查的业务建议？

---

## 3. 数据源与真实性声明

### 3.1 主数据集（公开合成教学数据）

RavenStack SaaS Subscription & Churn Analytics Dataset。**合成教学数据，不是任何企业的真实数据，也不是真实 AI 产品生产日志。** README 与所有产出必须保留此声明。

来源：<https://www.kaggle.com/datasets/rivalytics/saas-subscription-and-churn-analytics-dataset>
镜像：<https://github.com/tivonio/sql-churn-analysis>

### 3.2 阶段 0 实测结果（2026-10-30）

五个 Raw 链接全部可访问（HTTP 206/200），文件大小与表头均已核实：

| 文件 | 大小 | 行数 | 实测表头 |
|---|---|---|---|
| `ravenstack_accounts.csv` | 36 KB | 500 | account_id, account_name, industry, country, signup_date, referral_source, plan_tier, seats, is_trial, churn_flag |
| `ravenstack_subscriptions.csv` | 433 KB | 5,000 | subscription_id, account_id, start_date, end_date, plan_tier, seats, mrr_amount, arr_amount, is_trial, upgrade_flag, downgrade_flag, churn_flag, billing_frequency, auto_renew_flag |
| `ravenstack_feature_usage.csv` | 1.38 MB | 约 25,000（待阶段 1 确认） | usage_id, subscription_id, usage_date, feature_name, usage_count, usage_duration_secs, error_count, is_beta_feature |
| `ravenstack_support_tickets.csv` | 144 KB | 2,000 | ticket_id, account_id, submitted_at, closed_at, resolution_time_hours, priority, first_response_time_minutes, satisfaction_score, escalation_flag |
| `ravenstack_churn_events.csv` | 44 KB | 600 | churn_event_id, account_id, churn_date, reason_code, refund_amount_usd, preceding_upgrade_flag, preceding_downgrade_flag, is_reactivation, feedback_text |

行数以本机实跑为准；阶段 1 会重新统计并写入 `docs/data_audit.md`。

### 3.3 已识别的重要字段约束（影响后续口径设计）

1. **`feature_usage` 没有 `account_id`，只有 `subscription_id`。** 所有"组织客户活跃、留存、功能使用"指标必须先经 `subscriptions` 关联换算到组织层级。关联前必须验证 `subscription_id` 在订阅表中的唯一性，否则会放大使用记录。这是本项目最关键的关联限制，模块 2、3 的口径都要写明。
2. **`support_tickets` 无工单状态字段。** 未关闭工单只能通过 `closed_at IS NULL` 识别，`resolution_time_hours` 的空值处理方式必须显式声明，不能直接求均值。
3. **`feature_name` 建议为 `feature_1` 一类通用名。** 不得解释为"AI 写作""图片生成"等具体功能。
4. **`mrr_amount` / `arr_amount` 是订阅金额字段，不是现金流水。** 项目只谈订阅经常性收入，不谈实际收款；ARR 应核对是否等于 MRR×12，不重复乘除。
5. **`churn_events` 含 `is_reactivation`。** 统计流失客户数时需明确是否包含再激活记录，避免重复计数。
6. **`accounts` 与 `subscriptions` 都带 `churn_flag`。** 客户流失与订阅流失是两个口径，不得混用。

### 3.4 项目模拟数据（仅两张，均标记 `synthetic`）

| 文件 | 用途 | 关键约束 |
|---|---|---|
| `ai_request_logs.csv` | 请求成功率、延迟分布、Token 消耗、估算成本 | 费率单独放配置文件并注明为模拟费率；估算成本不得称为真实账单 |
| `ab_test_onboarding.csv` | 单个新手引导实验 | `user_id` 为实验样本 ID，不冒充真实成员；固定随机种子并记录生成逻辑；分析代码不得读取生成器内置效果参数 |

除上述两张外不再新增任何模拟表。

---

## 4. 六个分析模块

| 模块 | 核心产出 | 主要依赖表 |
|---|---|---|
| 1 指标体系与经营概览 | 指标字典、总体 KPI、月度趋势、套餐/行业/渠道汇总 | 全五表 |
| 2 增长、激活漏斗与 Cohort 留存 | 新增趋势、三级激活漏斗、月度活跃留存矩阵 | accounts + subscriptions + feature_usage |
| 3 客户分层与流失分析 | 4–5 层 R/F/M 分层、收入贡献、流失原因与关联线索 | 上述 + churn_events + support_tickets |
| 4 A/B Test | 样本量、SRM、两比例检验、置信区间、护栏指标 | ab_test_onboarding（合成） |
| 5 异常监控与异动拆解 | ≥2 个可证据化的异常案例 + 维度贡献拆解 | 指标时间序列 + ai_request_logs |
| 6 AI 请求用量与成本 | 请求量/成功率趋势、P50/P95 延迟、Token、估算成本 | ai_request_logs（合成） |
| 可选 | DeepSeek 生成经营摘要 | 前序模块已算好的 JSON 结果 |

**北极星指标候选：** 月活跃组织客户数（某自然月内存在有效功能使用记录的去重组织数）。选择理由：`feature_usage` 有可靠的 `usage_date`，经订阅关联可稳定换算到组织层级；而"有效功能使用组织数"需要额外定义"有效"阈值，主观性更强。最终口径在阶段 3 定稿。

---

## 5. 数据流

```
GitHub Raw CSV
   │  scripts/download_data.sh（curl -L --fail --retry 3）
   ▼
data/raw/ravenstack/*.csv  ──►  src/data_audit.py  ──►  docs/data_audit.md
   │                                                      docs/data_dictionary.md
   │  src/generate_ai_request_logs.py、generate_ab_test_data.py
   ▼
data/generated/*.csv（synthetic）
   │  sql/01_create_tables.sql 建立 raw_* 与 synthetic_* 表
   │  src/load_mysql.py 导入
   ▼
MySQL: raw_accounts / raw_subscriptions / raw_feature_usage
       raw_support_tickets / raw_churn_events
       synthetic_ai_request_logs / synthetic_ab_test_onboarding
   │  sql/03~06 查询与 src/*_analysis.py 计算，双向交叉核对
   ▼
output/tables/*.csv  ──►  Tableau 两张 Dashboard
output/reports/*.md  ──►  docs/analysis_conclusions.md
```

SQL 与 Pandas 对同一指标必须口径一致；阶段 3 起抽取 ≥5 个指标做交叉核对并记录容差。

---

## 6. 目录职责

```
ai-saas-product-analytics/
├── data/raw/ravenstack/     原始 CSV，只读，不入 Git
├── data/generated/          两张合成表，不入 Git
├── data/processed/          清洗中间产物，不入 Git
├── data/samples/            可入库的小样例
├── sql/                     建表、导入清洗、各模块查询
├── src/                     下载后的审计、生成、装载、分析与摘要脚本
├── notebooks/               分析走查（结论以 src/ 计算结果为准）
├── output/tables|charts|reports/   Tableau 数据源与报告，不入 Git
├── tableau/                 看板搭建说明
├── docs/                    审计、字典、结论、架构
├── tests/                   数据质量、指标、A/B 测试
└── scripts/                 下载与一键运行脚本
```

空目录不建占位文件；哪个阶段需要哪一层，就在该阶段创建。

---

## 7. 技术选型与理由

| 选型 | 理由 |
|---|---|
| Python 3.12.14（VS Code 已配置解释器 `/Users/yy3x0n/pyenv/bin/python`） | 版本符合任务书 3.11/3.12 要求；直接复用已配置解释器，VS Code 打开即能运行，不额外维护 venv |
| MySQL 8.4.7（用户级 tarball 安装，无 sudo） | 岗位要求 SQL 能力；原始表 + 分析查询可复现。本机无 Homebrew 且沙箱内无 sudo 权限，故采用官方 arm64 tarball 装到 `~/mysql`，不污染系统目录，卸载只需删目录 |
| SQLAlchemy + PyMySQL | 参数化写入，避免拼接 SQL；PyMySQL 连 MySQL 8 需 `cryptography` |
| SciPy / Statsmodels | 两比例 z 检验、置信区间、样本量估算 |
| Tableau Desktop | 只连 `output/tables/*.csv`，不引 OpenPyXL / Power BI |
| CSV 作为交换格式 | 分析结果与看板解耦，便于复现与审阅 |

### 7.1 本机环境实测记录（2026-10-30）

| 组件 | 版本 / 位置 | 状态 |
|---|---|---|
| macOS / 架构 | 27.0 / arm64 | ✅ |
| Python | 3.12.14，`/Users/yy3x0n/pyenv/bin/python`（VS Code `python.defaultInterpreterPath` 指向此路径） | ✅ |
| 分析库 | pandas 3.0.5、numpy 2.5.3、scipy 1.18.1、statsmodels 0.15.0 | ✅ 已装 |
| 数据库驱动 | sqlalchemy 2.1.6、pymysql 1.2.3、cryptography 50.0.2 | ✅ 本次安装 |
| MySQL | 8.4.7 Community，basedir `~/mysql/mysql-8.4.7-macos15-arm64`，datadir `~/mysql/data`，`127.0.0.1:3306` | ✅ 本次安装并连通 |
| 数据库与账号 | 库 `ai_saas_analytics`；应用账号 `saas_analyst@127.0.0.1`；root 密码存于 `~/mysql/.root_password`（600） | ✅ |
| VS Code | 已装 Python/Pylance/Jupyter 扩展 | ✅ |
| Git | 2.54.0；远程 `origin` = `git@github.com:Yy3x0n/AI-pm.git`（SSH） | ✅ |
| Tableau | Desktop 2026.3 (Apple silicon) | ✅ |

**MySQL 为何不用 Homebrew：** 本机未安装 Homebrew，且当前执行环境无 sudo 权限（`sudo` 被沙箱拒绝），Homebrew 安装链路必须写入 `/opt/homebrew`。改用 MySQL 官方 macOS15-arm64 tarball 装到用户目录，全程无需管理员密码，也不修改系统 `/usr/local` 数据目录。

**MySQL 启停：** `launchd` 在此环境下不可用（`launchctl bootstrap` 连最小测试 plist 都返回 `I/O error`，与本项目无关），因此提供 `scripts/mysql_ctl.sh {start|stop|status|shell}`。**重启电脑后需手动执行一次 `bash scripts/mysql_ctl.sh start`。**

---

## 8. 阶段与验收

| 阶段 | 交付 | 验收方式 | 建议提交 |
|---|---|---|---|
| 0 | 环境报告、架构说明、待确认事项 | 用户确认本文件 | `chore: initialize project plan` |
| 1 | 原始数据、`docs/data_audit.md`、`docs/data_dictionary.md` 初稿 | 审计文档记录真实行数/字段/日期范围/主键重复/空值 | `data: add source audit and download workflow` |
| 2 | 两张合成表 + 建表 SQL + 导入脚本 + 质量检查 | `pytest -q` 通过；库表行数与 CSV 一致 | `feat: build data ingestion and mysql layer` |
| 3 | 指标字典、KPI/趋势/维度汇总、漏斗、Cohort | ≥5 指标 SQL 与 Pandas 交叉核对在容差内 | `feat: add core product metrics and retention` |
| 4 | 分层结果、流失分析、运营建议 | 分层可解释、各层客户数与收入贡献可复算 | `feat: add account segmentation and churn analysis` |
| 5 | A/B 完整链路 | 样本量、SRM、p 值、CI、护栏齐备 | `feat: add onboarding ab test analysis` |
| 6 | ≥2 个异常案例、AI 请求分析 | 每个异常有检测结果 + 维度拆解 + 待验证项 | `feat: add anomaly and ai usage analysis` |
| 7 | 两张 Dashboard 所需 CSV 与说明、README、结论、可选 DeepSeek | 干净环境按 README 可跑通；无 API Key 不报错 | `docs: finalize project and dashboard guidance` |

每阶段固定动作：实现 → 实际运行 → 测试 → 用户确认 → commit → push。推送失败只保留本地提交并如实说明。

---

## 9. 风险与限制

| 风险 | 影响 | 处理 |
|---|---|---|
| `feature_usage` 缺 `account_id` | 活跃/留存/分层需多跳关联，可能放大使用量 | 关联前验证 `subscription_id` 唯一性；口径中显式写明关联路径 |
| 样本仅 500 个组织客户 | 细分维度（行业×国家×渠道）单元样本可能过小 | 交叉维度设置最小样本阈值，低于阈值不下结论 |
| 原始表无真实 A/B 分组 | 实验结论不可外推到真实产品 | 明确标注为合成实验，只演示方法 |
| 合成数据无季节性/真实波动 | 异常检测可能只剩噪声 | 异常案例必须有多维度证据支撑，否则降级为"疑似" |
| MySQL 为后台进程而非系统服务 | 重启后数据库不自启 | 已提供 `scripts/mysql_ctl.sh start`；README 写入启动步骤 |
| 依赖装在共用解释器而非独立 venv | 升级依赖可能影响其他项目 | 按用户要求复用 VS Code 已配置解释器；`requirements.txt` 记录实测最低版本 |
