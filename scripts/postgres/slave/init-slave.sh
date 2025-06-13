#!/bin/bash
set -e

# Variables
MASTER_HOST="db-master" # Service name from docker-compose
MASTER_PORT="5432"
REPL_USER="repl_user"
REPL_PASSWORD="$REPL_PASSWORD" # Get from environment
SLAVE_DATA_DIR="/var/lib/postgresql/data"
MASTER_READY_CMD="pg_isready -h $MASTER_HOST -p $MASTER_PORT"
REPL_SLOT_NAME="slave1_slot"

echo "Slave Script: Waiting for master ($MASTER_HOST:$MASTER_PORT) to become available..."
until $MASTER_READY_CMD; do
  >&2 echo "Master is unavailable - sleeping"
  sleep 1
done
echo "Slave Script: Master is available."

# Safety check: Ensure data directory is empty or doesn't exist before pg_basebackup
if [ -d "$SLAVE_DATA_DIR" ] && [ "$(ls -A $SLAVE_DATA_DIR)" ]; then
    echo "Slave Script: Data directory $SLAVE_DATA_DIR is not empty. Cleaning up..."
    # Stop postgres if it autostarted (it shouldn't if data dir is empty, but belt-and-suspenders)
    pg_ctl -D "$SLAVE_DATA_DIR" -m fast stop || echo "Slave Script: Postgres not running, continuing cleanup."
    rm -rf "$SLAVE_DATA_DIR"/*
else
    echo "Slave Script: Data directory $SLAVE_DATA_DIR is empty or non-existent. Proceeding."
fi

# Ensure the directory exists with correct permissions for pg_basebackup
mkdir -p "$SLAVE_DATA_DIR"
chown postgres:postgres "$SLAVE_DATA_DIR"
chmod 0700 "$SLAVE_DATA_DIR"

# 1. Run pg_basebackup
echo "Slave Script: Running pg_basebackup..."
# Need PGPASSWORD for pg_basebackup if using password auth
export PGPASSWORD="$REPL_PASSWORD"
pg_basebackup \
    --host=$MASTER_HOST \
    --port=$MASTER_PORT \
    --username=$REPL_USER \
    --pgdata="$SLAVE_DATA_DIR" \
    --wal-method=stream \
    --verbose \
    --progress \
    --slot=$REPL_SLOT_NAME

unset PGPASSWORD
echo "Slave Script: pg_basebackup completed."


# 2. Create standby signal file and configure recovery settings (for PG12+)
# For PG12+, create standby.signal and add primary_conninfo to postgresql.auto.conf or postgresql.conf
# For older versions, create recovery.conf
echo "Slave Script: Configuring standby settings..."
touch "$SLAVE_DATA_DIR/standby.signal"

# Append recovery settings to the main config file copied by pg_basebackup
cat >> "$SLAVE_DATA_DIR/postgresql.conf" <<-EOF

# Recovery settings added by init-slave.sh
primary_conninfo = 'host=$MASTER_HOST port=$MASTER_PORT user=$REPL_USER password=$REPL_PASSWORD application_name=skyeye_slave1 sslmode=prefer sslcompression=0 gssencmode=disable target_session_attrs=any'
primary_slot_name = '$REPL_SLOT_NAME'
hot_standby = on
EOF

# Ensure correct permissions again after backup and modifications
chown -R postgres:postgres "$SLAVE_DATA_DIR"
chmod 0700 "$SLAVE_DATA_DIR"

echo "Slave Script: Standby configuration complete. Slave will start replicating on next container start/postgres start."

# The container's main postgres process will start using this configuration
# No need to manually start postgres here if using the default entrypoint 