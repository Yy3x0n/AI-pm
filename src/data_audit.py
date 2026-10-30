"""原始数据审计：检查行数、字段类型、主键重复、空值、日期范围、外键可关联性。

运行：python -m src.data_audit
产出：
  docs/data_audit.md          审计报告
  docs/data_dictionary.md     数据字典（由字段画像生成）
  output/tables/audit_column_profile.csv  逐字段画像明细

只读取 data/raw/ravenstack 下的原始 CSV，不做任何修改。
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src import config

# 字段含义说明。含义取自字段命名与数据表现，不确定的标注"待确认"，不臆造业务含义。
FIELD_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "accounts": {
        "account_id": "组织客户唯一标识（主键）",
        "account_name": "组织客户名称",
        "industry": "所属行业",
        "country": "所在国家",
        "signup_date": "注册日期",
        "referral_source": "获客来源渠道",
        "plan_tier": "注册时所选套餐档位",
        "seats": "购买席位数",
        "is_trial": "是否试用中",
        "churn_flag": "该组织是否已流失（客户级标记）",
    },
    "subscriptions": {
        "subscription_id": "订阅唯一标识（主键）",
        "account_id": "所属组织客户（外键）",
        "start_date": "订阅开始日期",
        "end_date": "订阅结束日期",
        "plan_tier": "订阅套餐档位",
        "seats": "订阅席位数",
        "mrr_amount": "月度经常性收入（订阅金额，非现金流水）",
        "arr_amount": "年度经常性收入（订阅金额，非现金流水）",
        "is_trial": "是否试用订阅",
        "upgrade_flag": "该订阅期内是否发生升级",
        "downgrade_flag": "该订阅期内是否发生降级",
        "churn_flag": "该订阅是否以流失结束（订阅级标记）",
        "billing_frequency": "计费频率",
        "auto_renew_flag": "是否自动续费",
    },
    "feature_usage": {
        "usage_id": "使用记录唯一标识（主键）",
        "subscription_id": "所属订阅（外键，注意本表无 account_id）",
        "usage_date": "使用发生日期",
        "feature_name": "功能标识（通用命名，不代表具体业务功能）",
        "usage_count": "当日该功能使用次数",
        "usage_duration_secs": "当日该功能使用时长（秒）",
        "error_count": "当日该功能错误次数",
        "is_beta_feature": "是否灰度/测试功能",
    },
    "support_tickets": {
        "ticket_id": "工单唯一标识（主键）",
        "account_id": "提单组织客户（外键）",
        "submitted_at": "工单提交时间",
        "closed_at": "工单关闭时间，空值代表未关闭",
        "resolution_time_hours": "解决耗时（小时）",
        "priority": "工单优先级",
        "first_response_time_minutes": "首次响应耗时（分钟）",
        "satisfaction_score": "客户满意度评分",
        "escalation_flag": "是否升级处理",
    },
    "churn_events": {
        "churn_event_id": "流失事件唯一标识（主键）",
        "account_id": "流失组织客户（外键）",
        "churn_date": "流失发生日期",
        "reason_code": "流失原因代码",
        "refund_amount_usd": "退款金额（美元）",
        "preceding_upgrade_flag": "流失前是否发生升级",
        "preceding_downgrade_flag": "流失前是否发生降级",
        "is_reactivation": "该事件是否为再激活（回流）",
        "feedback_text": "客户反馈原文",
    },
}


# 各表粒度说明，写进数据字典
GRANULARITY = {
    "accounts": "一行一个组织客户，account_id 唯一",
    "subscriptions": "一行一个订阅周期记录，同一组织可有多条订阅",
    "feature_usage": "一行一条「订阅 × 日期 × 功能」的日粒度使用记录，注意本表无 account_id",
    "support_tickets": "一行一张客服工单",
    "churn_events": "一行一次流失事件，同一组织可有多条（含再激活）",
}


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    """生成 Markdown 表格。"""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        cells = ["" if cell is None else str(cell) for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load_table(table_name: str) -> pd.DataFrame:
    """读取单张原始表，并检查文件是否存在。"""
    path = config.table_path(table_name)
    if not path.exists():
        raise FileNotFoundError(f"未找到原始文件：{path}。请先执行 bash scripts/download_data.sh")
    return pd.read_csv(path)


def profile_columns(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """逐字段画像：类型、非空率、唯一值数、数值范围、样例值。"""
    records = []
    for column in df.columns:
        series = df[column]
        non_null = int(series.notna().sum())
        record = {
            "table": table_name,
            "column": column,
            "dtype": str(series.dtype),
            "non_null": non_null,
            "null_count": int(series.isna().sum()),
            "null_rate_pct": round(series.isna().mean() * 100, 2),
            "unique_count": int(series.nunique(dropna=True)),
            "min": "",
            "max": "",
            "sample_values": "",
            "description": FIELD_DESCRIPTIONS.get(table_name, {}).get(column, "待确认"),
        }

        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().any() and series.dtype != object:
            record["min"] = round(float(numeric.min()), 4)
            record["max"] = round(float(numeric.max()), 4)

        samples = series.dropna().unique()[:3]
        record["sample_values"] = "; ".join(str(value)[:40] for value in samples)
        records.append(record)

    return pd.DataFrame(records)


def check_primary_key(df: pd.DataFrame, key: str) -> dict:
    """检查主键空值与重复。"""
    if key not in df.columns:
        return {"key": key, "exists": False}
    return {
        "key": key,
        "exists": True,
        "null_count": int(df[key].isna().sum()),
        "duplicated_rows": int(df[key].duplicated().sum()),
        "unique_count": int(df[key].nunique(dropna=True)),
        "row_count": len(df),
    }


def profile_dates(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    """检查日期字段范围与解析失败数量。"""
    results = []
    for column in columns:
        if column not in df.columns:
            results.append({"column": column, "exists": False})
            continue
        raw = df[column]
        parsed = pd.to_datetime(raw, errors="coerce")
        failed = int(raw.notna().sum() - parsed.notna().sum())
        results.append(
            {
                "column": column,
                "exists": True,
                "min": parsed.min(),
                "max": parsed.max(),
                "null_count": int(raw.isna().sum()),
                "parse_failed": failed,
            }
        )
    return results


def profile_numeric(df: pd.DataFrame) -> list[dict]:
    """数值字段取值范围与异常值计数（负数、零值）。"""
    results = []
    for column in df.select_dtypes(include="number").columns:
        series = df[column]
        results.append(
            {
                "column": column,
                "min": round(float(series.min()), 4) if series.notna().any() else None,
                "max": round(float(series.max()), 4) if series.notna().any() else None,
                "mean": round(float(series.mean()), 4) if series.notna().any() else None,
                "negative_count": int((series < 0).sum()),
                "zero_count": int((series == 0).sum()),
            }
        )
    return results


def check_foreign_keys(frames: dict[str, pd.DataFrame]) -> list[dict]:
    """检查外键能否关联到父表，并统计关联不上的行数。"""
    results = []
    for child, child_key, parent, parent_key in config.FOREIGN_KEYS:
        child_df = frames[child]
        parent_df = frames[parent]
        if child_key not in child_df.columns or parent_key not in parent_df.columns:
            results.append(
                {"child": child, "child_key": child_key, "parent": parent, "status": "字段缺失"}
            )
            continue
        child_values = child_df[child_key].dropna()
        parent_values = set(parent_df[parent_key].dropna())
        unmatched = int((~child_values.isin(parent_values)).sum())
        results.append(
            {
                "child": child,
                "child_key": child_key,
                "parent": parent,
                "status": "通过" if unmatched == 0 else "存在未匹配",
                "child_non_null": int(len(child_values)),
                "unmatched": unmatched,
                "orphan_rate_pct": round(unmatched / len(child_values) * 100, 2) if len(child_values) else 0.0,
            }
        )
    return results


def specific_checks(frames: dict[str, pd.DataFrame]) -> list[tuple[str, str]]:
    """针对本项目关键口径的专项检查，返回 (检查项, 结论) 列表。"""
    findings: list[tuple[str, str]] = []

    subs = frames["subscriptions"]
    usage = frames["feature_usage"]
    accounts = frames["accounts"]
    tickets = frames["support_tickets"]
    churn = frames["churn_events"]

    # 1. subscription_id 是否唯一，直接决定 feature_usage 关联到组织层级时会不会放大使用量
    dup_subs = int(subs["subscription_id"].duplicated().sum())
    findings.append(
        (
            "subscriptions.subscription_id 唯一性",
            f"重复 {dup_subs} 行。{'唯一，feature_usage 可按 subscription_id 一对一关联，不会放大使用量。' if dup_subs == 0 else '不唯一，关联 feature_usage 前必须去重，否则使用量会被放大。'}",
        )
    )

    # 2. usage_id 是否唯一。本数据集存在 ID 碰撞，必须查明是整行重复还是 ID 冲突
    if "usage_id" in usage.columns:
        conflict_mask = usage["usage_id"].duplicated(keep=False)
        conflict_rows = int(conflict_mask.sum())
        if conflict_rows:
            conflict_ids = int(usage.loc[conflict_mask, "usage_id"].nunique())
            conflict_view = usage.loc[conflict_mask].sort_values("usage_id")
            identical_rows = int(conflict_view.duplicated(subset=list(usage.columns)).sum())
            findings.append(
                (
                    "feature_usage.usage_id 唯一性",
                    f"存在 {conflict_ids} 个 usage_id 各出现两次，共 {conflict_rows} 行；其中整行完全相同的仅 {identical_rows} 行。"
                    "冲突行的 subscription_id 与 usage_date 并不相同，属于 ID 碰撞而非重复上报。"
                    "结论：usage_id 不能作为唯一键使用，去重与计数应以 (subscription_id, usage_date, feature_name) 或行号为准。",
                )
            )
        else:
            findings.append(("feature_usage.usage_id 唯一性", "全部唯一。"))

    # 3. MRR 与 ARR 的关系
    if {"mrr_amount", "arr_amount"}.issubset(subs.columns):
        ratio = (subs["arr_amount"] / subs["mrr_amount"]).replace([float("inf")], pd.NA).dropna()
        findings.append(
            (
                "arr_amount 与 mrr_amount 的比例",
                f"中位数 {ratio.median():.3f}，最小 {ratio.min():.3f}，最大 {ratio.max():.3f}。"
                + ("接近 12，ARR 可视为 MRR 的年化值，两个指标不可相加。" if 11.5 <= ratio.median() <= 12.5 else "明显偏离 12，ARR 不是简单的 MRR×12，两个指标需分别按原字段口径使用。"),
            )
        )

        zero_mrr = int((subs["mrr_amount"] == 0).sum())
        findings.append(("mrr_amount 为 0 的订阅数", f"{zero_mrr} 行。计算付费 MRR 时需明确是否包含试用订阅。"))

    # 4. 订阅区间是否合法
    if {"start_date", "end_date"}.issubset(subs.columns):
        start = pd.to_datetime(subs["start_date"], errors="coerce")
        end = pd.to_datetime(subs["end_date"], errors="coerce")
        bad = int((end < start).sum())
        open_subs = int(end.isna().sum())
        findings.append(
            (
                "订阅起止日期合法性",
                f"end_date 早于 start_date 的 {bad} 行；end_date 为空（视为仍在生效）的 {open_subs} 行。",
            )
        )

    # 5. 同一组织是否同时存在多个订阅（影响"当前有效订阅"口径）
    per_account = subs.groupby("account_id")["subscription_id"].count()
    findings.append(
        (
            "每个组织客户的订阅记录数",
            f"最多 {int(per_account.max())} 条，中位数 {per_account.median():.0f} 条。"
            "取某一时点的 MRR 时必须限定订阅生效区间，不能把同一组织的多条订阅直接相加。",
        )
    )

    # 6. 工单未关闭情况
    if {"closed_at", "resolution_time_hours"}.issubset(tickets.columns):
        open_tickets = int(tickets["closed_at"].isna().sum())
        open_with_hours = int((tickets["closed_at"].isna() & tickets["resolution_time_hours"].notna()).sum())
        findings.append(
            (
                "未关闭工单",
                f"closed_at 为空 {open_tickets} 行，其中仍有 resolution_time_hours 值的 {open_with_hours} 行。"
                "计算平均解决时长时必须说明是否排除未关闭工单。",
            )
        )

    # 7. 客户级流失标记与流失事件表是否一致
    churn_flag_accounts = set(
        accounts.loc[accounts["churn_flag"].astype(str).isin(["1", "True", "true"]), "account_id"]
    )
    event_accounts = set(churn["account_id"].dropna())
    reactivation = int((churn["is_reactivation"] == 1).sum()) if "is_reactivation" in churn.columns else 0
    findings.append(
        (
            "客户流失口径交叉核对",
            f"accounts.churn_flag 标记流失的组织 {len(churn_flag_accounts)} 个；churn_events 覆盖 {len(event_accounts)} 个组织、"
            f"{len(churn)} 条事件（其中再激活 {reactivation} 条）。两者一致的 {len(churn_flag_accounts & event_accounts)} 个，"
            f"仅 flag 标记的 {len(churn_flag_accounts - event_accounts)} 个，仅事件表有记录的 {len(event_accounts - churn_flag_accounts)} 个。"
            "差异无法全部由再激活解释，说明两个流失来源本身不一致。"
            "结论：客户流失率必须选定唯一口径（建议以 churn_events 为事件源，因它带流失日期与原因），"
            "并在指标字典中写明分子来源，不得混用。",
        )
    )

    # 8. 满意度空值，直接影响平均值的分母
    if "satisfaction_score" in tickets.columns:
        null_sat = int(tickets["satisfaction_score"].isna().sum())
        findings.append(
            (
                "工单满意度空值",
                f"{null_sat} 行无评分（占 {null_sat / len(tickets) * 100:.1f}%）。计算平均满意度时需写明分母是全部工单还是仅有评分的工单。",
            )
        )

    # 9. feature_usage 的覆盖情况
    usage_subs = int(usage["subscription_id"].nunique())
    findings.append(
        (
            "feature_usage 覆盖的订阅数",
            f"{usage_subs} 个订阅存在使用记录，占全部 {len(subs)} 条订阅的 {usage_subs / len(subs) * 100:.1f}%。"
            "没有使用记录的订阅不能被当作流失，只能标记为未观测到使用。",
        )
    )

    # 10. 是否存在完全重复的使用记录
    subset = [c for c in ["subscription_id", "usage_date", "feature_name"] if c in usage.columns]
    if subset:
        dup_usage = int(usage.duplicated(subset=subset).sum())
        findings.append(
            (
                "feature_usage 业务键重复",
                f"(subscription_id, usage_date, feature_name) 组合重复 {dup_usage} 行。"
                + ("无重复，可作为使用事实表的天然业务键。" if dup_usage == 0 else "存在重复，聚合前需确认是否为多次上报。"),
            )
        )

    return findings


def main() -> None:
    config.ensure_dirs()

    frames: dict[str, pd.DataFrame] = {}
    file_stats: list[dict] = []

    for table_name, spec in config.TABLES.items():
        df = load_table(table_name)
        frames[table_name] = df
        file_stats.append(
            {
                "table": table_name,
                "file": spec["file"],
                "rows": len(df),
                "columns": df.shape[1],
                "size_kb": round(config.table_path(table_name).stat().st_size / 1024, 1),
                "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
            }
        )

    # 逐字段画像
    profiles = pd.concat(
        [profile_columns(name, df) for name, df in frames.items()], ignore_index=True
    )
    profiles.to_csv(config.OUTPUT_TABLES / "audit_column_profile.csv", index=False, encoding="utf-8-sig")

    # 各类检查。注意必须显式按表名取 frames[name]，
    # 不能用循环遗留的 df 变量，否则所有表都会拿到最后一张表的数据。
    primary_keys = {
        name: check_primary_key(frames[name], spec["primary_key"]) for name, spec in config.TABLES.items()
    }
    dates = {
        name: profile_dates(frames[name], spec["date_columns"]) for name, spec in config.TABLES.items()
    }
    numerics = {name: profile_numeric(frame) for name, frame in frames.items()}
    foreign_keys = check_foreign_keys(frames)
    findings = specific_checks(frames)

    # 组装报告
    report: list[str] = []
    report.append("# 数据审计报告")
    report.append("")
    report.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("- 数据来源：RavenStack SaaS Subscription & Churn Analytics Dataset（公开合成教学数据）")
    report.append("- 数据镜像：https://github.com/tivonio/sql-churn-analysis")
    report.append("- 审计对象：`data/raw/ravenstack/` 下五个 CSV，只读，未做任何修改")
    report.append("- 复现方式：`bash scripts/download_data.sh && python -m src.data_audit`")
    report.append("")
    report.append(
        "> 声明：本数据集为合成教学数据，不是任何企业的真实经营数据，也不是真实 AI 产品日志。"
        "以下所有结论仅描述本数据集自身特征。"
    )
    report.append("")

    report.append("## 1. 文件级概览")
    report.append("")
    report.append(
        md_table(
            ["表", "文件", "行数", "列数", "文件大小(KB)", "内存占用(KB)"],
            [[s["table"], s["file"], s["rows"], s["columns"], s["size_kb"], s["memory_kb"]] for s in file_stats],
        )
    )
    report.append("")

    report.append("## 2. 主键检查")
    report.append("")
    pk_rows = []
    for table_name, info in primary_keys.items():
        if not info.get("exists", True):
            pk_rows.append([table_name, config.TABLES[table_name]["primary_key"], "-", "-", "-", "字段不存在"])
            continue
        status = "通过" if info["duplicated_rows"] == 0 and info["null_count"] == 0 else "存在问题"
        pk_rows.append(
            [
                table_name,
                info["key"],
                info["row_count"],
                info["unique_count"],
                info["duplicated_rows"],
                f"{status}（主键空值 {info['null_count']}）",
            ]
        )
    report.append(md_table(["表", "主键", "行数", "去重值数", "重复行数", "结论"], pk_rows))
    report.append("")

    report.append("## 3. 外键可关联性")
    report.append("")
    fk_rows = []
    for item in foreign_keys:
        if item.get("status") == "字段缺失":
            fk_rows.append([item["child"], item["child_key"], item["parent"], "-", "-", "字段缺失"])
            continue
        fk_rows.append(
            [
                item["child"],
                item["child_key"],
                item["parent"],
                item["child_non_null"],
                item["unmatched"],
                f"{item['status']}（孤儿率 {item['orphan_rate_pct']}%）",
            ]
        )
    report.append(md_table(["子表", "字段", "父表", "非空值数", "未匹配数", "结论"], fk_rows))
    report.append("")

    report.append("## 4. 日期字段")
    report.append("")
    date_rows = []
    for table_name, items in dates.items():
        for item in items:
            if not item.get("exists"):
                date_rows.append([table_name, item["column"], "-", "-", "-", "字段不存在"])
                continue
            date_rows.append(
                [
                    table_name,
                    item["column"],
                    item["min"].strftime("%Y-%m-%d") if pd.notna(item["min"]) else "-",
                    item["max"].strftime("%Y-%m-%d") if pd.notna(item["max"]) else "-",
                    item["null_count"],
                    item["parse_failed"],
                ]
            )
    report.append(md_table(["表", "字段", "最早", "最晚", "空值数", "解析失败数"], date_rows))
    report.append("")

    report.append("## 5. 数值字段取值范围")
    report.append("")
    for table_name, items in numerics.items():
        if not items:
            continue
        report.append(f"**{table_name}**")
        report.append("")
        report.append(
            md_table(
                ["字段", "最小", "最大", "均值", "负值数", "零值数"],
                [[i["column"], i["min"], i["max"], i["mean"], i["negative_count"], i["zero_count"]] for i in items],
            )
        )
        report.append("")

    report.append("## 6. 空值分布")
    report.append("")
    null_rows = []
    for table_name, frame in profiles.groupby("table", sort=False):
        for _, row in frame[frame["null_count"] > 0].iterrows():
            null_rows.append([table_name, row["column"], row["null_count"], f"{row['null_rate_pct']}%"])
    if null_rows:
        report.append(md_table(["表", "字段", "空值数", "空值率"], null_rows))
    else:
        report.append("五张表均无空值。")
    report.append("")

    report.append("## 7. 关键字段取值分布")
    report.append("")
    for table_name, spec in config.TABLES.items():
        df = frames[table_name]
        distribution_lines = []
        for column in spec["key_columns"]:
            if column not in df.columns:
                continue
            counts = df[column].value_counts(dropna=False).head(6)
            parts = [f"{index}={count}" for index, count in counts.items()]
            distribution_lines.append(f"- `{column}`：共 {df[column].nunique()} 个取值；前几位 {'，'.join(parts)}")
        if distribution_lines:
            report.append(f"**{table_name}**")
            report.append("")
            report.extend(distribution_lines)
            report.append("")

    report.append("## 8. 专项检查结论")
    report.append("")
    report.append(md_table(["检查项", "结论"], [[name, text] for name, text in findings]))
    report.append("")

    report.append("## 9. 对后续分析口径的影响")
    report.append("")
    report.append(
        "1. `feature_usage` 不含 `account_id`，组织层级的活跃、留存、分层指标必须经 `subscriptions` 关联换算。"
    )
    report.append(
        "2. 客户流失沿用 `churn_events` 作为事件源（带流失日期与原因代码），`accounts.churn_flag` 仅作交叉核对；"
        "两者对同一组织的标记并不一致，分子不得混用。"
    )
    report.append(
        "3. `feature_usage.usage_id` 存在 ID 碰撞，不得作为唯一键；去重与计数以 (subscription_id, usage_date, feature_name) 或行号为准。"
    )
    report.append("4. 计算时点 MRR 需限定订阅生效区间，避免把同一组织的多条订阅简单相加。")
    report.append("5. 解决时长、响应时长、满意度的均值需说明分母（未关闭工单、无评分工单如何处理）。")
    report.append("6. 原始数据未做任何清洗；清洗规则与前后行数变化在阶段 2 记录。")
    report.append("")

    audit_path = config.DOCS_DIR / "data_audit.md"
    audit_path.write_text("\n".join(report), encoding="utf-8")

    # 数据字典：由字段画像 + 人工含义说明组成
    dictionary: list[str] = []
    dictionary.append("# 数据字典")
    dictionary.append("")
    dictionary.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    dictionary.append("- 所有表均为公开合成数据（RavenStack），非真实企业数据")
    dictionary.append("- 字段含义依据字段命名与数据表现归纳；标注为「待确认」的字段不做业务解释")
    dictionary.append("")
    for table_name, spec in config.TABLES.items():
        subset = profiles[profiles["table"] == table_name]
        date_ranges = {
            item["column"]: (item["min"], item["max"]) for item in dates[table_name] if item.get("exists")
        }
        dictionary.append(f"## {table_name}（`{spec['file']}`）")
        dictionary.append("")
        dictionary.append(f"- 粒度：{GRANULARITY[table_name]}")
        dictionary.append(f"- 主键：`{spec['primary_key']}`")
        dictionary.append(f"- 行数：{len(frames[table_name])}")
        dictionary.append("")

        rows = []
        for _, row in subset.iterrows():
            column = row["column"]
            if column in date_ranges:
                dtype_label = "date"
                low, high = date_ranges[column]
                value_label = f"{low:%Y-%m-%d} ~ {high:%Y-%m-%d}" if pd.notna(low) else "-"
            elif str(row["dtype"]).startswith(("int", "float")):
                dtype_label = str(row["dtype"])
                if str(row["dtype"]).startswith("int"):
                    value_label = f"{int(row['min'])} ~ {int(row['max'])}"
                else:
                    value_label = f"{row['min']} ~ {row['max']}"
            else:
                dtype_label = str(row["dtype"])
                value_label = row["sample_values"]
            rows.append(
                [
                    column,
                    dtype_label,
                    f"{(100 - row['null_rate_pct']):.1f}%",
                    row["unique_count"],
                    value_label,
                    row["description"],
                ]
            )

        dictionary.append(
            md_table(["字段", "类型", "非空率", "唯一值数", "取值范围/样例", "含义"], rows)
        )
        dictionary.append("")

    (config.DOCS_DIR / "data_dictionary.md").write_text("\n".join(dictionary), encoding="utf-8")

    print("审计完成")
    print(f"  报告：{audit_path.relative_to(config.PROJECT_ROOT)}")
    print(f"  字典：{(config.DOCS_DIR / 'data_dictionary.md').relative_to(config.PROJECT_ROOT)}")
    print(f"  字段画像：{(config.OUTPUT_TABLES / 'audit_column_profile.csv').relative_to(config.PROJECT_ROOT)}")
    print()
    for stat in file_stats:
        print(f"  {stat['table']:<18} {stat['rows']:>6} 行  {stat['columns']:>2} 列")
    print()
    print("专项检查：")
    for name, text in findings:
        print(f"  - {name}：{text}")


if __name__ == "__main__":
    main()
