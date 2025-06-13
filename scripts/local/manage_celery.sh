#!/bin/bash

# --- Error Handling ---
set -euo pipefail

# --- Color Definitions ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Configuration ---
LOGS_DIR="./logs"
CELERY_LOG="$LOGS_DIR/celery.log"
CELERY_PID="$LOGS_DIR/celery.pid"
CELERY_BEAT_LOG="$LOGS_DIR/celery-beat.log"
CELERY_BEAT_PID="$LOGS_DIR/celery-beat.pid"
FLOWER_LOG="$LOGS_DIR/flower.log"

# --- Environment Setup ---
setup_environment() {
    # Check and activate virtual environment
    if [[ ! -f ".venv/bin/activate" ]]; then
        echo -e "${RED}[ERROR]${NC} Virtual environment not found. Please run: uv venv .venv" >&2
        exit 1
    fi
    
    source .venv/bin/activate
    
    # Development environment configuration
    export PYTHONWARNINGS="ignore:Unverified HTTPS request"
    export PYTHONIOENCODING=utf-8
    export PYTHONNOUSERSITE=1
    
    # Ensure logs directory exists
    mkdir -p "$LOGS_DIR"
}

# --- Worker Configuration ---
get_worker_config() {
    # Get CPU cores, default to 2 workers minimum
    local cpu_cores
    if command -v sysctl &> /dev/null; then
        cpu_cores=$(sysctl -n hw.physicalcpu 2>/dev/null || echo "2")
    else
        cpu_cores=$(nproc 2>/dev/null || echo "2")
    fi
    
    WORKER_COUNT=$((cpu_cores > 2 ? cpu_cores : 2))
    echo -e "${GREEN}[INFO]${NC} Using $WORKER_COUNT worker processes (CPU cores: $cpu_cores)"
}

# --- Help Function ---
show_help() {
    cat << EOF
Celery Management Script - Usage:

Main Commands:
  ./manage_celery.sh start         Start all Celery services (worker + beat)
  ./manage_celery.sh stop          Stop all Celery services (worker + beat)
  ./manage_celery.sh restart       Restart all Celery services
  ./manage_celery.sh status        Check status of all services

Advanced Commands:
  ./manage_celery.sh start-worker  Start only Celery worker
  ./manage_celery.sh start-beat    Start only Celery Beat
  ./manage_celery.sh stop-worker   Stop only Celery worker
  ./manage_celery.sh stop-beat     Stop only Celery beat

Monitoring:
  ./manage_celery.sh logs          View recent worker logs
  ./manage_celery.sh active        View active tasks
  ./manage_celery.sh stats         View worker statistics
  ./manage_celery.sh flower        Start Flower monitoring UI

Utilities:
  ./manage_celery.sh purge         Clear all queued tasks (with confirmation)
  ./manage_celery.sh init-tasks    Initialize scheduled tasks
  ./manage_celery.sh help          Show this help message

EOF
}

# --- Worker Functions ---
start_worker_fg() {
    get_worker_config
    echo -e "${GREEN}[INFO]${NC} Starting Celery worker in foreground..."
    exec celery -A skyeye worker \
        --concurrency="$WORKER_COUNT" \
        --loglevel=INFO \
        --without-gossip \
        --without-heartbeat \
        --without-mingle \
        --max-tasks-per-child=20 \
        --task-events
}

start_worker_bg() {
    # First stop any existing workers
    if pgrep -f "celery.*skyeye.*worker" > /dev/null; then
        echo -e "${YELLOW}[WARNING]${NC} Existing worker detected, stopping first..."
        stop_worker
        sleep 2
    fi
    
    get_worker_config
    echo -e "${GREEN}[INFO]${NC} Starting Celery worker in background..."
    echo -e "${GREEN}[INFO]${NC} Log file: $CELERY_LOG"
    
    # Start worker in background
    celery -A skyeye worker \
        --concurrency="$WORKER_COUNT" \
        --loglevel=INFO \
        --without-gossip \
        --without-heartbeat \
        --without-mingle \
        --max-tasks-per-child=20 \
        --task-events \
        --pidfile="$CELERY_PID" \
        --logfile="$CELERY_LOG" \
        --detach
    
    echo -e "${GREEN}[SUCCESS]${NC} Celery worker started in background"
    echo -e "${GREEN}[INFO]${NC} View logs: ./manage_celery.sh logs"
}

stop_worker() {
    echo -e "${YELLOW}[INFO]${NC} Stopping Celery worker..."
    
    # Try graceful shutdown first
    if celery -A skyeye control shutdown 2>/dev/null; then
        echo -e "${GREEN}[INFO]${NC} Graceful shutdown command sent"
        
        # Wait for graceful shutdown
        local count=0
        while [[ $count -lt 10 ]] && pgrep -f "celery.*skyeye.*worker" > /dev/null; do
            sleep 1
            ((count++))
        done
        
        if ! pgrep -f "celery.*skyeye.*worker" > /dev/null; then
            echo -e "${GREEN}[SUCCESS]${NC} Worker stopped gracefully"
            [[ -f "$CELERY_PID" ]] && rm -f "$CELERY_PID"
            return 0
        fi
    fi
    
    # Force stop if graceful shutdown failed
    echo -e "${YELLOW}[WARNING]${NC} Graceful shutdown timeout, forcing stop..."
    if [[ -f "$CELERY_PID" ]]; then
        local pid
        pid=$(cat "$CELERY_PID" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null; then
            echo -e "${GREEN}[INFO]${NC} Sent SIGTERM to PID $pid"
            sleep 2
        fi
        rm -f "$CELERY_PID"
    fi
    
    # Final cleanup
    pkill -TERM -f "celery.*skyeye.*worker" 2>/dev/null || true
    sleep 1
    pkill -KILL -f "celery.*skyeye.*worker" 2>/dev/null || true
    
    echo -e "${GREEN}[SUCCESS]${NC} Worker stop completed"
}

stop_beat() {
    echo -e "${YELLOW}[INFO]${NC} Stopping Celery beat..."
    
    # Stop beat process
    if [[ -f "$CELERY_BEAT_PID" ]]; then
        local pid
        pid=$(cat "$CELERY_BEAT_PID" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null; then
            echo -e "${GREEN}[INFO]${NC} Sent SIGTERM to beat PID $pid"
            sleep 2
        fi
        rm -f "$CELERY_BEAT_PID"
    fi
    
    # Force stop beat processes
    pkill -TERM -f "celery.*skyeye.*beat" 2>/dev/null || true
    sleep 1
    pkill -KILL -f "celery.*skyeye.*beat" 2>/dev/null || true
    
    echo -e "${GREEN}[SUCCESS]${NC} Beat stop completed"
}

start_all() {
    echo -e "${GREEN}[INFO]${NC} Starting all Celery services..."
    
    # Start worker first
    start_worker_bg
    
    # Wait a moment for worker to initialize
    sleep 2
    
    # Start beat
    echo -e "${GREEN}[INFO]${NC} Starting Celery Beat..."
    start_beat_bg
    
    echo -e "${GREEN}[SUCCESS]${NC} All Celery services started"
    echo -e "${GREEN}[INFO]${NC} Use './manage_celery.sh status' to check status"
    echo -e "${GREEN}[INFO]${NC} Use './manage_celery.sh logs' to view logs"
}

stop_all() {
    echo -e "${YELLOW}[INFO]${NC} Stopping all Celery services..."
    stop_worker
    stop_beat
    echo -e "${GREEN}[SUCCESS]${NC} All Celery services stopped"
}

restart_all() {
    echo -e "${GREEN}[INFO]${NC} Restarting all Celery services..."
    stop_all
    sleep 3
    start_all
    echo -e "${GREEN}[SUCCESS]${NC} All Celery services restarted"
}

# --- Beat Functions ---
start_beat_fg() {
    echo -e "${GREEN}[INFO]${NC} Starting Celery Beat in foreground..."
    exec celery -A skyeye beat \
        --loglevel=INFO \
        --scheduler=django_celery_beat.schedulers:DatabaseScheduler
}

start_beat_bg() {
    echo -e "${GREEN}[INFO]${NC} Starting Celery Beat in background..."
    echo -e "${GREEN}[INFO]${NC} Log file: $CELERY_BEAT_LOG"
    
    celery -A skyeye beat \
        --loglevel=INFO \
        --scheduler=django_celery_beat.schedulers:DatabaseScheduler \
        --pidfile="$CELERY_BEAT_PID" \
        --logfile="$CELERY_BEAT_LOG" \
        --detach
    
    echo -e "${GREEN}[SUCCESS]${NC} Celery Beat started in background"
}

# --- Monitoring Functions ---
check_status() {
    local worker_running=false
    local beat_running=false
    
    if pgrep -f "celery.*skyeye.*worker" > /dev/null; then
        echo -e "${GREEN}[STATUS]${NC} Celery worker: RUNNING"
        worker_running=true
    else
        echo -e "${RED}[STATUS]${NC} Celery worker: STOPPED"
    fi
    
    if pgrep -f "celery.*skyeye.*beat" > /dev/null; then
        echo -e "${GREEN}[STATUS]${NC} Celery beat: RUNNING"
        beat_running=true
    else
        echo -e "${RED}[STATUS]${NC} Celery beat: STOPPED"
    fi
    
    echo ""
    echo -e "${GREEN}[INFO]${NC} Detailed worker status:"
    celery -A skyeye status 2>/dev/null || echo "No workers available"
    
    return $($worker_running || $beat_running)
}

view_logs() {
    if [[ -f "$CELERY_LOG" ]]; then
        echo -e "${GREEN}[INFO]${NC} Recent worker logs:"
        tail -n 50 "$CELERY_LOG"
    else
        echo -e "${YELLOW}[WARNING]${NC} Worker log file not found: $CELERY_LOG"
    fi
}

# --- Development Mode ---
start_dev_mode() {
    get_worker_config
    echo -e "${GREEN}[INFO]${NC} Starting development mode (Worker + Beat in foreground)"
    echo -e "${GREEN}[INFO]${NC} Press Ctrl+C to stop all services"
    
    # Start worker in background
    celery -A skyeye worker \
        --concurrency="$WORKER_COUNT" \
        --loglevel=INFO \
        --without-gossip \
        --without-heartbeat \
        --without-mingle \
        --max-tasks-per-child=20 \
        --task-events &
    local worker_pid=$!
    
    # Give worker time to start
    sleep 2
    
    # Start beat in background
    celery -A skyeye beat \
        --loglevel=INFO \
        --scheduler=django_celery_beat.schedulers:DatabaseScheduler &
    local beat_pid=$!
    
    echo -e "${GREEN}[INFO]${NC} Worker PID: $worker_pid, Beat PID: $beat_pid"
    
    # Handle shutdown
    trap 'echo -e "\n${YELLOW}[INFO]${NC} Stopping services..."; kill $worker_pid $beat_pid 2>/dev/null; exit' INT TERM
    wait
}

# --- Utility Functions ---
purge_tasks() {
    echo -e "${RED}[WARNING]${NC} This will clear ALL queued tasks!"
    read -p "Are you sure you want to continue? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        celery -A skyeye purge -f
        echo -e "${GREEN}[SUCCESS]${NC} All queues cleared"
    else
        echo -e "${YELLOW}[INFO]${NC} Operation cancelled"
    fi
}

init_tasks() {
    echo -e "${GREEN}[INFO]${NC} Initializing scheduled tasks..."
    python manage.py initialize_beat_tasks
    echo -e "${GREEN}[SUCCESS]${NC} Scheduled tasks initialized"
}

# --- Main Script ---
main() {
    # Setup environment
    setup_environment
    
    # Check arguments
    if [[ $# -eq 0 ]]; then
        show_help
        exit 1
    fi
    
    # Execute command
    case "$1" in
        start)
            start_all
            ;;
        stop)
            stop_all
            ;;
        restart)
            restart_all
            ;;
        start-worker)
            start_worker_bg
            ;;
        start-beat)
            start_beat_bg
            ;;
        stop-worker)
            stop_worker
            ;;
        stop-beat)
            stop_beat
            ;;
        # Legacy commands for backward compatibility
        start-fg)
            start_worker_fg
            ;;
        status)
            check_status
            ;;
        beat-fg)
            start_beat_fg
            ;;
        beat)
            start_beat_bg
            ;;
        active)
            echo -e "${GREEN}[INFO]${NC} Active tasks:"
            celery -A skyeye inspect active
            ;;
        scheduled)
            echo -e "${GREEN}[INFO]${NC} Scheduled tasks:"
            celery -A skyeye inspect scheduled
            ;;
        reserved)
            echo -e "${GREEN}[INFO]${NC} Reserved tasks:"
            celery -A skyeye inspect reserved
            ;;
        stats)
            echo -e "${GREEN}[INFO]${NC} Worker statistics:"
            celery -A skyeye inspect stats
            ;;
        logs)
            view_logs
            ;;
        purge)
            purge_tasks
            ;;
        init-tasks)
            init_tasks
            ;;
        flower)
            echo -e "${GREEN}[INFO]${NC} Starting Flower monitoring UI..."
            celery -A skyeye flower \
                --address=0.0.0.0 \
                --port=5555 \
                --pidfile="$LOGS_DIR/flower.pid" \
                --logfile="$FLOWER_LOG" \
                --detach
            echo -e "${GREEN}[SUCCESS]${NC} Flower started at http://localhost:5555"
            ;;
        # Legacy commands for backward compatibility
        flower-bg)
            echo -e "${GREEN}[INFO]${NC} Starting Flower monitoring UI..."
            celery -A skyeye flower \
                --address=0.0.0.0 \
                --port=5555 \
                --pidfile="$LOGS_DIR/flower.pid" \
                --logfile="$FLOWER_LOG" \
                --detach
            echo -e "${GREEN}[SUCCESS]${NC} Flower started at http://localhost:5555"
            ;;
        dev)
            start_dev_mode
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"