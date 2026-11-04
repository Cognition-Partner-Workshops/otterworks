"""doc_usage_dashboard: storage used against quota per account (Streamlit in Snowflake)."""

from pathlib import Path

import streamlit as st

session = st.connection("snowflake").session()
# Attribution: the runtime QUERY_TAG (rendered at deploy by sf_attribution.streamlit_query_tag_sql) runs first.
session.sql((Path(__file__).parent / "query_tag.sql").read_text().strip()).collect()

OUTPUT = "ANALYTICS.DOC_USAGE_DASHBOARD"
NEAR_LIMIT_RATIO = 0.80
COLUMNS = [
    "SNAPSHOT_DATE", "ACCOUNT_ID", "ACCOUNT_EMAIL", "TIER", "QUOTA_BYTES", "USED_BYTES",
    "REMAINING_BYTES", "USAGE_PCT", "USAGE_BAND", "ACTIVE_DOCUMENT_COUNT",
]
INTEGER = st.column_config.NumberColumn(format="%d")
CONFIG = {
    "QUOTA_BYTES": INTEGER, "USED_BYTES": INTEGER, "REMAINING_BYTES": INTEGER,
    "ACTIVE_DOCUMENT_COUNT": INTEGER, "USAGE_PCT": st.column_config.NumberColumn(format="%.2f"),
    "SNAPSHOT_DATE": st.column_config.DateColumn(format="YYYY-MM-DD"),
}

st.set_page_config(page_title="Storage quota by account", layout="wide")
st.title("Storage used against quota per account")

dates = [r[0] for r in session.sql(f"SELECT DISTINCT SNAPSHOT_DATE FROM {OUTPUT} ORDER BY 1 DESC").collect()]
if not dates:
    st.warning("No snapshot has been loaded yet.")
    st.stop()
snapshot = st.selectbox("Snapshot date (UTC)", dates, index=0, format_func=lambda d: d.isoformat())
rows = session.sql(
    f"SELECT {', '.join(COLUMNS)} FROM {OUTPUT} WHERE SNAPSHOT_DATE = ? ORDER BY USAGE_PCT DESC, ACCOUNT_ID",
    params=[snapshot],
).to_pandas()
above = rows[rows["USED_BYTES"] >= NEAR_LIMIT_RATIO * rows["QUOTA_BYTES"]]

a, b, c, d = st.columns(4)
a.metric("Accounts", len(rows))
b.metric("At or above 80% of quota", len(above))
c.metric("Over quota", int((rows["USAGE_BAND"] == "over_quota").sum()))
d.metric("Near limit", int((rows["USAGE_BAND"] == "near_limit").sum()))

st.subheader(f"Accounts at or above 80% of quota on {snapshot.isoformat()}")
st.dataframe(above, column_config=CONFIG, hide_index=True, use_container_width=True)

st.subheader("Look up one account")
account = st.selectbox("Account ID", rows["ACCOUNT_ID"].tolist())
st.dataframe(
    rows[rows["ACCOUNT_ID"] == account].melt(var_name="FIELD", value_name="VALUE").astype({"VALUE": str}),
    hide_index=True, use_container_width=True,
)

st.subheader(f"All accounts on {snapshot.isoformat()}")
st.dataframe(rows, column_config=CONFIG, hide_index=True, use_container_width=True)

st.subheader("Trend, last 30 days")
trend = session.sql(
    f"""SELECT SNAPSHOT_DATE, COUNT(*) AS ACCOUNTS,
      COUNT_IF(USED_BYTES >= {NEAR_LIMIT_RATIO} * QUOTA_BYTES) AS ACCOUNTS_AT_OR_ABOVE_80_PCT,
      COUNT_IF(USAGE_BAND = 'over_quota') AS ACCOUNTS_OVER_QUOTA,
      SUM(USED_BYTES) AS USED_BYTES, SUM(QUOTA_BYTES) AS QUOTA_BYTES
    FROM {OUTPUT}
    WHERE SNAPSHOT_DATE > DATEADD(day, -30, (SELECT MAX(SNAPSHOT_DATE) FROM {OUTPUT}))
    GROUP BY 1 ORDER BY 1"""
).to_pandas()
st.caption(f"{len(trend)} daily snapshot(s) loaded in the window; storage_quotas has no history before the first export.")
st.line_chart(trend.set_index("SNAPSHOT_DATE")[["ACCOUNTS_AT_OR_ABOVE_80_PCT", "ACCOUNTS_OVER_QUOTA"]])
st.dataframe(trend, column_config=CONFIG, hide_index=True, use_container_width=True)
