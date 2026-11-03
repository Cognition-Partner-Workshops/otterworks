# OtterShops feature research

Before phase 2 we reviewed the storefronts of large apparel chains, department stores, marketplaces and direct-to-consumer labels, looking only at interaction patterns that most of them share and that public conversion studies keep crediting. No retailer's name, copy, imagery or layout is used in OtterShops, and the table below describes each pattern generically.

## Patterns reviewed

| Area | Pattern | Why stores use it | OtterShops |
|---|---|---|---|
| Discovery | Typeahead under the search box with category terms, collections and a few product rows | Shoppers who search convert at a much higher rate, and suggestions cut misspelled or empty searches | Adopted (header search, keyboard and screen-reader friendly) |
| Discovery | Search results page with filters and a no-results page that offers popular searches | A dead end loses the visit; a few suggested terms keep the shopper moving | Adopted |
| Discovery | Quick add from the product grid | Repeat buyers know their size and skip the product page | Adopted (color and size picker on each card) |
| Discovery | Load more instead of numbered pages | Keeps the scroll position on phones | Kept from the core slice |
| Discovery | Recently viewed and "you may also like" rows | Brings back products the shopper already considered | Adopted |
| Discovery | Complete the look | Raises units per order by pairing tops, bottoms and layers | Adopted (uses the curated product links in the catalog) |
| Conversion | Size guide in a dialog on the product page | Size doubt is the top reason apparel shoppers abandon or return | Adopted |
| Conversion | Fit summary from reviews ("runs small", "true to size") | Shoppers trust other buyers on fit more than a chart | Adopted |
| Conversion | Store stock check and buy online, pick up in store | Lets the shopper see the item today and saves shipping | Adopted (store stock check on the product page; pickup at checkout from the core slice) |
| Conversion | Back-in-stock email for a sold-out size | Captures demand that would otherwise leave | Adopted |
| Conversion | Free-shipping progress bar in the bag | Small add-ons to cross the threshold raise order value | Adopted (bag and mini-bag) |
| Conversion | Save for later in the bag | Keeps the item without inflating the order total | Adopted |
| Conversion | Favorites for guests that carry over at sign-in | A heart icon is the cheapest way to start a list, and members expect the list on every device | Adopted |
| Trust | Rating histogram with star filters, sort and helpful votes | Mixed reviews read as honest; helpful votes surface the useful ones | Adopted |
| Trust | Write a review on the product page | Fresh reviews keep products ranked | Adopted (the "verified" badge applies to signed-in buyers of that product) |
| Trust | Clear shipping, returns, privacy, terms, accessibility and contact pages in the footer | Shoppers check the return policy before a first order | Adopted |
| Post-purchase | Order page with a status timeline and tracking number | Cuts "where is my order" contacts | Adopted (demo timings; no carrier integration) |
| Post-purchase | Self-service return start with reasons and a refund estimate | Return reasons feed merchandising, and self-service lowers support cost | Adopted (mail or store drop-off, 45-day window) |
| Post-purchase | Saved addresses in the account | Faster repeat checkout | Adopted (address book; checkout prefill is not wired yet) |
| Post-purchase | Gift card balance check | Common support question that needs no agent | Adopted |
| Navigation | Slide-in menu on phones and a skip link, focus handling and labels for keyboard users | Most apparel traffic is mobile, and accessibility complaints are a legal risk | Adopted |
| Not adopted | Live chat, buy now pay later, virtual try-on, loyalty tiers, social login, ratings syndication | Each needs a third-party service or would distract from the on-call demo | Skipped |

## Data captured for analytics

Reviews (rating, fit and helpful votes), favorites, back-in-stock requests and returns are loaded to Snowflake with the orders. The `product_engagement` mart puts these signals next to units sold, so a demo can show, for example, that a style with many "runs small" reviews also has a high return rate for "Too small". Review text, reviewer names and alert email addresses stay in Postgres.
