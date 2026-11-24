"""Reconcile all 200 golden policies against saved widened-parity outputs."""

import collections
import json
from decimal import Decimal
from pathlib import Path

import driver

estate = Path(__file__).resolve().parents[1]
build = estate / 'build'
rating_fields = ('status', 'reason', 'base', 'modified', 'minimum', 'source', 'total')
quote_fields = (*rating_fields, 'endorsements')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def zoned(raw):
    zone_byte = raw[-1].encode('cp037')[0]
    zone, final = divmod(zone_byte, 16)
    require(zone in (12, 13, 15) and final < 10 and raw[:-1].isdigit(),
            f'Invalid zoned decimal: {raw!r}')
    return (-1 if zone == 13 else 1) * (int(raw[:-1]) * 10 + final)

def cobol(raw):
    key = raw[:8]
    fields = (('status', 3, str.strip), ('reason', 4, str.strip), ('rate', 9, int),
              ('factor', 4, int), ('source', 1, str.strip), ('base', 11, zoned),
              ('modified', 11, zoned), ('minimum', 1, str.strip), ('fee', 5, int),
              ('total', 11, zoned))
    result, index = {}, 8
    for name, width, decode in fields:
        result[name] = decode(raw[index:index + width])
        index += width
    require(index == 68, f'Unexpected RATEOUT field boundary: {index}')
    return key, result

def quote(raw):
    policy, status, reason, base, modified, minimum, charge, fee, total, source = raw.split('|')
    return policy, dict(status=status, reason=reason, base=int(base), modified=int(modified),
                        minimum=minimum, endorsements=int(charge), fee=int(fee), total=int(total),
                        source=source)

def load(path, parse):
    lines = path.read_text().splitlines()
    rows = dict(map(parse, lines))
    require(len(rows) == len(lines) == 200, f'{path}: expected 200 unique rows')
    return rows

def table(name):
    return [r.split('|') for r in (estate / 'tables' / (name + '.dat')).read_text().splitlines()
            if r.strip() and not r.startswith('*')]

def scaled(s, scale):
    return int(Decimal(s) * scale)

def in_force(on, terms):
    first, last = (terms + [''])[:2]
    return first <= on and (not last or on <= last)

def first(rows, scope, on):
    return next((r for r in rows if r[:len(scope)] == scope and in_force(on, r[len(scope)+1:])), None)

def rounded(numerator, denominator):
    q, r = divmod(numerator, denominator)
    return q + (2 * r >= denominator)

def rate(raw):
    line, state, klass, territory, date = raw[8:10], raw[10:12], raw[12:17].strip(), raw[17:20], raw[20:28]
    exposure = zoned(raw[28:37])
    years, claims, deductible = int(raw[37:39]), int(raw[39:41]), int(raw[41:46])
    package = raw[46] == 'Y' and line in ('GL', 'PR')
    plan = zoned(raw[47:50])
    insureds = int(raw[50:52])
    equip, waiver, hnoa = [c == 'Y' for c in raw[52:55]]
    def refused(status, reason):
        p = dict(status=status, reason=reason, base=0, modified=0, minimum='N', fee=0, total=0, source='')
        return [dict(p, rate=0, factor=0), dict(p, endorsements=0), dict(p, endorsements=0)], (0, 0)
    if line not in ('GL', 'PR', 'CA'):
        return refused('REJ', 'LN')
    if exposure <= 0:
        return refused('REJ', 'EX')
    allow = eligibility.get((line, klass, state), eligibility.get((line, klass, '**')))
    if allow and allow[0] == 'N':
        return refused('DEC', allow[1])
    klass_row = first(classes, [line, klass], date)
    if klass_row is None:
        return refused('REJ', 'CL')
    territory_row, source = first(territories, [line, territory], date), 'T'
    if territory_row is None:
        territory_row, source = first(territories, [line, '000'], date), 'D'
    if territory_row is None:
        return refused('REJ', 'TR')
    override = first(overrides, [line, klass, territory], date)
    factor, rate = scaled(territory_row[2], 1000), scaled(klass_row[2], 10000)
    if override is not None:
        factor, source = scaled(override[3], 1000), 'O'
    base = rounded(rounded(exposure * rate, 10000) * factor, 1000)
    exp = 125 if claims >= 3 else 90 if claims == 0 and years >= 3 else 100
    ded = next((c for d, c in ((5000, 92), (2500, 95), (1000, 98)) if deductible >= d), 100) if line != 'GL' else 100
    common = rounded(rounded(base * exp, 100) * ded, 100)
    schedule = 100 + max(-25, min(25, plan))
    minimum = minimums.get((line, state), minimums.get((line, '**'), 0))
    def factors(premium):
        return rounded(rounded(premium * schedule, 100) * (95 if package else 100), 100)
    before_late_floor = factors(common)
    early = factors(max(minimum, common))
    late = max(minimum, before_late_floor)
    def endorsements(mod):
        charges = (min(3, insureds) * 5000 + hnoa * 12000) if line == 'GL' else 0
        if equip and line == 'PR':
            charges += rounded(max(7500, rounded(mod * 3, 100)), 100) * 100
        if waiver and line != 'PR':
            charges += rounded(rounded(mod * 2, 100), 100) * 100
        return min(charges, rounded(mod * 25, 100))
    other = dict(status='OK', reason='', source=source, base=base, fee=3500)
    late_row = dict(other, modified=late, minimum='Y' if before_late_floor < minimum else 'N')
    early_row = dict(other, modified=early, minimum='Y' if common < minimum else 'N')
    c = dict(late_row, rate=rate, factor=factor, total=late+3500)
    p = dict(early_row, endorsements=endorsements(early), total=early+endorsements(early)+3500)
    j = dict(late_row, endorsements=endorsements(late), total=late+endorsements(late)+3500)
    return [c, p, j], (early - late, endorsements(late) - endorsements(early))

classes, territories, overrides = [table(t) for t in ('class-factors', 'territory-factors', 'overrides')]
require(not any(r[:2] == ['PR', 'WND'] for r in territories),
        'Unexpected PR/WND row in territory-factors.dat')
minimums = {(line, state): scaled(p, 100) for line, state, p in table('minimum-premium')}
eligibility = {(line, klass, state): (eligible, reason)
               for line, klass, state, eligible, reason in table('line-eligibility')}
fixtures = load(estate / 'fixtures' / 'policies.dat', lambda raw: (raw[:8], raw))
files = [build / n for n in ('cobol.dat', 'pharo.txt', 'java.txt')]
rows = [load(file, parser) for file, parser in zip(files, [cobol, quote, quote])]
require(all(r.keys() == fixtures.keys() for r in rows), 'Output policy IDs differ from fixtures')
actual_parity = json.loads((build / 'parity.json').read_text())['pairs']
pairs = [('cobol~java', 0, 2), ('pharo~java', 1, 2), ('cobol~pharo', 0, 1)]
groups = {name: collections.defaultdict(list) for name, *_ in pairs}
field_diffs = {name: [] for name, *_ in pairs}
delta_rows = {}
fees_by_status = collections.defaultdict(set)
for digit in range(10):
    for zone, sign in ((12, 1), (13, -1), (15, 1)):
        last = bytes((zone * 16 + digit,)).decode('cp037')
        require(driver.overpunch('123' + last) == zoned('123' + last) == sign * (1230 + digit),
                f'Zoned sign/digit mismatch: zone {zone}, digit {digit}')
for index, file in enumerate(files):
    decoder = driver.read_cobol if index == 0 else driver.read_canonical
    parsed = decoder(file)
    require(parsed.keys() == fixtures.keys(), f'{file}: driver policy IDs differ from fixtures')
    for policy, fields in parsed.items():
        require(all(rows[index][policy][k] == v for k, v in fields.items()),
                f'{file}: driver decoding differs for {policy}')
for policy, raw in fixtures.items():
    expected, (early_minus_late, charge_repricing) = rate(raw)
    for stack, result, rated in zip(('COBOL', 'Pharo', 'Java'), rows, expected):
        require(result[policy] == rated,
                f'{stack} {policy}: got {result[policy]}, expected {rated}')
        fees_by_status[rated['status']].add(rated['fee'])
    c, p, j = expected
    if early_minus_late:
        delta_rows[policy] = (early_minus_late, p['endorsements'], charge_repricing)
    for name, a, b in pairs:
        left, right = rows[a][policy], rows[b][policy]
        fields = quote_fields if a else rating_fields
        diffs = {k for k in fields if left[k] != right[k]}
        r94 = {'modified', 'minimum', 'total', 'endorsements'} if early_minus_late and 1 in (a, b) else set()
        r100 = right['endorsements'] if a == 0 else 0
        timing = 0 if b == 2 and a == 0 else early_minus_late if a == 0 else -early_minus_late + charge_repricing
        causes = tuple(rule for rule, gap in [('R94', timing), ('R100', r100)] if gap)
        require((diffs - r94) <= ({'total'} if r100 else set()),
                f'{name} {policy}: unexplained field differences in {diffs}')
        residual = right['total'] - left['total'] - r100 - timing
        require(residual == 0, f'{name} {policy}: unexplained total gap of {residual} cents')
        if diffs:
            require(causes, f'{name} {policy}: mismatch without a recorded cause')
            groups[name][causes].append(policy)
            left_name, right_name = name.split('~')
            field_diffs[name].append({
                'policy': policy,
                'fields': {k: {left_name: left[k], right_name: right[k]} for k in diffs},
            })
require([pair['pair'] for pair in actual_parity] == [name for name, *_ in pairs],
        'Unexpected comparison pairs or order in parity.json')
for pair in actual_parity:
    name = pair['pair']
    grouped = groups[name]
    require(pair['mismatches'] == sorted(field_diffs[name], key=lambda row: row['policy']),
            f'{name}: mismatch records differ from parity.json')
    require(sum(map(len, grouped.values())) == pair['mismatched'] == 200 - pair['matched'],
            f'{name}: mismatch counts differ from parity.json')
    print(name, 'matched', pair['matched'], 'mismatched', pair['mismatched'])
    for causes, policies in sorted(grouped.items()):
        print('+'.join(causes), len(policies), ', '.join(policies))
print('R94 policy cents: Pharo minus late-floor modified, Pharo endorsement, endorsement repricing under late floor')
for policy, components in delta_rows.items():
    print(policy, *components)
print('Independent arithmetic and raw serialization checks passed: 600 rows, 600 pair residuals zero, 30 zoned sign/digit cases.')
print('Golden rows by COBOL territory source:', dict(collections.Counter(c['source'] for c in rows[0].values())))
print('Fees by status:', dict(fees_by_status))
