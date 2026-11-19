from common.runtime import landing, save, session

spark = session("collab_session_sessionize")
events = landing(spark, "COLLAB_SESSION").rdd.map(lambda r: ((r.USER_ID, r.DOCUMENT_ID), r.EVENT_AT))


def sessions(group):
    (user, document), times = group
    ordered = sorted(times)
    if not ordered:
        return []
    result, start, previous, number = [], ordered[0], ordered[0], 1
    for timestamp in ordered[1:]:
        if (timestamp - previous).total_seconds() > 1800:
            result.append((user, document, number, start, previous))
            number, start = number + 1, timestamp
        previous = timestamp
    result.append((user, document, number, start, previous))
    return result


frame = spark.createDataFrame(events.groupByKey().flatMap(sessions),
                              "USER_ID long, DOCUMENT_ID long, SESSION_NUMBER long, START_AT timestamp, END_AT timestamp")
save(frame, "documents", "collab_session_sessionize")
spark.stop()
