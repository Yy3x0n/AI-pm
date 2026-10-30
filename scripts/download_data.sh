#!/usr/bin/env bash
# 下载 RavenStack 五张原始 CSV 到 data/raw/ravenstack/
# 数据源优先官方 GitHub Raw，失败时依次回退到公开镜像；任一文件最终失败即以非 0 退出，
# 并打印手动下载说明，不静默跳过。
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="$PROJECT_ROOT/data/raw/ravenstack"
BASE_URL="https://raw.githubusercontent.com/tivonio/sql-churn-analysis/main/data/raw"

# 下载源候选链。第 1 个是官方地址，其余为公开镜像，仅在官方地址不可达时使用。
SOURCES=(
  "$BASE_URL"
  "https://gh-proxy.com/$BASE_URL"
  "https://ghfast.top/$BASE_URL"
)

FILES=(
  ravenstack_accounts.csv
  ravenstack_subscriptions.csv
  ravenstack_feature_usage.csv
  ravenstack_support_tickets.csv
  ravenstack_churn_events.csv
)

# 每个文件的表头首字段，用于确认下到的确实是目标数据而不是错误页
EXPECTED_FIRST_COLUMN=(
  account_id
  subscription_id
  usage_id
  ticket_id
  churn_event_id
)

mkdir -p "$RAW_DIR"

failed=0
echo "下载目录：$RAW_DIR"
echo "------------------------------------------------------------"

for i in "${!FILES[@]}"; do
  file="${FILES[$i]}"
  expected="${EXPECTED_FIRST_COLUMN[$i]}"
  target="$RAW_DIR/$file"
  tmp="$target.part"

  # 已有完整文件且表头正确则跳过，保证脚本可重复执行
  if [ -s "$target" ] && head -1 "$target" | cut -d',' -f1 | grep -qx "$expected"; then
    echo "[跳过] $file 已存在（$(wc -c <"$target" | tr -d ' ') 字节）"
    continue
  fi

  echo "[下载] $file"
  got=0
  index=0
  for source in "${SOURCES[@]}"; do
    host="$(echo "$source" | cut -d'/' -f3)"
    # 官方源给较短超时，避免网络不通时长时间空等；镜像源给足时间
    if [ "$index" -eq 0 ]; then
      max_time=45
      retries=1
    else
      max_time=180
      retries=2
    fi
    index=$((index + 1))
    # 不使用 -C - 续传：本机代理环境下续传请求会挂起不返回（已实测）
    rm -f "$tmp"
    if curl -sS -L --fail --retry "$retries" --retry-delay 2 \
         --connect-timeout 15 --max-time "$max_time" -o "$tmp" "$source/$file"; then
      first_column="$(head -1 "$tmp" | cut -d',' -f1)"
      if [ "$first_column" = "$expected" ]; then
        echo "       来源 ${host}，$(wc -c <"$tmp" | tr -d ' ') 字节"
        got=1
        break
      fi
      echo "       来源 ${host} 表头异常（首列 ${first_column}），换下一个源"
    else
      echo "       来源 ${host} 不可用，换下一个源"
    fi
  done

  if [ "$got" -ne 1 ]; then
    echo "[失败] $file 所有下载源均不可用" >&2
    rm -f "$tmp"
    failed=1
    continue
  fi

  mv "$tmp" "$target"
  echo "       完成，$(( $(wc -l <"$target") - 1 )) 行"
done

echo "------------------------------------------------------------"

if [ "$failed" -ne 0 ]; then
  cat >&2 <<'EOF'
有文件下载失败。手动下载步骤：
  1. 打开 https://www.kaggle.com/datasets/rivalytics/saas-subscription-and-churn-analytics-dataset
  2. 登录后点击 Download，解压得到五个 ravenstack_*.csv
  3. 把文件放到 data/raw/ravenstack/，文件名保持一致
  4. 重新执行 python -m src.data_audit 即可，下载脚本会跳过已存在的文件
EOF
  exit 1
fi

echo "全部文件就绪。下一步：python -m src.data_audit"
