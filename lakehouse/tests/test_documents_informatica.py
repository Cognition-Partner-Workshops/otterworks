from datetime import date

import pytest

from etl.informatica.runner.engine import coerce
from etl.informatica.runner.expr import compile_expr
from lakehouse.orchestration.graph import load
from lakehouse.parity.readers import postgres_connection
from lakehouse.runtime.documents_informatica import DOCUMENT, SHARE, checkpoint, convert, ports, read_feed


def document(**changes):
    return {**dict(zip(DOCUMENT, ['1', '2', '3', '4', '  Name  ', '2026-11-09', ' active ', ' pdf '])),
            **changes}


def share(**changes):
    return {**dict(zip(SHARE, ['1', '2', '3', ' view ', '2026-11-09'])), **changes}


USERS = [{'user_id': 3, 'status_cd': 'INACTIVE'}]


def test_ports_match_legacy_expression_and_qualifier_widths():
    raw = document(document_id=' 12.9suffix', folder_id=None, document_name=' ' + 'x' * 150,
                   created_dt='2026-1-9', status_cd='ß' * 12)
    row = ports(raw)
    assert row['document_id'] == compile_expr('TO_BIGINT(V)')({'V': raw['document_id'][:20]}) == 12
    assert row['folder_id'] is None
    assert row['document_name'] == 'x' * 119
    assert row['status_cd'] == 'SS' * 12
    assert row['created_dt'] == date(2026, 1, 9)
    expected = compile_expr('LTRIM(RTRIM(V))')({'V': coerce(raw['document_name'], 'string', 120)})
    assert row['document_name'] == expected
    assert ports(document(document_name='   ', file_type='\tPDF\t'))['document_name'] == ''
    assert ports(document(file_type='\tPDF\t'))['file_type'] == '\tPDF\t'


def test_owner_filter_is_not_reject_and_null_status_is_not_known():
    result = convert([document(), document(document_id='2', owner_user_id='99'),
                      document(document_id='3', owner_user_id='4')], [],
                     USERS + [{'user_id': 4, 'status_cd': None}], [])
    assert len(result['document']) == 1
    assert len(result['filtered']) == 2
    assert result['rejects'] == []
    assert result['metrics'][1]['source_rows'] == 3
    assert result['metrics'][1]['written_rows'] == 1
    assert result['metrics'][1]['rejected_rows'] == 0


def test_upserts_retain_absent_rows_and_update_all_fields():
    first = convert([document(), document(document_id='9')], [share(), share(share_id='9')], USERS, [])
    second = convert([document(document_name='Changed')], [share(access_level='edit')], USERS, [],
                     first['document'], first['doc_share'], len(first['stg_document']))
    assert len(second['document']) == len(second['doc_share']) == 2
    assert next(r for r in second['document'] if r['document_id'] == 1)['document_name'] == 'Changed'
    assert next(r for r in second['doc_share'] if r['share_id'] == 1)['access_level'] == 'EDIT'
    assert second['metrics'][1]['inserted_rows'] == 0
    assert second['metrics'][1]['updated_rows'] == 1
    assert second['metrics'][2]['updated_rows'] == 1
    assert len(second['stg_document']) == 1


def test_cached_document_insert_lookup_and_share_update_else_insert():
    feed = [document(document_name='First'), document(document_name='Second')]
    first = convert(feed, [share(access_level='view'), share(access_level='edit')], USERS, [])
    assert first['document'][0]['document_name'] == 'First'
    assert first['metrics'][1]['rejected_rows'] == 1
    assert len(first['stg_document']) == 2
    assert first['doc_share'][0]['access_level'] == 'EDIT'
    assert first['metrics'][2]['inserted_rows'] == first['metrics'][2]['updated_rows'] == 1
    second = convert(feed, [], USERS, [], first['document'])
    assert second['document'][0]['document_name'] == 'Second'
    assert second['metrics'][1]['updated_rows'] == 2


@pytest.mark.parametrize('role,access,expected', [('ADMIN', 'VIEW', 'OWNER'), ('EDITOR', 'VIEW', 'EDIT'),
                                               ('EDITOR', 'OWNER', 'OWNER'), ('MEMBER', 'VIEW', 'VIEW'),
                                               (None, 'VIEW', 'VIEW'), ('admin', 'VIEW', 'VIEW')])
def test_share_role_upgrade(role, access, expected):
    result = convert([], [share(access_level=access)], [], [{'user_id': 3, 'role_cd': role}])
    assert result['doc_share'][0]['access_level'] == expected


def test_errors_and_nullable_ports_remain_observable():
    result = convert([document(document_id='bad'), document(created_dt='2026-02-30'),
                      document(document_id=None), document(document_id='4', status_cd='ß' * 12)],
                     [share(share_id=None), share(shared_dt='bad')], USERS, [])
    assert [r['rejected_rows'] for r in result['metrics']] == [2, 2, 2]
    assert [r['transformation_errors'] for r in result['metrics']] == [2, 0, 1]
    assert len(result['rejects']) == 6
    assert len(result['stg_document']) == 2
    assert result['document'] == result['doc_share'] == []
    good = convert([document(created_dt=None, document_name=None)], [], USERS, [])
    assert good['document'][0]['created_dt'] is None
    assert good['document'][0]['document_name'] is None


def test_empty_input_and_first_lookup_match():
    result = convert([], [], [], [])
    assert all(not result[k] for k in ('stg_document', 'document', 'doc_share', 'rejects', 'filtered'))
    assert all(r['source_rows'] == r['written_rows'] == r['rejected_rows'] == 0 for r in result['metrics'])
    result = convert([], [share()], [], [{'user_id': 3, 'role_cd': 'EDITOR'},
                                       {'user_id': 3, 'role_cd': 'ADMIN'}])
    assert result['doc_share'][0]['access_level'] == 'EDIT'


def test_retry_checkpoint_preserves_initial_counts_and_dates(tmp_path):
    path = tmp_path / 'transaction.json'
    first = checkpoint(path, 'delivery-1', lambda: convert([document()], [share()], USERS, []))

    def unexpected_compute():
        raise AssertionError('A retry must not recalculate against partially published targets')

    assert checkpoint(path, 'delivery-1', unexpected_compute) == first
    second = checkpoint(path, 'delivery-2',
                        lambda: convert([], [], [], [], first['document'], first['doc_share']))
    assert second['metrics'][1]['rows_before'] == 1
    assert second['metrics'][1]['inserted_rows'] == 0
    assert checkpoint(path, 'delivery-2', unexpected_compute) == second


def test_share_output_port_truncates_after_uppercase():
    assert ports(share(access_level='ß' * 12), share=True)['access_level'] == 'SS' * 6
    result = convert([], [share(user_id=None)], [], [{'user_id': None, 'role_cd': 'ADMIN'}])
    assert result['doc_share'][0]['access_level'] == 'VIEW'


def test_checkpoint_corruption_fails_instead_of_recomputing(tmp_path):
    path = tmp_path / 'transaction.json'
    path.write_text('not json')
    with pytest.raises(ValueError):
        checkpoint(path, 'delivery', lambda: convert([], [], [], []))


def test_database_zero_byte_reject_is_observable():
    result = convert([document(document_name='bad\x00name')], [share(access_level='\x00')], USERS, [])
    assert [m['rejected_rows'] for m in result['metrics']] == [1, 0, 1]
    assert all(m['transformation_errors'] == 0 for m in result['metrics'])
    assert len(result['rejects']) == 2


def test_flatfile_reader_matches_quote_none_and_missing_fields(tmp_path):
    path = tmp_path / 'feed.psv'
    path.write_text('1|2|3|"view"|2026-11-09|ignored\n\n2|\n')
    rows = read_feed(path, SHARE)
    assert rows[0]['access_level'] == '"view"'
    assert rows[1]['document_id'] is None and rows[1]['shared_dt'] is None
    with pytest.raises(FileNotFoundError):
        read_feed(tmp_path / 'missing.psv', SHARE)


def test_informatica_graph_dependencies_and_distinct_models():
    nodes = {n['id']: n for n in load()['lakehouse_daily']['nodes']}
    assert set(nodes['documents_informatica']['depends_on']) == {'bronze_users', 'bronze_documents'}
    assert {'documents_informatica', 'bronze_users'} <= set(nodes['dbt_documents']['depends_on'])
    assert len(nodes['documents_informatica']['legacy_objects']) == 12


def test_postgres_reader_database_override(monkeypatch):
    observed = {}
    monkeypatch.setattr('lakehouse.parity.readers.psycopg.connect',
                        lambda dsn, **kwargs: observed.update(kwargs))
    postgres_connection('isolated-database')
    assert observed['dbname'] == 'isolated-database'
