from datetime import datetime

import pytest

from lakehouse.audit import spark as audit
from lakehouse.tests.test_audit import spark


def register(session, rows=None):
    rows = rows or {}
    for name, (_, schema) in audit.FEEDS.items():
        session.createDataFrame(rows.get(name, []), schema).createOrReplaceTempView('audit_spark_' + name)


def test_spark_audit_empty_inputs(spark):
    register(spark)
    for query in audit.QUERIES.values():
        assert spark.sql(query).collect() == []


def test_spark_audit_rules_and_anomaly_edges(spark):
    register(spark, {
        'compliance_flag': [(1, 2, 3, 'x', 7000, 'closed'), (2, 3, 4, 'x', 7000, 'open'),
                            (3, 4, 5, 'x', 6999, None)],
    })
    result = spark.sql(audit.QUERIES['compliance_flag_rules']).orderBy('FLAG_ID').collect()
    assert [row.DISPOSITION for row in result] == ['resolved', 'review', 'monitor']
    spark.createDataFrame([(1, 2, 3.0), (2, 2, 3.0)],
                          'SECURITY_ALERT_ID long, USER_ID long, SCORE double').createOrReplaceTempView(
                              'audit_spark_security_alert')
    assert [row.Z_SCORE for row in spark.sql(audit.QUERIES['security_alert_anomaly']).collect()] == [0.0, 0.0]
    spark.createDataFrame([(1, 2, 1.0), (2, 2, 3.0)],
                          'SECURITY_ALERT_ID long, USER_ID long, SCORE double').createOrReplaceTempView(
                              'audit_spark_security_alert')
    result = spark.sql(audit.QUERIES['security_alert_anomaly']).orderBy('ALERT_ID').collect()
    assert [row.Z_SCORE for row in result] == [-1.0, 1.0]


def test_spark_actor_join_thresholds_null_actor_and_utf8(spark):
    register(spark, {
        'audit_event': [(1, None, 2, 'x', datetime(2026, 11, 9), '')],
        'user_activity_daily': [(1, 3, datetime(2026, 11, 9).date(), 13, 5)],
        'login_event': [(1, 3, datetime(2026, 11, 9, 7), '', 'agent', 'é')],
    })
    result = spark.sql(audit.QUERIES['audit_actor_activity_join']).collect()
    assert len(result) == 1 and result[0].USER_KEY == 0 and result[0].LOGIN_TEXT_BYTES == 2
    assert result[0].ACTION_COUNT == 5
    summary = spark.sql(audit.QUERIES['audit_daily_summary']).collect()[0]
    assert summary.EVENT_COUNT == 1 and summary.ACTORS == 0


def test_delta_optimize_preserves_audit_summary(spark):
    original = spark.createDataFrame([(1, 'x'), (2, 'y')], 'id long, value string')
    audit.publish(original.coalesce(1), 'gold', 'spark_audit_daily_summary')
    original.limit(1).write.format('delta').mode('append').saveAsTable('gold_audit.spark_audit_daily_summary')
    assert len(spark.table('gold_audit.spark_audit_daily_summary').inputFiles()) == 2
    before = spark.table('gold_audit.spark_audit_daily_summary').collect()
    audit.compact(spark)
    assert sorted(spark.table('gold_audit.spark_audit_daily_summary').collect()) == sorted(before)
    assert len(spark.table('gold_audit.spark_audit_daily_summary').inputFiles()) == 1
    history = spark.sql('DESCRIBE HISTORY gold_audit.spark_audit_daily_summary').collect()
    assert history[0].operation == 'OPTIMIZE'


def test_spark_missing_feed_fails(spark, tmp_path):
    with pytest.raises(FileNotFoundError, match='No Spark landing files'):
        audit.ingest(spark, tmp_path, '20261109')
