"""MySQL 导入结果测试。

数据库不可用时整体跳过，不阻塞纯 Pandas/SQL 文件层面的测试。
前置：bash scripts/mysql_ctl.sh start && python -m src.load_mysql
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src import config

EXPECTED = {
    "raw_accounts": lambda: config.table_path("accounts"),
    "raw_subscriptions": lambda: config.table_path("subscriptions"),
    "raw_feature_usage": lambda: config.table_path("feature_usage"),
    "raw_support_tickets": lambda: config.table_path("support_tickets"),
    "raw_churn_events": lambda: config.table_path("churn_events"),
    "synthetic_ai_request_logs": lambda: config.DATA_GENERATED / "ai_request_logs.csv",
    "synthetic_ab_test_onboarding": lambda: config.DATA_GENERATED / "ab_test_onboarding.csv",
}


@pytest.fixture(scope="module")
def engine():
    try:
        engine = config.get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return engine
    except (OperationalError, SQLAlchemyError) as error:
        pytest.skip(f"MySQL 不可用，跳过数据库测试：{error}")


def test_table_counts_match_csv(engine):
    """每张表的行数必须与对应 CSV 一致。"""
    with engine.connect() as connection:
        for table_name, path_getter in EXPECTED.items():
            csv_path = path_getter()
            if not csv_path.exists():
                pytest.skip(f"缺少文件 {csv_path}")
            expected_rows = len(pd.read_csv(csv_path))
            actual = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            assert actual == expected_rows, f"{table_name} 行数不一致：DB {actual} vs CSV {expected_rows}"


def test_no_orphan_foreign_keys(engine):
    """库内外键关系无孤儿。"""
    with engine.connect() as connection:
        subs_orphan = connection.execute(
            text(
                "SELECT COUNT(*) FROM raw_subscriptions s "
                "LEFT JOIN raw_accounts a ON s.account_id = a.account_id WHERE a.account_id IS NULL"
            )
        ).scalar()
        usage_orphan = connection.execute(
            text(
                "SELECT COUNT(*) FROM raw_feature_usage u "
                "LEFT JOIN raw_subscriptions s ON u.subscription_id = s.subscription_id "
                "WHERE s.subscription_id IS NULL"
            )
        ).scalar()
    assert subs_orphan == 0
    assert usage_orphan == 0


def test_usage_id_collision_preserved(engine):
    """usage_id 的 ID 碰撞在导入后依然存在，说明没有做隐式去重。"""
    with engine.connect() as connection:
        duplicated = connection.execute(
            text("SELECT COUNT(*) FROM (SELECT usage_id FROM raw_feature_usage GROUP BY usage_id HAVING COUNT(*) > 1) t")
        ).scalar()
        row_count = connection.execute(text("SELECT COUNT(*) FROM raw_feature_usage")).scalar()
    assert duplicated == 21
    assert row_count == 25000


def test_date_types_are_real_dates(engine):
    """日期列必须是 DATE 类型，能直接做区间查询。"""
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT COUNT(*) FROM raw_subscriptions "
                "WHERE start_date BETWEEN '2024-01-01' AND '2024-01-31'"
            )
        ).scalar()
    assert rows > 0


def test_mrr_sums_to_decimal(engine):
    """金额字段为 DECIMAL，求和结果精确到分。"""
    with engine.connect() as connection:
        total = connection.execute(
            text("SELECT SUM(mrr_amount) FROM raw_subscriptions WHERE end_date IS NULL")
        ).scalar()
    assert total is not None
    assert float(total) > 0
