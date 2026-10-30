"""项目公共配置：路径、表登记信息、数据库连接。

所有脚本从这里取路径和表定义，避免各处硬编码。
数据库凭据只从 .env 读取，不写死在代码里。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = PROJECT_ROOT / "data" / "raw" / "ravenstack"
DATA_GENERATED = PROJECT_ROOT / "data" / "generated"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_SAMPLES = PROJECT_ROOT / "data" / "samples"
OUTPUT_TABLES = PROJECT_ROOT / "output" / "tables"
OUTPUT_CHARTS = PROJECT_ROOT / "output" / "charts"
OUTPUT_REPORTS = PROJECT_ROOT / "output" / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

# 显式指定 .env 路径，避免从其他工作目录执行时找不到配置
load_dotenv(PROJECT_ROOT / ".env")


def ensure_dirs() -> None:
    """创建运行所需的输出目录。"""
    for directory in (
        DATA_RAW,
        DATA_GENERATED,
        DATA_PROCESSED,
        OUTPUT_TABLES,
        OUTPUT_CHARTS,
        OUTPUT_REPORTS,
    ):
        directory.mkdir(parents=True, exist_ok=True)


# 五张原始表的登记信息。
# primary_key  用于检查主键唯一性
# date_columns 用于检查日期范围与解析失败情况
# key_columns  需要在报告中重点看空值和取值分布的字段
TABLES = {
    "accounts": {
        "file": "ravenstack_accounts.csv",
        "primary_key": "account_id",
        "date_columns": ["signup_date"],
        "key_columns": ["industry", "country", "referral_source", "plan_tier", "is_trial"],
    },
    "subscriptions": {
        "file": "ravenstack_subscriptions.csv",
        "primary_key": "subscription_id",
        "date_columns": ["start_date", "end_date"],
        "key_columns": [
            "account_id",
            "plan_tier",
            "is_trial",
            "upgrade_flag",
            "downgrade_flag",
            "churn_flag",
            "billing_frequency",
        ],
    },
    "feature_usage": {
        "file": "ravenstack_feature_usage.csv",
        "primary_key": "usage_id",
        "date_columns": ["usage_date"],
        "key_columns": ["subscription_id", "feature_name", "is_beta_feature"],
    },
    "support_tickets": {
        "file": "ravenstack_support_tickets.csv",
        "primary_key": "ticket_id",
        "date_columns": ["submitted_at", "closed_at"],
        "key_columns": ["account_id", "priority", "escalation_flag"],
    },
    "churn_events": {
        "file": "ravenstack_churn_events.csv",
        "primary_key": "churn_event_id",
        "date_columns": ["churn_date"],
        "key_columns": ["account_id", "reason_code", "is_reactivation"],
    },
}

# 外键检查：子表字段 -> (父表, 父表字段)
FOREIGN_KEYS = [
    ("subscriptions", "account_id", "accounts", "account_id"),
    ("feature_usage", "subscription_id", "subscriptions", "subscription_id"),
    ("support_tickets", "account_id", "accounts", "account_id"),
    ("churn_events", "account_id", "accounts", "account_id"),
]


def table_path(table_name: str) -> Path:
    """返回某张原始表的本地路径。"""
    return DATA_RAW / TABLES[table_name]["file"]


def get_db_url() -> URL:
    """从环境变量构造数据库连接串。

    缺少配置时抛出明确错误，提示用户检查 .env，而不是静默连接到错误的库。
    """
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "数据库配置缺失：" + ", ".join(missing) + "。请复制 .env.example 为 .env 并填写。"
        )

    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        query={"charset": "utf8mb4"},
    )


def get_engine():
    """创建 SQLAlchemy 引擎。"""
    from sqlalchemy import create_engine

    return create_engine(get_db_url(), pool_pre_ping=True)
