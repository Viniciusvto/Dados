"""
banco_gr06.py  -  Banco de dados SQLite da coleta (eventos e paradas).

SQLite = um banco de dados inteiro dentro de UM arquivo (ex.: gr06.db).
Não precisa instalar servidor: o módulo sqlite3 já vem com o Python.

Tabelas:
  eventos  -> cada vez que um sinal MUDA (não grava leitura repetida)
  paradas  -> cada parada encerrada, com causa e duração
Visão (VIEW, calculada na hora da consulta, não ocupa espaço):
  resumo_diario -> paradas e tempo parado por dia e por causa

Teste sozinho:   python banco_gr06.py --demo
  cria gr06_demo.db com dados de exemplo e mostra consultas.
"""
import sqlite3
from datetime import datetime

ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id         INTEGER PRIMARY KEY,      -- número automático
    data_hora  TEXT    NOT NULL,         -- 'AAAA-MM-DD HH:MM:SS' (hora de quem grava)
    maquina    TEXT    NOT NULL,         -- 'GR06' (prepara para várias máquinas)
    sinal      TEXT    NOT NULL,         -- nome do mapa, ex. 'IHM_EMERG_3'
    valor      INTEGER NOT NULL          -- 0 ou 1 (valor NOVO)
);
CREATE INDEX IF NOT EXISTS ix_eventos_data ON eventos(maquina, data_hora);

CREATE TABLE IF NOT EXISTS paradas (
    id         INTEGER PRIMARY KEY,
    maquina    TEXT    NOT NULL,
    inicio     TEXT    NOT NULL,
    fim        TEXT    NOT NULL,
    duracao_s  REAL    NOT NULL,
    causa      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_paradas_inicio ON paradas(maquina, inicio);

CREATE VIEW IF NOT EXISTS resumo_diario AS
SELECT maquina,
       date(inicio)               AS dia,
       causa,
       COUNT(*)                   AS qtd_paradas,
       ROUND(SUM(duracao_s) / 60, 1) AS minutos_parado
FROM paradas
GROUP BY maquina, dia, causa;
"""


def agora_txt(t=None):
    """Converte um horário (segundos do relógio) em texto legível e ordenável."""
    return datetime.fromtimestamp(t if t is not None else datetime.now().timestamp()) \
                   .strftime("%Y-%m-%d %H:%M:%S")


def conectar(caminho):
    """Abre (ou cria) o arquivo do banco e garante que as tabelas existem."""
    con = sqlite3.connect(caminho, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")   # permite ler (dash/Excel) enquanto grava
    con.executescript(ESQUEMA)
    return con


def registrar_mudancas(con, maquina, anterior, atual, t=None):
    """Compara duas leituras {sinal: 0/1} e grava SÓ os sinais que mudaram.
    Na primeira leitura (anterior=None) grava o estado inicial completo."""
    quando = agora_txt(t)
    if anterior is None:
        linhas = [(quando, maquina, k, int(v)) for k, v in atual.items()]
    else:
        linhas = [(quando, maquina, k, int(v)) for k, v in atual.items() if v != anterior.get(k)]
    if linhas:
        con.executemany("INSERT INTO eventos (data_hora, maquina, sinal, valor) VALUES (?,?,?,?)", linhas)
        con.commit()
    return len(linhas)


def registrar_parada(con, maquina, t_inicio, t_fim, causa):
    con.execute("INSERT INTO paradas (maquina, inicio, fim, duracao_s, causa) VALUES (?,?,?,?,?)",
                (maquina, agora_txt(t_inicio), agora_txt(t_fim), round(t_fim - t_inicio, 1), causa))
    con.commit()


# ------------------------------------------------------------------ demonstração
def _demo():
    import os
    arq = "gr06_demo.db"
    if os.path.exists(arq):
        os.remove(arq)
    con = conectar(arq)
    t0 = datetime(2026, 11, 24, 8, 0, 0).timestamp()

    # 1ª leitura: grava o estado inicial de todos os sinais (aqui, só 3 para o exemplo)
    s1 = {"EMERG_SERIE": 1, "IHM_EMERG_3": 0, "HABILITA_OK": 1}
    print("1ª leitura  -> gravou", registrar_mudancas(con, "GR06", None, s1, t0), "linhas (estado inicial)")
    # leitura igual: não grava nada
    print("leitura igual -> gravou", registrar_mudancas(con, "GR06", s1, dict(s1), t0 + 5), "linhas")
    # emergência 3 apertada: mudam 3 sinais
    s2 = {"EMERG_SERIE": 0, "IHM_EMERG_3": 1, "HABILITA_OK": 0}
    print("emergência 3 -> gravou", registrar_mudancas(con, "GR06", s1, s2, t0 + 600), "linhas")

    registrar_parada(con, "GR06", t0 + 600, t0 + 690, "Emergência 3 (esquerdo)")
    registrar_parada(con, "GR06", t0 + 3600, t0 + 3640, "Cortina 2")
    registrar_parada(con, "GR06", t0 + 7200, t0 + 7330, "Emergência 3 (esquerdo)")

    print("\nSELECT * FROM eventos")
    for l in con.execute("SELECT * FROM eventos"):
        print("  ", l)
    print("\nSELECT * FROM paradas")
    for l in con.execute("SELECT * FROM paradas"):
        print("  ", l)
    print("\nSELECT * FROM resumo_diario   (calculado pela VIEW)")
    for l in con.execute("SELECT * FROM resumo_diario"):
        print("  ", l)
    con.close()
    print(f"\nArquivo criado: {arq}  -> abra no 'DB Browser for SQLite' para ver as tabelas")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        _demo()
    else:
        print(__doc__)
