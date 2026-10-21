from io import BytesIO
from decimal import Decimal
import pytest
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from openpyxl import load_workbook
from app import app
from comparator import parse_table, compare, parse_text

HEADERS = ['Código', 'Data Emissão', 'Data Entrada', 'Nota Série', 'Espécie', 'Código Fornecedor', 'CNPJ/CPF/CEI/CAEPF I', 'Insc. Est.', 'CFOP', 'AC. UF', 'Valor Contábil Tipo', 'Base Cálculo', 'Alíq.', 'Valor', 'IPI', 'Sub. Trib', 'Isentas', 'Outras']
ROW = ['1','01/10/2026','02/10/2026','000123 1','NF','00042','12.345.678/0001-90','123456','1102','MT','1.234,56 1','1.000,00','12,00','120,00','5,00','10,00','20,00','30,00']


def make_pdf(rows, width=1500):
    out = BytesIO()
    table = Table(rows, colWidths=[width/len(rows[0])]*len(rows[0]))
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,'black'),('FONTSIZE',(0,0),(-1,-1),6)]))
    SimpleDocTemplate(out,pagesize=(width+60,500),leftMargin=30,rightMargin=30,topMargin=30,bottomMargin=30).build([table])
    out.seek(0)
    return out


def test_domain_columns_do_not_use_tax_or_internal_code_as_name():
    notes, warnings, recognized = parse_table([HEADERS,ROW],1)
    assert recognized and not warnings
    note = notes[0]
    assert note['valor'] == '1234.56'  # Not ICMS 120.00 / base 1000.00 / IPI 5.00.
    assert note['documento'] == '123'
    assert note['serie'] == '1'
    assert note['codigo_fornecedor'] == '00042'
    assert note['fornecedor'] == ''
    sped,_ = parse_text('12345678000190 | 123 | Empresa Exemplo | 1.234,56',1)
    result=compare(sped, notes)[0]
    assert result['status']=='Conferência parcial'
    assert result['diferencas']==''
    assert result['pendencias']
    notes[0]['valor']='1234.55'
    result=compare(sped,notes)[0]
    assert result['status']=='Divergente' and result['diferencas']=='Valor'
    assert result['pendencias']


def test_multiline_headers_and_separate_type_column():
    table=[['CNPJ/CPF/CEI/CAEPF','Nota','Código','Valor','Tipo','Valor'],['I','Série','Fornecedor','Contábil','',''],['12345678000190','123/1','42','1.234,56','1','120,00']]
    notes,warnings,recognized=parse_table(table,2)
    assert recognized and not warnings
    assert notes[0]['valor']=='1234.56'
    assert notes[0]['serie']=='1'


def test_sped_operation_total_takes_precedence_over_tax_value():
    table=[['CNPJ/CPF','Nº Doc.','Nome/Razão Social','Valor da Operação','Valor'],['12345678000190','123','Empresa Exemplo','1.234,56','120,00']]
    notes,warnings,recognized=parse_table(table,1)
    assert recognized and not warnings
    assert notes[0]['documento']=='123'
    assert notes[0]['fornecedor']=='Empresa Exemplo'
    assert notes[0]['valor']=='1234.56'


def test_real_pdf_domain_layout_and_exports_with_partial_supplier_check():
    client=app.test_client()
    def payload():
        return {'sped':(make_pdf([['CNPJ','NR. DOC.','FORNECEDOR','VALOR'],['12345678000190','123','Empresa Exemplo','1.234,56']],800),'sped.pdf'), 'dominio':(make_pdf([HEADERS,ROW]),'dominio.pdf')}
    response=client.post('/comparar',data=payload())
    assert response.status_code==200
    data=response.json
    assert data['counts']==[1,1]
    assert data['rows'][0]['status']=='Conferência parcial'
    assert data['warnings'] and 'razão social' in data['warnings'][0]
    response=client.post('/exportar/xlsx',data=payload())
    assert response.status_code==200
    sheet=load_workbook(BytesIO(response.data)).active
    assert sheet['A2'].value=='Conferência parcial'
    assert '00042' in sheet['G2'].value
    assert 'fornecedor' in sheet['I2'].value
    response=client.post('/exportar/pdf',data=payload())
    assert response.status_code==200 and response.data.startswith(b'%PDF-')


@pytest.mark.parametrize('invalid_identity',['123456789012','CEI12345678',''])
def test_non_cnpj_identifiers_are_flagged_instead_of_compared(invalid_identity):
    row=ROW.copy();row[6]=invalid_identity
    notes,warnings,recognized=parse_table([HEADERS,row],1)
    assert recognized and not notes and warnings
