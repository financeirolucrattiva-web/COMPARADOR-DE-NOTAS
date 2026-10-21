from io import BytesIO
from decimal import Decimal
import pytest
import pypdfium2 as pdfium
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak
from comparator import extract_pdf

DOCUMENT_HEADERS = ['Data Entrada','Data emissão','Nr. Doc.','Modelo',None,'Série',None,'Subsérie',None,'Situação',None,'CNPJ/CPF',None,'IE',None,'UF','Município',None,'Razão social',None]
TAX_HEADERS = [None,None,'CST/ICMS',None,'CFOP',None,'Alíquota ICMS',None,'Valor Operação',None,'Base de Cálculo ICMS',None,'Valor ICMS',None,'Base de Cálculo',None,'Valor ICMS ST','Valor IPI',None,'Redução da Base de Cálculo']


def document(number, identity, supplier):
    row=[None]*20
    for index,value in [(0,'01/09/2026'),(1,'01/09/2026'),(2,str(number)),(3,'55'),(5,'1'),(9,'00'),(11,identity),(15,'MT'),(16,'Cidade Exemplo'),(18,supplier)]:
        row[index]=value
    return row


def detail(amount, cfop='1102'):
    row=[None]*20
    for index,value in [(2,'040'),(4,cfop),(6,'0,00'),(8,amount),(10,'0,00'),(12,'0,00'),(14,'0,00'),(16,'0,00'),(17,'0,00'),(19,'0,00')]:
        row[index]=value
    return row


def table(rows):
    value=Table(rows,colWidths=[50]*20,rowHeights=35)
    value.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,'black'),('FONTSIZE',(0,0),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    return value


def sped_pdf(rotation=0, invalid=False):
    continuation=[None]*20;continuation[18]='CONTINUAÇÃO\nLTDA'
    summary=['RESUMO - TOTAIS']+[None]*19
    bad=detail('inválido' if invalid else '200,00')
    story=[table([DOCUMENT_HEADERS,TAX_HEADERS,document(10,'12.345.678/0001-90','Fornecedor\nExemplo'),detail('1.000,00'),detail('250,15','2102'),document(20,'123.456.789-09','Pessoa Exemplo')]),PageBreak(),table([DOCUMENT_HEADERS,TAX_HEADERS,continuation,bad,detail('30,00'),summary,detail('99.999,99')]),PageBreak(),table([DOCUMENT_HEADERS,TAX_HEADERS,summary,detail('99.999,99')])]
    stream=BytesIO()
    SimpleDocTemplate(stream,pagesize=(1100,800),leftMargin=30,rightMargin=30,topMargin=30,bottomMargin=30).build(story)
    if rotation:
        with pdfium.PdfDocument(stream.getvalue()) as pdf:
            for page in pdf:
                page.set_rotation(rotation);page.close()
            output=BytesIO();pdf.save(output)
        stream=output
    stream.seek(0)
    return stream


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_sped_blocks_are_merged_across_pages_and_rotations(rotation):
    stream=sped_pdf(rotation)
    original=stream.getvalue()
    notes,warnings=extract_pdf(stream)
    assert stream.getvalue()==original
    assert not warnings
    assert len(notes)==2
    assert [n['documento'] for n in notes]==['10','20']
    assert [n['valor'] for n in notes]==['1250.15','230.00']
    assert notes[0]['linhas_fiscais']==2
    assert notes[1]['tipo_identificacao']=='CPF'
    assert notes[1]['fornecedor']=='Pessoa Exemplo CONTINUAÇÃO LTDA'
    assert notes[1]['paginas']==[1,2]
    assert all(n['serie']=='1' for n in notes)


def test_invalid_detail_prevents_incorrect_partial_total():
    notes,warnings=extract_pdf(sped_pdf(invalid=True))
    assert len(notes)==1 and notes[0]['documento']=='10'
    assert any('total parcial não utilizado' in w for w in warnings)
