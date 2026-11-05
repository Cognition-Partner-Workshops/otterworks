#!/usr/bin/env bash
set -euo pipefail

wave=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$wave"
read -r -a compose <<< "${COMPOSE:-docker compose -f vm/compose.yaml}"

query() {
  "${compose[@]}" exec -T wave1-db sh -c \
    'PGPASSWORD="${STATEMENTS_DB_PASSWORD:-$POSTGRES_PASSWORD}" exec psql -X -h wave1-db -U statements_app -d bankwave -qAt -v ON_ERROR_STOP=1 -v VERBOSITY=verbose'
}

flags=$(query <<'SQL'
SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user;
SQL
)
if [[ "$flags" != 'f|f|f' ]]; then
  echo 'FAIL statements_app must be NOSUPERUSER NOCREATEROLE NOCREATEDB'
  exit 1
fi
echo 'PASS statements_app role flags are all false'

query >/dev/null <<'SQL'
SELECT count(*) FROM accounts;
SELECT count(*) FROM statement_lines;
SQL
echo 'PASS SELECT accounts and statement_lines'

deny() {
  local label=$1 sql=$2 result
  if result=$(printf 'BEGIN;\n%s;\nROLLBACK;\n' "$sql" | query 2>&1); then
    echo "FAIL $label was allowed"
    exit 1
  fi
  if [[ "$result" != *'42501:'* ]]; then
    echo "FAIL $label did not fail with insufficient_privilege"
    exit 1
  fi
  echo "PASS denied $label (42501)"
}
deny 'SELECT branches' 'SELECT count(*) FROM branches'
deny 'INSERT accounts' "INSERT INTO accounts VALUES ('boundary_probe','Probe','SAVINGS')"
deny 'UPDATE accounts' "UPDATE accounts SET holder = holder WHERE false"
deny 'DELETE accounts' 'DELETE FROM accounts WHERE false'
deny 'CREATE TABLE public' 'CREATE TABLE public.boundary_probe (i int)'

python3 - <<'PY'
from pathlib import Path
import re
import xml.etree.ElementTree as ET

context = Path('statements-web/vm/conf/context.xml')
resource = ET.parse(context).find("Resource[@name='jdbc/StatementsDB']")
assert resource is not None and resource.get('password') == '${STATEMENTS_DB_PASSWORD}', 'datasource password must reference the environment'
compose = Path('vm/compose.yaml').read_text()
values = re.findall(r'^\s*\w*PASSWORD\s*:\s*(.*?)\s*$', compose, re.M | re.I)
assert values and all(re.fullmatch(r'\$\{[A-Z0-9_]+(?::\?[^}]*)?\}', v) for v in values), 'compose passwords must reference the environment'
dockerfile = Path('statements-web/vm/Dockerfile').read_text()
assert not re.search(r'password\s*[=:]', dockerfile, re.I), 'Dockerfile must not assign passwords'
print('PASS static password references (context.xml, compose.yaml, Dockerfile)')
PY
echo 'PASS statements DB boundary'
