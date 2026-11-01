"""把原始 CSV 与两张模拟 CSV 导入 MySQL。

流程：
1. 执行 sql/01_create_tables.sql 重建表结构（脚本可重复执行）。
2. 按外键依赖顺序导入：accounts → subscriptions → feature_usage → support_tickets
   → churn_events → ai_request_logs → ab_test。
3. 导入前后打印行数，并与 CSV 行数逐表核对。
4. 不删除任何记录。审计阶段已确认主键无空值、外键无孤儿，因此清洗只做类型转换，
   不做行级过滤；若将来需要过滤，必须在下方 clean_frame 中显式记录前后行数。

运行：python -m src.load_mysql
"""

from __future__ import annotations

import json
import os

import pandas as pd
import pymysql
from pymysql.constants import CLIENT

from src import config

DDL_PATH = config.PROJECT_ROOT / "sql" / "01_create_tables.sql"
BATCH_SIZE = 2000

# DB 表名 -> (CSV 路径, 说明)
LOAD_PLAN = [
    ("raw_accounts", lambda: config.table_path("accounts"), "原始表"),
    ("raw_subscriptions", lambda: config.table_path("subscriptions"), "原始表"),
    ("raw_feature_usage", lambda: config.table_path("feature_usage"), "原始表"),
    ("raw_support_tickets", lambda: config.table_path("support_tickets"), "原始表"),
    ("raw_churn_events", lambda: config.table_path("churn_events"), "原始表"),
    ("synthetic_ai_request_logs", lambda: config.DATA_GENERATED / "ai_request_logs.csv", "模拟表"),
    ("synthetic_ab_test_onboarding", lambda: config.DATA_GENERATED / "ab_test_onboarding.csv", "模拟表"),
]


def connect(use_database: bool = True):
    """建立数据库连接。建表阶段不指定库名，因为库可能尚不存在。"""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME") if use_database else None,
        charset="utf8mb4",
        autocommit=False,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )


def apply_ddl(connection) -> None:
    """执行建表脚本。"""
    sql = DDL_PATH.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        cursor.execute(sql)
        # 多语句执行后需要把所有结果集读干净，否则后续命令会报 "Commands out of sync"
        while cursor.nextset():
            pass
    connection.commit()


def table_columns(connection, table_name: str) -> list[tuple[str, str]]:
    """从 information_schema 读取目标表的列名与类型，保证写入顺序与表结构一致。"""
    query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND extra NOT LIKE '%%auto_increment%%'
        ORDER BY ordinal_position
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (os.getenv("DB_NAME"), table_name))
        return [(row[0], row[1].lower()) for row in cursor.fetchall()]


def convert_series(series: pd.Series, data_type: str) -> list:
    """按目标列类型转换，空值统一转为 None（写入 SQL NULL）。"""
    if data_type == "date":
        parsed = pd.to_datetime(series, errors="coerce")
        return [None if pd.isna(value) else value.date() for value in parsed]

    if data_type == "datetime":
        parsed = pd.to_datetime(series, errors="coerce")
        return [None if pd.isna(value) else value.to_pydatetime() for value in parsed]

    if data_type in {"int", "bigint", "smallint", "tinyint", "mediumint"}:
        return [None if pd.isna(value) else int(value) for value in series]

    if data_type in {"decimal", "float", "double"}:
        return [None if pd.isna(value) else float(value) for value in series]

    return [None if pd.isna(value) else str(value) for value in series]


def load_table(connection, table_name: str, csv_path, label: str) -> dict:
    """导入单张表并返回核对结果。"""
    if not csv_path.exists():
        raise FileNotFoundError(f"缺少数据文件：{csv_path}")

    frame = pd.read_csv(csv_path)
    columns = table_columns(connection, table_name)

    missing = [name for name, _ in columns if name not in frame.columns]
    if missing:
        raise ValueError(f"{table_name} 缺少 CSV 字段：{', '.join(missing)}")

    converted = [convert_series(frame[name], data_type) for name, data_type in columns]
    rows = list(zip(*converted))

    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f"`{name}`" for name, _ in columns)
    insert_sql = f"INSERT INTO `{table_name}` ({column_sql}) VALUES ({placeholders})"

    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM `{table_name}`")
        for start in range(0, len(rows), BATCH_SIZE):
            cursor.executemany(insert_sql, rows[start : start + BATCH_SIZE])
    connection.commit()

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        imported = cursor.fetchone()[0]

    return {
        "table": table_name,
        "label": label,
        "csv_rows": len(frame),
        "db_rows": int(imported),
        "match": int(imported) == len(frame),
        "columns": len(columns),
    }


def main() -> None:
    config.ensure_dirs()

    print("连接数据库 ...")
    connection = connect(use_database=False)
    try:
        print(f"执行建表脚本：{DDL_PATH.relative_to(config.PROJECT_ROOT)}")
        apply_ddl(connection)
        connection.select_db(os.getenv("DB_NAME"))

        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        connection.commit()

        results = []
        for table_name, path_getter, label in LOAD_PLAN:
            result = load_table(connection, table_name, path_getter(), label)
            results.append(result)
            flag = "OK" if result["match"] else "不一致"
            print(
                f"  {table_name:<30} CSV {result['csv_rows']:>6} 行 -> DB {result['db_rows']:>6} 行  [{flag}]"
            )

        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        connection.commit()

        # 外键关系复查：导入后在库内再验证一次
        fk_query = """
            SELECT
              (SELECT COUNT(*) FROM raw_subscriptions s
                 LEFT JOIN raw_accounts a ON s.account_id = a.account_id
                WHERE a.account_id IS NULL) AS subs_orphan,
              (SELECT COUNT(*) FROM raw_feature_usage u
                 LEFT JOIN raw_subscriptions s ON u.subscription_id = s.subscription_id
                WHERE s.subscription_id IS NULL) AS usage_orphan
        """
        with connection.cursor() as cursor:
            cursor.execute(fk_query)
            subs_orphan, usage_orphan = cursor.fetchone()

        print()
        print(f"外键复查：订阅孤儿 {subs_orphan} 行，使用记录孤儿 {usage_orphan} 行")

        summary_path = config.OUTPUT_REPORTS / "load_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "tables": results,
                    "orphans": {"raw_subscriptions": subs_orphan, "raw_feature_usage": usage_orphan},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"导入汇总：{summary_path.relative_to(config.PROJECT_ROOT)}")

        if not all(item["match"] for item in results) or subs_orphan or usage_orphan:
            raise SystemExit("导入校验未通过，请检查上面的行数对照")
        print("全部表导入完成，行数与 CSV 一致。")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
