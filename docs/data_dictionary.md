# 数据字典

- 生成时间：2026-11-01 12:35:30
- 所有表均为公开合成数据（RavenStack），非真实企业数据
- 字段含义依据字段命名与数据表现归纳；标注为「待确认」的字段不做业务解释

## accounts（`ravenstack_accounts.csv`）

- 粒度：一行一个组织客户，account_id 唯一
- 主键：`account_id`
- 行数：500

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| account_id | str | 100.0% | 500 | A-2e4581; A-43a9e3; A-0a282f | 组织客户唯一标识（主键） |
| account_name | str | 100.0% | 500 | Company_0; Company_1; Company_2 | 组织客户名称 |
| industry | str | 100.0% | 5 | EdTech; FinTech; DevTools | 所属行业 |
| country | str | 100.0% | 7 | US; IN; UK | 所在国家 |
| signup_date | date | 100.0% | 370 | 2023-01-02 ~ 2024-12-31 | 注册日期 |
| referral_source | str | 100.0% | 5 | partner; other; organic | 获客来源渠道 |
| plan_tier | str | 100.0% | 3 | Basic; Enterprise; Pro | 注册时所选套餐档位 |
| seats | int64 | 100.0% | 73 | 1 ~ 163 | 购买席位数 |
| is_trial | bool | 100.0% | 2 | False; True | 是否试用中 |
| churn_flag | bool | 100.0% | 2 | False; True | 该组织是否已流失（客户级标记） |

## subscriptions（`ravenstack_subscriptions.csv`）

- 粒度：一行一个订阅周期记录，同一组织可有多条订阅
- 主键：`subscription_id`
- 行数：5000

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| subscription_id | str | 100.0% | 5000 | S-8cec59; S-0f6f44; S-51c0d1 | 订阅唯一标识（主键） |
| account_id | str | 100.0% | 500 | A-3c1a3f; A-9b9fe9; A-659280 | 所属组织客户（外键） |
| start_date | date | 100.0% | 625 | 2023-01-09 ~ 2024-12-31 | 订阅开始日期 |
| end_date | date | 9.7% | 208 | 2023-04-05 ~ 2024-12-31 | 订阅结束日期 |
| plan_tier | str | 100.0% | 3 | Enterprise; Pro; Basic | 订阅套餐档位 |
| seats | int64 | 100.0% | 123 | 1 ~ 189 | 订阅席位数 |
| mrr_amount | int64 | 100.0% | 306 | 0 ~ 33830 | 月度经常性收入（订阅金额，非现金流水） |
| arr_amount | int64 | 100.0% | 306 | 0 ~ 405960 | 年度经常性收入（订阅金额，非现金流水） |
| is_trial | bool | 100.0% | 2 | False; True | 是否试用订阅 |
| upgrade_flag | bool | 100.0% | 2 | False; True | 该订阅期内是否发生升级 |
| downgrade_flag | bool | 100.0% | 2 | False; True | 该订阅期内是否发生降级 |
| churn_flag | bool | 100.0% | 2 | True; False | 该订阅是否以流失结束（订阅级标记） |
| billing_frequency | str | 100.0% | 2 | monthly; annual | 计费频率 |
| auto_renew_flag | bool | 100.0% | 2 | True; False | 是否自动续费 |

## feature_usage（`ravenstack_feature_usage.csv`）

- 粒度：一行一条「订阅 × 日期 × 功能」的日粒度使用记录，注意本表无 account_id
- 主键：`usage_id`
- 行数：25000

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| usage_id | str | 100.0% | 24979 | U-1c6c24; U-f07cb8; U-096807 | 使用记录唯一标识（主键） |
| subscription_id | str | 100.0% | 4967 | S-0fcf7d; S-c25263; S-f29e7f | 所属订阅（外键，注意本表无 account_id） |
| usage_date | date | 100.0% | 731 | 2023-01-01 ~ 2024-12-31 | 使用发生日期 |
| feature_name | str | 100.0% | 40 | feature_20; feature_5; feature_3 | 功能标识（通用命名，不代表具体业务功能） |
| usage_count | int64 | 100.0% | 27 | 0 ~ 26 | 当日该功能使用次数 |
| usage_duration_secs | int64 | 100.0% | 4168 | 0 ~ 12696 | 当日该功能使用时长（秒） |
| error_count | int64 | 100.0% | 9 | 0 ~ 8 | 当日该功能错误次数 |
| is_beta_feature | bool | 100.0% | 2 | False; True | 是否灰度/测试功能 |

## support_tickets（`ravenstack_support_tickets.csv`）

- 粒度：一行一张客服工单
- 主键：`ticket_id`
- 行数：2000

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| ticket_id | str | 100.0% | 2000 | T-0024de; T-4d04b9; T-d5e12f | 工单唯一标识（主键） |
| account_id | str | 100.0% | 492 | A-712f1c; A-e43bf7; A-0f3e88 | 提单组织客户（外键） |
| submitted_at | date | 100.0% | 671 | 2023-01-02 ~ 2024-12-31 | 工单提交时间 |
| closed_at | date | 100.0% | 1893 | 2023-01-03 ~ 2024-12-31 | 工单关闭时间，空值代表未关闭 |
| resolution_time_hours | float64 | 100.0% | 72 | 1.0 ~ 72.0 | 解决耗时（小时） |
| priority | str | 100.0% | 4 | high; urgent; medium | 工单优先级 |
| first_response_time_minutes | int64 | 100.0% | 180 | 1 ~ 180 | 首次响应耗时（分钟） |
| satisfaction_score | float64 | 58.8% | 3 | 3.0 ~ 5.0 | 客户满意度评分 |
| escalation_flag | bool | 100.0% | 2 | False; True | 是否升级处理 |

## churn_events（`ravenstack_churn_events.csv`）

- 粒度：一行一次流失事件，同一组织可有多条（含再激活）
- 主键：`churn_event_id`
- 行数：600

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| churn_event_id | str | 100.0% | 600 | C-816288; C-5a81e7; C-a174be | 流失事件唯一标识（主键） |
| account_id | str | 100.0% | 352 | A-c37cab; A-37f969; A-b07346 | 流失组织客户（外键） |
| churn_date | date | 100.0% | 311 | 2023-01-25 ~ 2024-12-31 | 流失发生日期 |
| reason_code | str | 100.0% | 6 | pricing; support; budget | 流失原因代码 |
| refund_amount_usd | float64 | 100.0% | 142 | 0.0 ~ 392.92 | 退款金额（美元） |
| preceding_upgrade_flag | bool | 100.0% | 2 | False; True | 流失前是否发生升级 |
| preceding_downgrade_flag | bool | 100.0% | 2 | False; True | 流失前是否发生降级 |
| is_reactivation | bool | 100.0% | 2 | False; True | 该事件是否为再激活（回流） |
| feedback_text | str | 75.3% | 3 | switched to competitor; missing features; too expensive | 客户反馈原文 |

## 模拟数据（synthetic）

> 本节两张表**不是真实企业数据**，由 `src/generate_ai_request_logs.py` 与 `src/generate_ab_test_data.py` 按固定随机种子生成。生成逻辑与注入的异常窗口见 `docs/synthetic_data.md`。

## ai_request_logs（`ai_request_logs.csv`）

- 粒度：一行一次 AI 请求（模拟数据），请求级粒度
- 主键：`request_id`
- 行数：37490

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| request_id | str | 100.0% | 37490 | R-0004399; R-0033453; R-0029690 | 请求唯一标识（主键，模拟） |
| account_id | str | 100.0% | 499 | A-6843f2; A-d27f50; A-b2225d | 发起请求的组织客户（外键到 accounts） |
| request_date | date | 100.0% | 731 | 2023-01-01 ~ 2024-12-31 | 请求日期 |
| feature_name | str | 100.0% | 40 | feature_5; feature_13; feature_26 | 功能标识，复用原始数据的通用功能名 |
| input_tokens | int64 | 100.0% | 8321 | 294 ~ 28410 | 输入 token 数 |
| output_tokens | int64 | 100.0% | 2232 | 91 ~ 7873 | 输出 token 数 |
| latency_ms | int64 | 100.0% | 2496 | 178 ~ 8233 | 响应耗时（毫秒） |
| request_status | str | 100.0% | 3 | success; error; timeout | 请求状态：success / error / timeout |
| estimated_cost | float64 | 100.0% | 4109 | 0.0004 ~ 0.0105 | 估算成本（美元），按 config/ai_pricing.json 的模拟费率计算，不是真实账单 |

## ab_test_onboarding（`ab_test_onboarding.csv`）

- 粒度：一行一个实验样本（模拟数据），样本级粒度
- 主键：`user_id`
- 行数：7524

| 字段 | 类型 | 非空率 | 唯一值数 | 取值范围/样例 | 含义 |
|---|---|---|---|---|---|
| user_id | str | 100.0% | 7524 | EXP-000001; EXP-000002; EXP-000003 | 实验样本编号（主键，非真实成员 ID） |
| experiment_group | str | 100.0% | 2 | control; treatment | 分组：control 或 treatment |
| assigned_at | date | 100.0% | 720 | 2024-09-01 ~ 2024-09-30 | 进入实验的时间 |
| activated | int64 | 100.0% | 2 | 0 ~ 1 | 是否完成激活，目标指标 |
| retained_d7 | int64 | 100.0% | 2 | 0 ~ 1 | 7 日后是否留存，护栏指标 |
