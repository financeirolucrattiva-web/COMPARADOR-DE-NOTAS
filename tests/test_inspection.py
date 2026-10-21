from io import BytesIO
from decimal import Decimal
import pytest
from app import app
from reportlab.pdfgen import canvas


def single_pdf(lines):
    stream=BytesIO()
    pdf=canvas.Canvas(stream)
    for index,line in enumerate(lines):
        pdf.drawString(30,800-index*20,line)
    pdf.save()
    stream.seek(0)
    return stream


def upload(lines):
    return (single_pdf(lines),'arquivo.pdf')


@pytest.mark.parametrize('source',['sped','dominio'])
def test_single_pdf_does_not_require_other_source(source):
    response=app.test_client().post('/conferir/'+source,data={source:upload(['12345678000190 | 1 | Empresa | 0,10','12345678909 | 2 | Pessoa Exemplo | 0,20'])})
    assert response.status_code==200
    result=response.json
    assert result['source']==source
    assert result['summary']==dict(quantidade=2,paginas=1,total='0.30',cnpj=1,cpf=1,warnings=[],error=None)
    assert len(result['notes'])==2
    assert result['notes'][1]['documento']=='2'
    assert response.headers['Cache-Control']=='no-store'


def test_unrecognized_pdf_retains_diagnostics():
    response=app.test_client().post('/conferir/sped',data={'sped':upload(['Arquivo com texto, sem notas reconheciveis'])})
    assert response.status_code==422
    result=response.json
    assert result['summary']['paginas']==1
    assert result['summary']['quantidade']==0
    assert result['summary']['warnings']
    assert result['notes']==[]
    assert result['error']


def test_comparison_error_keeps_successful_source_summary():
    response=app.test_client().post('/comparar',data={'sped':upload(['12345678000190 | 1 | Empresa | 100,50']),'dominio':upload(['Layout ainda nao reconhecido'])})
    assert response.status_code==422
    result=response.json
    assert result['sources']['sped']['quantidade']==1
    assert result['sources']['sped']['total']=='100.50'
    assert result['sources']['sped']['error'] is None
    assert result['sources']['dominio']['quantidade']==0
    assert result['sources']['dominio']['warnings']
    assert result['sources']['dominio']['error']


def test_invalid_first_pdf_does_not_hide_valid_second_pdf():
    response=app.test_client().post('/comparar',data={'sped':(BytesIO(b'bad'),'bad.pdf'),'dominio':upload(['12345678000190 | 1 | Empresa | 100,50'])})
    assert response.status_code==422
    assert response.json['sources']['sped']['error']
    assert response.json['sources']['dominio']['quantidade']==1
    assert response.json['sources']['dominio']['error'] is None


def test_inspection_rejects_missing_and_invalid_files():
    client=app.test_client()
    assert client.post('/conferir/sped').status_code==422
    assert client.post('/conferir/sped',data={'sped':(BytesIO(b'bad'),'bad.pdf')}).status_code==422
    assert client.post('/conferir/other').status_code==404


def test_sped_inspection_includes_tax_details_and_page_continuation():
    import runpy
    fixture=runpy.run_path('tests/test_sped_blocks.py')['sped_pdf']
    response=app.test_client().post('/conferir/sped',data={'sped':(fixture(270),'sped.pdf')})
    assert response.status_code==200
    result=response.json
    assert result['summary']['paginas']==3
    assert result['summary']['quantidade']==2
    assert result['summary']['total']=='1480.15'
    assert result['notes'][1]['paginas']==[1,2]
