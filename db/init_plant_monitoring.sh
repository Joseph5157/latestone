#!/bin/bash
# Create the monitoring schema using the *configured* schema name.
#
# The DDL used to hard-code `plant_monitoring` while config/settings.py and
# .env.example advertised PLANT_MONITORING_SCHEMA as configurable. Setting it to
# anything else produced an application and seed pointed at a schema a fresh
# Docker database had never created. Substituting here keeps one source of truth.
#
# Runs only on first initialisation of an empty data directory, which is
# standard postgres image behaviour.
set -euo pipefail

SCHEMA="${PLANT_MONITORING_SCHEMA:-plant_monitoring}"
TEMPLATE="/docker-entrypoint-initdb.d/init_plant_monitoring.sql.template"

# Same rule as _validate_identifier() in config/settings.py. The value is
# substituted into DDL, so it is validated rather than trusted.
if ! printf '%s' "$SCHEMA" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*$'; then
  echo "FATAL: PLANT_MONITORING_SCHEMA is not a valid identifier: '$SCHEMA'" >&2
  exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
  echo "FATAL: schema template not found at $TEMPLATE" >&2
  exit 1
fi

echo "Initialising monitoring schema: $SCHEMA"
sed "s/@SCHEMA@/${SCHEMA}/g" "$TEMPLATE" \
  | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
