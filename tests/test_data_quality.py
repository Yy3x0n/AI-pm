"""原始数据质量测试。

这些断言对应 docs/data_audit.md 中记录的审计结论。
如果原始 CSV 被替换成不同版本，测试会失败，这是预期行为：数据变了就要重新审计。
"""

from __future__ import annotations

import pandas as pd
import pytest

from src import config

EXPECTED_ROW_COUNTS = {
    "accounts": 500,
    "subscriptions": 5000,
    "feature_usage": 25000,
    "support_tickets": 2000,
    "churn_events": 600,
}


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.DataFrame]:
    """一次性读取五张原始表。"""
    missing = [name for name in config.TABLES if not config.table_path(name).exists()]
    if missing:
        pytest.skip("原始数据未下载，先执行 bash scripts/download_data.sh：" + ", ".join(missing))
    return {name: pd.read_csv(config.table_path(name)) for name in config.TABLES}


@pytest.mark.parametrize("table_name", list(EXPECTED_ROW_COUNTS))
def test_row_counts(frames, table_name):
    """行数与审计报告一致。"""
    assert len(frames[table_name]) == EXPECTED_ROW_COUNTS[table_name]


@pytest.mark.parametrize("table_name", ["accounts", "subscriptions", "support_tickets", "churn_events"])
def test_primary_keys_unique(frames, table_name):
    """这些表的主键唯一且非空。"""
    key = config.TABLES[table_name]["primary_key"]
    series = frames[table_name][key]
    assert series.notna().all(), f"{table_name}.{key} 存在空值"
    assert not series.duplicated().any(), f"{table_name}.{key} 存在重复"


def test_usage_id_collision_is_known(frames):
    """feature_usage.usage_id 存在 21 个 ID 碰撞，属于数据集已知问题。

    一旦这个数字变化，说明数据版本变了，需要回到 data_audit 重新确认结论。
    """
    usage = frames["feature_usage"]
    duplicated_rows = int(usage["usage_id"].duplicated().sum())
    assert duplicated_rows == 21, f"usage_id 重复行数变为 {duplicated_rows}，请重新审计"


def test_foreign_keys_have_no_orphans(frames):
    """外键全部能关联到父表。"""
    for child, child_key, parent, parent_key in config.FOREIGN_KEYS:
        child_values = frames[child][child_key].dropna()
        orphans = ~child_values.isin(set(frames[parent][parent_key].dropna()))
        assert not orphans.any(), f"{child}.{child_key} 有 {int(orphans.sum())} 行关联不到 {parent}"


def test_subscription_id_unique_enables_usage_join(frames):
    """subscriptions.subscription_id 唯一，feature_usage 关联到组织层级不会放大使用量。"""
    subs = frames["subscriptions"]
    assert subs["subscription_id"].is_unique


def test_churn_sources_are_inconsistent(frames):
    """两套流失口径不一致，这是审计记录在案的数据问题，不是代码问题。

    测试锁定该事实，防止后续分析误以为两者等价而混用。
    """
    accounts = frames["accounts"]
    churn = frames["churn_events"]

    flagged = set(accounts.loc[accounts["churn_flag"].astype(str).isin(["1", "True", "true"]), "account_id"])
    with_events = set(churn["account_id"].dropna())

    assert len(flagged) == 110
    assert len(with_events) == 352
    assert flagged != with_events


def test_core_columns_present(frames):
    """阶段 0 依据表头设计的口径所依赖的字段必须存在。"""
    required = {
        "accounts": ["account_id", "signup_date", "referral_source", "plan_tier", "churn_flag"],
        "subscriptions": ["subscription_id", "account_id", "mrr_amount", "arr_amount", "churn_flag"],
        "feature_usage": ["subscription_id", "usage_date", "feature_name", "usage_count"],
        "support_tickets": ["account_id", "submitted_at", "first_response_time_minutes"],
        "churn_events": ["account_id", "churn_date", "reason_code"],
    }
    for table_name, columns in required.items():
        for column in columns:
            assert column in frames[table_name].columns, f"{table_name} 缺少字段 {column}"
