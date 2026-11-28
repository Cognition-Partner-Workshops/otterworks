"""The exact statements the legacy-portal handlers send, each mapped to trusted static SQL.

The local Data API never runs the SQL text it receives. It looks the text up among the statements
the DataApi*Repository classes build (with the DB_SCHEMA values in docker-compose.yml) and runs the
psycopg statement written here instead, binding only the parameter values after checking their names
and types. Anything else fails closed. A handler change that alters its SQL needs a matching entry.
"""
from dataclasses import dataclass

STRING, LONG, BOOLEAN = "stringValue", "longValue", "booleanValue"
ANNOUNCEMENT_COLUMNS = "id, title, body, published, created_at"


class OperationError(Exception):
    pass


@dataclass(frozen=True)
class Operation:
    name: str
    handler_sql: str
    sql: str
    params: tuple = ()  # (name, field kind, typeHint or None)


OPERATIONS = (
    Operation(
        "announcements.insert",
        "INSERT INTO announcements.announcement (title, body, published, created_at)"
        " VALUES (:title, :body, :published, CAST(:created_at AS timestamp))"
        " RETURNING id, title, body, published, created_at",
        "INSERT INTO announcements.announcement (title, body, published, created_at)"
        " VALUES (%(title)s::varchar, %(body)s::varchar, %(published)s::boolean,"
        " CAST(%(created_at)s::varchar AS timestamp))"
        " RETURNING id, title, body, published, created_at",
        (("title", STRING, None), ("body", STRING, None), ("published", BOOLEAN, None),
         ("created_at", STRING, None))),
    Operation(
        "announcements.update",
        "UPDATE announcements.announcement"
        " SET title = :title, body = :body, published = :published, created_at = CAST(:created_at AS timestamp)"
        " WHERE id = :id",
        "UPDATE announcements.announcement"
        " SET title = %(title)s::varchar, body = %(body)s::varchar, published = %(published)s::boolean,"
        " created_at = CAST(%(created_at)s::varchar AS timestamp)"
        " WHERE id = %(id)s::bigint",
        (("id", LONG, None), ("title", STRING, None), ("body", STRING, None), ("published", BOOLEAN, None),
         ("created_at", STRING, None))),
    Operation(
        "announcements.published",
        "SELECT id, title, body, published, created_at FROM announcements.announcement"
        " WHERE published = true ORDER BY created_at DESC",
        "SELECT id, title, body, published, created_at FROM announcements.announcement"
        " WHERE published = true ORDER BY created_at DESC"),
    Operation(
        "announcements.all",
        "SELECT id, title, body, published, created_at FROM announcements.announcement",
        "SELECT id, title, body, published, created_at FROM announcements.announcement"),
    Operation(
        "announcements.by-id",
        "SELECT id, title, body, published, created_at FROM announcements.announcement WHERE id = :id",
        "SELECT id, title, body, published, created_at FROM announcements.announcement WHERE id = %(id)s::bigint",
        (("id", LONG, None),)),
    Operation(
        "preferences.by-user",
        "SELECT user_id, theme, locale, email_notifications FROM user_preferences.user_preference"
        " WHERE user_id = :u",
        "SELECT user_id, theme, locale, email_notifications FROM user_preferences.user_preference"
        " WHERE user_id = %(u)s::varchar",
        (("u", STRING, None),)),
    Operation(
        "preferences.upsert",
        "INSERT INTO user_preferences.user_preference (user_id, theme, locale, email_notifications)"
        " VALUES (:u, :t, :l, :e)"
        " ON CONFLICT (user_id) DO UPDATE SET"
        " theme=EXCLUDED.theme, locale=EXCLUDED.locale,"
        " email_notifications=EXCLUDED.email_notifications",
        "INSERT INTO user_preferences.user_preference (user_id, theme, locale, email_notifications)"
        " VALUES (%(u)s::varchar, %(t)s::varchar, %(l)s::varchar, %(e)s::boolean)"
        " ON CONFLICT (user_id) DO UPDATE SET"
        " theme=EXCLUDED.theme, locale=EXCLUDED.locale,"
        " email_notifications=EXCLUDED.email_notifications",
        (("u", STRING, None), ("t", STRING, None), ("l", STRING, None), ("e", BOOLEAN, None))),
    Operation(
        "feedback.insert",
        "INSERT INTO feedback.feedback (created_at, message, rating, user_id) "
        "VALUES (:createdAt, :message, :rating, :userId) RETURNING id",
        "INSERT INTO feedback.feedback (created_at, message, rating, user_id) "
        "VALUES (%(createdAt)s::timestamp, %(message)s::varchar, %(rating)s::bigint, %(userId)s::varchar)"
        " RETURNING id",
        (("createdAt", STRING, "TIMESTAMP"), ("message", STRING, None), ("rating", LONG, None),
         ("userId", STRING, None))),
    Operation(
        "feedback.by-user",
        "SELECT id, created_at, message, rating, user_id FROM feedback.feedback"
        " WHERE user_id = :userId ORDER BY created_at DESC, id DESC",
        "SELECT id, created_at, message, rating, user_id FROM feedback.feedback"
        " WHERE user_id = %(userId)s::varchar ORDER BY created_at DESC, id DESC",
        (("userId", STRING, None),)),
    Operation(
        "feedback.aggregate",
        "SELECT count(*), coalesce(sum(rating), 0) FROM feedback.feedback",
        "SELECT count(*), coalesce(sum(rating), 0) FROM feedback.feedback"),
)


def _value(op, spec, param):
    name, kind, hint = spec
    if param.get("typeHint") != hint:
        raise OperationError(f"{op.name}: parameter {name} must have typeHint {hint}")
    field = param.get("value") or {}
    if field.get("isNull") is True and len(field) == 1:
        return None
    if set(field) != {kind}:
        raise OperationError(f"{op.name}: parameter {name} must be a {kind}")
    value = field[kind]
    ok = {STRING: isinstance(value, str), LONG: isinstance(value, int) and not isinstance(value, bool),
          BOOLEAN: isinstance(value, bool)}[kind]
    if not ok:
        raise OperationError(f"{op.name}: parameter {name} has the wrong type")
    return value


def resolve(handler_sql, parameters):
    """Return (operation, values) for a known handler statement, or raise OperationError."""
    for op in OPERATIONS:
        if op.handler_sql == handler_sql:
            break
    else:
        raise OperationError("statement is not one the legacy-portal handlers send")
    given = {}
    for p in parameters or []:
        if not isinstance(p, dict) or not isinstance(p.get("name"), str) or p["name"] in given:
            raise OperationError(f"{op.name}: malformed or repeated parameter")
        given[p["name"]] = p
    expected = {spec[0] for spec in op.params}
    if set(given) != expected:
        raise OperationError(f"{op.name}: expected parameters {sorted(expected)}, got {sorted(given)}")
    return op, {spec[0]: _value(op, spec, given[spec[0]]) for spec in op.params}
