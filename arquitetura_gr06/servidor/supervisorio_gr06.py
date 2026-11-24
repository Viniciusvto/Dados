"""
supervisorio_gr06.py  -  Supervisório da GR06 (FastAPI + página HTML).

Duas fontes de dados possíveis (escolhidas na linha de comando):
  SERIAL  (arquitetura nova):  IHM -> Raspberry -> UDP/rede OT -> ESP32 -> USB -> aqui
          python supervisorio_gr06.py --serial COM5
  MODBUS  (direto, notebook ligado na máquina):
          python supervisorio_gr06.py --ip 192.168.1.11
Depois abrir:  http://localhost:8000          (API crua: /api/estado)

Gravação: eventos e paradas no SQLite gr06.db (banco_gr06.py) e, por enquanto,
as paradas também em paradas_gr06.csv.

Partes do programa:
  1. COLETA  - tarefa em segundo plano lê a IHM a cada 1 s.
  2. ANÁLISE - estado, causa da parada, duração, linha do tempo, contadores.
  3. API     - /api/estado (JSON) e /api/paradas.csv (histórico).
  4. PÁGINA  - static/index.html desenha e consulta a API a cada 1 s.

Histórico: cada parada encerrada é gravada em paradas_gr06.csv (mesma pasta),
então o histórico sobrevive se o programa for fechado.
"""
import argparse
import asyncio
import csv
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pymodbus.client import ModbusTcpClient

import banco_gr06 as banco
import mapa_gr06 as mapa
import protocolo

CONFIG = {"ip": mapa.IP_IHM, "porta": 502, "serial": None}
MAQUINA = "GR06"
SEM_PACOTE_MAX = 15      # s sem pacote do ESP32 = sem dados (Pi envia no mínimo a cada 5 s)
PERIODO = 1.0            # a IHM só recebe dados novos a cada ~5 s; 1 s basta
JANELA_TIMELINE = 3600   # linha do tempo mostra a última 1 h
PASTA = Path(__file__).parent
ARQ_PARADAS = PASTA / "paradas_gr06.csv"
db = banco.conectar(PASTA / "gr06.db")

NOMES_EMERG = {
    "IHM_EMERG_1": "Emergência 1 (direito)",
    "IHM_EMERG_2": "Emergência 2 (direito)",
    "IHM_EMERG_3": "Emergência 3 (esquerdo)",
    "IHM_EMERG_4": "Emergência 4 (esquerdo)",
    "IHM_EMERG_5": "Emergência 5 (painel)",
}


# ---------------------------------------------------------------- 1. Coleta
class LeitorSerial(threading.Thread):
    """Fica lendo, em segundo plano, as linhas que o ESP32 manda pela USB."""

    def __init__(self, porta, baud=115200):
        super().__init__(daemon=True)
        self.porta, self.baud = porta, baud
        self.ultimo = None          # (status, seq, dados, hora)
        self.aberta = False
        self.perdidos = 0           # pacotes que faltaram (pulos no seq)
        self.recebidos = 0

    def run(self):
        import serial               # pyserial; só é preciso no modo --serial
        while True:
            try:
                with serial.Serial(self.porta, self.baud, timeout=1) as sp:
                    self.aberta = True
                    print(f"Serial {self.porta} aberta")
                    while True:
                        linha = sp.readline().decode("ascii", "replace").strip()
                        if not linha:
                            continue
                        if linha.startswith("#"):
                            print("ESP32", linha)
                            continue
                        d = protocolo.ler_linha(linha)
                        if d is None:
                            continue
                        _, status, seq, dados = d
                        if self.ultimo is not None:
                            pulo = (seq - self.ultimo[1] - 1) & 0xFFFF
                            if 0 < pulo < 1000:      # pulos enormes = Pi reiniciou o contador
                                self.perdidos += pulo
                        self.recebidos += 1
                        self.ultimo = (status, seq, dados, time.time())
            except Exception as e:  # cabo USB solto, porta errada...
                self.aberta = False
                print(f"Serial {self.porta}: {e} - tentando de novo em 3 s")
                time.sleep(3)

    def elo(self):
        """Situação de cada trecho da corrente, para mostrar na dash."""
        if not self.aberta:
            return "USB do ESP32 desconectado"
        if self.ultimo is None or time.time() - self.ultimo[3] > SEM_PACOTE_MAX:
            return "ESP32 OK, sem pacotes do Raspberry"
        if self.ultimo[0] == 0:
            return "Raspberry OK, IHM sem resposta"
        return "OK"

    def ler(self):
        if self.elo() != "OK":
            return None
        return mapa.bytes_para_sinais(self.ultimo[2])


leitor = None   # criado no __main__ se usar --serial


def ler():
    if leitor is not None:
        return leitor.ler()
    return ler_modbus()


def ler_modbus():
    c = ModbusTcpClient(CONFIG["ip"], port=CONFIG["porta"], timeout=2)
    try:
        if not c.connect():
            return None
        r = c.read_holding_registers(mapa.ENDERECO_DS1, mapa.N_REGISTRADORES,
                                     slave=mapa.UNIT_ID)
        if r.isError():
            return None
        return mapa.bytes_para_sinais(mapa.registradores_para_bytes(r.registers))
    finally:
        c.close()


# ---------------------------------------------------------------- 2. Análise
def estado(s):
    """OPERANDO = girando | PRONTO = habilitada, esperando operador | PARADA = sem habilitação."""
    if s["COL_OPERACAO"]:
        return "OPERANDO"
    if s["COL_PRONTO"]:
        return "PRONTO"
    return "PARADA"


def indexador_ok(s):
    return all(s[k] for k in ("IHM_IDX_MOTOR_1", "IHM_IDX_MOTOR_2",
                              "IHM_IDX_MOVIDA_1", "IHM_IDX_MOVIDA_2"))


def causa(s):
    """Por que a máquina está sem habilitação? Mesma ordem das condições do bloco Restart.
    Devolve (causa, o que fazer)."""
    if not s["EMERG_SERIE"]:
        quais = [n for k, n in NOMES_EMERG.items() if s[k]]
        nome = quais[0] if quais else "Emergência"
        return nome, f"Destravar {nome.lower()} e apertar RESET"
    if not s["TRAVAS_PORTAS"]:
        return "Porta destravada/aberta", "Fechar e travar as portas"
    for k, n in (("CORTINA_1", "Cortina 1"), ("CORTINA_2", "Cortina 2"),
                 ("CORTINA_3", "Cortina 3")):
        if not s[k]:
            return n, f"Liberar a área da {n.lower()}"
    if not s["INVERSOR_OK"]:
        return "Inversor em falha", "Ver código de falha no display do inversor"
    if not s["TERMICOS_OK"]:
        return "Térmico do inversor/freio", "Verificar térmicos do motor e do freio"
    if not indexador_ok(s):
        return "Sensores do indexador", "Verificar posição e sensores do indexador"
    if not s["LIBERA_OPERADOR"]:
        return "Operador não liberado", "Liberar pelo comando do operador"
    if s["AGUARDA_RESET"]:
        return "Aguardando reset", "Apertar RESET"
    return "Não identificada", "Conferir sinais na seção Condições"


def condicoes(s):
    """Lista para a página: (grupo, nome, ok). ok=True = condição satisfeita."""
    c = [("Emergências", f"EM{i}", not s[f"IHM_EMERG_{i}"]) for i in range(1, 6)]
    c += [("Proteções", "Portas travadas", s["TRAVAS_PORTAS"]),
          ("Proteções", "Trava 1", s["TRAVA_1"]),
          ("Proteções", "Trava 2", s["TRAVA_2"]),
          ("Proteções", "Cortina 1", s["CORTINA_1"]),
          ("Proteções", "Cortina 2", s["CORTINA_2"]),
          ("Proteções", "Cortina 3", s["CORTINA_3"]),
          ("Acionamento", "Inversor OK", s["INVERSOR_OK"]),
          ("Acionamento", "Térmicos OK", s["TERMICOS_OK"]),
          ("Acionamento", "Liberação operador", s["LIBERA_OPERADOR"]),
          ("Indexador", "Motor 1", s["IHM_IDX_MOTOR_1"]),
          ("Indexador", "Motor 2", s["IHM_IDX_MOTOR_2"]),
          ("Indexador", "Movida 1", s["IHM_IDX_MOVIDA_1"]),
          ("Indexador", "Movida 2", s["IHM_IDX_MOVIDA_2"])]
    return [{"grupo": g, "nome": n, "ok": bool(ok)} for g, n, ok in c]


def saidas(s):
    """Saídas/estados de comando: só ligado/desligado (não é falha)."""
    lista = [("Habilita inversor", "HABILITA_INVERSOR"), ("Contatores potência", "CONTATORES_POTENCIA"),
             ("Freio liberado", "LIBERA_FREIO"), ("Gira horário", "CONT_GIRA_HOR"),
             ("Gira anti-horário", "CONT_GIRA_ANTI"), ("Fim curso horário", "LIM_GIRO_HOR"),
             ("Fim curso anti", "LIM_GIRO_ANTI"), ("Alarme sonoro", "ALARME_SONORO")]
    return [{"nome": n, "on": bool(s[k])} for n, k in lista]


def hora(t):
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


class Supervisor:
    def __init__(self):
        self.inicio = time.time()
        self.s = None
        self.ant = None
        self.t_ant = time.time()
        self.ultima_ok = None
        self.tempo = {"OPERANDO": 0.0, "PRONTO": 0.0, "PARADA": 0.0, "SEM_DADOS": 0.0}
        self.est = None              # estado atual (inclui SEM_DADOS)
        self.desde = time.time()     # desde quando está nesse estado
        self.segmentos = []          # linha do tempo: {e, ini, fim}
        self.giros = {"horario": 0, "anti_horario": 0}
        self.parada = None           # parada em andamento: {ini, causa, acao}
        self.paradas = []            # paradas encerradas (mais recente primeiro)
        self.por_causa = {}          # causa -> {n, seg}
        self.eventos = []

    def evento(self, tipo, texto):
        self.eventos.insert(0, {"hora": hora(time.time()), "tipo": tipo, "texto": texto})
        del self.eventos[100:]

    def _timeline(self, e, agora):
        if self.segmentos and self.segmentos[-1]["e"] == e:
            self.segmentos[-1]["fim"] = agora
        else:
            self.segmentos.append({"e": e, "ini": agora, "fim": agora})
        while self.segmentos and self.segmentos[0]["fim"] < agora - JANELA_TIMELINE:
            self.segmentos.pop(0)

    def _fecha_parada(self, agora):
        p = self.parada
        dur = agora - p["ini"]
        reg = {"ini": p["ini"], "fim": agora, "dur": dur, "causa": p["causa"]}
        self.paradas.insert(0, reg)
        del self.paradas[200:]
        try:
            banco.registrar_parada(db, MAQUINA, p["ini"], agora, p["causa"])
        except Exception as e:
            print("SQLite (parada):", e)
        c = self.por_causa.setdefault(p["causa"], {"n": 0, "seg": 0.0})
        c["seg"] += dur
        novo = not ARQ_PARADAS.exists()
        try:
            with open(ARQ_PARADAS, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                if novo:
                    w.writerow(["inicio", "fim", "duracao_s", "causa"])
                w.writerow([datetime.fromtimestamp(p["ini"]).isoformat(sep=" ", timespec="seconds"),
                            datetime.fromtimestamp(agora).isoformat(sep=" ", timespec="seconds"),
                            round(dur), p["causa"]])
        except OSError:
            pass  # arquivo aberto no Excel, por ex. — não derruba o supervisório
        self.parada = None

    def atualizar(self, s):
        agora = time.time()
        dt = agora - self.t_ant
        e = "SEM_DADOS" if s is None else estado(s)
        if self.est is not None:
            self.tempo[self.est] += dt
        if e != self.est:
            self.desde = agora
            if e == "SEM_DADOS":
                self.evento("falha", "Sem dados da máquina")
            elif self.est == "SEM_DADOS":
                self.evento("ok", "Comunicação restabelecida")
        self.est = e
        self._timeline(e, agora)

        a = self.ant
        if s is not None and a is not None:
            if s["CONT_GIRA_HOR"] and not a["CONT_GIRA_HOR"]:
                self.giros["horario"] += 1
                self.evento("giro", "Giro horário")
            if s["CONT_GIRA_ANTI"] and not a["CONT_GIRA_ANTI"]:
                self.giros["anti_horario"] += 1
                self.evento("giro", "Giro anti-horário")
            if a["HABILITA_OK"] and not s["HABILITA_OK"]:
                c, acao = causa(s)
                self.parada = {"ini": agora, "causa": c, "acao": acao}
                self.por_causa.setdefault(c, {"n": 0, "seg": 0.0})["n"] += 1
                self.evento("parada", f"Parada: {c}")
            if s["HABILITA_OK"] and not a["HABILITA_OK"]:
                if self.parada:
                    dur = agora - self.parada["ini"]
                    self._fecha_parada(agora)
                    m, x = divmod(round(dur), 60)
                    self.evento("ok", f"Habilitada (parou {m}m {x:02d}s)" if m else f"Habilitada (parou {x}s)")
                else:
                    self.evento("ok", "Habilitada")
        if s is not None:
            try:
                banco.registrar_mudancas(db, MAQUINA, self.ant, s, agora)
            except Exception as e:
                print("SQLite (eventos):", e)
            self.ant, self.ultima_ok = s, agora
        self.s = s
        self.t_ant = agora

    def snapshot(self):
        agora = time.time()
        s = self.s
        ao_vivo = None
        if s is not None:
            c, acao = (None, None)
            if not s["HABILITA_OK"]:
                c, acao = causa(s)
            ao_vivo = {"estado": estado(s), "causa": c, "acao": acao,
                       "aguarda_reset": bool(s["AGUARDA_RESET"]),
                       "condicoes": condicoes(s), "saidas": saidas(s)}
        total_med = sum(v for k, v in self.tempo.items() if k != "SEM_DADOS")
        disp = None if total_med < 1 else 100 * (self.tempo["OPERANDO"] + self.tempo["PRONTO"]) / total_med
        n_par = sum(v["n"] for v in self.por_causa.values())
        seg_par = sum(p["dur"] for p in self.paradas) + (agora - self.parada["ini"] if self.parada else 0)
        ranking = sorted(({"causa": k, **v} for k, v in self.por_causa.items()),
                         key=lambda x: (-x["n"], -x["seg"]))
        return {
            "agora": agora,
            "conectado": s is not None,
            "fonte": (f"ESP32 {CONFIG['serial']} · {leitor.elo()} · {leitor.recebidos} pacotes, {leitor.perdidos} perdidos"
                      if leitor else f"IHM {CONFIG['ip']}:{CONFIG['porta']}"),
            "idade_s": None if self.ultima_ok is None else round(agora - self.ultima_ok, 1),
            "estado": self.est, "desde": self.desde,
            "ao_vivo": ao_vivo,
            "parada_atual": self.parada,
            "kpi": {"inicio": self.inicio, "disponibilidade": disp,
                    "giros": self.giros, "paradas": n_par, "tempo_parado": seg_par,
                    "mttr": (sum(p["dur"] for p in self.paradas) / len(self.paradas)) if self.paradas else None,
                    "tempo": self.tempo},
            "timeline": {"janela": JANELA_TIMELINE, "segmentos": self.segmentos},
            "ranking": ranking,
            "historico": [{**p, "ini_h": hora(p["ini"]), "fim_h": hora(p["fim"])} for p in self.paradas[:10]],
            "eventos": self.eventos[:30],
        }


sup = Supervisor()


async def laco():
    while True:
        sup.atualizar(await asyncio.to_thread(ler))
        await asyncio.sleep(PERIODO)


# ---------------------------------------------------------------- 3 e 4. API e página
@asynccontextmanager
async def vida(app):
    t = asyncio.create_task(laco())
    yield
    t.cancel()


app = FastAPI(title="Supervisório GR06", lifespan=vida)


@app.get("/api/estado")
def api_estado():
    return sup.snapshot()


@app.get("/api/paradas.csv")
def api_paradas():
    if not ARQ_PARADAS.exists():
        return JSONResponse({"erro": "nenhuma parada registrada ainda"}, status_code=404)
    return FileResponse(ARQ_PARADAS, filename="paradas_gr06.csv", media_type="text/csv")


@app.get("/")
def pagina():
    for p in (PASTA / "static" / "index.html", PASTA / "index.html"):
        if p.exists():
            return FileResponse(p)
    return {"erro": "index.html não encontrado: coloque em Dash_Modbus\\static\\"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ip", default=mapa.IP_IHM)
    p.add_argument("--porta", type=int, default=502)
    p.add_argument("--serial", help="porta do ESP32, ex.: COM5 (Windows) ou /dev/ttyUSB0 (Linux)")
    p.add_argument("--web", type=int, default=8000, help="porta da página")
    a = p.parse_args()
    CONFIG.update(ip=a.ip, porta=a.porta, serial=a.serial)
    if a.serial:
        leitor = LeitorSerial(a.serial)
        leitor.start()
        print(f"Lendo ESP32 na {a.serial} | abra http://localhost:{a.web}")
    else:
        print(f"Lendo Modbus {a.ip}:{a.porta} | abra http://localhost:{a.web}")
    uvicorn.run(app, host="127.0.0.1", port=a.web, log_level="warning")
