import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from uuid import UUID, NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from bson.decimal128 import Decimal128


def required(value):
    if value is None:
        raise ValueError('null_required')
    return value


def text(value):
    value = required(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError('invalid_text')
    return value


def db2_key(value):
    value = text(value).rstrip()
    if not re.fullmatch(r'C\d{7}', value):
        raise ValueError('invalid_key')
    return value


def integer(value):
    value = Decimal(str(required(value)))
    if not value.is_finite() or value != value.to_integral_value() or not 0 < value < 2**63:
        raise ValueError('invalid_key')
    return int(value)


def uuid_key(value):
    return str(UUID(str(required(value))))


def db2_name(hex_value):
    raw = bytes.fromhex(text(hex_value))
    try:
        return text(raw.decode('utf-8', errors='strict'))
    except UnicodeDecodeError:
        return text(raw.decode('cp037', errors='strict'))


def date_string(value):
    if isinstance(value, datetime):
        raise ValueError('expected_date')
    return date.fromisoformat(str(required(value))).isoformat()


def customer_since(value):
    value = date_string(value)
    return None if value == '0001-01-01' else value


def money(value, rounded=False):
    value = Decimal(str(required(value)))
    if not value.is_finite():
        raise ValueError('invalid_money')
    if rounded:
        value = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    return Decimal128(value)


def oracle_time(value):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError('expected_naive_datetime')
    zone = ZoneInfo('America/New_York')
    early = value.replace(tzinfo=zone, fold=0)
    late = value.replace(tzinfo=zone, fold=1)
    if early.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != value:
        raise ValueError('nonexistent_local_time')
    return early.astimezone(timezone.utc), early.utcoffset() != late.utcoffset()


def utc_time(value):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError('expected_naive_datetime')
    return value.replace(tzinfo=timezone.utc)


def match_text(value):
    return ' '.join(unicodedata.normalize('NFC', text(value)).split()).casefold()


def match_key(name, address):
    return hashlib.sha256(f'{match_text(name)}|{match_text(address)}'.encode()).hexdigest()


def golden_id(anchor):
    return 'cus_' + str(uuid5(NAMESPACE_URL, 'otterworks:odl:customer:' + anchor))


def exception_id(reason, keys):
    return 'exc_' + str(uuid5(NAMESPACE_URL, 'otterworks:odl:exception:' + reason + ':' + ':'.join(sorted(keys))))
