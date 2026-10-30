# 数据审计报告

- 生成时间：2026-10-30 17:58:54
- 数据来源：RavenStack SaaS Subscription & Churn Analytics Dataset（公开合成教学数据）
- 数据镜像：https://github.com/tivonio/sql-churn-analysis
- 审计对象：`data/raw/ravenstack/` 下五个 CSV，只读，未做任何修改
- 复现方式：`bash scripts/download_data.sh && python -m src.data_audit`

> 声明：本数据集为合成教学数据，不是任何企业的真实经营数据，也不是真实 AI 产品日志。以下所有结论仅描述本数据集自身特征。

## 1. 文件级概览

| 表 | 文件 | 行数 | 列数 | 文件大小(KB) | 内存占用(KB) |
|---|---|---|---|---|---|
| accounts | ravenstack_accounts.csv | 500 | 10 | 35.3 | 57.2 |
| subscriptions | ravenstack_subscriptions.csv | 5000 | 14 | 422.4 | 569.7 |
| feature_usage | ravenstack_feature_usage.csv | 25000 | 8 | 1343.6 | 2265.2 |
| support_tickets | ravenstack_support_tickets.csv | 2000 | 9 | 140.2 | 224.3 |
| churn_events | ravenstack_churn_events.csv | 600 | 9 | 43.0 | 57.1 |

## 2. 主键检查

| 表 | 主键 | 行数 | 去重值数 | 重复行数 | 结论 |
|---|---|---|---|---|---|
| accounts | account_id | 500 | 500 | 0 | 通过（主键空值 0） |
| subscriptions | subscription_id | 5000 | 5000 | 0 | 通过（主键空值 0） |
| feature_usage | usage_id | 25000 | 24979 | 21 | 存在问题（主键空值 0） |
| support_tickets | ticket_id | 2000 | 2000 | 0 | 通过（主键空值 0） |
| churn_events | churn_event_id | 600 | 600 | 0 | 通过（主键空值 0） |

## 3. 外键可关联性

| 子表 | 字段 | 父表 | 非空值数 | 未匹配数 | 结论 |
|---|---|---|---|---|---|
| subscriptions | account_id | accounts | 5000 | 0 | 通过（孤儿率 0.0%） |
| feature_usage | subscription_id | subscriptions | 25000 | 0 | 通过（孤儿率 0.0%） |
| support_tickets | account_id | accounts | 2000 | 0 | 通过（孤儿率 0.0%） |
| churn_events | account_id | accounts | 600 | 0 | 通过（孤儿率 0.0%） |

## 4. 日期字段

| 表 | 字段 | 最早 | 最晚 | 空值数 | 解析失败数 |
|---|---|---|---|---|---|
| accounts | signup_date | 2023-01-02 | 2024-12-31 | 0 | 0 |
| subscriptions | start_date | 2023-01-09 | 2024-12-31 | 0 | 0 |
| subscriptions | end_date | 2023-04-05 | 2024-12-31 | 4514 | 0 |
| feature_usage | usage_date | 2023-01-01 | 2024-12-31 | 0 | 0 |
| support_tickets | submitted_at | 2023-01-02 | 2024-12-31 | 0 | 0 |
| support_tickets | closed_at | 2023-01-03 | 2024-12-31 | 0 | 0 |
| churn_events | churn_date | 2023-01-25 | 2024-12-31 | 0 | 0 |

## 5. 数值字段取值范围

**accounts**

| 字段 | 最小 | 最大 | 均值 | 负值数 | 零值数 |
|---|---|---|---|---|---|
| seats | 1.0 | 163.0 | 20.56 | 0 | 0 |

**subscriptions**

| 字段 | 最小 | 最大 | 均值 | 负值数 | 零值数 |
|---|---|---|---|---|---|
| seats | 1.0 | 189.0 | 29.852 | 0 | 0 |
| mrr_amount | 0.0 | 33830.0 | 2267.7494 | 0 | 778 |
| arr_amount | 0.0 | 405960.0 | 27212.9928 | 0 | 778 |

**feature_usage**

| 字段 | 最小 | 最大 | 均值 | 负值数 | 零值数 |
|---|---|---|---|---|---|
| usage_count | 0.0 | 26.0 | 10.021 | 0 | 2 |
| usage_duration_secs | 0.0 | 12696.0 | 3042.2029 | 0 | 2 |
| error_count | 0.0 | 8.0 | 0.5643 | 0 | 17269 |

**support_tickets**

| 字段 | 最小 | 最大 | 均值 | 负值数 | 零值数 |
|---|---|---|---|---|---|
| resolution_time_hours | 1.0 | 72.0 | 35.861 | 0 | 0 |
| first_response_time_minutes | 1.0 | 180.0 | 88.48 | 0 | 0 |
| satisfaction_score | 3.0 | 5.0 | 3.9813 | 0 | 0 |

**churn_events**

| 字段 | 最小 | 最大 | 均值 | 负值数 | 零值数 |
|---|---|---|---|---|---|
| refund_amount_usd | 0.0 | 392.92 | 14.4204 | 0 | 458 |

## 6. 空值分布

| 表 | 字段 | 空值数 | 空值率 |
|---|---|---|---|
| subscriptions | end_date | 4514 | 90.28% |
| support_tickets | satisfaction_score | 825 | 41.25% |
| churn_events | feedback_text | 148 | 24.67% |

## 7. 关键字段取值分布

**accounts**

- `industry`：共 5 个取值；前几位 DevTools=113，FinTech=112，Cybersecurity=100，HealthTech=96，EdTech=79
- `country`：共 7 个取值；前几位 US=291，UK=58，IN=49，AU=32，DE=25，CA=23
- `referral_source`：共 5 个取值；前几位 organic=114，other=103，ads=98，event=96，partner=89
- `plan_tier`：共 3 个取值；前几位 Pro=178，Basic=168，Enterprise=154
- `is_trial`：共 2 个取值；前几位 False=403，True=97

**subscriptions**

- `account_id`：共 500 个取值；前几位 A-d4ac0e=19，A-5a92e7=19，A-592832=19，A-726cfa=19，A-5a215a=18，A-8bde0c=18
- `plan_tier`：共 3 个取值；前几位 Enterprise=1723，Pro=1675，Basic=1602
- `is_trial`：共 2 个取值；前几位 False=4222，True=778
- `upgrade_flag`：共 2 个取值；前几位 False=4471，True=529
- `downgrade_flag`：共 2 个取值；前几位 False=4782，True=218
- `churn_flag`：共 2 个取值；前几位 False=4514，True=486
- `billing_frequency`：共 2 个取值；前几位 monthly=2539，annual=2461

**feature_usage**

- `subscription_id`：共 4967 个取值；前几位 S-0896f4=16，S-52385a=14，S-115823=14，S-02b754=14，S-e7e4bd=13，S-66bae1=13
- `feature_name`：共 40 个取值；前几位 feature_12=659，feature_32=659，feature_6=655，feature_17=651，feature_34=650，feature_26=649
- `is_beta_feature`：共 2 个取值；前几位 False=22456，True=2544

**support_tickets**

- `account_id`：共 492 个取值；前几位 A-bb3bd4=11，A-3ce5b8=10，A-e98302=9，A-503d5a=9，A-139c3b=9，A-ed510f=9
- `priority`：共 4 个取值；前几位 urgent=514，high=510，medium=491，low=485
- `escalation_flag`：共 2 个取值；前几位 False=1905，True=95

**churn_events**

- `account_id`：共 352 个取值；前几位 A-0a62f5=5，A-180abf=5，A-37f969=4，A-0baac2=4，A-9208f0=4，A-425e76=4
- `reason_code`：共 6 个取值；前几位 features=114，support=104，budget=104，unknown=95，competitor=92，pricing=91
- `is_reactivation`：共 2 个取值；前几位 False=539，True=61

## 8. 专项检查结论

| 检查项 | 结论 |
|---|---|
| subscriptions.subscription_id 唯一性 | 重复 0 行。唯一，feature_usage 可按 subscription_id 一对一关联，不会放大使用量。 |
| feature_usage.usage_id 唯一性 | 存在 21 个 usage_id 各出现两次，共 42 行；其中整行完全相同的仅 0 行。冲突行的 subscription_id 与 usage_date 并不相同，属于 ID 碰撞而非重复上报。结论：usage_id 不能作为唯一键使用，去重与计数应以 (subscription_id, usage_date, feature_name) 或行号为准。 |
| arr_amount 与 mrr_amount 的比例 | 中位数 12.000，最小 12.000，最大 12.000。接近 12，ARR 可视为 MRR 的年化值，两个指标不可相加。 |
| mrr_amount 为 0 的订阅数 | 778 行。计算付费 MRR 时需明确是否包含试用订阅。 |
| 订阅起止日期合法性 | end_date 早于 start_date 的 0 行；end_date 为空（视为仍在生效）的 4514 行。 |
| 每个组织客户的订阅记录数 | 最多 19 条，中位数 10 条。取某一时点的 MRR 时必须限定订阅生效区间，不能把同一组织的多条订阅直接相加。 |
| 未关闭工单 | closed_at 为空 0 行，其中仍有 resolution_time_hours 值的 0 行。计算平均解决时长时必须说明是否排除未关闭工单。 |
| 客户流失口径交叉核对 | accounts.churn_flag 标记流失的组织 110 个；churn_events 覆盖 352 个组织、600 条事件（其中再激活 61 条）。两者一致的 75 个，仅 flag 标记的 35 个，仅事件表有记录的 277 个。差异无法全部由再激活解释，说明两个流失来源本身不一致。结论：客户流失率必须选定唯一口径（建议以 churn_events 为事件源，因它带流失日期与原因），并在指标字典中写明分子来源，不得混用。 |
| 工单满意度空值 | 825 行无评分（占 41.2%）。计算平均满意度时需写明分母是全部工单还是仅有评分的工单。 |
| feature_usage 覆盖的订阅数 | 4967 个订阅存在使用记录，占全部 5000 条订阅的 99.3%。没有使用记录的订阅不能被当作流失，只能标记为未观测到使用。 |
| feature_usage 业务键重复 | (subscription_id, usage_date, feature_name) 组合重复 3 行。存在重复，聚合前需确认是否为多次上报。 |

## 9. 对后续分析口径的影响

1. `feature_usage` 不含 `account_id`，组织层级的活跃、留存、分层指标必须经 `subscriptions` 关联换算。
2. 客户流失沿用 `churn_events` 作为事件源（带流失日期与原因代码），`accounts.churn_flag` 仅作交叉核对；两者对同一组织的标记并不一致，分子不得混用。
3. `feature_usage.usage_id` 存在 ID 碰撞，不得作为唯一键；去重与计数以 (subscription_id, usage_date, feature_name) 或行号为准。
4. 计算时点 MRR 需限定订阅生效区间，避免把同一组织的多条订阅简单相加。
5. 解决时长、响应时长、满意度的均值需说明分母（未关闭工单、无评分工单如何处理）。
6. 原始数据未做任何清洗；清洗规则与前后行数变化在阶段 2 记录。
