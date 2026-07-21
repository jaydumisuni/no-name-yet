#!/usr/bin/env bash
set -euo pipefail

# Configure three isolated Hermes Agent profiles for Sergeant learning.
# The default Hermes profile must already have a working model provider. This
# script clones only the provider configuration; each role gets separate memory,
# sessions, skills, API server key, port, and role instructions.

START=false
if [[ "${1:-}" == "--start" ]]; then
  START=true
elif [[ -n "${1:-}" ]]; then
  echo "usage: $0 [--start]" >&2
  exit 2
fi

command -v hermes >/dev/null 2>&1 || {
  echo "hermes CLI is required" >&2
  exit 1
}

HERMES_ROOT="${HERMES_HOME:-${HOME}/.hermes}"
OUTPUT_ENV="${HERMES_ROOT}/sergeant-learning.env"
mkdir -p "${HERMES_ROOT}/profiles"

require_secret() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "missing required local environment variable: ${name}" >&2
    exit 1
  fi
}

require_secret SERGEANT_HERMES_TEACHER_KEY
require_secret SERGEANT_HERMES_PROSECUTOR_KEY
require_secret SERGEANT_HERMES_DEFENDER_KEY

profile_exists() {
  hermes profile list | sed 's/^[*[:space:]]*//' | grep -Fxq "$1"
}

write_env_value() {
  local file="$1" key="$2" value="$3"
  mkdir -p "$(dirname "${file}")"
  touch "${file}"
  python - "${file}" "${key}" "${value}" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
lines = [line for line in lines if not line.startswith(f"{key}=")]
lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

configure_profile() {
  local role="$1" profile="$2" port="$3" key_var="$4"
  local profile_home="${HERMES_ROOT}/profiles/${profile}"
  local api_key="${!key_var}"

  if ! profile_exists "${profile}"; then
    hermes profile create "${profile}" --clone --no-alias
  fi

  mkdir -p "${profile_home}"
  cat > "${profile_home}/SOUL.md" <<EOF
# Sergeant ${role^} Officer

You are an isolated ${role} in Sergeant's controlled learning council.

- Work only on the bounded case packet supplied through the API.
- Return exactly the requested JSON contract.
- Do not modify repositories, run merge operations, or claim promotion authority.
- Distinguish root mechanism from identifiers copied from a fixing patch.
- Executable evidence outranks majority agreement.
- Treat missing provenance, negative controls, or unrelated-language transfer as a blocker.
EOF

  write_env_value "${profile_home}/.env" API_SERVER_ENABLED true
  write_env_value "${profile_home}/.env" API_SERVER_HOST 127.0.0.1
  write_env_value "${profile_home}/.env" API_SERVER_PORT "${port}"
  write_env_value "${profile_home}/.env" API_SERVER_KEY "${api_key}"
  write_env_value "${profile_home}/.env" API_SERVER_MODEL_NAME "${profile}"

  local upper
  upper="$(printf '%s' "${role}" | tr '[:lower:]' '[:upper:]')"
  write_env_value "${OUTPUT_ENV}" "SERGEANT_HERMES_${upper}_URL" "http://127.0.0.1:${port}"
  write_env_value "${OUTPUT_ENV}" "SERGEANT_HERMES_${upper}_KEY" "${api_key}"
  write_env_value "${OUTPUT_ENV}" "SERGEANT_HERMES_${upper}_MODEL" "${profile}"

  if [[ "${START}" == true ]]; then
    hermes -p "${profile}" gateway start
  fi
}

configure_profile teacher srg-teacher 8643 SERGEANT_HERMES_TEACHER_KEY
configure_profile prosecutor srg-prosecutor 8644 SERGEANT_HERMES_PROSECUTOR_KEY
configure_profile defender srg-defender 8645 SERGEANT_HERMES_DEFENDER_KEY

write_env_value "${OUTPUT_ENV}" SERGEANT_LEARNING_BACKEND hermes
chmod 600 "${OUTPUT_ENV}"

cat <<EOF
Hermes learning profiles configured.

Local Sergeant environment:
  source "${OUTPUT_ENV}"

Health checks:
  curl -H "Authorization: Bearer \$SERGEANT_HERMES_TEACHER_KEY" http://127.0.0.1:8643/health
  curl -H "Authorization: Bearer \$SERGEANT_HERMES_PROSECUTOR_KEY" http://127.0.0.1:8644/health
  curl -H "Authorization: Bearer \$SERGEANT_HERMES_DEFENDER_KEY" http://127.0.0.1:8645/health
EOF

if [[ "${START}" != true ]]; then
  cat <<'EOF'

Start the isolated gateways when ready:
  hermes -p srg-teacher gateway start
  hermes -p srg-prosecutor gateway start
  hermes -p srg-defender gateway start
EOF
fi
