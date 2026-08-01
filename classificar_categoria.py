"""Mapeador de categoria (desc_norm -> categoria), reconstruido do zero em
31/jul/2026 porque a versao anterior nunca foi salva em arquivo (so rodou
ad-hoc via Supabase MCP em sessoes passadas). Segue os 7 principios
documentados em achados_nicho.md (ancora de fim de palavra, sufixo composto
em vez de curto, modificador de dominio pra palavra ambigua, sinonimo
completo, cobertura de variacao de wording, validacao em populacao
completa). Roda 100% local (DuckDB) -- sem timeout de Supabase MCP.
"""
import re
import time
import duckdb

DB_PATH = "market_scan_local.duckdb"

# ---- Servico / exclusao (roda ANTES de qualquer categoria de produto) ----
SERVICO_PATTERNS = [
    r"\bservi[cç]o(s)?\b",  # standalone tambem conta (rodada 2: "servico engenharia" sem "de")
    r"\bcontrata[cç][ãa]o\s+de\s+(empresa|servi[cç]o)",
    r"\bmanuten[cç][ãa]o\b", r"\bconserto\b", r"\breparo\b",
    r"\bloca[cç][ãa]o\s+de\b",  # rodada 2: bug, faltava a variante com C (cedilha)
    r"\baluguel\s+de\b",
    r"\bconsultoria\b", r"\btreinamento\b", r"\bcurso(s)?\b", r"\bcapacita[cç][ãa]o\b",
    r"\bexame(s)?\b", r"\bconsulta(s)?\s+(m[eé]dica|oftalmolog|odontol)", r"\bcirurgia\b",
    r"\bradiologia\b", r"\banalise(s)?\s+cl[ií]nica", r"\banálise(s)?\s+cl[ií]nica",
    r"\btransporte\s+(escolar|de\s+pacient|rodovi[aá]rio|coletivo|de\s+[aá]gua)", r"\bfretamento\b", r"\bfrete\b",
    r"\bcarro\s+pipa\b",
    r"\bseguro\s+(de|para|automotivo|de\s+vida)\b",
    r"\bassinatura\b", r"\bfranquia\b",
    r"\bm[ãa]o\s+de\s+obra\b", r"\bstaffing\b", r"\benfermagem\b", r"\bpsicologia\b",
    r"\bfisioterapia\b", r"\bterapia\b", r"\bendoscopia\b", r"\bultrassonografia(s)?\b",
    r"\bfornecimento\s+de\s+m[ãa]o", r"\bhospedagem\b", r"\blimpeza\s+e\s+conserva[cç][ãa]o\b",
    r"\bvigil[âa]ncia\s+(patrimonial|armada|desarmada)\b", r"\bgest[ãa]o\s+de\b",
    r"\bcess[ãa]o\s+de\s+direito",
    # rodada 2 -- novos sinonimos achados na auditoria de "Outros" (31/jul)
    r"\bassist[êe]ncia\s+m[eé]dica\b", r"\bconv[êe]nio\b", r"\bplano\s+de\s+sa[uú]de\b",
    r"\bbuffet\b", r"\brefei[çc][õo]es\b", r"\blanches\b",
    r"\bdesinsetiza[çc][ãa]o\b", r"\bdesratiza[çc][ãa]o\b", r"\bdedetiza[çc][ãa]o\b",
    r"\bpatroc[íi]nio\b", r"\benergia\s+el[eé]trica\b", r"\besgoto\s+sanit[aá]rio\b",
    r"\bsemin[aá]rio\b", r"\bpalestra\b", r"\bapresenta[çc][ãa]o\s+art[íi]stica\b",
    r"\brealiza[çc][ãa]o\s+de\s+shows\b", r"\bevento(s)?\s+(cultural|art[íi]stico)",
    r"\bsoftware\s+como\s+servi[çc]o\b", r"\bsaas\b",
    r"\bper[íi]cia\b", r"\blaudo\b", r"\bavalia[çc][ãa]o\s+t[eé]cnica\b",
    r"\bdocente\b", r"\bobra(s)?\s+civi(l|s)\b",
    r"\bpavimenta[çc][ãa]o\s+asf[aá]ltica\b",  # obra, nao produto -> mas mantem como servico/obra
    # rodada 3
    r"\binscri[çc][ãa]o\s+(de\s+)?evento", r"\brecolhimento\s+de\s+(taxa|imposto|multa)\b",
    r"\bpagamento\s+cobertura(s)?\s+seguro\b", r"\bseguro\s+ve[ií]culo\b",
    r"\belabora[çc][ãa]o\s*/?\s*an[aá]lise\s+projeto\b", r"\banalise\s+tecnica\s+de\s+parecer\b",
    r"\bacesso\s+a\s+internet\b", r"\bdecora[çc][ãa]o\s*-?\s*eventos?\b", r"\bpromo[çc][ãa]o\s+de\s+evento(s)?\b",
    r"\bshow(s)?\b", r"\bapresenta[çc][ãa]o\s+art[íi]stica", r"\bloca[çc][ãa]o\b",  # locacao standalone tambem
    # rodada 4
    r"\binstala[çc][ãa]o\b", r"\bremo[çc][ãa]o\b", r"\bcoopera[çc][ãa]o\b", r"\bconv[êe]nios?\b",
    r"\bafer[ií][çc][ãa]o\b", r"\bcalibra[çc][ãa]o\b", r"\bcontrole\s+de\s+abastecimento\b",
    r"\bcomunica[çc][ãa]o\s+por\s+correio\b", r"\bdespacho(s)?\s+aduaneiro(s)?\b",
    r"\barbitragem\b", r"\bcol[oô]nia\s+de\s+f[eé]rias\b", r"\bcontrata[çc][ãa]o\s+(de\s+)?grupo\s+art[íi]stico\b",
    r"\brecrutamento\b", r"\bconcurso\s+p[uú]blico\b", r"\bvestibular\b",
    r"\blimpeza\s+de\s+(fossa|esgoto)\b", r"\brecolhimento\s+(de\s+)?(contribui[çc][ãa]o|anuidade)\b",
    r"\badministra[çc][ãa]o\s+local\b", r"\bcoleta\s+de\s+lixo\b", r"\bfolha\s+de\s+pagamento\b",
    r"\bconcess[ãa]o\s+(de\s+)?uso\b", r"\bpassagem\s+a[eé]rea\b", r"\bensino\s+especial\b",
    r"\batendimento\s+educacional\b", r"\bajuda\s+de\s+custo\b", r"\blicenciamento\b",
    # rodada 5
    r"\bcantina\b", r"\blanchonete\b", r"\brestaurante\b", r"\breserva\s+em\s+hot[eé]is\b",
    r"\bhotel(aria)?\b", r"\bcongresso\b", r"\bsimp[óo]sio\b", r"\bconfer[êe]ncia\b",
    r"\btradu[çc][ãa]o\b", r"\binterpreta[çc][ãa]o\s+simult[âa]nea\b", r"\blimpeza\s+urbana\b",
    r"\brecrea[çc][ãa]o\b", r"\brevitaliza[çc][ãa]o\b",
    # rodada 6
    r"\bapresenta[çc][ãa]o\s+musical\b", r"\bdivulga[çc][ãa]o\s+de\s+eventos?\b",
    r"\badministra[çc][ãa]o\s+p[uú]blica\b", r"\bpavimenta[çc][ãa]o\b", r"\brevis[ãa]o\s+ve[ií]culo\b",
    r"\bduplica[çc][ãa]o\b", r"\betiquetagem\b",
    r"\b(porteiro|copeiro|servente(s)?|auxiliar\s+administrativo|vigia|zelador|recepcionista|motorista)\s*\d*\b",
    r"\bcontrata[çc][ãa]o\s+de\s+artista\b", r"\bmonitoramento\b",
    r"\bvale\s+transporte\b", r"\bmedicina\s+(do\s+)?trabalho\b", r"\bengenharia\s+(do\s+)?trabalho\b",
    r"\btratamento\s+(de\s+)?lixo\b", r"\bprofessor\s+palestrante\b", r"\bpagamento\s+di[aá]ria\b",
    r"\bpublica[çc][ãa]o\s+legal\b",
    # rodada 7
    r"\bemiss[ãa]o\s+de\s+certificado\b", r"\bentrevistador\b", r"\bint[ée]rprete\b",
    r"\bro[çc]ada\b", r"\barmazenamento\b", r"\bseguro\s+patrimonial\b",
    r"\bconfec[çc][ãa]o\s+de\s+crach[aá]s\b", r"\batra[çc][ãa]o\s+musical\b",
    r"\baux[íi]lios?\s+a\s+pessoa\s+f[íi]sica\b", r"\bdocumento\s+[uú]nico\s+de\s+arrecada[çc][ãa]o\b",
    r"\balinhamento\b", r"\bbalanceamento\b", r"\balceamento\b", r"\benvelopamento\b",
    # rodada 8
    r"\bcontrata[çc][ãa]o\s+de\s+pessoa\s+jur[íi]dica\b", r"\bobra\s+rodovi[aá]ria\b",
    r"\bobras?\s+de\s+engenharia\b", r"\bsecret[aá]ria\b(?!\s+de\b)", r"\btarifa\s+banc[aá]ria\b",
    r"\bpropaganda\b", r"\bpublicidade\b", r"\baudiovisual\b", r"\bpassagem\s+rodovi[aá]ria\b",
    r"\boficinas?\b", r"\bseguro\s*/\s*garantia\b",
    # rodada 9
    r"\breforma\b", r"\bassessoria\b", r"\btaxas?\s+de\s+embarque\b", r"\bleiloeiro\b",
    r"\bcorretagem\b", r"\bcach[êe]\s+art[íi]stico\b", r"\bengenheiro\b", r"\ban[aá]lise\s+f[íi]sico",
    # rodada 10
    r"\bconfec[çc][ãa]o\s+documentos\b", r"\bsondagens?\b", r"\b[aá]gua\s+canalizada\b",
    r"\btratamento\s+de\s+res[íi]duos\b",
    # rodada 11
    r"\bmoderador\b", r"\bpainelista\b", r"\bdebatedor\b", r"\bconferencista\b", r"\bpalestrante\b",
    r"\bsonoriza[çc][ãa]o\b", r"\bilumina[çc][ãa]o\b", r"\brecauchutagem\b", r"\brecapagem\b",
    r"\bpoda\b", r"\ban[aá]lise\s+qu[íi]mica\b", r"\bcart[ãa]o\s+magn[eé]tico\b",
    r"\btarifas?\s+banc[aá]ria(s)?\b", r"\bconsigna[çc][õo]es\b", r"\bcolonoscopia\b",
    # rodada 12
    r"\blocutor\b", r"\bmestre\s+de\s+cerim[ôo]nia\b", r"\bauditoria\b", r"\bdeslocamento\b",
    r"\bcoffee\s+break\b",
    # rodada 13 (correcao via outlier de preco)
    r"\bsustenta[çc][ãa]o\s+de\s+software\b", r"\bmensura[çc][ãa]o\s+de\s+software\b",
    r"\bcomodato\b", r"\bcess[ãa]o\s+n[ãa]o\s+oner",
    # rodada 14 (auditoria completa por categoria)
    r"\bimplanta[çc][ãa]o\s+de\s+software\b", r"\bimplementa[çc][ãa]o\s+(de\s+|[aá]gil\s+de\s+)?software\b",
    r"\bescava[çc][ãa]o\s+mecanizada\b", r"\btransporte\s+de\s+alunos\b",
    # rodada 4 (amostra final)
    r"\bavalia[çc][ãa]o\s*-\s*avalia\s+rede\b", r"\bavalia\s+rede\b",
    r"\bpassagem\b", r"\btrasporte\s+do\s+material\s+escavado\b", r"\btransporte\s+do\s+material\s+escavado\b",
    r"\bmanut(en[çc][ãa]o)?\s+corretiva\b",
]

# ---- Junk / generico demais pra classificar por texto sozinho ----
JUNK_TERMS = {
    "peca", "pecas", "peça", "peças", "bomba", "suporte", "filtro", "solucao", "solução",
    "kit", "material", "item", "produto", "diversos", "outros", "acessorio", "acessório",
    "acessorios", "acessórios", "mes", "mês", "grupo de itens 01", "grupo de itens",
}

BOILERPLATE_PATTERNS = [
    r"\bproposta\s+para\s+todos\s+os\s+itens\b",
    # nota: removido "conforme anexo" -- muito amplo, varria produto real
    # que so' menciona "estampa/arte conforme anexo" como especificacao
    r"\bclassifica[çc][ãa]o\s+de\s+produto\s*\(\s*material\s*\)",  # sem \b final: ")" e nao-letra, \b nunca dispara ali (bug de classe nova)
    r"^lote\s*\d+\s*$", r"^exemplo$", r"\blote\s+[ée]\s+composto\b",
    # nota: "lote N" generico so' conta como boilerplate se for a string INTEIRA
    # (sem produto depois) -- antes varria "LOTE 01 - banana/vestido/etc" tambem
    r"^constru[çc][ãa]o$", r"\bver\s+itens\s+e\s+quantidades\b",
    r"\bespecifica[çc][õo]es\s+e\s+quantitativos\b", r"^conforme\s+termo\s+de\s+refer[êe]ncia$",
]
_boilerplate_re = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

# ---- Categorias: (nome, regex_incluir, regex_excluir_opcional) ----
# Ordem importa: Combustivel roda antes de Farmaceutico pra nao perder
# gasolina/etanol pro sufixo -ina/-ol (bug ja documentado).
CATEGORIAS = [
    ("Combustivel", [
        r"\bgasolina\b", r"\betanol\b", r"\b[oó]leo\s+diesel\b", r"\bdiesel\b",
        r"\bgnv\b", r"\bquerosene\b", r"\bg[aá]s\s+liquefeito\b", r"\bglp\b",
        r"\bg[aá]s\s+(de\s+)?refino\b", r"\bbotij[ãa]o\b", r"\bcilindro\s+g[aá]s\b",
    ], [r"\bmotoriza[çc][ãa]o\b", r"\bcabine\s+dupla\b", r"\btorque\b", r"\bcilindrada\b",
        r"\bveiculo\b", r"\bve[ií]culo\b", r"\bpick-?up\b", r"\bcombustivel\s+alcool\b",
        r"\bocupantes\b", r"\brenavam\b", r"\bcobertura(s)?\s*:", r"\bmotor\s+\d\s*tempos\b",
        r"\bsoprador\b", r"\brocadeira\b", r"\bro[çc]adeira\b"]),

    ("Veiculos/Frota", [
        r"\bautom[oó]vel\b", r"\b[oô]nibus\b", r"\bcaminh[ãa]o\b", r"\bmicro[oô]nibus\b",
        r"\bmotocicleta\b", r"\bve[ií]culo\s+(oficial|utilit[aá]rio|de\s+passeio|de\s+transporte)",
        r"\bcaminhonete\b", r"\bpick-?up\b", r"\bfurg[ãa]o\b", r"\b[ôo]nibus\s+escolar\b",
        r"\bve[ií]culo\s+van\b", r"\bretroescavadeira\b", r"\bmoto\s+\d+\s*cc\b",
        r"\bcamionete\b", r"\bve[ií]culo\s+passeio\b", r"\bambul[âa]ncia\b",
        r"\bsedan\b", r"\bhatch\b",
    ], None),

    ("Veiculos/Pecas", [
        r"\bpe[çc]a(s)?\s+(automotiv|de\s+ve[ií]culo|de\s+moto|de\s+carro|de\s+caminh[ãa]o)",
        r"\bpneu\b", r"\bfiltro\s+de\s+[oó]leo\b", r"\bfiltro\s+de\s+combust[ií]vel\b",
        # nota: exclui equipamento onde "pneu" e' so' componente mencionado, nao o produto
        r"\bbateria\s+automotiv", r"\b[oó]leo\s+lubrificante\b",
        r"\bpe[çc]a\s+mec[âa]nica\b", r"\bpe[çc]a\s+el[eé]trica\b", r"\bve[ií]culo\s+automotivo\b",
        r"\belemento\s+filtrante\b", r"\bfiltro\s+(de\s+)?(ar|[oó]leo|combust[íi]vel|lubrificante)\b",
        r"\bamortecedor\b", r"\brolamento\s+(de\s+)?(esfera|roda|mancal|rolo)\b",
        r"\bpastilha\s+de\s+freio\b", r"\bgraxa\b",
        r"\bretentor\b", r"\bcorreia\s+transmiss[ãa]o\b", r"\belemento\s+do\s+filtro\b",
        r"\bpneum[aá]tico\b",
    ], [r"\brolamento\s*/?\s*capa\s+asf[aá]ltica\b", r"\bcbuq\b",
        r"\bcarrinho\s+de\s+m[ãa]o\b", r"\bdistribuidor\s+(de\s+)?calc[aá]rio\b",
        r"\bespalhador\s+de\s+esterco\b", r"\bro[çc]adeira\b", r"\bplantadeira\b"]),

    ("Saude/Farmaceutico", [
        r"\bmedicamento(s)?\b", r"\bcompr[ií]mido(s)?\b", r"\bc[aá]psula(s)?\b",
        r"\bxarope\b", r"\bpomada\b", r"\binjet[aá]vel\b", r"\bsoluc?[ãa]o\s+injet[aá]vel\b",
        r"\S+cloridrato\S*", r"\S+mesilato\S*", r"\S+dipropionato\S*", r"\S+succinato\S*",
        r"\S+besilato\S*", r"\S+maleato\S*", r"\S+fosfato\s+de\s+s[oó]dio\b",
        r"\bamoxicilina\b", r"\bdipirona\b", r"\bparacetamol\b", r"\bibuprofeno\b",
        r"\binsulina\b", r"\bomeprazol\b", r"\bsoro\s+(fisiol[oó]gico|glicosado)\b",
        r"\bcarbamazepina\b", r"\b[aá]cido\s+acetilsalic[íi]lico\b", r"\blidoca[íi]na\b",
        r"\bbenzilpenicilina\b", r"\b[aá]cido\s+asc[oó]rbico\b",
        r"\b[aá]cido\s+tranex[âa]mico\b", r"\bacetilciste[íi]na\b", r"\bclonazepam\b",
        r"\bdexametasona\b", r"\balbendazol\b",
        r"\b[aá]cido\s+f[oó]lico\b", r"\bampicilina\b", r"\bamiodarona\b",
        r"\bbicarbonato\s+de\s+s[oó]dio\b", r"\batenolol\b", r"\bglicose\b",
        r"\b[aá]cido\s+ac[eé]tico\b", r"\bescopolamina\b", r"\bbromoprida\b",
        r"\baripiprazol\b", r"\b[aá]cido\s+valpr[oó]ico\b", r"\banlodipino\b",
        r"\bfentanila\b", r"\b[aá]cidos\s+graxos\b", r"\bfenobarbital\b", r"\benoxaparina\b",
        r"\bamitriptilina\b", r"\bazitromicina\b", r"\badenosina\b", r"\bselexipague\b",
        r"\bliraglutida\b", r"\bdulaglutida\b", r"\btirzepatida\b",
        r"\b[aá]cido\s+zoledr[ôo]nico\b", r"\bvacina(s)?\b", r"\bsuplemento\s+nutricional\b",
        r"\bacebrofilina\b", r"\bhaloperidol\b", r"\bcarvedilol\b", r"\batorvastatina\b",
        r"\batropina\b", r"\bbetametasona\b", r"\bsemaglutida\b", r"\bondansetrona\b",
        r"\balbumina\s+humana\b", r"\balfaepoetina\b", r"\bbiperideno\b", r"\bquetiapina\b",
        r"\bceftriaxona\b", r"\bmidazolam\b", r"\bclaritromicina\b", r"\bamino[aá]cidos\b",
        r"\baminofilina\b", r"\bcefalexina\b", r"\bvalproato\b", r"\bclorpromazina\b",
    ], [
        r"\bgasolina\b", r"\betanol\b", r"\bcortina\b", r"\bresina\b", r"\bprato\b",
        r"\bboina\b", r"\bcartolina\b", r"\bvaselina\b\s*t[eé]cnica",
    ]),

    ("Saude/Hospitalar", [
        r"\bequipamento\s+(hospitalar|m[eé]dico|de\s+laborat[oó]rio)\b",
        r"\bconsum[ií]vel\s+(hospitalar|m[eé]dico)\b", r"\bseringa(s)?\b", r"\bagulha(s)?\b",
        r"\bcateter\b", r"\bcurativo(s)?\b", r"\bfio\s+de\s+sutura\b", r"\bluva(s)?\s+(cir[uú]rgica|de\s+procedimento|l[aá]tex|nitrilica)",
        r"\breagente(s)?\b", r"\bg[aá]s\S*terapia\b",
        r"\bcompressor\s+de\s+ar\s+odontol[oó]gico\b", r"\bequipamento\s+odontol[oó]gico\b",
        r"\bcimento\s+(odontol[oó]gico|ortop[eé]dico)\b",
        r"\bdieta\s+(enteral|infantil)\b", r"\bmeio\s+de\s+cultura\b", r"\bc[âa]nula\b",
        r"\bfralda\b", r"\babsorvente\b",
        r"\bsonda\b", r"\baciclovir\b", r"\banticorpo(s)?\b", r"\batadura\b",
        r"\b[aá]gua\s+destilada\b", r"\bluva(s)?\s+p(/|ara)?\s+procedimento\b",
        r"\banestesia\b", r"\bcloreto\s+de\s+s[oó]dio\b", r"\bantibiograma\b",
        r"\balgod[ãa]o\b", r"\bclorexidina\b", r"\besteriliza[çc][ãa]o\b",
        r"\bbroca\s+(alta\s+rota[çc][ãa]o|odontol[oó]gica)\b",
        r"\babaixador\s+de\s+l[íi]ngua\b", r"\bdreno\s+cir[uú]rgico\b", r"\bintrodutor\s+percut[âa]neo\b",
        r"\bmodelo\s+anat[ôo]mico\b",
        r"\bpadr[ãa]o\s+de\s+refer[êe]ncia\b", r"\btubo\s+para\s+coleta\b", r"\bvestimenta\s+hospitalar\b",
        r"\blima\s+uso\s+odontol[oó]gico\b", r"\bgaze\b", r"\bbal[ãa]o\s+laborat[oó]rio\b",
        r"\bpin[çc]a\s+cir[uú]rgica\b", r"\besfigmoman[ôo]metro\b", r"\bindicador\s+qu[íi]mico\b",
        r"\btrefina\b", r"\btrepano\b", r"\bafastador\s+cir[uú]rgico\b", r"\bmotor\s+cir[uú]rgico\b",
        r"\bcadeira\s+de\s+rodas\b",
        r"\btubo\s+endotraqueal\b", r"\bequipo\s+p/?\s*bomba\s+de\s+infus[ãa]o\b",
        r"\bsistema\s+p/?\s*estomia\b", r"\bl[âa]mina\s+bisturi\b", r"\bfilme\s+radiol[oó]gico\b",
        r"\bresina\s+composta\b", r"\bb[eé]quer\b", r"\bfrasco\s+laborat[oó]rio\b",
        r"\bafastador\s+odontol[oó]gico\b", r"\bresina\s+acr[íi]lica\s+uso\s+odontol[oó]gico\b",
        r"\btouca\s+descart[aá]vel\b", r"\bsolu[çc][ãa]o\s+padr[ãa]o\b", r"\bcontraste\s+radiol[oó]gico\b",
        r"\bextensor\s+infus[ãa]o\s+vascular\b", r"\bbal[ãa]o\s+dilata[çc][ãa]o\b",
        r"\bcompressa\s+campo\s+operat[oó]rio\b", r"\bmanta\s+t[eé]rmica\b", r"\bcone\s+endod[ôo]ntico\b",
        r"\besp[eé]culo\b", r"\bcoletor\s+de\s+urina\b", r"\bequipo\s+de\s+infus[ãa]o\b",
        r"\binstrumental\s+p/?\s*endosc[oó]pio\b", r"\bcampo\s+cir[uú]rgico\b", r"\bvni\b|\bbipap\b|\bcpap\b",
        r"\bbolsa\s+coletora\b", r"\balavanca\s+odontol[oó]gica\b", r"\bcondicionador\s+dental\b",
        r"\bponteira\s+laborat[oó]rio\b", r"\badjuvante\s+p/?\s*estomia\b", r"\bcardioversor\b",
        r"\bdesfibrilador\b", r"\bmonitoriza[çc][ãa]o\b", r"\bnutri[çc][ãa]o\s+parenteral\b",
        r"\bfixador\s+p/?\s*dispositivo\s+m[eé]dico\b", r"\bpapel\s+grau\s+cir[uú]rgico\b",
        r"\bper[óo]xido\s+de\s+hidrog[êe]nio\b", r"\bindicador\s+biol[oó]gico\b",
        r"\btesoura\s+instrumental\b", r"\blanceta\b", r"\bequipamento\s+laborat[oó]rio\b",
        r"\btubo\s+supragl[óo]tico\b", r"\bterm[ôo]metro\b", r"\bbr[aá]quete\b",
        r"\bconector\s+uso\s+m[eé]dico\b",
        r"\bescova\s+dental\b", r"\bescova\s+limpeza\b", r"\bpin[çc]a\s+p/?\s*videocirurgia\b",
        r"\breanimador\b", r"\bl[âa]mina\s+laborat[oó]rio\b", r"\bequipo\s+de\s+nutri[çc][ãa]o\s+enteral\b",
        r"\bcama\s+hospitalar\b", r"\balmotolia\b", r"\bsolu[çc][ãa]o\s+tamp[ãa]o\b", r"\bbandagem\b",
    ], None),

    ("Saude/Implantavel", [
        r"\bpr[oó]tese\b", r"\bstent\b", r"\bmarca[- ]?passo\b", r"\bimplante(s)?\b",
        r"\bcateter\s+central\s+implant[aá]vel\b", r"\bplaca\s+ortop[eé]dica\b",
        r"\bendopr[oó]tese\b", r"\bfio\s+guia\b", r"\bsistema\s+fixa[çc][ãa]o\s+coluna\b",
        r"\bortopedia\b", r"\bfio\s+ortop[eé]dico\b", r"\b[âa]ncora\s+de\s+sutura\b",
        r"\bestimula[çc][ãa]o\s+card[íi]aca\b",
    ], [r"\beletroduto\b"]),

    ("Construcao_Civil/Material", [
        r"\bcimento\b", r"\bareia\b", r"\bbrita\b", r"\btijolo(s)?\b", r"\btelha(s)?\b",
        r"\bconcreto\b", r"\bargamassa\b", r"\bvergalh[ãa]o\b",
        r"\bconex[ãa]o\s+hidr[aá]ulica\b", r"\bcabo\s+el[eé]trico\b",
        r"\bmateriais?\s+de\s+constru[çc][ãa]o\b",
        r"\babra[çc]adeira\b", r"\bparafuso(s)?\b", r"\btinta\b",
        r"\bl[âa]mpada\b", r"\bbroca\b", r"\bmadeira\s+(de\s+)?(constru[çc][ãa]o|serrada|compensada|tratada)\b",
        r"\bchapa\s+(de\s+)?a[çc]o\b",
        r"\bdisjuntor\b", r"\bcadeado\b", r"\btubo\s+hidr[aá]ulico\b",
        r"\bbomba\s+hidr[aá]ulica\b", r"\bpersiana\b",
        r"\blumin[aá]ria\b", r"\btorneira\b", r"\balicate\b", r"\bbarra\s+(chata|a[çc]o)\b",
        r"\bchave\s+matriz\b", r"\bp[óo]\s+de\s+pedra\b", r"\bfechadura\b", r"\barame\b",
        r"\bestrutura\s+met[aá]lica\b", r"\brevestimento\s+piso\b", r"\banilha\s+(de\s+)?press[ãa]o\b", r"\barruela\b",
        r"\banel\s+veda[çc][ãa]o\b", r"\bjogo\s+chave\b", r"\bporta\b", r"\baguarr[aá]s\b",
        r"\bconector\s+el[eé]trico\b",
        r"\bemuls[ãa]o\s+asf[aá]ltica\b", r"\bv[aá]lvula\s+reten[çc][ãa]o\b", r"\bconjunto\s+drenagem\b",
        r"\bsif[ãa]o\b", r"\bfiltro\s+linha\b", r"\bfiltro\s+purifica[çc][ãa]o\b",
        r"\bmedidor\s+vaz[ãa]o\b", r"\bcontator\b", r"\btubo\s+isolante\b",
        r"\bcompressor\s+de\s+ar\b", r"\blona\b", r"\brel[eé]\s+fotoel[eé]trico\b",
        r"\bferramenta\b", r"\btoldo\b", r"\bbucha\b",
    ], [r"\bcimento\s+(odontol[oó]gico|ortop[eé]dico)\b", r"\bbroca\s+(alta\s+rota[çc][ãa]o|odontol[oó]gica)\b",
        r"\bcartucho\b", r"\bimpressora\b"]),

    ("TI/Hardware_e_Redes", [
        r"\bcomputador(es)?\b", r"\bnotebook\b", r"\bservidor\b",
        r"\bswitch\b", r"\broteador\b", r"\bcabo\s+de\s+rede\b",
        r"\bmicrocomputador\b", r"\bimpressora\b", r"\bsoftware\b", r"\btablet\b",
        r"\bunidade\s+(de\s+)?disco\b", r"\btransceiver\b",
    ], [r"^papel\b", r"\bpapel\s+a4\b", r"\bservidor\s+p[uú]blico\b",
        r"\bcomenda\b", r"\bmesa\b"]),

    ("Eletronicos/Eletrodomesticos", [
        r"\btelevisor\b", r"\bfrigobar\b", r"\bmicrofone\b", r"\bbebedouro\b",
        r"\bestabilizador\s+(de\s+)?tens[ãa]o\b", r"\bcafeteira\s+el[eé]trica\b",
        r"\bforno\s+microondas\b", r"\bventilador\b", r"\bbateria\s+(n[ãa]o\s+)?recarreg[aá]vel\b",
        r"\bbateria\s+estacion[aá]ria\b", r"\bpurificador\s+de\s+[aá]gua\b",
        r"\bcaixa\s+(de\s+)?som\b", r"\bbalan[çc]a\s+eletr[ôo]nica\b",
        r"\bfone\s+(de\s+)?ouvido\b", r"\badaptador\s+(el[eé]trico|eletr[ôo]nico|de\s+tomada|ac\b|hdmi|usb|vga)",
        r"\bfreezer\b", r"\brefrigerador\s+dom[eé]stico\b",
        r"\bliquidificador\s+industrial\b", r"\bfonte\s+alimenta[çc][ãa]o\b", r"\bpilha(s)?\b",
        r"\btelefone\s+celular\b", r"\baparelho\s+telef[ôo]nico\b", r"\bm[óo]dulo\s+eletr[ôo]nico\b",
        r"\bsensor\b", r"\bponto\s+de\s+acesso\b", r"\bprojetor\s+multim[íi]dia\b", r"\btomada\b",
        r"\brefrigerador\s+duplex\b", r"\bbatedeira\s+industrial\b", r"\bcabo\s+extensor\b",
        r"\bcarregador\s+(de\s+)?bateria\b", r"\beletrodo\b", r"\bc[âa]mera\s+videoconfer[êe]ncia\b",
        r"\bfog[ãa]o\b", r"\bteclado\b", r"\bcabo\s+[aá]udio\b", r"\blavadora\s+alta\s+press[ãa]o\b",
        r"\bfirewall\b", r"\bmem[óo]ria\s+ram\b", r"\bdisco\s+magn[eé]tico\b", r"\bcaixa\s+ac[uú]stica\b",
        r"\bscanner\b", r"\bwireless\b", r"\bliquidificador\b",
    ], None),

    ("Instrumentos_Musicais", [
        r"\binstrumento(s)?\s+musical(is)?\b",
    ], None),

    ("Brindes_Premiacao", [
        r"\bmedalha(s)?\b", r"\btrof[eé]u(s)?\b", r"\bchaveiro(s)?\b", r"\bbotom\b", r"\bbrinde(s)?\b",
    ], None),

    ("Educacao/Material_Escolar", [
        r"\bcaderno(s)?\b", r"\bl[aá]pis\b", r"\bgiz\b", r"\bmochila\s+escolar\b",
        r"\bmaterial\s+escolar\b", r"\bcarteira\s+escolar\b", r"\blivro\s+did[aá]tico\b",
        r"\blivro\b", r"\bbrinquedo(s)?\b", r"\bconjunto\s+escolar\b", r"\bjogo\s+educativo\b",
        r"\bmaterial\s+pedag[óo]gico\b",
    ], [r"\blivro\s+de\s+ata\b", r"\blivro\s+caixa\b", r"\blivro\s+protocolo\b"]),

    ("Material_Escritorio", [
        r"\bcaneta\s+esferogr[aá]fica\b", r"\bgrampeador\b", r"\bclips\b", r"\bpasta\s+arquivo\b",
        r"\bbloco\s+(de\s+)?recado\b", r"\bpapel\s+a4\b", r"\bpapel\s+alcalino\b", r"\bresma\b",
        r"\bborracha\s+(apagadora|escolar)\b", r"\benvelope(s)?\b", r"\bfita\s+adesiva\b",
        r"\balmofada\s+(de\s+)?carimbo\b", r"\bapagador\b", r"\bcaixa\s+(pl[aá]stica|arquivo)\b",
        r"\bcaneta\b", r"\bagenda\b", r"\bbloco\s+rascunho\b", r"\bclipe(s)?\b",
        r"\betiqueta\s+adesiva\b", r"\bcarimbo\b", r"\balfinete\b", r"\bcartolina\b",
        r"\bcola\b", r"\bpincel\b", r"\bcapa\s+(para\s+)?encaderna[çc][ãa]o\b",
        r"\bcart[ãa]o\s+(de\s+)?identifica[çc][ãa]o\b", r"\bplaca\s+(sinalizadora|homenagem|acr[íi]lica)\b",
        r"\bpapel,?\s+a4\b", r"\betiqueta\s+(auto-?)?adesiva\b",
        r"\bcone\s+sinaliza[çc][ãa]o\b", r"\bcolete\s+identifica[çc][ãa]o\b", r"\bpulseira\s+identifica[çc][ãa]o\b",
        r"\bformul[aá]rio\b", r"\bsinalizador\b",
    ], [r"\bextrato\s+de\s+cola\b", r"\brefrigerante\b"]),

    ("Textil/Vestuario", [
        r"\bfardamento\b", r"\bcamiseta(s)?\b", r"\baviamento\b", r"\btecido\b",
        r"\bhelanca\b", r"\bcal[çc]a\b", r"\bbermuda\b", r"\bsaia\s+shorts?\b",
        r"\bmochila\b", r"\bcolcha\b", r"\bjaqueta\b", r"\bcamisa\b",
        r"\btoalha\s+(de\s+)?banho\b", r"\blen[çc]ol\b", r"\bjaleco\b", r"\bvestido\b",
    ], [r"\btipo\s+camiseta\b"]),

    ("Alimentacao/Perecivel", [
        r"\bcarne\s+bovina\b", r"\bfrango\b", r"\bpeixe\b", r"\bhortifr[uú]ti\b",
        r"\bleite\b", r"\bp[ãa]o\b", r"\bfruta(s)?\b", r"\bverdura(s)?\b", r"\blegume(s)?\b",
        r"\bcebola\b", r"\balface\b", r"\bcarne\s+de\s+ave\b", r"\bbolo\b",
        r"\bcheiro\s+verde\b", r"\bcebolinha\b", r"\bcoentro\b", r"\bbatata\b",
        r"\bcarne\s+su[íi]na\b", r"\bfrios\b", r"\bovo\b", r"\bsalgados?\b",
        r"\babacaxi\b", r"\bbeterraba\b", r"\bcouve\b", r"\bchic[óo]ria\b",
        r"\bab[óo]bora\b", r"\babacate\b", r"\bcarne\s+salgada\b", r"\bcarne\s+processada\b",
        r"\bcenoura\b", r"\bembutido\b", r"\babobrinha\b", r"\boleaginosa(s)?\b",
        r"\bqueijo\b", r"\bacelga\b", r"\bcarne\s+defumada\b",
    ], [r"\bra[çc][ãa]o\s+(de\s+)?peixe\b",
        r"\bpuxador\b", r"\btrinco\b", r"\bfechadura\b", r"\b[áa]udio\b",
        r"\bel[áa]stico\s+embutido\b", r"\bmdp\b", r"\bprateleira\b"]),

    ("Alimentacao/Mercearia", [
        r"\barroz\b", r"\bfeij[ãa]o\b", r"\ba[çc][uú]car\b", r"\b[oó]leo\s+de\s+cozinha\b",
        r"\bcaf[eé]\b", r"\b[aá]gua\s+mineral\b", r"\bbiscoito(s)?\b", r"\bcondimento(s)?\b",
        r"\balho\b", r"\bbanana\b", r"\bcanela\b",
        r"\bamido\b", r"\bazeite\b", r"\bado[çc]ante\b", r"\bfarinha\b",
        r"\bachocolatado\b", r"\bch[aá]\b", r"\bleguminosa(s)?\b", r"\b[oó]leo\s+vegetal\b",
        r"\b[oó]leo\s+de\s+soja\b", r"\baveia\b", r"\bcanjica\b", r"\bcanjiquinha\b", r"\bmacarr[ãa]o\b",
        r"\bcorante\b", r"\ba[çc]afr[ãa]o\b", r"\brefrigerante\b", r"\bdoce\s+n[ãa]o\s+confeitado\b",
        r"\bmistura\s+aliment[íi]cia\b", r"\bmilho\s+verde\b", r"\blouro\b", r"\bmanteiga\b",
        r"\bmassa\s+de\s+tomate\b", r"\btempero\b",
    ], None),

    ("HVAC/Climatizacao", [
        r"\bar\s+condicionado\b", r"\bventilador\s+industrial\b", r"\bexaustor\b",
        r"\bclimatiza[çc][ãa]o\b",
    ], None),

    ("Mobiliario", [
        r"\bmesa\b", r"\bcadeira\b", r"\barm[aá]rio\b", r"\bestante\b",
        # nota: "cadeira de rodas" e "motor cirurgico" (bateria recarregavel) sao
        # intercept explicito em Saude/Hospitalar, checado antes desta categoria
        r"\bgarrafa\s+t[eé]rmica\b", r"\burna\s+mortu[aá]ria\b", r"\bgarraf[ãa]o\b", r"\bcolher\b",
        r"\bcaixa\s+t[eé]rmica\b", r"\bpoltrona\b", r"\bcarrinho\b", r"\bcortina\b",
        r"\bgarrafa\b", r"\bassadeira\b", r"\bpanela\b", r"\bprato\b", r"\bcolch[ãa]o\b",
        r"\bbalc[ãa]o\s+t[eé]rmico\b", r"\bca[çc]arola\b", r"\bgaveteiro\b", r"\bcobertor\b",
        r"\bbandeja\b", r"\besta[çc][ãa]o\s+(de\s+)?trabalho\b", r"\bcontainer\b",
        r"\bbanco\b", r"\bm[óo]vel\s+multiuso\b", r"\btapete\b",
    ], [r"\bmesa\s+de\s+(som|[aá]udio|v[ií]deo)\b", r"\bautoclave\b"]),

    ("Seguranca/Vigilancia_Eletronica", [
        r"\bc[âa]mera(s)?\s+(de\s+seguran[çc]a|de\s+vigil[âa]ncia|ip)\b",
        r"\balarme\b", r"\bcerca\s+el[eé]trica\b", r"\bdvr\b", r"\bnvr\b", r"\bextintor\b",
        # nota: exclui pastilha de freio abaixo (feature "com alarme" de desgaste, nao alarme de seguranca)
        r"\bc[âa]mera\s+v[íi]deo\s+de\s+seguran[çc]a\b", r"\bc[âa]mera\s+(de\s+)?rede\b", r"\bptz\b",
        r"\blacre\s+de\s+seguran[çc]a\b", r"\bportal\s+detector\s+(de\s+)?metal\b",
    ], [r"\bc[âa]mera\s+(de\s+)?videoconfer[êe]ncia\b", r"\bpastilha\b", r"\bfreio\b"]),

    ("Agro/Paisagismo", [
        r"\bsemente(s)?\b", r"\badubo\b", r"\bra[çc][ãa]o\s+animal\b", r"\bra[çc][ãa]o\s+(de\s+)?peixe\b",
        r"\bmuda(s)?\s+de\s+planta\b", r"\bfertilizante\b", r"\bcarreta\s+agr[íi]cola\b",
        r"\bro[çc]adeira\b", r"\btrator\b",
    ], None),

    ("Grafico/Insumo_de_Impressao", [
        r"\btoner\b", r"\btinta\s+(offset|ofsete|de\s+impress[ãa]o)\b", r"\bpapel\s+offset\b",
        r"\bimpresso(s)?\b", r"\bpapel\s+(para\s+)?impress[ãa]o\b", r"\badesivo\b", r"\bcartaz\b",
        r"\bpapel\s+fotogr[aá]fico\b", r"\bpapel\s+n[ãa]o\s+clorado\b", r"\bcart[õo]es\s+de\s+visita\b",
        r"\bfolheto\b", r"\bbanner\b", r"\bcrach[aá]s\b",
    ], [r"\bdentin[aá]rio\b", r"\bdental\b", r"\binstant[âa]neo\b", r"\bviscosidade\b",
        r"\bdispositivo\s+intravenoso\b", r"\bdurepox\b"]),

    ("Equipamentos/Fitness", [
        r"\besteira\s+(de\s+)?gin[aá]stica\b", r"\bbicicleta\s+ergom[eé]trica\b", r"\bhalter(e)?(s)?\b",
        r"\baparelho\s+(de\s+)?mus?cula[çc][ãa]o\b", r"\bbola\b", r"\bdesporto\b",
        r"\bcondicionamento\s+f[íi]sico\b", r"\bbarraca\b", r"\brede\s+esport",
        r"\baparelho\s+gin[aá]stica\b", r"\bbambol[êe]\b", r"\bcaneleira\b",
        r"\bfaixa\s+exercitadora\b",
    ], None),

    ("Armamento", [
        r"\barma\s+de\s+fogo\b", r"\bmuni[çc][ãa]o\b", r"\bcolete\s+bal[ií]stico\b",
        r"\balvo\s+de\s+tiro\b",
    ], None),

    ("Nautico/Fluvial", [
        r"\bembarca[çc][ãa]o\b", r"\bmotor\s+(de\s+)?popa\b", r"\bcolete\s+salva-vidas\b",
        r"\bbarco\b",
    ], None),

    ("Limpeza/Higiene", [
        r"\bdetergente\b", r"\bsab[ãa]o\b", r"\bdesinfetante\b", r"\bpapel\s+higi[êe]nico\b",
        r"\b[aá]lcool\b", r"\b[aá]gua\s+sanit[aá]ria\b", r"\b[aá]cido\s+perac[eé]tico\b",
        r"\bcopo\s+descart[aá]vel\b", r"\besponja\b", r"\bbacia\b", r"\bbalde\b",
        r"\blixeira\b", r"\bcesto\s+(de\s+)?lixo\b", r"\bdesodorizador\b",
        r"\b[aá]cido,?\s*muri[aá]tico\b", r"\bsabonete\b", r"\bpano\s+(de\s+)?limpeza\b",
        r"\bsaco\s+pl[aá]stico\b", r"\bsacola\b", r"\btoalha\s+de\s+papel\b", r"\bborrifador\b",
        r"\bsaco\s+(para\s+)?lixo\b", r"\blimpador\b", r"\bsolu[çc][ãa]o\s+limpeza\b", r"\bamaciante\b",
        r"\bhipoclorito\b", r"\bestopa\b", r"\balgicida\b", r"\bguardanapo\b",
        r"\bvassoura\b", r"\bflanela\b", r"\bbombona\b", r"\bcera\b", r"\bprotetor\s+solar\b",
    ], None),

    ("EPI/Uniforme", [
        r"\bcapacete\s+(de\s+)?seguran[çc]a\b", r"\b[oó]culos\s+(de\s+)?prote[çc][ãa]o\b",
        r"\buniforme\b", r"\bluva(s)?\s+(de\s+)?(prote[çc][ãa]o|seguran[çc]a|borracha)\b",
        r"\bbota\s+(de\s+)?seguran[çc]a\b", r"\baventa(l|is)\b", r"\bbotina\s+(de\s+)?seguran[çc]a\b",
        r"\bvestu[aá]rio\s+(de\s+)?prote[çc][ãa]o\b", r"\bcolete\b", r"\bbota\s+de\s+borracha\b",
    ], [r"\b(colora[çc][ãa]o|cor|tamanho)\s+uniforme\b"]),
]

_servico_re = re.compile("|".join(SERVICO_PATTERNS), re.IGNORECASE)
_categorias_compiled = [
    (nome, re.compile("|".join(inc), re.IGNORECASE),
     re.compile("|".join(exc), re.IGNORECASE) if exc else None)
    for nome, inc, exc in CATEGORIAS
]


def classificar(desc_norm: str) -> str:
    if not desc_norm:
        return "Outros/Sem_Descricao"
    if _boilerplate_re.search(desc_norm):
        return "Outros/Boilerplate_Nao_Item"
    if _servico_re.search(desc_norm):
        return "Servico"
    for nome, inc_re, exc_re in _categorias_compiled:
        if inc_re.search(desc_norm):
            if exc_re and exc_re.search(desc_norm):
                continue
            return nome
    stripped = desc_norm.strip()
    if stripped in JUNK_TERMS:
        return "Outros/Generico_Nao_Classificavel"
    return "Outros/Nao_Classificado"


def main():
    t0 = time.time()
    con = duckdb.connect(DB_PATH)
    rows = con.execute(
        "SELECT id, lower(trim(descricao_item)) FROM itens_pncp"
    ).fetchall()
    print(f"carregado {len(rows)} linhas ({time.time()-t0:.1f}s)", flush=True)

    resultados = [(id_, classificar(desc)) for id_, desc in rows]

    con.execute("DROP TABLE IF EXISTS categoria_regex_v19")
    con.execute("CREATE TABLE categoria_regex_v19 (id_item INTEGER, categoria TEXT)")
    con.executemany("INSERT INTO categoria_regex_v19 VALUES (?, ?)", resultados)
    print(f"classificado e gravado ({time.time()-t0:.1f}s)", flush=True)

    print(con.execute("""
        SELECT categoria, count(*) n, round(100.0*count(*)/(SELECT count(*) FROM categoria_regex_v19),1) pct
        FROM categoria_regex_v19 GROUP BY categoria ORDER BY n DESC
    """).fetchdf().to_string())
    con.close()


if __name__ == "__main__":
    main()
