COPY categoria_sem_oferta FROM 'export_sem_oferta_classificado/categoria_sem_oferta.parquet' (FORMAT 'parquet');
COPY tudo FROM 'export_sem_oferta_classificado/tudo.parquet' (FORMAT 'parquet');
COPY tudo_classificado FROM 'export_sem_oferta_classificado/tudo_classificado.parquet' (FORMAT 'parquet');
