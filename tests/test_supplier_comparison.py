from copy import deepcopy
from io import BytesIO

import pdfplumber
import pytest
from openpyxl import load_workbook

import app as application
from comparator import compare, supplier_matches


@pytest.mark.parametrize('left,right', [
    ('Empresa Exemplo LTDA.', 'EMPRESA EXEMPLO LTDA'),
    ('Ação, Comércio LTDA', 'acao comercio ltda.'),
    ('Exemplo S.A.', 'Exemplo SA'),
    ('Empresa Exemplo LTDA (LOJA EXEMPLO)', 'Empresa Exemplo LTDA'),
    ('Empresa Exemplo LTDA', 'Empresa Exemplo LTDA (LOJA EXEMPLO)'),
    ('Empresa Exemplo LTDA (LOJA) (CENTRO)', 'Empresa Exemplo LTDA.'),
])
def test_supplier_formatting_and_extra_trade_name(left, right):
    assert supplier_matches(left, right)
    assert supplier_matches(right, left)


@pytest.mark.parametrize('left,right', [
    ('Empresa Um LTDA', 'Empresa Dois LTDA'),
    ('Empresa Exemplo', 'Empresa Exemplo LTDA'),
    ('Empresa Exemplo 1', 'Empresa Exemplo 2'),
    ('Exempl LTDA (LOJA)', 'Exemplo LTDA'),
    ('Empresa Exemplo (CENTRO)', 'Empresa Exemplo (BAIRRO)'),
    ('Empresa (CENTRO) LTDA', 'Empresa LTDA'),
    ('Empresa (LOJA)', 'Empresa Outra'),
    ('(EMPRESA)', 'EMPRESA DIFERENTE'),
    ('...', ','),
    ('', ''),
])
def test_meaningful_name_changes_still_require_review(left, right):
    assert not supplier_matches(left, right)
    assert not supplier_matches(right, left)


def notes():
    base = dict(cnpj='12345678000190', documento='123', pagina=1, valor='340.00')
    return ([dict(base, fornecedor='Empresa Exemplo LTDA (LOJA EXEMPLO)')],
            [dict(base, fornecedor='Empresa Exemplo LTDA', codigo_fornecedor='0042')])


def test_internal_code_is_metadata_and_values_still_checked():
    left, right = notes()
    originals = deepcopy((left, right))
    assert compare(left, right)[0]['status'] == 'Conferente'
    assert (left, right) == originals  # Preserve the original names for review.
    right[0]['codigo_fornecedor'] = '9999'
    assert compare(left, right)[0]['status'] == 'Conferente'
    right[0]['valor'] = '339.99'
    row = compare(left, right)[0]
    assert row['status'] == 'Divergente' and row['diferencas'] == 'Valor'
    right[0]['fornecedor'] = ''
    right[0]['valor'] = '340.00'
    assert compare(left, right)[0]['status'] == 'Conferência parcial'


def test_exports_separate_code_from_preserved_name(monkeypatch):
    monkeypatch.setattr(application, 'analyze', lambda: dict(rows=compare(*notes()), warnings=[]))
    client = application.app.test_client()
    response = client.post('/exportar/xlsx')
    assert response.status_code == 200
    sheet = load_workbook(BytesIO(response.data)).active
    assert sheet['A2'].value == 'Conferente'
    assert sheet['E2'].value == 'Empresa Exemplo LTDA (LOJA EXEMPLO)'
    assert sheet['G2'].value == 'Empresa Exemplo LTDA\nCódigo interno: 0042'
    assert sheet['G2'].alignment.wrap_text
    response = client.post('/exportar/pdf')
    assert response.status_code == 200
    with pdfplumber.open(BytesIO(response.data)) as pdf:
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    assert 'Conferente' in text and 'Código interno: 0042' in text
