#!/usr/bin/env bash
# 本地 MySQL 实例启停脚本（用户级安装，无需 sudo）
# 用法: bash scripts/mysql_ctl.sh {start|stop|status|shell}
set -uo pipefail

MYSQL_HOME="$HOME/mysql"
BASE="$MYSQL_HOME/mysql-8.4.7-macos15-arm64"
CNF="$MYSQL_HOME/my.cnf"
SOCK="$MYSQL_HOME/mysql.sock"
PIDFILE="$MYSQL_HOME/mysqld.pid"
ROOT_PW_FILE="$MYSQL_HOME/.root_password"

# root 密码由安装时随机生成，存于 600 权限文件，不在脚本里硬编码
root_pw() {
  cat "$ROOT_PW_FILE" 2>/dev/null || echo ""
}

is_running() {
  [ -S "$SOCK" ] || return 1
  "$BASE/bin/mysqladmin" --defaults-file="$CNF" -uroot -p"$(root_pw)" \
    --connect-timeout=3 ping >/dev/null 2>&1
}

case "${1:-status}" in
  start)
    if is_running; then
      echo "MySQL 已在运行。"
      exit 0
    fi
    echo "正在启动 MySQL ..."
    nohup "$BASE/bin/mysqld_safe" --defaults-file="$CNF" >/dev/null 2>&1 &
    disown 2>/dev/null || true
    for _ in $(seq 1 30); do
      sleep 1
      if is_running; then
        echo "启动成功：127.0.0.1:3306，socket $SOCK"
        exit 0
      fi
    done
    echo "启动超时，请查看 $MYSQL_HOME/error.log" >&2
    exit 1
    ;;
  stop)
    if ! is_running; then
      echo "MySQL 未在运行。"
      exit 0
    fi
    "$BASE/bin/mysqladmin" --defaults-file="$CNF" -uroot -p"$(root_pw)" shutdown 2>/dev/null \
      || kill "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
    echo "已停止。"
    ;;
  status)
    if is_running; then
      echo "运行中："
      "$BASE/bin/mysql" --defaults-file="$CNF" -uroot -p"$(root_pw)" \
        -e "SELECT VERSION() AS version, @@port AS port;" 2>/dev/null
    else
      echo "未运行。用 bash scripts/mysql_ctl.sh start 启动。"
      exit 1
    fi
    ;;
  shell)
    exec "$BASE/bin/mysql" --defaults-file="$CNF" -uroot -p"$(root_pw)" ai_saas_analytics
    ;;
  *)
    echo "用法: $0 {start|stop|status|shell}" >&2
    exit 2
    ;;
esac
