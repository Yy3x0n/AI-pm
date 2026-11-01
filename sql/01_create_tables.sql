-- =============================================================
-- AI SaaS 产品增长与运营数据分析 —— 建表脚本
--
-- 命名规则：
--   raw_*        五张 RavenStack 原始表（公开合成教学数据）
--   synthetic_*  两张项目模拟表（A/B Test 与 AI 请求日志）
--
-- 设计说明：
--   1. raw_feature_usage 的 usage_id 存在 ID 碰撞（审计发现 21 个 ID 各出现两次），
--      因此不能作为主键，改用自增 row_id，并保留 usage_id 供追溯。
--   2. 金额统一用 DECIMAL，日期用 DATE / DATETIME，布尔标记用 TINYINT(1)。
--   3. 外键仅在同一份数据内部成立（原始表之间、模拟表指向原始表），已通过审计确认无孤儿。
--   4. 脚本可重复执行：DROP 后重建，不使用 IF NOT EXISTS 掩盖结构变更。
--
-- 执行方式：
--   mysql -u <user> -p < sql/01_create_tables.sql
--   或由 python -m src.load_mysql 自动执行
-- =============================================================

CREATE DATABASE IF NOT EXISTS ai_saas_analytics
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE ai_saas_analytics;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS synthetic_ab_test_onboarding;
DROP TABLE IF EXISTS synthetic_ai_request_logs;
DROP TABLE IF EXISTS raw_churn_events;
DROP TABLE IF EXISTS raw_support_tickets;
DROP TABLE IF EXISTS raw_feature_usage;
DROP TABLE IF EXISTS raw_subscriptions;
DROP TABLE IF EXISTS raw_accounts;
SET FOREIGN_KEY_CHECKS = 1;

-- -------------------------------------------------------------
-- 1. 组织客户
-- -------------------------------------------------------------
CREATE TABLE raw_accounts (
  account_id       VARCHAR(20)  NOT NULL COMMENT '组织客户唯一标识',
  account_name     VARCHAR(100) NOT NULL COMMENT '组织名称',
  industry         VARCHAR(50)  NOT NULL COMMENT '所属行业',
  country          VARCHAR(10)  NOT NULL COMMENT '所在国家代码',
  signup_date      DATE         NOT NULL COMMENT '注册日期',
  referral_source  VARCHAR(30)  NOT NULL COMMENT '获客来源渠道',
  plan_tier        VARCHAR(20)  NOT NULL COMMENT '注册套餐档位',
  seats            INT          NOT NULL COMMENT '席位数',
  is_trial         TINYINT(1)   NOT NULL COMMENT '是否试用',
  churn_flag       TINYINT(1)   NOT NULL COMMENT '客户级流失标记（与 churn_events 口径不一致，见 data_audit）',
  PRIMARY KEY (account_id),
  KEY idx_accounts_signup_date (signup_date),
  KEY idx_accounts_referral (referral_source),
  KEY idx_accounts_plan (plan_tier),
  KEY idx_accounts_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始表：组织客户';

-- -------------------------------------------------------------
-- 2. 订阅
-- -------------------------------------------------------------
CREATE TABLE raw_subscriptions (
  subscription_id    VARCHAR(20)   NOT NULL COMMENT '订阅唯一标识',
  account_id         VARCHAR(20)   NOT NULL COMMENT '所属组织客户',
  start_date         DATE          NOT NULL COMMENT '订阅开始日期',
  end_date           DATE          NULL     COMMENT '订阅结束日期，空值表示仍生效',
  plan_tier          VARCHAR(20)   NOT NULL COMMENT '套餐档位',
  seats              INT           NOT NULL COMMENT '席位数',
  mrr_amount         DECIMAL(12,2) NOT NULL COMMENT '月度经常性收入（订阅金额，非现金流）',
  arr_amount         DECIMAL(14,2) NOT NULL COMMENT '年度经常性收入，等于 MRR×12',
  is_trial           TINYINT(1)    NOT NULL COMMENT '是否试用订阅',
  upgrade_flag       TINYINT(1)    NOT NULL COMMENT '是否发生升级',
  downgrade_flag     TINYINT(1)    NOT NULL COMMENT '是否发生降级',
  churn_flag         TINYINT(1)    NOT NULL COMMENT '订阅级流失标记',
  billing_frequency  VARCHAR(20)   NOT NULL COMMENT '计费频率',
  auto_renew_flag    TINYINT(1)    NOT NULL COMMENT '是否自动续费',
  PRIMARY KEY (subscription_id),
  KEY idx_subs_account (account_id),
  KEY idx_subs_start (start_date),
  KEY idx_subs_end (end_date),
  CONSTRAINT fk_subs_account FOREIGN KEY (account_id) REFERENCES raw_accounts (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始表：订阅周期';

-- -------------------------------------------------------------
-- 3. 功能使用
-- -------------------------------------------------------------
CREATE TABLE raw_feature_usage (
  row_id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '代理主键，因 usage_id 存在碰撞',
  usage_id             VARCHAR(20)  NOT NULL COMMENT '原表使用记录 ID（不唯一）',
  subscription_id      VARCHAR(20)  NOT NULL COMMENT '所属订阅，本表无 account_id',
  usage_date           DATE         NOT NULL COMMENT '使用日期',
  feature_name         VARCHAR(30)  NOT NULL COMMENT '通用功能标识，不代表具体业务功能',
  usage_count          INT          NOT NULL COMMENT '当日使用次数',
  usage_duration_secs  INT          NOT NULL COMMENT '当日使用时长（秒）',
  error_count          INT          NOT NULL COMMENT '当日错误次数',
  is_beta_feature      TINYINT(1)   NOT NULL COMMENT '是否灰度功能',
  PRIMARY KEY (row_id),
  KEY idx_usage_usage_id (usage_id),
  KEY idx_usage_sub_date (subscription_id, usage_date),
  KEY idx_usage_date (usage_date),
  KEY idx_usage_feature (feature_name),
  CONSTRAINT fk_usage_subscription FOREIGN KEY (subscription_id) REFERENCES raw_subscriptions (subscription_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始表：功能使用（订阅×日期×功能）';

-- -------------------------------------------------------------
-- 4. 客服工单
-- -------------------------------------------------------------
CREATE TABLE raw_support_tickets (
  ticket_id                    VARCHAR(20)  NOT NULL COMMENT '工单唯一标识',
  account_id                   VARCHAR(20)  NOT NULL COMMENT '提单组织客户',
  submitted_at                 DATETIME     NOT NULL COMMENT '提交时间',
  closed_at                    DATETIME     NULL     COMMENT '关闭时间，空值表示未关闭',
  resolution_time_hours        DECIMAL(8,2) NULL     COMMENT '解决耗时（小时）',
  priority                     VARCHAR(20)  NOT NULL COMMENT '优先级',
  first_response_time_minutes  DECIMAL(8,2) NULL     COMMENT '首次响应耗时（分钟）',
  satisfaction_score           DECIMAL(3,1) NULL     COMMENT '满意度评分，约四成工单无评分',
  escalation_flag              TINYINT(1)   NOT NULL COMMENT '是否升级处理',
  PRIMARY KEY (ticket_id),
  KEY idx_tickets_account (account_id),
  KEY idx_tickets_submitted (submitted_at),
  KEY idx_tickets_priority (priority),
  CONSTRAINT fk_tickets_account FOREIGN KEY (account_id) REFERENCES raw_accounts (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始表：客服工单';

-- -------------------------------------------------------------
-- 5. 流失事件
-- -------------------------------------------------------------
CREATE TABLE raw_churn_events (
  churn_event_id           VARCHAR(20)   NOT NULL COMMENT '流失事件唯一标识',
  account_id               VARCHAR(20)   NOT NULL COMMENT '流失组织客户',
  churn_date               DATE          NOT NULL COMMENT '流失日期',
  reason_code              VARCHAR(30)   NOT NULL COMMENT '流失原因代码',
  refund_amount_usd        DECIMAL(10,2) NOT NULL COMMENT '退款金额（美元）',
  preceding_upgrade_flag   TINYINT(1)    NOT NULL COMMENT '流失前是否升级',
  preceding_downgrade_flag TINYINT(1)    NOT NULL COMMENT '流失前是否降级',
  is_reactivation          TINYINT(1)    NOT NULL COMMENT '是否再激活事件',
  feedback_text            TEXT          NULL     COMMENT '客户反馈原文',
  PRIMARY KEY (churn_event_id),
  KEY idx_churn_account (account_id),
  KEY idx_churn_date (churn_date),
  KEY idx_churn_reason (reason_code),
  CONSTRAINT fk_churn_account FOREIGN KEY (account_id) REFERENCES raw_accounts (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始表：流失事件';

-- -------------------------------------------------------------
-- 6. 模拟：AI 请求日志
--    来源为脚本生成，不是真实生产日志；estimated_cost 基于模拟费率
-- -------------------------------------------------------------
CREATE TABLE synthetic_ai_request_logs (
  request_id      VARCHAR(20)   NOT NULL COMMENT '请求唯一标识',
  account_id      VARCHAR(20)   NOT NULL COMMENT '发起请求的组织客户',
  request_date    DATE          NOT NULL COMMENT '请求日期',
  feature_name    VARCHAR(30)   NOT NULL COMMENT '功能标识',
  input_tokens    INT           NOT NULL COMMENT '输入 token 数',
  output_tokens   INT           NOT NULL COMMENT '输出 token 数',
  latency_ms      INT           NOT NULL COMMENT '响应耗时（毫秒）',
  request_status  VARCHAR(20)   NOT NULL COMMENT '请求状态：success / error / timeout',
  estimated_cost  DECIMAL(12,6) NOT NULL COMMENT '估算成本（美元，按模拟费率计算，非真实账单）',
  PRIMARY KEY (request_id),
  KEY idx_ai_account (account_id),
  KEY idx_ai_date (request_date),
  KEY idx_ai_feature (feature_name),
  KEY idx_ai_status (request_status),
  CONSTRAINT fk_ai_account FOREIGN KEY (account_id) REFERENCES raw_accounts (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟表：AI 请求日志（synthetic）';

-- -------------------------------------------------------------
-- 7. 模拟：A/B Test
--    user_id 为实验样本编号，与原始数据的 ID 体系无关
-- -------------------------------------------------------------
CREATE TABLE synthetic_ab_test_onboarding (
  user_id           VARCHAR(20) NOT NULL COMMENT '实验样本编号（非真实成员 ID）',
  experiment_group  VARCHAR(20) NOT NULL COMMENT '分组：control / treatment',
  assigned_at       DATETIME    NOT NULL COMMENT '分组时间',
  activated         TINYINT(1)  NOT NULL COMMENT '是否激活，目标指标',
  retained_d7       TINYINT(1)  NOT NULL COMMENT '7 日是否留存，护栏指标',
  PRIMARY KEY (user_id),
  KEY idx_ab_group (experiment_group)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟表：新手引导 A/B 实验（synthetic）';
