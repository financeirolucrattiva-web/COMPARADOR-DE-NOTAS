from collections import Counter
from copy import deepcopy
from io import BytesIO
import json

from openpyxl import load_workbook
import pytest

import app as application
from comparator import compare


def note(doc, *, dominio=False, value='100.00', date='04/09/2026', identity='12345678000190'):
    return dict(cnpj=identity, documento=str(doc), valor=value, data_emissao=date,
                fornecedor='Fornecedor Exemplo', pagina=1, **({'especie':'66'} if dominio else {'modelo':'01'}))


def assert_conservation(rows, left, right):
    def counts(notes):
        return Counter(json.dumps(n, sort_keys=True) for n in notes)
    assert counts(n for row in rows for n in row['sped']) == counts(left)
    assert counts(n for row in rows for n in row['dominio']) == counts(right)


def test_annual_service_number_is_reconciled_and_originals_preserved():
    left, right = [note(2)], [note('2600000000002', dominio=True)]
    original = deepcopy((left,right))
    row, = compare(left,right)
    assert row['status'] == 'Conferente'
    assert row['correspondencia'] == 'sequencial_nfse'
    assert row['sped'][0]['documento']=='2'
    assert row['dominio'][0]['documento']=='2600000000002'
    assert (left,right)==original
    right[0]['valor']='100.01'
    row, = compare(left,right)
    assert row['status']=='Divergente' and row['diferencas']=='Valor'


@pytest.mark.parametrize('change', [dict(especie='58'), dict(documento='2500000000002'), dict(data_emissao='04/09/2025')])
def test_long_numbers_are_not_blindly_truncated(change):
    left, right = [note(2)], [note('2600000000002', dominio=True)]
    right[0].update(change)
    rows=compare(left,right)
    assert all(row['status']!='Conferente' for row in rows)
    assert all(row['correspondencia']!='sequencial_nfse' for row in rows)
    assert_conservation(rows,left,right)


def test_same_value_two_invoices_do_not_reuse_the_sped_note():
    left=[note(8)]
    right=[note('2600000000007',dominio=True),note('2600000000008',dominio=True)]
    rows=compare(left,right)
    matched,= [row for row in rows if row['status']=='Conferente']
    assert matched['dominio'][0]['documento']=='2600000000008'
    remaining,=[row for row in rows if row['status']=='Somente Domínio']
    assert remaining['dominio'][0]['documento']=='2600000000007'
    assert_conservation(rows,left,right)
    assert compare(left,list(reversed(right)))==rows


def test_different_number_is_one_document_divergence_not_two_absences():
    row,=compare([note(9)],[note(10,dominio=True)])
    assert row['status']=='Divergente' and row['diferencas']=='Documento'
    assert row['correspondencia']=='cnpj_valor_data'
    assert row['pendencias']


def test_ambiguous_equal_values_remain_for_review_without_forced_pairing():
    left=[note(9),note(11)]
    right=[note(10,dominio=True),note(12,dominio=True)]
    row,=rows=compare(left,right)
    assert row['status']=='Correspondência a revisar'
    assert len(row['sped'])==len(row['dominio'])==2
    assert_conservation(rows,left,right)


def test_one_note_cannot_choose_arbitrarily_between_two_equal_candidates():
    left=[note(9)]
    right=[note(10,dominio=True),note(11,dominio=True)]
    row,=rows=compare(left,right)
    assert row['status']=='Correspondência a revisar'
    assert len(row['sped'])==1 and len(row['dominio'])==2
    assert_conservation(rows,left,right)


def test_exact_matches_reserved_before_document_candidates_and_duplicates_not_reused():
    left=[note(8),note(9)]
    right=[note(8,dominio=True)]
    rows=compare(left,right)
    assert [r['status'] for r in rows]==['Conferente','Somente SPED']
    assert_conservation(rows,left,right)
    rows=compare(left+left[:1],[note('2600000000008',dominio=True)])
    assert any(r['status']=='Duplicidade / revisar' for r in rows)
    assert all(r['status']!='Conferente' for r in rows)
    assert_conservation(rows,left+left[:1],[note('2600000000008',dominio=True)])


@pytest.mark.parametrize('change',[dict(cnpj='98765432000110'),dict(data_emissao='05/09/2026'),dict(data_emissao=''),dict(valor='101.00')])
def test_value_alone_never_confirms_a_different_document(change):
    a,b=note(9),note(10,dominio=True)
    b.update(change)
    rows=compare([a],[b])
    assert {r['status'] for r in rows}=={'Somente SPED','Somente Domínio'}
    assert_conservation(rows,[a],[b])


def test_report_contains_both_original_numbers_and_number_difference(monkeypatch):
    rows=compare([note(9)],[note(10,dominio=True)])
    monkeypatch.setattr(application,'analyze',lambda:dict(rows=rows,warnings=[]))
    response=application.app.test_client().post('/exportar/xlsx')
    sheet=load_workbook(BytesIO(response.data)).active
    assert sheet['A2'].value=='Divergente'
    assert sheet['C2'].value=='SPED: 9\nDomínio: 10'
    assert sheet['D2'].value=='Número do documento'
