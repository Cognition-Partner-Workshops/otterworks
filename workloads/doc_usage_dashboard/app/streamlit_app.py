"""Warehouse-runtime Streamlit entry point."""

import streamlit as st
from snowflake.snowpark.context import get_active_session

from dashboard import (
    COLUMNS,
    account_history_sql,
    account_rows_sql,
    close_to_limit_sql,
    load_runtime_config,
    snapshot_dates_sql,
    statement_prefix,
    trend_sql,
)

config = load_runtime_config()
session = get_active_session()
if "doc_usage_attribution" not in st.session_state:
    try:
        session.sql(config["query_tag_sql"]).collect()
    except Exception:
        st.session_state.doc_usage_attribution = "statement comment"
    else:
        st.session_state.doc_usage_attribution = "session QUERY_TAG"

mode = st.session_state.doc_usage_attribution
prefix = statement_prefix(config) if mode == "statement comment" else ""


def query(built):
    sql, params = built
    frame = session.sql(prefix + sql, params=params).to_pandas()
    frame.columns = [name.lower() for name in frame.columns]
    return frame


def show_accounts(frame):
    display = frame.loc[:, list(COLUMNS)].copy()
    for column in ("quota_bytes", "used_bytes", "remaining_bytes", "active_document_count"):
        display[column] = display[column].map(lambda value: str(int(value)))
    display["usage_pct"] = display["usage_pct"].map(
        lambda value: None if value is None or value != value else f"{value:.2f}"
    )
    st.dataframe(display, use_container_width=True)


st.title("Account storage usage")
st.caption(f"Attribution: {mode}")
dates = query(snapshot_dates_sql(config))
if dates.empty:
    st.info("No snapshots available.")
    st.stop()
selected = st.selectbox("Snapshot date", dates["snapshot_date"].tolist(), index=0)
accounts = query(account_rows_sql(config, selected))
close = query(close_to_limit_sql(config, selected))
metrics = st.columns(3)
metrics[0].metric("Accounts", len(accounts))
used = sum(int(value) for value in accounts["used_bytes"])
quota = sum(int(value) for value in accounts["quota_bytes"])
metrics[1].metric("Total used / total quota (bytes)", f"{used} / {quota}")
metrics[2].metric("Accounts at or above 80%", len(close))

st.header("Storage used vs quota per account")
search = st.text_input("Filter by account ID or email")
show_accounts(query(account_rows_sql(config, selected, search)) if search else accounts)
st.header("Accounts at or above 80% of quota")
show_accounts(close)

st.header("Last 30 days")
trend = query(trend_sql(config, selected)).set_index("snapshot_date")
st.caption("Accounts close to limit")
st.line_chart(trend[["accounts_close_to_limit"]])
st.caption("Aggregate usage %")
st.line_chart(trend[["usage_pct"]])
if accounts.empty:
    st.info("No accounts in the selected snapshot.")
else:
    account_id = st.selectbox("Account usage history", accounts["account_id"].tolist())
    history = query(account_history_sql(config, selected, account_id))
    st.line_chart(history.set_index("snapshot_date")[["usage_pct"]])
