# Achados — classificação item a item (Fase 0)

Atualizado no lote 130 (itens 1-3250 classificados, 55,5% de 5.856).

## Metodologia
Dupla passada (passada1_categoria/passada2_categoria) por item, gravado em `gabarito_nicho`
(Supabase `qmqcagnmgjxglxbxozlx`), lotes de 25, zero custo (raciocínio inline, sem LLM pago).
`inseguranca=true` quando as passadas divergem ou bate critério de ambiguidade (ver regras
sistêmicas abaixo).

## Nichos fortes (candidatos a "onde entrar")

Ordenados por confiança de sinal (volume × valor × consistência), não por valor bruto:

1. **Dispositivos Médicos de Altíssimo Ticket** — implantes, próteses, cateteres, equipamento
   de centro cirúrgico. Nicho #1 desde o início, consistente em volume e valor.
2. **Pneu Automotivo/Caminhão** — validação direta da tese do LICIT. Itens 2838-2840 têm
   linguagem de edital (certificação INMETRO/IBAMA, marcas Pirelli/Goodyear/Firestone/Michelin,
   garantia 5 anos) quase idêntica ao que o LICIT já vende.
3. **Transporte Escolar** — consolidado.
4. **Ferramentas Industriais/Usinagem** — consolidado.
5. **Equipamento Audiovisual/Fotográfico** — muito forte: projetor, tela retrátil, câmera
   broadcast 4K60, microfone lapela sem fio, gravador de áudio, cartão SD, mais linha completa
   de som/palco em processos de eventos municipais.
6. **Drone/VANT** — DJI Matrice 350 RTK LiDAR (R$144.999,99), DJI Mavic 4 Pro (R$22.800).
7. **Energia Solar Completa** — cabo solar + conector MC4 + kits de fixação por tipo de
   telhado (fibrocimento/metálico/colonial/laje). Nicho B2B bem definido.
8. **Insumos Químicos/Laboratoriais** — muito forte e heterogêneo: reagentes de produção
   farmacêutica federal, kits de biologia molecular/genômica (Qiagen, Sigma, GE/Cytiva,
   colunas cromatográficas, lâminas de microdissecção a laser), microbiologia (LAL, ATCC,
   ágar, caldos), equipamento de bancada (microscópio, balança de precisão).
9. **Material de Limpeza** — muito forte, inclui linha de marca completa (Granado, Proderm,
   Off, Johnson's, Huggies, Colgate) em contexto de higiene infantil/geriátrica.
10. **Construção Civil** — muito forte: cimento, areia, brita, tinta, hidráulico, massa
    corrida, argamassa, demolição, série completa "aquisição de X (anexo I do edital)".
11. **Saúde/Farmacêutico** e **Saúde/Hospitalar** — pilares recorrentes em quase todo
    município, séries completas de medicamentos/insumos.
12. **Serviços/Postos de Trabalho Terceirizados** — muito forte: cozinheiro, magarefe,
    auxiliar de cozinha, técnico de nutrição, copeiragem — staffing hospitalar/municipal
    recorrente em múltiplos processos do mesmo órgão.
13. **TI/Software (licenciamento)** — Microsoft Enterprise (M365 E5 R$44,97mi sozinho,
    Copilot, Entra, Intune, Project, Visio, Power Automate — subtotal ~R$63mi num único
    processo), Windows Server, HikCentral/Hikvision (CFTV), SaaS diversos.
14. **Serviços Gráficos/Impressão** — forte, série completa de impressão de livro/revista
    por faixa de páginas no mesmo processo, somando centenas de milhares de reais.

## Guarda-chuvas / valores extremos (contratos-mega, não são nicho de produto)
- Item 2326 "Serviço Engenharia": **R$282.449.860,02** — valor máximo de todo o dataset.
- Item 3144 "Serviços acessórios administração/RH/financeiro": **R$34.130.448,31**.
- Item 3028/3029 "Médicos de urgência/emergência" + "Serviços médicos especializados":
  R$8.491.060,80 + R$8.650.066,40.
- Item 3089 "Tratamento de resíduos sólidos urbanos" (RSU, Rio das Ostras): R$13.884.306,54.
- Item 2198 "Instalação tubulações industriais": R$99,8mi.
- Item 2185 "Monitor Imagem": R$11,3mi.
- Item 2890 Locação equipamento TIC+notebooks+nobreaks+antivírus NGAV (consórcio
  intermunicipal CIDENNF): R$20.134.808,76.

## Taxonomia completa (categoria_ampla), ~90 categorias
Dispositivos Médicos, Pneu Automotivo/Caminhão, Transporte Escolar, Ferramentas Industriais,
Kit Lanche Escolar, Equipamento Audiovisual/Fotográfico, Drone/VANT, Radiofármacos, CME,
Farmacologia Veterinária, Buffet/Eventos, Emulsão Asfáltica, Aulas Esportivas, Vigilância
Patrimonial/Orgânica, Braquete Ortodôntico, Psiquiátricos/Controlados, Estomia/Curativos,
Copa/Cozinha, Dieta Infantil, Anestésicos Odontológicos, Transporte Marítimo/Fluvial,
Neurológicos/Alzheimer, Brindes/Produtos Promocionais, Construção Civil, Manutenção
Industrial, Mobiliário Hospitalar, Fralda Descartável, Cortes Bovinos/Aves Nobres, Energia
Solar Completa, Kit Enxoval/Puericultura, Saúde/Farmacêutico, Saúde/Hospitalar, Insumos
Químicos/Laboratoriais, Serviços/Limpeza e Conservação, Equipamento de Eventos/Palco/
Sonorização, Saneamento/Tratamento de Água, Material de Limpeza, TI/Software, Equipamento
Aeroportuário/Controle de Tráfego Aéreo, Serviços/Locação de Veículos, Saúde/Serviços
Médicos, Serviços/Arquitetura e Engenharia, Serviços Gráficos/Impressão, TI/Acessórios,
Saúde/Diagnóstico Laboratorial, TI/Hardware, Decoração Temática/Personagens, Equipamento
Têxtil/Costura Industrial, Fomento a Micro-Empreendedorismo, Mobiliário/Equipamento de
Comércio, Serviços/Brigada de Incêndio, Serviços/Gestão de Resíduos Sólidos, Equipamento
de Construção/Locação de Máquinas Pesadas, Equipamento HVAC/Climatização, Peças e
Implementos Agrícolas, Mobiliário/Decoração de Interiores, Serviços/Assinaturas e
Publicações, Frota Municipal/Peças e Acessórios de Veículos, EPI, Combustíveis, TI/
Suprimentos de Impressão, TI/Telecomunicações, Serviços/Manutenção de Veículos,
Equipamento Veterinário, Serviços/Inspeção e Laudo Técnico, Manutenção Predial/Elevadores,
Manutenção Predial/Instalações Elétricas, Serviços/Terceirização Administrativa, Serviços/
Postos de Trabalho Terceirizados, Saúde/Radiologia e Imagem, Controle de Pragas,
Equipamento de Metrologia/Aferição, Uniformes/Vestuário Profissional, Saúde/Vigilância
Nutricional, Serviços/Recrutamento e Seleção, Serviços/Logística e Distribuição,
Equipamento de Segurança/Cofres, TI/Serviços de Rede, Indefinido/Não Classificável.

## Regras sistêmicas (aplicadas em toda classificação)
1. Boilerplate recorrente ("Serviço Engenharia", "de acordo com edital", "os serviços a
   serem executados pela empresa contratada") sem especificação real do objeto →
   `Indefinido/Não Classificável`, `inseguranca=true`.
2. `tipo` (produto/servico) às vezes vem errado na fonte — classificar pelo conteúdo real
   da descrição, não pelo campo.
3. Gatilhos de `inseguranca=true`: `valor_suspeito=true`, item de SRP com valor
   simbólico/zero, valor isolado atipicamente alto ou genérico, sigla ambígua sem
   contexto, valor idêntico repetido no mesmo processo (mesmo em qualquer faixa de valor),
   descrição vazia de conteúdo real, descrição truncada, convênio/termo de colaboração
   (não é compra convencional).
4. Cruzamento órgão/processo resolve ambiguidade — inclusive **retroativamente**: item
   isolado e ambíguo pode ser resolvido quando o MESMO PROCESSO reaparece em lote
   posterior com mais contexto (ex.: item 2575 "Botão comando" precisa harmonizar com
   2576/2578 do mesmo processo, que revelaram contexto industrial/elétrico).
5. `revendavel`: `nao` para quase todo serviço puro; `talvez` quando ambíguo (kit sem
   itemização, decoração temática pode ou não interessar a um comprador de nicho).
6. Órgãos dominantes no dataset: `42498600000171` (megaórgão — hub de TI, laboratório,
   audiovisual, impressão gráfica, postos de trabalho terceirizados); `29116902000170`
   (município com programa forte de fomento a pequenos negócios/eventos/decoração);
   `09206510000194` (secretaria de saúde — uniformes ACS, laboratório, material elétrico,
   construção civil, vigilância nutricional); `02385669000174` (pesquisa/biologia
   molecular); `11800731000138` (linha completa de óleos/fluidos automotivos).

## Pendências para revisão (Fase de revisão de inseguros)
Lista integral de IDs/processos flagados `inseguranca=true` ou marcados para revisão
cruzada, acumulada desde o lote 1 até o lote 130 (itens 149 até 3244). Ver histórico
completo na tabela `gabarito_nicho` via:

```sql
select id_item, categoria_ampla, nicho_especifico, motivo_inseguranca
from gabarito_nicho
where inseguranca = true
order by id_item;
```

Pontos específicos que precisam de harmonização manual na revisão (não apenas
"olhar de novo"):
- **Item 2575** "Botão comando" — reclassificar pra bater com 2576/2578 (mesmo processo,
  contexto industrial/elétrico revelado depois).
- **Itens 2964-2966** "Tipo: Bruta, Granulometria: N/D" (R$4-8mi cada, órgão
  42498600000171) — descoberta o que é de fato (nome do produto não aparece na descrição).
- **Itens 3001-3004** "R-AFIS" (NAV Brasil) — descrição críptica, só localização, não diz
  o que é fornecido.

## Progresso
- Itens 1-3250 classificados (130 lotes de 25).
- 55,5% do total (5.856).
- Continua automaticamente até esgotar, depois revisão de inseguros, depois revisão geral.
