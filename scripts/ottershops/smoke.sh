#!/usr/bin/env bash
# API smoke test for OtterShops: browse, guest checkout, decline, oversell, pickup, lookup.
# Usage: scripts/ottershops/smoke.sh [BASE_URL]   (default http://localhost:3000)
set -euo pipefail
BASE="${1:-http://localhost:3000}"
API="$BASE/api"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT
pass=0
ok() { pass=$((pass + 1)); echo "ok  $*"; }
fail() { echo "FAIL $*" >&2; exit 1; }
req() { # method path [body] -> prints body, sets $code
  local method=$1 path=$2 body=${3:-}
  local out
  out=$(curl -s -b "$JAR" -c "$JAR" -X "$method" -H 'Content-Type: application/json' \
    ${body:+--data "$body"} -w '\n%{http_code}' "$API$path")
  code=${out##*$'\n'}
  resp=${out%$'\n'*}
}
expect() { [[ "$code" == "$1" ]] || fail "$2: expected HTTP $1, got $code: $resp"; ok "$2 ($code)"; }

req GET /products?pageSize=500; expect 200 "catalog lists products"
total=$(jq -r .total <<<"$resp"); (( total >= 160 )) || fail "only $total products"; ok "catalog has $total products"
req GET "/products?department=women&size=M&color=black&sort=price-asc"; expect 200 "PLP filter + sort"
req GET /promotions/active; expect 200 "promotion endpoint"

# Pick an in-stock, promo-eligible SKU with plenty of stock.
req GET "/products?department=women&category=dresses&pageSize=50"
pid=$(jq -r '[.items[] | select(.stockState=="IN_STOCK" and (.collections | index("maternity") | not))][0].id' <<<"$resp")
req GET "/products/$pid"; expect 200 "PDP $pid"
sku=$(jq -r '[.skus[] | select(.stock >= 3)][0].sku' <<<"$resp")
stock=$(jq -r --arg s "$sku" '.skus[] | select(.sku==$s) | .stock' <<<"$resp")

new_bag() { req POST /bags; expect 201 "create bag"; bag=$(jq -r .id <<<"$resp"); }
new_bag
req POST "/bags/$bag/items" "{\"sku\":\"$sku\",\"quantity\":1}"; expect 200 "add to bag"
req POST "/bags/$bag/promo" '{"code":"NOPE123"}'; expect 400 "unknown promo rejected"
req POST "/bags/$bag/promo" '{"code":"BLACKFRIDAY"}'
if [[ "$(curl -s "$API/promotions/active" | jq -r .active)" == "true" ]]; then expect 200 "apply BLACKFRIDAY"; else expect 400 "promo off: code rejected"; fi

card() { echo "{\"number\":\"$1\",\"expMonth\":12,\"expYear\":2030,\"cvc\":\"123\",\"name\":\"Ava Test\"}"; }
ship='{"name":"Ava Test","line1":"1 Market St","city":"San Francisco","state":"CA","zip":"94105"}'
checkout() { echo "{\"bagId\":\"$bag\",\"email\":\"ava@example.com\",\"fulfillment\":\"SHIP\",\"shippingMethod\":\"STANDARD\",\"address\":$ship,\"card\":$(card "$1")}"; }

req POST /checkout "$(checkout 4000000000000002)"; expect 402 "declined card"
req GET "/products/$pid"
[[ "$(jq -r --arg s "$sku" '.skus[] | select(.sku==$s) | .stock' <<<"$resp")" == "$stock" ]] || fail "stock changed after decline"; ok "stock unchanged after decline"
req POST /checkout "$(checkout 4242424242424241)"; expect 400 "bad Luhn rejected"
req POST /checkout "$(checkout 4242424242424242)"; expect 201 "guest order placed"
number=$(jq -r .orderNumber <<<"$resp")
[[ "$number" =~ ^OS-1[0-9]{5}$ ]] || fail "order number $number"; ok "order number $number"
req GET /products/$pid
[[ "$(jq -r --arg s "$sku" '.skus[] | select(.sku==$s) | .stock' <<<"$resp")" == "$((stock - 1))" ]] || fail "stock not decremented"; ok "stock decremented"
req GET "/orders/lookup?number=$number&email=AVA@example.com"; expect 200 "order lookup"
req GET "/orders/lookup?number=$number&email=someone@else.com"; expect 404 "lookup with wrong email"
curl -sf "$API/orders/$number/invoice?email=ava@example.com" | grep -q "INV-" && ok "invoice renders"

# Oversell: bag more than stock, then drain stock so checkout must 409.
low=$(curl -s "$API/products?pageSize=500" | jq -r '.items[].id' | while read -r p; do
  curl -s "$API/products/$p" | jq -r '.skus[] | select(.stock == 1) | .sku'; done | head -1)
if [[ -n "$low" ]]; then
  new_bag; b1=$bag
  req POST "/bags/$b1/items" "{\"sku\":\"$low\",\"quantity\":2}"; expect 409 "cannot bag more than stock"
  req POST "/bags/$b1/items" "{\"sku\":\"$low\",\"quantity\":1}"; expect 200 "bag last unit"
  new_bag; b2=$bag
  req POST "/bags/$b2/items" "{\"sku\":\"$low\",\"quantity\":1}"; expect 200 "second shopper bags last unit"
  bag=$b2; req POST /checkout "$(checkout 4242424242424242)"; expect 201 "second shopper buys it"
  bag=$b1; req POST /checkout "$(checkout 4242424242424242)"; expect 409 "oversell returns 409"
fi

# Member pickup with guest bag merge.
new_bag
req POST "/bags/$bag/items" "{\"sku\":\"$sku\",\"quantity\":1}"; expect 200 "guest adds item"
req POST /auth/login "{\"email\":\"maya@ottershops.test\",\"password\":\"otters-2026\",\"bagId\":\"$bag\"}"; expect 200 "demo shopper signs in"
bag=$(jq -r .bagId <<<"$resp")
req GET "/bags/$bag"; expect 200 "merged bag readable"
(( $(jq -r .itemCount <<<"$resp") >= 1 )) || fail "guest item not merged"; ok "guest bag merged"
req GET "/stores?q=94103"; expect 200 "store search by ZIP"
store=$(jq -r '[.stores[] | select(.pickupEnabled)][0].id' <<<"$resp")
closed=$(curl -s "$API/stores" | jq -r '[.stores[] | select(.pickupEnabled | not)][0].id')
pickup() { echo "{\"bagId\":\"$bag\",\"email\":\"maya@ottershops.test\",\"fulfillment\":\"PICKUP\",\"storeId\":\"$1\",\"card\":$(card 4242424242424242)}"; }
req POST /checkout "$(pickup "$closed")"; expect 400 "pickup-disabled store rejected"
before=$(curl -s -b "$JAR" "$API/account" | jq -r .customer.rewardsPoints)
req POST /checkout "$(pickup "$store")"; expect 201 "member pickup order"
pnum=$(jq -r .orderNumber <<<"$resp"); total=$(jq -r .totalCents <<<"$resp")
req GET /account; expect 200 "account"
jq -e --arg n "$pnum" '.orders[] | select(.orderNumber==$n)' <<<"$resp" >/dev/null || fail "order missing from history"; ok "order in history"
after=$(jq -r .customer.rewardsPoints <<<"$resp")
(( after - before == total / 100 )) || fail "points $before -> $after for $total cents"; ok "rewards +$((after - before)) points"
req POST /auth/logout; expect 204 "sign out"
req GET /account; expect 401 "account requires sign-in"

echo "smoke passed: $pass checks against $BASE"
