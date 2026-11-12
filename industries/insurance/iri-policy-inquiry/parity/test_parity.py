from decimal import Decimal
import unittest

import yaml

from parity import ROOT, SPEC, canonical, compare, transform, validator


class ParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = yaml.safe_load((ROOT / 'lineage/lineage.yaml').read_text())['entries']
        cls.spec = yaml.safe_load(SPEC.read_text())

    def setUp(self):
        self.case = {'case_id': 'values-test', 'operation': 'values', 'policy_number': '0001200137',
                     'body': {'RTN_CD': '00', 'CNTR_NO': '0001200137', 'VAL_DT': '20260630',
                              'ACCT_VAL': '000000000051250', 'SURR_VAL': '000000000050000',
                              'PREM_TD': '000000000040000', 'WDR_TD': '000000000000100'}}
        self.body = {'valuesAsOfDate': '2026-06-30', 'totalDepositITD': Decimal('400'),
                     'accountValues': {'endingAccountValue': Decimal('512.50'),
                                       'surrenderValue': Decimal('500'),
                                       'totalNetWithdrawalSinceIssue': Decimal('1')}}

    def check_case(self, case=None, body=None, status=200):
        return compare(case or self.case, status, self.body if body is None else body, self.entries, self.spec)

    def test_transforms(self):
        self.assertEqual(canonical('0001200137'), '1200137')
        self.assertEqual(transform('20260630', 'yyyymmdd_to_date', {}), '2026-06-30')
        self.assertEqual(transform('000000000051250', 'implied_decimal', {'scale': 2}), Decimal('512.50'))
        self.assertEqual(transform('000000123456789', 'implied_decimal', {'scale': 6}), Decimal('123.456789'))
        self.assertEqual(transform('IF', 'enum_map', {'map': {'IF': 'ACTIVE'}}), 'ACTIVE')
        self.assertEqual(transform('abc', 'identity', {}), 'abc')

    def test_invalid_transforms(self):
        for value in ('', 'ABC123', '-1', '１２３'):
            with self.assertRaises(ValueError):
                canonical(value)
        with self.assertRaises(ValueError):
            transform('20260230', 'yyyymmdd_to_date', {})
        with self.assertRaises(ValueError):
            transform('1.23', 'implied_decimal', {'scale': 2})
        with self.assertRaises(KeyError):
            transform('??', 'enum_map', {'map': {}})

    def test_values_pass(self):
        self.assertEqual(self.check_case()['outcome'], 'PASS')

    def test_wrong_value(self):
        self.body['accountValues']['endingAccountValue'] = Decimal('512.51')
        self.assertEqual(self.check_case()['outcome'], 'FAIL')

    def test_schema_and_dates(self):
        for body in ({}, {'valuesAsOfDate': '2026-02-30', 'accountValues': {}}):
            self.assertTrue(self.check_case(body=body)['schema_errors'])
        self.assertTrue(list(validator(self.spec, 'Error').iter_errors({'code': 'bad', 'message': 'x', 'timestamp': 'yesterday'})))

    def test_errors(self):
        for rtn, status, code in [('04', 404, 'policy.inquiry.notFound'), ('08', 400, 'policy.inquiry.invalidPolicyNumber'), ('96', 503, 'policy.inquiry.unavailable')]:
            self.case['body'] = {'RTN_CD': rtn}
            self.assertEqual(self.check_case(status=status, body={'code': code, 'message': 'error'})['outcome'], 'PASS')
        self.assertEqual(self.check_case(status=400, body={})['outcome'], 'FAIL')

    def test_signoff(self):
        case = {'operation': 'summary', 'case_id': 'dp', 'policy_number': '1', 'body': {'RTN_CD': '00', 'STAT_CD': 'DP'}}
        body = {'code': 'policy.status.unmapped', 'message': 'DP requires sign-off'}
        self.assertEqual(self.check_case(case, body, 422)['outcome'], 'SIGNOFF')
        self.assertEqual(self.check_case(case, {}, 422)['outcome'], 'FAIL')

    def test_summary(self):
        case = {'operation': 'summary', 'case_id': 'summary', 'policy_number': '0001',
                'body': {'RTN_CD': '00', 'CNTR_NO': '1', 'STAT_CD': 'IF', 'PROD_NM': 'Annuity',
                         'PLAN_CD': 'FLEX', 'QUAL_CD': 'NQ', 'ISS_ST': 'NY', 'CCY_CD': 'USD',
                         'EFF_DT': '20260630', 'GRX_IND': 'X'}}
        body = {'carrierId': 'SYNANN', 'issueType': 'GUARANTEED',
                'policyLastRefreshDateTime': '2026-06-30T00:00:00Z', 'policyStatus': 'ACTIVE',
                'product': {'planName': 'Annuity', 'planCode': 'FLEX', 'productType': 'DEFERRED'},
                'qualificationType': 'Non-Qualified', 'issueState': 'NY', 'currency': 'USD',
                'effectiveDate': '2026-06-30'}
        result = self.check_case(case, body)
        self.assertEqual(result['outcome'], 'PASS', result)
        self.assertIn('/carrierId', result['provisional_elements_emitted'])
        case['body']['STAT_CD'] = 'UNKNOWN'
        self.assertEqual(self.check_case(case, body)['outcome'], 'FAIL')

    def test_funds_index_and_empty(self):
        case = {'operation': 'funds', 'case_id': 'funds', 'policy_number': '1',
                'body': {'RTN_CD': '00', 'CNTR_NO': '1', 'FUND_CNT': '0'}}
        body = {'startIndex': 0, 'itemsCount': 0, 'totalItemsCount': 0, 'funds': []}
        self.assertEqual(self.check_case(case, body)['outcome'], 'PASS')
        for i in (1, 2):
            case['body'].update({f'FUND_CD_{i:02d}': f'F{i}', f'FUND_NM_{i:02d}': f'Fund {i}', f'UNIT_VAL_{i:02d}': '1234567', f'FUND_VAL_{i:02d}': '100'})
            body['funds'].append({'fundId': f'F{i}', 'fundName': f'Fund {i}', 'fundPrice': Decimal('1.234567'), 'totalFundValue': Decimal('1'), 'fundAccountType': 'OTHER', 'fundValuationDate': '2026-06-30'})
        case['body']['FUND_CNT'] = '2'
        body.update(itemsCount=2, totalItemsCount=2)
        self.assertEqual(self.check_case(case, body)['outcome'], 'PASS')
        body['funds'].reverse()
        self.assertEqual(self.check_case(case, body)['outcome'], 'FAIL')

    def test_missing_source(self):
        del self.case['body']['ACCT_VAL']
        self.assertEqual(self.check_case()['outcome'], 'FAIL')

    def test_invalid_funds_body_types(self):
        case = {'operation': 'funds', 'case_id': 'invalid-funds', 'policy_number': '1',
                'body': {'RTN_CD': '00', 'CNTR_NO': '1', 'FUND_CNT': '0'}}
        for body in (None, [], 'not an object', 5):
            result = compare(case, 200, body, self.entries, self.spec)
            self.assertEqual(result['outcome'], 'FAIL')
            self.assertTrue(result['schema_errors'])
    def test_no_echo(self):
        self.body['policyNumber'] = '1200137'
        self.assertEqual(self.check_case()['outcome'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
