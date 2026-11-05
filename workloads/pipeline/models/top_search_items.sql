{{ config(database=database_for("doc_search_api"), period="window_end_date", column_ddl="window_end_date DATE, window_days NUMBER(3,0), account_id VARCHAR(36), item_type VARCHAR(8), rank NUMBER(2,0), term VARCHAR(500), document_id VARCHAR(36), document_title VARCHAR(500), search_count NUMBER(10,0), zero_result_count NUMBER(10,0), last_searched_at TIMESTAMP_NTZ", columns_order=["window_end_date", "window_days", "account_id", "item_type", "rank", "term", "document_id", "document_title", "search_count", "zero_result_count", "last_searched_at"]) }}
with events as (
  {{ raw_rows("ANALYTICS_ANALYTICS_EVENTS", "event_id") }}
), documents as (
  {{ raw_rows("DOCUMENT_DOCUMENTS", "id") }}
), periods as (
  {{ report_periods("window_end_date") }}
)
select * from ({{ search_items("events", "documents", "periods") }})
