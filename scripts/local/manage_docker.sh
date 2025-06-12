#!/bin/bash

# Script to manage docker-compose-local.yaml services

COMPOSE_FILE="docker-compose-local.yaml"
ACTION=$1
SERVICE_NAME=$2
# Capture all arguments from the third one onwards for the exec command
EXEC_ARGS=("${@:3}")

# Function to display usage
usage() {
    echo "Usage: $0 {up|down|down-v|logs|status|restart|exec}"
    echo "  up                 : Start services in detached mode."
    echo "                       Example: $0 up"
    echo "  down               : Stop and remove services."
    echo "                       Example: $0 down"
    echo "  down-v             : Stop and remove services and volumes."
    echo "                       Example: $0 down-v"
    echo "  logs [service]     : Follow logs for a specific service or all services."
    echo "                       Example: $0 logs"
    echo "                       Example: $0 logs db-master"
    echo "  status             : Show status of services (alias for ps)."
    echo "                       Example: $0 status"
    echo "  ps                 : Show status of services."
    echo "                       Example: $0 ps"
    echo "  restart [service]  : Restart a specific service or all services."
    echo "                       Example: $0 restart"
    echo "                       Example: $0 restart db-slave"
    echo "  exec <service> <cmd> : Execute a command in a running service."
    echo "                       Example: $0 exec db-master psql -U skyeye_user -d skyeye"
    echo "                       Example: $0 exec db-master bash"
    exit 1
}

# Check if no action is provided
if [ -z "$ACTION" ]; then
    usage
fi

case "$ACTION" in
  up)
    echo "Starting services in detached mode..."
    docker compose -f "$COMPOSE_FILE" up -d
    ;;
  down)
    echo "Stopping and removing services..."
    docker compose -f "$COMPOSE_FILE" down
    ;;
  down-v)
    echo "Stopping and removing services and associated volumes..."
    docker compose -f "$COMPOSE_FILE" down -v
    ;;
  logs)
    if [ -z "$SERVICE_NAME" ]; then
      echo "Following logs for all services..."
      docker compose -f "$COMPOSE_FILE" logs -f
    else
      echo "Following logs for service: $SERVICE_NAME..."
      docker compose -f "$COMPOSE_FILE" logs -f "$SERVICE_NAME"
    fi
    ;;
  status|ps) # Added 'status' as an alias for 'ps'
    echo "Status of services:"
    docker compose -f "$COMPOSE_FILE" ps
    ;;
  restart)
    if [ -z "$SERVICE_NAME" ]; then
      echo "Restarting all services..."
      docker compose -f "$COMPOSE_FILE" restart
    else
      echo "Restarting service: $SERVICE_NAME..."
      docker compose -f "$COMPOSE_FILE" restart "$SERVICE_NAME"
    fi
    ;;
  exec)
    if [ -z "$SERVICE_NAME" ] || [ ${#EXEC_ARGS[@]} -eq 0 ]; then
      echo "Error: Missing service name or command for exec."
      usage
    fi
    echo "Executing command in service '$SERVICE_NAME': ${EXEC_ARGS[*]}"
    docker compose -f "$COMPOSE_FILE" exec "$SERVICE_NAME" "${EXEC_ARGS[@]}"
    ;;
  *)
    echo "Error: Unknown action '$ACTION'"
    usage
    ;;
esac

exit 0 