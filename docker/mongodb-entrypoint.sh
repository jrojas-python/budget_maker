#!/bin/sh
set -eu

ROOT_USER="${MONGO_INITDB_ROOT_USERNAME:?MONGO_INITDB_ROOT_USERNAME es requerido}"
ROOT_PASSWORD="${MONGO_INITDB_ROOT_PASSWORD:?MONGO_INITDB_ROOT_PASSWORD es requerido}"

auth_ping() {
  mongosh --quiet     --username "$ROOT_USER"     --password "$ROOT_PASSWORD"     --authenticationDatabase admin     --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1
}

local_ping() {
  mongosh --quiet --eval "db.adminCommand({ ping: 1 }).ok" >/dev/null 2>&1
}

cleanup() {
  kill "$mongodb_pid" >/dev/null 2>&1 || true
  wait "$mongodb_pid" >/dev/null 2>&1 || true
}

trap cleanup INT TERM

docker-entrypoint.sh mongod --auth --bind_ip_all &
mongodb_pid=$!

until auth_ping || local_ping; do
  sleep 2
done

if ! auth_ping; then
  mongosh --quiet --eval "
    const adminDb = db.getSiblingDB('admin');
    try {
      adminDb.createUser({
        user: '$ROOT_USER',
        pwd: '$ROOT_PASSWORD',
        roles: [{ role: 'root', db: 'admin' }],
      });
    } catch (error) {
      const message = String(error.message || '');
      if (!message.includes('already exists') && !message.includes('duplicate')) {
        throw error;
      }
    }
  "
fi

auth_ping
wait "$mongodb_pid"
