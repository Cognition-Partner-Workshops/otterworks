#!/usr/bin/env bash
# API smoke test for OtterShops: browse, guest checkout, decline, oversell, pickup, lookup,
# plus search, reviews, favorites, store stock, back-in-stock, save for later, gift cards,
# tracking, returns and the address book.
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

# Discovery, reviews and store stock.
req GET "/search/suggest?q=denim"; expect 200 "search suggestions"
(( $(jq -r .totalProducts <<<"$resp") > 0 )) || fail "no suggestions for denim"; ok "suggestions found products"
req GET "/search/suggest?q=zzqxv"; expect 200 "empty suggestions"
[[ "$(jq -r .totalProducts <<<"$resp")" == "0" ]] || fail "nonsense query matched"; ok "no-result query is empty"
req GET "/products/$pid/reviews?sort=helpful"; expect 200 "reviews list"
req GET "/products/$pid/reviews?rating=9"; expect 400 "bad rating filter"
req POST "/products/$pid/reviews" '{"rating":5,"title":"Smoke","body":"Fits well and washes fine.","fitNote":"True to size","author":"Smoke"}'; expect 201 "write review"
rid=$(jq -r .id <<<"$resp")
req POST "/reviews/$rid/helpful" '{"voter":"smoke-voter"}'; expect 200 "helpful vote"
req POST "/reviews/$rid/helpful" '{"voter":"smoke-voter"}'; expect 409 "second vote rejected"
req GET "/products/$pid/availability?sku=$sku&q=CA"; expect 200 "store availability"
(( $(jq '.stores | length' <<<"$resp") > 0 )) || fail "no stores for CA"; ok "stores returned for CA"
req POST /stock-notifications "{\"sku\":\"$sku\",\"email\":\"ava@example.com\"}"; expect 409 "notify-me refused for in-stock size"
gone=$(curl -s "$API/products?pageSize=60" | jq -r '.items[].id' | while read -r p; do
  curl -s "$API/products/$p" | jq -r '.skus[] | select(.stock == 0) | .sku'; done | head -1)
if [[ -n "$gone" ]]; then
  req POST /stock-notifications "{\"sku\":\"$gone\",\"email\":\"ava@example.com\"}"; expect 201 "notify-me for sold-out size"
fi

# Favorites, save for later, gift cards.
req POST /wishlists; expect 201 "guest favorites list"
wl=$(jq -r .id <<<"$resp")
req PUT "/wishlists/$wl/items/$pid" '{"color":null}'; expect 200 "favorite a product"
[[ "$(jq -r .count <<<"$resp")" == "1" ]] || fail "favorite not saved"; ok "favorite saved"
req DELETE "/wishlists/$wl/items/$pid"; expect 200 "unfavorite"
req PUT "/wishlists/$wl/items/$pid" '{"color":null}'; expect 200 "favorite again for claim"
new_bag
req POST "/bags/$bag/items" "{\"sku\":\"$sku\",\"quantity\":1}"; expect 200 "add for save-for-later"
req POST "/bags/$bag/saved" "{\"sku\":\"$sku\"}"; expect 200 "save for later"
[[ "$(jq -r '.itemCount' <<<"$resp")" == "0" && "$(jq -r '.saved | length' <<<"$resp")" == "1" ]] || fail "save for later state"; ok "line moved to saved"
req POST "/bags/$bag/saved/$sku/move" ; expect 200 "move back to bag"
[[ "$(jq -r '.itemCount' <<<"$resp")" == "1" ]] || fail "move to bag"; ok "line back in bag"
req POST /gift-cards/balance '{"number":"6006 4912 3456 7890","pin":"1234"}'; expect 200 "gift card balance"
[[ "$(jq -r .balanceCents <<<"$resp")" == "5000" ]] || fail "gift card balance"; ok "balance is \$50.00"
req POST /gift-cards/balance '{"number":"6006491234567890","pin":"9999"}'; expect 404 "wrong gift card PIN"

# Tracking and returns on the guest order.
req GET "/orders/$number?email=ava@example.com"; expect 200 "order detail"
jq -e '.tracking.steps | length >= 4' <<<"$resp" >/dev/null || fail "no tracking timeline"; ok "tracking timeline"
req POST "/orders/$number/returns" '{"email":"ava@example.com","method":"MAIL","lines":[{"lineNo":1,"quantity":1,"reason":"Nope"}]}'; expect 400 "return needs a valid reason"
req POST "/orders/$number/returns" '{"email":"ava@example.com","method":"MAIL","lines":[{"lineNo":1,"quantity":1,"reason":"Too small"}]}'; expect 201 "start a return"
(( $(jq -r .refundCents <<<"$resp") > 0 )) || fail "zero refund"; ok "refund $(jq -r .refundCents <<<"$resp") cents"
req POST "/orders/$number/returns" '{"email":"ava@example.com","method":"MAIL","lines":[{"lineNo":1,"quantity":1,"reason":"Too small"}]}'; expect 409 "line can't be returned twice"
req POST "/orders/$number/returns" '{"email":"someone@else.com","method":"MAIL","lines":[{"lineNo":1,"quantity":1,"reason":"Too small"}]}'; expect 404 "return with wrong email"

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
# Address book and favorites claim for the signed-in shopper.
req POST /account/addresses '{"label":"Smoke","name":"Maya Otter","line1":"1 Main St","city":"Denver","state":"ZZ","zip":"80202"}'; expect 400 "address with bad state"
req POST /account/addresses '{"label":"Smoke","name":"Maya Otter","line1":"1 Main St","city":"Denver","state":"CO","zip":"80202"}'; expect 200 "save address"
aid=$(jq -r '[.[] | select(.label=="Smoke")][0].id' <<<"$resp")
[[ -n "$aid" && "$aid" != null ]] || fail "address not in book"; ok "address in book"
req POST "/account/addresses/$aid/default"; expect 200 "make address default"
jq -e --arg a "$aid" '.[] | select(.id==$a and .isDefault)' <<<"$resp" >/dev/null || fail "default not set"; ok "default address set"
req DELETE "/account/addresses/$aid"; expect 200 "delete address"
jq -e --arg a "$aid" 'all(.[]; .id != $a)' <<<"$resp" >/dev/null || fail "address not deleted"; ok "address removed"
req POST /wishlists/claim "{\"wishlistId\":\"$wl\"}"; expect 200 "claim guest favorites"
jq -e --arg p "$pid" '.member and (.items[] | select(.productId==$p))' <<<"$resp" >/dev/null || fail "favorites not merged"; ok "guest favorites merged into account"
req DELETE "/wishlists/$(jq -r .id <<<"$resp")/items/$pid"; expect 200 "tidy member favorites"
req POST /auth/logout; expect 204 "sign out"
req GET /account; expect 401 "account requires sign-in"

echo "smoke passed: $pass checks against $BASE"
