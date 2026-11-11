import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('billing_promotion',
    Path(__file__).resolve().parents[1] / 'billing/promote.py')
PROMOTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMOTION)


def test_control_uses_shared_objects_location():
    assert PROMOTION.CONTROL == 'SFX_D1110_AFTER.MIGRATION_CONTROL.OBJECTS'


def test_every_verified_billing_relation_is_registered():
    manifest = json.loads((PROMOTION.SQL.parent / 'parity/billing.json').read_text())
    targets = {target for _, _, _, target in PROMOTION.inventory_objects()}
    assert {entry['after'] for entry in manifest} <= targets


def test_missing_procedure_stops_verification():
    class Cursor:
        sfqid = 'test-query'

        def execute(self, sql):
            if 'P_MONTHLY_INVOICE' in sql:
                raise RuntimeError('Procedure does not exist')

    with pytest.raises(RuntimeError, match='Procedure does not exist'):
        PROMOTION.verify_routines(Cursor())


def test_control_evidence_reads_objects_columns_and_billing_only():
    class Cursor:
        def execute(self, sql):
            assert 'OBJECT_NAME,OBJECT_TYPE,MIGRATION_STATUS,PARITY_STATUS' in sql
            assert 'FROM SFX_D1110_AFTER.MIGRATION_CONTROL.OBJECTS' in sql
            assert "WHERE SUBJECT_AREA='billing'" in sql

        def fetchall(self):
            return [('SFX_BILLING.P_MONTHLY_INVOICE', 'procedure', 'migrated', 'verified')]

    assert PROMOTION.read_control(Cursor())[0][2:] == ('migrated', 'verified')
