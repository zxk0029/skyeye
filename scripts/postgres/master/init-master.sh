#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# Variables from docker-compose environment
PG_DBNAME="$POSTGRES_DB"
PG_USER="$POSTGRES_USER"
PG_PASSWORD="$POSTGRES_PASSWORD" # Master's password
REPL_USER="repl_user"
REPL_PASSWORD="$REPL_PASSWORD" # Get from environment
PG_CONF="/var/lib/postgresql/data/postgresql.conf"
PG_HBA="/var/lib/postgresql/data/pg_hba.conf"
PG_READY_CMD="pg_isready -U \"$PG_USER\" -d \"$PG_DBNAME\"" # Check via Unix socket by default

echo "Master Script: Waiting for PostgreSQL to start (via socket check)..."
until $PG_READY_CMD; do
  >&2 echo "Postgres is unavailable (socket check) - sleeping"
  sleep 1
done
echo "Master Script: PostgreSQL started (socket check passed)."

# 1. Modify postgresql.conf for replication
echo "Master Script: Configuring postgresql.conf..."
echo "listen_addresses = '*'" >> "$PG_CONF" # Listen on all interfaces
echo "wal_level = replica" >> "$PG_CONF"
echo "max_wal_senders = 10" >> "$PG_CONF"        # Adjust as needed
echo "max_replication_slots = 10" >> "$PG_CONF"  # Adjust as needed
echo "wal_keep_size = 512MB" >> "$PG_CONF" # PG13+ alternative to wal_keep_segments
echo "hot_standby = on" >> "$PG_CONF"            # Allow read queries on standby

# 2. Modify pg_hba.conf to allow replication connections from the slave
# NOTE: Adjust the IP range '172.16.0.0/12' or 'all' based on your docker network.
# Using 'all' is less secure but simpler for local dev.
echo "Master Script: Configuring pg_hba.conf..."
# Allow replication connection from any IP (adjust CIDR for security if needed)
# Ensure this line is not duplicated if script runs multiple times on existing data (though initdb.d scripts usually run once)
if ! grep -Fxq "host replication $REPL_USER all md5" "$PG_HBA"; then
    echo "host replication $REPL_USER all md5" >> "$PG_HBA"
fi
# Allow regular connection from any IP (useful for direct checks)
if ! grep -Fxq "host all $PG_USER all md5" "$PG_HBA"; then
    echo "host all $PG_USER all md5" >> "$PG_HBA"
fi


# 3. Create the replication user
echo "Master Script: Creating replication user '$REPL_USER'..."
psql -v ON_ERROR_STOP=1 --username "$PG_USER" --dbname "$PG_DBNAME" <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$REPL_USER') THEN
        CREATE ROLE $REPL_USER WITH REPLICATION LOGIN PASSWORD '$REPL_PASSWORD';
      ELSE
        RAISE NOTICE 'Role $REPL_USER already exists, skipping creation.';
      END IF;
    END
    \$\$;
EOSQL

# 4. Create replication slot (optional but recommended)
# Note: Creating slot requires restart/reload usually handled by script end or entrypoint
echo "Master Script: Attempting to create replication slot 'slave1_slot'..."
psql -v ON_ERROR_STOP=0 --username "$PG_USER" --dbname "$PG_DBNAME" -c \
    "SELECT pg_create_physical_replication_slot('slave1_slot');" \
    || echo "Master Script: Replication slot 'slave1_slot' might already exist or other error (ignoring)."


# 5. Reload PostgreSQL configuration
echo "Master Script: Reloading PostgreSQL configuration..."
psql -v ON_ERROR_STOP=1 --username "$PG_USER" --dbname "$PG_DBNAME" -c "SELECT pg_reload_conf();"

echo "Master Script: Configuration complete."

# Keep container running (Postgres process is the main one)
# The original entrypoint likely handles keeping the main process alive.
# If overriding command completely, you might need 'tail -f /dev/null' or similar,
# but here we assume we modify settings and let the main process continue. 