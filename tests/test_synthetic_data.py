"""模拟数据的结构与口径测试。

只校验"生成结果是否自洽"，不下任何统计结论。
真正的 A/B 检验见阶段 5 的 src/ab_test_analysis.py。
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src import config

AI_LOG_PATH = config.DATA_GENERATED / "ai_request_logs.csv"
AB_TEST_PATH = config.DATA_GENERATED / "ab_test_onboarding.csv"


@pytest.fixture(scope="module")
def ai_logs() -> pd.DataFrame:
    if not AI_LOG_PATH.exists():
        pytest.skip("模拟日志未生成，先执行 python -m src.generate_ai_request_logs")
    return pd.read_csv(AI_LOG_PATH)


@pytest.fixture(scope="module")
def ab_test() -> pd.DataFrame:
    if not AB_TEST_PATH.exists():
        pytest.skip("实验数据未生成，先执行 python -m src.generate_ab_test_data")
    return pd.read_csv(AB_TEST_PATH)


# ------------------------- AI 请求日志 -------------------------


def test_ai_request_id_unique(ai_logs):
    assert ai_logs["request_id"].is_unique
    assert ai_logs["request_id"].notna().all()


def test_ai_accounts_exist_in_source(ai_logs):
    """模拟日志的 account_id 必须能关联回真实组织客户。"""
    accounts = pd.read_csv(config.table_path("accounts"), usecols=["account_id"])
    unknown = set(ai_logs["account_id"]) - set(accounts["account_id"])
    assert not unknown, f"存在 {len(unknown)} 个无法关联的 account_id"


def test_ai_feature_names_come_from_source(ai_logs):
    """功能名必须复用原始数据中已出现的通用名，不得臆造。"""
    usage = pd.read_csv(config.table_path("feature_usage"), usecols=["feature_name"])
    unknown = set(ai_logs["feature_name"]) - set(usage["feature_name"])
    assert not unknown, f"出现原始数据中不存在的功能名：{sorted(unknown)[:5]}"


def test_ai_status_values(ai_logs):
    assert set(ai_logs["request_status"]) <= {"success", "error", "timeout"}


def test_ai_metrics_positive(ai_logs):
    assert (ai_logs["input_tokens"] > 0).all()
    assert (ai_logs["output_tokens"] > 0).all()
    assert (ai_logs["latency_ms"] > 0).all()


def test_estimated_cost_matches_pricing(ai_logs):
    """估算成本必须能由 token 数与模拟费率精确重算。"""
    pricing = json.loads((config.PROJECT_ROOT / "config" / "ai_pricing.json").read_text(encoding="utf-8"))
    expected = (
        ai_logs["input_tokens"] / 1_000_000 * pricing["input_token_price"]
        + ai_logs["output_tokens"] / 1_000_000 * pricing["output_token_price"]
    )
    assert np.allclose(ai_logs["estimated_cost"], expected, atol=1e-6)


def test_ai_dates_within_source_range(ai_logs):
    dates = pd.to_datetime(ai_logs["request_date"])
    assert dates.min() >= pd.Timestamp("2023-01-01")
    assert dates.max() <= pd.Timestamp("2024-12-31")


# ------------------------- A/B 实验 -------------------------


def test_ab_user_id_unique(ab_test):
    assert ab_test["user_id"].is_unique


def test_ab_group_sizes_balanced(ab_test):
    """两组样本量必须相等，这是生成时的设计，不是统计结论。"""
    counts = ab_test["experiment_group"].value_counts()
    assert set(counts.index) == {"control", "treatment"}
    assert counts["control"] == counts["treatment"]


def test_ab_binary_outcomes(ab_test):
    for column in ["activated", "retained_d7"]:
        assert set(ab_test[column].unique()) <= {0, 1}


def test_ab_sample_size_matches_design(ab_test):
    """样本量应与样本量估算结果一致（每组 3,762，共 7,524）。"""
    assert len(ab_test) == 7524


def test_ab_ids_do_not_masquerade_as_source_ids(ab_test):
    """实验样本 ID 不得与原始数据的 ID 体系混淆。"""
    assert ab_test["user_id"].str.startswith("EXP-").all()


def test_ab_assignment_window(ab_test):
    dates = pd.to_datetime(ab_test["assigned_at"])
    assert dates.min() >= pd.Timestamp("2024-09-01")
    assert dates.max() < pd.Timestamp("2024-10-01")
