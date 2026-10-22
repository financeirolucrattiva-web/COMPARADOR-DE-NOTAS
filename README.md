# Comparador de notas · Lucrattiva

Aplicação web em português para comparar notas de entrada dos relatórios SPED e
Domínio. Confere **CNPJ/CPF, número do documento, fornecedor e valor**, identifica
ausências e duplicidades e gera Excel e PDF. Versão atual: **0.6.2**.

## Abrir no seu computador

1. Baixe o ZIP do repositório e extraia em uma pasta.
2. Tenha Python 3.12 ou superior instalado.
3. No Windows, abra **INICIAR_WINDOWS.bat**. No macOS/Linux, execute
   `python3 iniciar.py` na pasta extraída.
4. O inicializador instala as dependências e abre o navegador. Mantenha o terminal
   aberto durante o uso; Ctrl+C encerra o servidor.

A instalação das dependências precisa de Internet. Se o navegador não abrir, use
o endereço mostrado em **Endereço desta cópia**, no computador em que iniciou o
programa. A porta padrão é 5000; quando ocupada, outra porta livre é escolhida.
O navegador só abre depois de confirmar o identificador da nova execução, para
não mostrar uma cópia antiga do programa. O inicializador não encerra outros
programas. Se outro processo ocupar a porta escolhida antes da inicialização, a
falha será mostrada e a instância errada não será aberta.

Para atualizar, extraia o novo ZIP em outra pasta e execute o inicializador dessa
pasta. Confira **Versão 0.6.2** no topo da tela. Um endereço local não acessa o
ambiente na nuvem. Ainda não existe um site público desta aplicação.

## Como usar

- Selecione ou arraste um PDF em cada campo, da mesma empresa e período.
- **Conferir leitura SPED/Domínio** permite revisar um arquivo por vez: quantidade,
  páginas, total lido e lista de notas. Use a busca para localizar documentos,
  CNPJ/CPF com ou sem pontuação e fornecedores com ou sem acentos.
- **Comparar notas** fica disponível com os dois arquivos selecionados. O resultado
  abre em **Somente pendências**. Há filtros por situação e totais clicáveis.
- **Baixar Excel/PDF** inclui todas as notas da comparação, conforme indicado na
  tela. Os filtros mudam a visualização. O Excel também tem uma aba de avisos.
- **Usar exemplos** preenche os dois campos com dados fictícios, sem iniciar a
  comparação automaticamente. Os arquivos estão em `exemplos/`, com gabarito.

A tela mostra nomes completos, tamanhos, estado da leitura e tempo decorrido.
Trocar/remover um arquivo invalida o comparativo anterior. O resumo de uma origem
continua disponível quando a outra falha. Avisos de extração exigem revisão:
a soma das notas reconhecidas, sozinha, não garante cobertura do relatório inteiro.

## Relatórios suportados

PDFs com texto selecionável, até **200 páginas por arquivo** e **20 MB por envio**.
PDFs que são apenas imagens precisam de OCR, ainda não implementado. Outros
layouts podem precisar de adaptação com amostras.

### Livro de entradas SPED PVA

O leitor reconhece blocos com Data Entrada, Data emissão, Nr. Doc., Modelo, Série,
Situação, CNPJ/CPF e Razão social. Soma **Valor Operação** nas linhas fiscais do
mesmo documento, sem confundir base de cálculo e impostos. Mantém a continuidade
de notas e nomes entre páginas, exclui **RESUMO - TOTAIS** e detecta a orientação
dominante do texto. A correção de orientação ocorre em memória; o original não
é alterado. Um detalhe fiscal inválido impede usar um total parcial da nota.

### Acompanhamento de entradas Domínio

O relatório **ACOMPANHAMENTO DE ENTRADAS** pode não ter grade e pode sobrepor
visualmente Fornecedor, CNPJ/CPF e inscrição estadual. A extração comum mistura
os caracteres. O leitor usa os objetos de texto do PDF e o alinhamento dos
cabeçalhos, preservando os nomes completos; não usa coordenadas fixas de um cliente.

Nota e Série são separadas, inclusive série em branco, alfanumérica e números
longos. Código interno e nome do fornecedor são preservados separadamente.
Usa exclusivamente **Valor Contábil** da linha da nota. Totais diários, linhas
adicionais de impostos e Total Geral não são importados como outras notas.
A soma é conferida com **Total Geral**; ausência, diferença ou campos ambíguos
geram avisos. Nenhum campo ambíguo é escolhido automaticamente.

Quando disponível, a API e a tela informam se a soma coincide com o Total Geral.
Isso complementa a conferência de quantidade e conteúdo das notas.

### Tabelas e formato simples

Também reconhece tabelas com cabeçalhos explícitos CNPJ, NR. DOC./DOCUMENTO,
FORNECEDOR e VALOR, ou variantes documentadas no leitor, inclusive cabeçalhos
em até três linhas. Domínio tabular aceita Código Fornecedor e Valor Contábil.
Sem razão social, a conferência do nome fica pendente.

O formato de uma nota por linha, com quatro campos separados por `|` ou `;`,
continua disponível em PDFs com texto:

```text
12.345.678/0001-90 | 000123 | Empresa Exemplo LTDA | 1.250,00
```

## Regras da comparação

- Chave: **CNPJ/CPF + número**, ignorando zeros à esquerda no número.
- CNPJ de 14 dígitos e CPF de 11 dígitos são normalizados, sem validar dígitos
  verificadores. Formatos CEI/CAEPF não são homologados.
- Fornecedor ignora acentos, maiúsculas, pontuação, espaços extras e os sufixos
  terminais LTDA/LIMITADA. Apenas palavras inteiras no final são removidas;
  o restante do nome precisa coincidir. Um
  complemento entre parênteses no final de apenas um dos nomes é aceito quando
  a razão social principal coincide com o nome completo do outro arquivo. Dois
  complementos diferentes, mudanças na razão social e erros de digitação
  continuam sinalizados, mesmo com identificação e valor iguais. Não há
  aproximação por similaridade. Os nomes originais são preservados.
- Na tela, apenas nomes e valores divergentes são destacados. A coluna de
  diferenças identifica o nome do fornecedor ou o valor; os relatórios também
  explicitam que a diferença de fornecedor é no nome.
- Código interno do fornecedor aparece em uma linha separada na tela e nos
  relatórios e não entra na comparação. Nome ausente continua pendente.
- Valores usam Decimal e comparação exata em centavos. Retenções e diferenças
  entre valores líquidos e brutos não são compensadas automaticamente.
- Chave presente em apenas um arquivo aparece como ausência no outro. Não há
  pareamento aproximado por nome ou valor. Série não faz parte da chave atual.
- Registros duplicados são preservados e ficam para revisão; não são pareados
  ou removidos automaticamente.

## Validação realizada

Os dois PDFs reais enviados foram lidos sem avisos: **589 documentos SPED**
(39 páginas) e **591 Domínio** (12 páginas). Os 591 registros Domínio foram
conferidos individualmente contra o texto lógico: identificação, número, série,
fornecedor, códigos, datas e valor. A soma coincide com o Total Geral. O SPED
teve cada documento conferido contra uma leitura independente e seu resumo.

O comparativo real tem 602 chaves: 498 conferentes, 80 divergentes (78 de nome
e 2 de valor), 13 somente no Domínio e 11 somente no SPED. O fluxo completo foi
verificado no Chromium com esses arquivos, incluindo busca/filtros e downloads.
O Excel contém 602 documentos; as 602 situações também foram conferidas no PDF.
Os arquivos originais, notas, identificações, nomes e valores privados ficam
fora do checkout. Os testes publicados usam apenas dados fictícios.

## Desenvolvimento e testes

No ambiente na nuvem:

```bash
cd /workspace/COMPARADOR-DE-NOTAS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

O servidor de desenvolvimento usa porta 5000, sem debug. Para outro endereço
ou porta, use `COMPARADOR_HOST` e `COMPARADOR_PORT`. Não publicar dados reais em
instância pública sem autenticação, HTTPS e servidor de produção. Não há contas
ou histórico. PDFs/resultados são processados na requisição, sem armazenamento
permanente no servidor nem serviços externos de leitura.

```bash
.venv/bin/python -m pytest -q
```

Os testes cobrem extração, comparação, erros, duplicidades, exportações, CPF,
quatro orientações, continuidade de páginas, sobreposição de objetos e totais.
A simulação pública tem 100 registros SPED, 95 Domínio e 105 chaves. Para gerar
novamente: `.venv/bin/python scripts/gerar_exemplos.py`.

### Navegador (opcional)

`scripts/testar_interface.cjs` usa Node.js, Playwright e Chromium já instalados,
com dados fictícios. Verifica seleção, arrastar/soltar, remoção, exemplos, leitura,
busca, filtros, avisos, downloads e larguras móveis. Execute com a aplicação aberta:

```bash
COMPARADOR_TEST_URL=http://127.0.0.1:5000 node scripts/testar_interface.cjs
```

O pacote padrão é `playwright`; `PLAYWRIGHT_MODULE` permite selecionar outro
caminho de módulo compatível. `CHROMIUM_PATH` seleciona o executável, e
`COMPARADOR_UI_OUTPUT` a pasta temporária de capturas/relatórios. Playwright não
é necessário para usar a aplicação ou rodar os testes Python. O inicializador
Windows não foi executado neste ambiente Linux; sua rotina Python foi testada.

### API

`POST /conferir/sped` recebe o PDF no campo multipart `sped`;
`POST /conferir/dominio` usa o campo `dominio`. A resposta inclui `notes` e
`summary` com quantidade, páginas, total decimal em string, contagens CNPJ/CPF,
avisos e erro. Quando identificado, inclui `total_relatorio` e `total_confere`.
PDFs válidos sem notas retornam 422 com diagnóstico. `POST /comparar` recebe os
dois arquivos e preserva os resumos em `sources`, mesmo se uma origem falhar.
`POST /exportar/xlsx` e `/exportar/pdf` recebem os mesmos dois arquivos.
`GET /versao` informa versão e identificador da execução, sem credenciais.
