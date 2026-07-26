# market-scan-2026

Piloto isolado de extração de dados públicos do PNCP (Portal Nacional de
Contratações Públicas) para montar um "market scan" — descobrir nichos de
mercado (produto ou serviço) com alto volume financeiro e baixa concentração
de fornecedores vencedores, usando a hierarquia oficial CATMAT (produto) /
CATSER (serviço): Grupo → Classe → PDM → Item.

## Isolamento (requisito não-negociável)

Projeto totalmente separado do LICIT (vertical pneu/onco, `C:\Users\ghumb\code\licit`):

- Repositório Git próprio, não subpasta nem branch do repo licit.
- Projeto Supabase próprio (`market-scan-2026`, `sa-east-1`, free tier) — sem
  tabela, schema, credencial ou `DATABASE_URL` compartilhada com o licit.
- `.env` próprio, nunca copiado do `.env` do licit.
- Nenhuma escrita/leitura/dependência de runtime no repo ou banco do licit.
  Código de referência (rate limiting, paginação, tratamento de erro) pode
  ter sido inspirado nos scripts do licit (`analise/coletor_pncp.py`,
  `analise/coletor_pncp_detalhe.py`) mas foi escrito do zero aqui, sem
  import nem path compartilhado.

## Escopo do piloto

| Parâmetro | Valor |
|---|---|
| UF | RJ (piloto original); expandido pro resto do Brasil (26 UFs restantes) 25/jul/2026, "se sobrar tempo" dentro da janela de 4h da sessão — ver `rodar_resto_brasil.py` |
| Período | 01/01/2026 a 31/01/2026 |
| Status | só itens com resultado HOMOLOGADO |
| Tipo | produto (CATMAT) e serviço (CATSER), ambos |
| Piso de valor | nenhum — o piloto serve pra decidir esse piso depois, com dado real |

Objetivo do piloto: validar viabilidade técnica (endpoint certo, rate
limit contra o WAF, tempo de execução) e viabilidade do dado (cobertura real
do campo de classificação oficial) antes de qualquer extração nacional/anual.

## Achados da verificação de API (antes de escrever o script)

- **Busca por data/UF** — `GET /api/consulta/v1/contratacoes/publicacao`,
  documentado no swagger oficial (`https://pncp.gov.br/api/consulta/swagger-ui/index.html`).
  `dataInicial`/`dataFinal`/`uf` são honrados pela API (confirmado ao vivo —
  diferente do endpoint interno de busca que o licit usa pra pneu, que ignora
  filtro de data). `codigoModalidadeContratacao` é **obrigatório**, não existe
  "todas modalidades" — testados ao vivo os códigos 1-14 pra RJ/jan-2026,
  todos válidos (200 ou 204, nenhum 400 recebido); script varre os 14.
- **Itens** — `GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens`. Não
  está no swagger oficial de consulta (só o nível "contratação" está
  documentado formalmente) — mas já validado em produção há meses no licit.
  `materialOuServico` (`"M"`/`"S"`) mapeia direto pro `tipo` produto/serviço.
- **Status homologado (nível item)** — `situacaoCompraItemNome == "Homologado"`.
- **Resultado (fornecedor/valor homologado)** — mesma base de
  `api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{n}/resultados` usada
  pelo licit.
- **Campo de classificação CATMAT/CATSER** — candidatos `catalogo` /
  `categoriaItemCatalogo` / `catalogoCodigoItem` no payload de item. Testados
  ao vivo 5 itens reais de 3 processos diferentes (pneu/moto, licença de
  software, brigadista): **100% null**. O próprio `analisa_edital.py` do
  licit já tinha essa lição — extrai CATMAT do texto do PDF via Claude
  porque não confia no campo estruturado da API (`analisa_edital.py`, campo
  `catmat` do prompt: "se não encontrar, use ''"). Decisão consciente
  (25/jul/2026): gravar os 3 campos como vierem da API (sem LLM no loop,
  fora do escopo do piloto) e medir a cobertura real na validação — ver
  seção "Resultado do piloto" abaixo.

## Estrutura

```
market-scan-2026/
├── extract_pncp.py       Script de extração — busca (14 modalidades) → itens → resultado
│                          → filtra homologado → grava itens_pncp (raw_json completo)
├── requirements.txt       requests, psycopg2-binary, python-dotenv
├── .env                   DATABASE_URL do Supabase deste projeto (gitignorado)
└── .gitignore              .env, __pycache__/, *.pyc, raw_cache/
```

## Setup

```bash
pip install -r requirements.txt
# .env: DATABASE_URL=postgresql://...pooler.supabase.com:6543/postgres (transaction pooler)
python extract_pncp.py
```

## Resultado do piloto

**Rodada 25/jul/2026** (RJ, 01/01/2026-31/01/2026, 2.715 contratações inspecionadas):

- **Tempo total:** 81min a rodada final (fase 2 sozinha, já com ~1.900/2.715
  puladas por resumibilidade) — 5h04 no total contando a 1ª rodada que
  crashou na volta ~1.900/2.715 (bug de tipo, ver "Achados" abaixo) + fix +
  restart.
- **Volume:** 5.856 linhas (item × resultado homologado) — 3.649 produto
  (850 editais distintos) + 2.207 serviço (1.308 editais distintos).
- **Cobertura do campo de classificação oficial (`codigo_catalogo`):**
  9/5.856 = **0,2%**. Confirma em escala real o achado da amostra de 5 itens
  (100% null) — campo estruturado do PNCP é essencialmente inexistente,
  mesmo em processo real homologado. **Fecha as rotas 2 e 4** da tabela de
  opções de classificação de nicho (cruzar com catálogo oficial / usar só
  subset com catálogo preenchido) — não sobra base suficiente pra nenhuma
  das duas. Seguem viáveis: regex por nicho conhecido (1), LLM por item (3),
  clustering de texto (5).
- **Distribuição de valor homologado:** mediana R$ 8.999,55, p90 R$ 300.000,
  p99 R$ 8.694.925, máximo R$ 282.449.860,02, soma total **R$ 3,16 bi**.
- **Bug achado e corrigido:** `catalogo`/`categoriaItemCatalogo`/
  `catalogoCodigoItem` às vezes vêm como objeto `{"codigo":.., "nome":..}`
  (mesmo padrão de outros campos categóricos do PNCP), não só string/null —
  psycopg2 não adapta dict direto numa coluna `text`, quebrou o piloto na
  contratação ~1.900/2.715. Fix: serializa como JSON se vier objeto (ver
  `codigo_catalogo_de()` em `extract_pncp.py`). Junto com o fix, script
  ganhou resumibilidade (pula contratação já gravada, checando
  `processo_pncp` antes de chamar a API de novo) — sem isso, rerodar depois
  do crash teria duplicado as ~1.900 já processadas.

**Classificação de nicho — rodada 25/jul/2026 (zero custo, sem API paga):**

Decisão: já que 3.955 descrições distintas era demais pra classificar item a
item manualmente, e classificador LLM pago ficou travado por resposta
contraditória do usuário (regra "jamais custo sem aprovação"), rodou-se
clustering de texto (TF-IDF + KMeans, `clusterizar_nicho.py`) — zero custo,
sem chamada de API. 1ª tentativa (30 clusters, stopwords básicas) deu um
cluster genérico com 88% dos itens (boilerplate administrativo dominava a
distância TF-IDF). 2ª tentativa (80 clusters, stopwords ampliadas pra
boilerplate tipo "contratação"/"empresa especializada"/"prestação de
serviços") melhorou pra 77% no cluster genérico — o resto (1.318 itens, 23%)
segmentou em 79 nichos específicos, nomeados manualmente (nesta sessão, sem
LLM pago) a partir dos termos-top e amostras de cada cluster. Cluster
genérico não é bug — é estrutural: a maioria das descrições de obra/serviço
é heterogênea de verdade e não compartilha vocabulário suficiente pra
TF-IDF separar sem embeddings ou classificação item a item.

**Achado de valor:** "Serviço de engenharia (genérico)" (24 itens, R$ 401mi)
e "Obras civis públicas" (29 itens, R$ 300mi) têm razão valor/item muito
alta — candidatos a nicho de alto volume financeiro, bate com o objetivo
original do piloto (ver topo do documento).

**Pendente, não rodado nessa sessão:**
- Segmentar melhor o cluster genérico (77%, R$ 2,08bi) — precisa de LLM por
  item ou embeddings semânticos, não TF-IDF puro.
- Classificador de nicho via LLM pago (Claude Haiku) — decisão do usuário
  ficou contraditória, não rodado por segurança (regra "jamais custo sem
  aprovação"). Zero-custo (clustering) cobriu a demanda desta sessão.
- Extração pro resto do Brasil (26 UFs restantes, jan/2026) — script pronto
  (`rodar_resto_brasil.py`), não rodou por estourar o teto de horário da
  sessão (RJ sozinho já passou de 4h por causa do crash).
