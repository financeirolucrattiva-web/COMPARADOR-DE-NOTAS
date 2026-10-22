from io import BytesIO
from decimal import Decimal
import pytest
from reportlab.pdfgen import canvas
from comparator import extract_pdf, compare
from app import app


def domain_pdf(scale=1, translation=0, ambiguous=False, total='1000,00', no_total=False):
    """Fictitious vector text objects with deliberate overlap and no table grid."""
    out=BytesIO();pdf=canvas.Canvas(out,pagesize=(1000,650));pdf.translate(translation,0);pdf.scale(scale,scale)
    pdf.setFont('Helvetica',6)
    pdf.drawString(10,600,'ACOMPANHAMENTO DE ENTRADAS')
    headers=[('Código',20,'right'),('Data Emissão',50,'center'),('Data Entrada',110,'center'),('Nota',180,'right'),('Série',185,'left'),('Espécie',235,'right'),('Código',265,'right'),('Fornecedor',270,'left'),('CNPJ/CPF/CEI/CAEPF',310,'left'),('Valor Contábil',520,'right'),('Tipo',525,'left'),('Valor',620,'right')]
    def draw(text,x,y,alignment):
        method={'left':pdf.drawString,'right':pdf.drawRightString,'center':pdf.drawCentredString}[alignment]
        method(x,y,text)
    for text,x,alignment in headers:draw(text,x,560,alignment)
    records=[('1001','123','11','36','90','FORNECEDOR COM NOME MUITO LONGO SOBRE AS COLUNAS','12.345.678/0001-90','100,00'),('1002','2600000000002','','66','36','12 EMPRESA EXEMPLO','23.456.789/0001-01','200,00'),('1003','7','U','66','88','PESSOA EXEMPLO','123.456.789-09','300,00'),('1004','8','920','36','66','FORNECEDOR MODELO','34.567.890/0001-12','400,00')]
    for index,(code,note,series,species,supplier_code,supplier,identity,amount) in enumerate(records):
        y=530-index*30
        draw('1',0,y-.54,'left')  # Decorative mark; not part of the record code.
        for field,x,alignment in [(code,20,'right'),('01/09/2026',50,'center'),('02/09/2026',110,'center'),(note,180,'right'),(series,185,'left'),(species,235,'right'),(supplier_code,265,'right'),(supplier,270,'left'),(identity,310,'left'),(amount,520,'right'),('ICMS',525,'left'),('99,99',620,'right')]:
            if field:draw(field,x,y,alignment)
        if ambiguous and index==0:draw('111,11',520,y,'right')
    draw('Total Dia',430,395,'left');draw('1000,00',520,385,'right')
    # A tax-only continuation is not another note or an additional total.
    draw('ICMS',525,375,'left');draw('99,99',620,375,'right')
    if not no_total:
        draw('Total Geral',430,350,'left');draw(total,520,340,'right')
        draw('IRRF',525,325,'left');draw('10,00',620,325,'right')
    pdf.save();out.seek(0);return out


@pytest.mark.parametrize('scale,translation',[(1,0),(.85,60),(1.1,10)])
def test_dominio_objects_preserve_overlapping_fields_and_separate_note_series(scale,translation):
    stream=domain_pdf(scale,translation);original=stream.getvalue();metadata={}
    notes,warnings=extract_pdf(stream,metadata)
    assert stream.getvalue()==original
    assert warnings==[] and len(notes)==4
    assert metadata['total_declarado']=='1000.00'
    assert metadata['documentos_identificados']==4
    assert [n['documento'] for n in notes]==['123','2600000000002','7','8']
    assert [n['serie'] for n in notes]==['11','','U','920']
    assert [n['valor'] for n in notes]==['100.00','200.00','300.00','400.00']
    assert notes[0]['fornecedor']=='FORNECEDOR COM NOME MUITO LONGO SOBRE AS COLUNAS'
    assert notes[1]['codigo_fornecedor']=='36' and notes[1]['fornecedor']=='12 EMPRESA EXEMPLO'
    assert notes[2]['tipo_identificacao']=='CPF'
    assert sum((Decimal(n['valor']) for n in notes),Decimal(0))==Decimal('1000.00')


def test_ambiguous_amount_is_not_silently_selected():
    notes,warnings=extract_pdf(domain_pdf(ambiguous=True))
    assert len(notes)==3
    assert all(n['documento']!='123' for n in notes)
    assert any('ambígua' in w for w in warnings)
    assert any('difere do Total Geral' in w for w in warnings)


def test_missing_or_different_report_total_requires_review():
    notes,warnings=extract_pdf(domain_pdf(no_total=True))
    assert len(notes)==4 and any('não identificado' in w for w in warnings)
    notes,warnings=extract_pdf(domain_pdf(total='999,00'))
    assert len(notes)==4 and any('difere do Total Geral' in w for w in warnings)


def test_dominio_api_reports_independent_total_and_compares_supplier_names():
    client=app.test_client()
    response=client.post('/conferir/dominio',data={'dominio':(domain_pdf(),'dominio.pdf')})
    assert response.status_code==200
    assert response.json['summary']['quantidade']==4
    assert response.json['summary']['total_relatorio']=='1000.00'
    assert response.json['summary']['total_confere'] is True
    notes=response.json['notes']
    sped=[dict(n) for n in notes]
    assert all(row['status']=='Conferente' for row in compare(sped,notes))
    notes[0]['fornecedor']='Nome diferente'
    assert next(r for r in compare(sped,notes) if r['documento']=='123')['diferencas']=='Fornecedor'
    response=client.post('/conferir/dominio',data={'dominio':(domain_pdf(total='999,00'),'dominio.pdf')})
    assert response.json['summary']['total_confere'] is False
    assert response.json['summary']['warnings']
