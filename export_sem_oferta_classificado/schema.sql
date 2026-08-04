CREATE TABLE categoria_sem_oferta(id INTEGER, categoria VARCHAR);;
CREATE TABLE tudo(id BIGINT, processo_pncp VARCHAR, uf VARCHAR, tipo VARCHAR, descricao_item VARCHAR, valor_estimado DOUBLE, situacao VARCHAR, modalidade INTEGER, orgao_cnpj VARCHAR, criado_em TIMESTAMP, uf_arquivo VARCHAR);;
CREATE TABLE tudo_classificado(id BIGINT, processo_pncp VARCHAR, uf VARCHAR, tipo VARCHAR, descricao_item VARCHAR, valor_estimado DOUBLE, situacao VARCHAR, modalidade INTEGER, orgao_cnpj VARCHAR, criado_em TIMESTAMP, uf_arquivo VARCHAR, categoria VARCHAR);;

