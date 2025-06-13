#!/bin/bash

# 激活虚拟环境
#source .venv/bin/activate

# 设置Python DNS解析配置
export PYTHONWARNINGS="ignore:Unverified HTTPS request"
# 禁用c-ares
export PYTHONIOENCODING=utf-8
export PYTHONHASHSEED=random
export PYTHONNOUSERSITE=1
# 显式禁用aiodns的c-ares解析器
export PYTHONHOSTSTATICOVERRIDE=1

# 获取CPU核心数
CPU_CORES=$(sysctl -n hw.physicalcpu)
# 设置worker数量为CPU核心数
WORKER_COUNT=$((CPU_CORES))
# 确保至少有2个worker
if [ $WORKER_COUNT -lt 2 ]; then
    WORKER_COUNT=2
fi

# 日志和PID文件路径
LOGS_DIR="./logs"
CELERY_LOG="$LOGS_DIR/celery.log"
CELERY_PID="$LOGS_DIR/celery.pid"

# 确保日志目录存在
mkdir -p $LOGS_DIR

# 显示帮助信息
show_help() {
    echo "Celery管理脚本 - 使用说明:"
    echo "  ./manage_celery.sh start       在后台启动Celery worker"
    echo "  ./manage_celery.sh start-fg    在前台启动Celery worker"
    echo "  ./manage_celery.sh stop        停止Celery worker"
    echo "  ./manage_celery.sh restart     重启Celery worker"
    echo "  ./manage_celery.sh status      查看worker状态"
    echo "  ./manage_celery.sh active      查看正在执行的任务"
    echo "  ./manage_celery.sh scheduled   查看计划中的任务"
    echo "  ./manage_celery.sh reserved    查看已被预留但未执行的任务"
    echo "  ./manage_celery.sh flower      启动Flower监控界面"
    echo "  ./manage_celery.sh flower-bg   在后台启动Flower监控界面"
    echo "  ./manage_celery.sh purge       清空所有队列中的任务"
    echo "  ./manage_celery.sh stats       查看统计信息"
    echo "  ./manage_celery.sh logs        查看最近的日志"
    echo "  ./manage_celery.sh start-beat-db  在前台启动 Celery Beat (使用 DatabaseScheduler)"
    echo "  ./manage_celery.sh help        显示此帮助信息"
}

# 前台启动worker
start_worker_fg() {
    echo "系统CPU核心数: $CPU_CORES, 使用 $WORKER_COUNT 个worker进程"
    celery -A skyeye worker \
      -c $WORKER_COUNT \
      -l INFO \
      --without-gossip \
      --without-heartbeat \
      --without-mingle \
      --max-tasks-per-child=20 \
      --task-events
}

# 后台启动worker
start_worker_bg() {
    echo "系统CPU核心数: $CPU_CORES, 使用 $WORKER_COUNT 个worker进程"
    echo "在后台启动Celery worker，日志输出到 $CELERY_LOG"
    
    # 使用nohup在后台启动celery
    nohup celery -A skyeye worker \
      -c $WORKER_COUNT \
      -l INFO \
      --without-gossip \
      --without-heartbeat \
      --without-mingle \
      --max-tasks-per-child=20 \
      --task-events \
      > "$CELERY_LOG" 2>&1 &
    
    # 保存PID
    echo $! > "$CELERY_PID"
    
    echo "Celery worker已在后台启动，PID: $!"
    echo "查看日志: ./manage_celery.sh logs"
}

# 停止worker
stop_worker() {
    echo "停止所有Celery worker进程..."

    echo "尝试通过Celery control命令优雅关闭所有worker..."
    # 向所有skyeye应用的worker广播关闭命令
    celery -A skyeye control shutdown || echo "Celery control shutdown 命令执行可能遇到问题（例如没有运行中的worker），继续执行后续停止步骤。"

    echo "等待Celery worker优雅退出 (最长10秒)..."
    for i in {1..10}; do
        if ! pgrep -f "celery -A skyeye worker" > /dev/null; then
            echo "Celery worker已通过control命令退出。"
            break
        fi
        sleep 1
    done

    if pgrep -f "celery -A skyeye worker" > /dev/null; then
        echo "Celery worker仍在运行或PID文件存在，尝试通过PID文件和pkill停止..."
        if [ -f "$CELERY_PID" ]; then
            PID=$(cat "$CELERY_PID")
            if [ -n "$PID" ]; then
                if ps -p $PID > /dev/null; then # 检查PID是否存在且在运行
                    echo "通过PID文件发送SIGTERM信号给进程: $PID"
                    kill -15 $PID 2>/dev/null
                    # 等待进程结束
                    for i in {1..5}; do # 等待5秒
                        if ! ps -p $PID > /dev/null; then
                            break
                        fi
                        sleep 1
                    done
                    # 如果进程仍在运行，强制终止
                    if ps -p $PID > /dev/null; then
                        echo "进程 $PID 未响应SIGTERM，发送SIGKILL强制终止"
                        kill -9 $PID 2>/dev/null
                    fi
                else
                    echo "PID文件中的进程 $PID 未运行。"
                fi
                # 无论进程是否运行，都删除PID文件，因为它可能已失效
                rm -f "$CELERY_PID"
            else
                echo "PID文件存在但为空，删除之。"
                rm -f "$CELERY_PID"
            fi
        else
            echo "Celery PID文件 ($CELERY_PID) 未找到。"
        fi

        # 如果进程仍然存在 (可能是因为PID文件无效或没有PID文件)，使用pkill
        if pgrep -f "celery -A skyeye worker" > /dev/null; then
            echo "使用 pkill -SIGTERM -f 'celery -A skyeye worker' 尝试停止worker..."
            pkill -SIGTERM -f "celery -A skyeye worker"
            sleep 3 # 等待pkill生效
            if pgrep -f "celery -A skyeye worker" > /dev/null; then
                echo "仍有celery进程在运行，使用 pkill -SIGKILL -f 'celery -A skyeye worker' 强制终止..."
                pkill -SIGKILL -f "celery -A skyeye worker"
            fi
        fi
    else
        # 如果control命令后worker已退出，且之前没有PID文件，也尝试清理一下PID文件以防万一
        if [ -f "$CELERY_PID" ]; then
            rm -f "$CELERY_PID"
            echo "Celery worker已退出，并清理了PID文件。"
        fi
    fi

    echo "Celery worker停止操作完成。"
    # 最终状态检查
    echo "正在检查最终Celery状态..."
    celery -A skyeye status
}

# 查看日志
view_logs() {
    if [ -f "$CELERY_LOG" ]; then
        echo "显示最近的日志 ($CELERY_LOG):"
        tail -n 50 "$CELERY_LOG"
    else
        echo "日志文件不存在: $CELERY_LOG"
    fi
}

# 检查worker状态
check_worker_status() {
    if pgrep -f "celery worker" > /dev/null; then
        echo "Celery worker正在运行"
        return 0
    else
        echo "Celery worker未运行"
        return 1
    fi
}

# 检查命令行参数
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

# 根据参数执行不同操作
case "$1" in
    start)
        start_worker_bg
        ;;
    start-fg)
        echo "在前台启动Celery worker..."
        start_worker_fg
        ;;
    stop)
        stop_worker
        ;;
    restart)
        echo "重启Celery worker..."
        stop_worker
        sleep 2
        start_worker_bg
        ;;
    status)
        check_worker_status
        echo "查看详细worker状态..."
        celery -A skyeye status
        ;;
    active)
        echo "查看正在执行的任务..."
        celery -A skyeye inspect active
        ;;
    scheduled)
        echo "查看计划中的任务..."
        celery -A skyeye inspect scheduled
        ;;
    reserved)
        echo "查看已被预留但未执行的任务..."
        celery -A skyeye inspect reserved
        ;;
    flower)
        echo "启动Flower监控界面..."
        celery -A skyeye flower
        ;;
    flower-bg)
        echo "在后台启动Flower监控界面..."
        celery -A skyeye flower --address=0.0.0.0 --port=5555 > "$LOGS_DIR/flower.log" 2>&1 &
        echo "Flower已在后台启动，访问 http://localhost:5555"
        ;;
    start-beat-db)
        echo "在前台启动 Celery Beat (使用 DatabaseScheduler)..."
        celery -A skyeye beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    purge)
        echo "警告: 即将清空所有队列中的任务!"
        read -p "确定要继续吗? [y/N] " confirm
        if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
            celery -A skyeye purge -f
            echo "所有队列已清空"
        else
            echo "操作已取消"
        fi
        ;;
    stats)
        echo "查看统计信息..."
        celery -A skyeye inspect stats
        ;;
    logs)
        view_logs
        ;;
    help)
        show_help
        ;;
    *)
        echo "未知命令: $1"
        show_help
        exit 1
        ;;
esac