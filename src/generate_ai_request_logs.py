"""生成模拟 AI 请求日志 data/generated/ai_request_logs.csv。

【重要声明】
本文件是【项目模拟数据】，不是任何真实 AI 产品的生产日志。
生成过程为可复现的随机模拟，固定随机种子，生成逻辑全部在本文件内，无隐藏参数。

用途仅限：请求成功率、响应时间分布、Token 消耗、估算成本分析。

生成逻辑：
1. 按日生成请求量：基础量随时间缓慢增长，叠加工作日/周末季节性。
2. 请求落在 2023-01-01 ~ 2024-12-31，与原始数据时间范围一致。
3. account_id 只从真实存在的组织客户中抽取，席位越多被抽中的概率越高。
4. feature_name 复用原始 feature_usage 中已出现的通用功能名，不臆造业务含义。
5. 两组人为注入的异常窗口，用于验证阶段 5 的异常检测方法，已在 docs/synthetic_data.md 备案：
   - E1 2024-08-12 ~ 2024-08-18：平台级故障，全部功能延迟上升、成功率下降
     （原始数据中各功能使用量接近均匀，若只影响少数功能则信号过弱，故设定为平台级）
   - E2 2024-11-05 ~ 2024-11-09：全平台请求量骤降约 55%
6. 估算成本按 config/ai_pricing.json 的【模拟费率】计算，不是真实账单。

运行：python -m src.generate_ai_request_logs
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src import config

SEED = 20240101
START_DATE = date(2023, 1, 1)
END_DATE = date(2024, 12, 31)

# 人为注入的异常窗口，仅用于方法验证，属于模拟设定
INCIDENT_LATENCY = (date(2024, 8, 12), date(2024, 8, 18))
INCIDENT_VOLUME = (date(2024, 11, 5), date(2024, 11, 9))

BASE_REQUESTS_PER_DAY = 40.0
GROWTH_RATE = 0.55  # 期末相对期初的日请求量增长幅度
WEEKDAY_FACTOR = {0: 1.20, 1: 1.20, 2: 1.18, 3: 1.15, 4: 1.05, 5: 0.70, 6: 0.62}

SUCCESS_RATE_BASE = 0.985
SUCCESS_RATE_INCIDENT = 0.82


def load_pricing() -> dict:
    """读取模拟费率配置。"""
    path = config.PROJECT_ROOT / "config" / "ai_pricing.json"
    with path.open(encoding="utf-8") as handle:
        pricing = json.load(handle)
    if pricing.get("source") != "synthetic":
        raise ValueError("config/ai_pricing.json 必须标注 source=synthetic，避免与真实费率混淆")
    return pricing


def load_account_pool() -> tuple[list[str], np.ndarray]:
    """从原始 accounts 表构造按席位加权的组织客户池。"""
    accounts = pd.read_csv(config.table_path("accounts"))
    weights = accounts["seats"].to_numpy(dtype=float)
    weights = weights / weights.sum()
    return accounts["account_id"].tolist(), weights


def load_feature_pool() -> tuple[list[str], np.ndarray]:
    """从原始 feature_usage 中取已出现的功能名，按其原有使用频次作为抽样概率。"""
    usage = pd.read_csv(config.table_path("feature_usage"), usecols=["feature_name"])
    counts = usage["feature_name"].value_counts()
    names = counts.index.tolist()
    probabilities = (counts / counts.sum()).to_numpy()
    return names, probabilities


def daily_request_counts(rng: np.random.Generator) -> dict[date, int]:
    """生成每天的请求量，含增长趋势、周内季节性与 E2 异常窗口。"""
    total_days = (END_DATE - START_DATE).days + 1
    counts: dict[date, int] = {}
    for offset in range(total_days):
        current = START_DATE + timedelta(days=offset)
        progress = offset / (total_days - 1)
        expected = BASE_REQUESTS_PER_DAY * (1 + GROWTH_RATE * progress)
        expected *= WEEKDAY_FACTOR[current.weekday()]

        if INCIDENT_VOLUME[0] <= current <= INCIDENT_VOLUME[1]:
            expected *= 0.45

        counts[current] = int(rng.poisson(expected))
    return counts


def build_requests(rng: np.random.Generator, pricing: dict) -> pd.DataFrame:
    """拼装请求级明细。"""
    account_ids, account_weights = load_account_pool()
    feature_names, feature_probs = load_feature_pool()

    counts = daily_request_counts(rng)

    rows: list[dict] = []
    request_seq = 0

    for current, count in counts.items():
        if count == 0:
            continue

        accounts_of_day = rng.choice(account_ids, size=count, p=account_weights)
        features_of_day = rng.choice(feature_names, size=count, p=feature_probs)
        in_latency_incident = INCIDENT_LATENCY[0] <= current <= INCIDENT_LATENCY[1]

        # Token 消耗：长尾分布，输入约为输出的 3~6 倍
        input_tokens = rng.lognormal(mean=8.0, sigma=0.6, size=count).astype(int)
        output_tokens = rng.lognormal(mean=6.5, sigma=0.5, size=count).astype(int)

        # 基础延迟：随 Token 数小幅上升，叠加随机抖动
        base_latency = 420 + input_tokens * 0.09 + output_tokens * 0.22
        latency = base_latency * rng.lognormal(mean=0, sigma=0.35, size=count)

        status = np.where(rng.random(count) < SUCCESS_RATE_BASE, "success", "error")

        # E1：平台级故障，所有功能同时受影响，超时占比上升
        if in_latency_incident:
            latency = latency * 2.4
            incident_roll = rng.random(count)
            degraded = incident_roll > SUCCESS_RATE_INCIDENT
            timeout_roll = rng.random(count) < 0.6
            status = np.where(
                degraded,
                np.where(timeout_roll, "timeout", "error"),
                np.where(rng.random(count) < SUCCESS_RATE_BASE, "success", "error"),
            )

        for index in range(count):
            request_seq += 1
            rows.append(
                {
                    "request_id": f"R-{request_seq:07d}",
                    "account_id": accounts_of_day[index],
                    "request_date": current,
                    "feature_name": features_of_day[index],
                    "input_tokens": int(input_tokens[index]),
                    "output_tokens": int(output_tokens[index]),
                    "latency_ms": int(round(latency[index])),
                    "request_status": status[index],
                    "estimated_cost": round(
                        input_tokens[index] / 1_000_000 * pricing["input_token_price"]
                        + output_tokens[index] / 1_000_000 * pricing["output_token_price"],
                        6,
                    ),
                }
            )

    frame = pd.DataFrame(rows)
    # 同一天的请求随机打散时间顺序，避免按功能聚集
    return frame.sample(frac=1, random_state=SEED).reset_index(drop=True)


def main() -> None:
    config.ensure_dirs()
    pricing = load_pricing()
    rng = np.random.default_rng(SEED)

    frame = build_requests(rng, pricing)
    output_path = config.DATA_GENERATED / "ai_request_logs.csv"
    frame.to_csv(output_path, index=False)

    success_rate = (frame["request_status"] == "success").mean()
    print("模拟 AI 请求日志已生成")
    print(f"  文件：{output_path.relative_to(config.PROJECT_ROOT)}")
    print(f"  行数：{len(frame):,}，随机种子：{SEED}")
    print(f"  日期范围：{frame['request_date'].min()} ~ {frame['request_date'].max()}")
    print(f"  覆盖组织客户：{frame['account_id'].nunique()} 个")
    print(f"  整体成功率：{success_rate:.2%}")
    print(f"  估算成本合计（模拟费率）：{frame['estimated_cost'].sum():,.2f} USD")
    print()
    print("提醒：本文件为模拟数据，估算成本基于 config/ai_pricing.json 的模拟费率，不是真实账单。")


if __name__ == "__main__":
    main()
