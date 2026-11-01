"""生成模拟 A/B Test 数据 data/generated/ab_test_onboarding.csv。

【重要声明】
这是一个独立的【模拟随机实验】，不是任何真实产品上跑过的实验。
user_id 是本实验的样本编号，与 RavenStack 数据的 account_id / subscription_id 无关，不冒充真实成员 ID。

流程（先算样本量，再生成数据）：
1. 基准激活率 p1 = 30%，最小可检测的【相对】提升 10%，即 p2 = 33%。
2. alpha = 0.05（双侧），power = 0.8。
3. 用 statsmodels 的 NormalIndPower 求解每组所需样本量。
4. 按求解结果精确生成对照组与实验组各 n 个样本。
5. 7 日留存作为护栏指标，两组真实留存率相同（不设提升），用于观察是否被伤害。

生成参数：
- 固定随机种子
- 对照组真实激活率 0.30，实验组 0.33
- 两组 7 日留存率均为 0.62

注意：分析代码不得读取本文件的生成参数来输出结论，必须从 CSV 重新做检验。

运行：python -m src.generate_ab_test_data
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from src import config

SEED = 20240915

BASELINE_RATE = 0.30
RELATIVE_LIFT = 0.10
ALPHA = 0.05
POWER = 0.8

TRUE_RATE_CONTROL = BASELINE_RATE
TRUE_RATE_TREATMENT = BASELINE_RATE * (1 + RELATIVE_LIFT)
TRUE_RETAINED_D7 = 0.62

EXPERIMENT_START = date(2024, 9, 1)
EXPERIMENT_DAYS = 30


def required_sample_size() -> tuple[int, float]:
    """计算每组所需样本量，返回 (每组样本量, 效应量)。"""
    treatment_rate = BASELINE_RATE * (1 + RELATIVE_LIFT)
    effect_size = proportion_effectsize(treatment_rate, BASELINE_RATE)
    analysis = NormalIndPower()
    size = analysis.solve_power(
        effect_size=effect_size,
        alpha=ALPHA,
        power=POWER,
        ratio=1.0,
        alternative="two-sided",
    )
    return int(np.ceil(size)), float(effect_size)


def build_frame(rng: np.random.Generator, sample_size: int) -> pd.DataFrame:
    """生成实验样本。"""
    groups = ["control", "treatment"] * sample_size
    assignments = np.array(groups)
    rng.shuffle(assignments)

    rates = np.where(assignments == "treatment", TRUE_RATE_TREATMENT, TRUE_RATE_CONTROL)
    activated = (rng.random(len(assignments)) < rates).astype(int)
    retained_d7 = (rng.random(len(assignments)) < TRUE_RETAINED_D7).astype(int)

    offsets = rng.integers(0, EXPERIMENT_DAYS, size=len(assignments))
    base_dt = datetime.combine(EXPERIMENT_START, datetime.min.time())
    assigned_at = [base_dt + timedelta(days=int(offset), hours=int(rng.integers(0, 24))) for offset in offsets]

    return pd.DataFrame(
        {
            "user_id": [f"EXP-{index:06d}" for index in range(1, len(assignments) + 1)],
            "experiment_group": assignments,
            "assigned_at": [timestamp.strftime("%Y-%m-%d %H:%M:%S") for timestamp in assigned_at],
            "activated": activated,
            "retained_d7": retained_d7,
        }
    ).sort_values("user_id", ignore_index=True)


def main() -> None:
    config.ensure_dirs()

    sample_size, effect_size = required_sample_size()
    rng = np.random.default_rng(SEED)
    frame = build_frame(rng, sample_size)

    output_path = config.DATA_GENERATED / "ab_test_onboarding.csv"
    frame.to_csv(output_path, index=False)

    control = frame[frame["experiment_group"] == "control"]
    treatment = frame[frame["experiment_group"] == "treatment"]

    print("模拟 A/B Test 数据已生成")
    print(f"  文件：{output_path.relative_to(config.PROJECT_ROOT)}")
    print(f"  随机种子：{SEED}，总样本：{len(frame):,}（每组 {sample_size:,}）")
    print()
    print("样本量估算：")
    print(f"  基准激活率 {BASELINE_RATE:.0%}，目标相对提升 {RELATIVE_LIFT:.0%}，alpha={ALPHA}，power={POWER}")
    print(f"  Cohen's h 效应量 {effect_size:.4f}，每组需要 {sample_size:,} 个样本")
    print()
    print("生成后的实际表现（仅供核对生成是否符合设定，不作为实验结论）：")
    print(f"  对照组激活率 {control['activated'].mean():.2%}，实验组 {treatment['activated'].mean():.2%}")
    print(f"  对照组 7 日留存 {control['retained_d7'].mean():.2%}，实验组 {treatment['retained_d7'].mean():.2%}")
    print()
    print("结论必须由 src.ab_test_analysis 重新检验得出，不在此处下判断。")


if __name__ == "__main__":
    main()
