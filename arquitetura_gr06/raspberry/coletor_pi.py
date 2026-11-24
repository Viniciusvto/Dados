#!/usr/bin/env python3
"""
coletor_pi.py  -  Roda no RASPBERRY PI.

Em laço, a cada 1 s:
  1. LÊ a IHM via Modbus TCP (função 03, somente leitura) pelo cabo (eth0).
  2. Se algum byte mudou, ou passaram 5 s desde o último envio:
     ENVIA uma linha de texto ao ESP32 por TCP (porta 5000) pela rede GBMX,
     do mesmo jeito que o enviar_teste_esp32.py (que funcionou),
     e espera a confirmação "OK <seq>".
  Se o envio falhar, tenta de novo na volta seguinte (não perde a mudança).
  Se a IHM não responder, envia status 0 ("Raspberry vivo, IHM sem resposta").

Uso:
  cd ~/Documents/Dados
  venv/bin/python coletor_pi.py                       (padrão: ESP32 192.168.80.5:5000)
  venv/bin/python coletor_pi.py --esp 192.168.80.5 --porta-esp 5000
"""
import argparse
import logging
import socket
import time

from pymodbus.client import ModbusTcpClient

import mapa_gr06 as mapa
import protocolo

MAQUINA = 1          # 1 = GR06
PERIODO = 1.0        # lê a IHM a cada 1 s (ela recebe dados novos a cada ~5 s)
VIVO_A_CADA = 5.0    # reenvia mesmo sem mudança ("estou vivo")

log = logging.getLogger("coletor")


def enviar(esp, porta, linha, seq):
    """Abre a conexão TCP, envia a linha e espera 'OK <seq>'. Devolve True se confirmado."""
    try:
        with socket.create_connection((esp, porta), timeout=3.0) as s:
            s.sendall(linha.encode("ascii"))
            s.settimeout(3.0)
            resposta = s.recv(64).decode("ascii", "ignore").strip()
    except OSError as e:                       # timeout, recusada, sem rota...
        log.warning("ESP32 %s:%s sem resposta: %s", esp, porta, e)
        return False
    if resposta == f"OK {seq}":
        return True
    log.warning("ESP32 respondeu '%s' (esperado 'OK %d')", resposta, seq)
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ihm", default=mapa.IP_IHM, help="IP da IHM (rede da máquina)")
    p.add_argument("--porta", type=int, default=502, help="porta Modbus da IHM")
    p.add_argument("--esp", default="192.168.80.5", help="IP do ESP32 na rede GBMX")
    p.add_argument("--porta-esp", type=int, default=5000, help="porta TCP do ESP32")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)   # cala os avisos repetidos da biblioteca

    cli = ModbusTcpClient(a.ihm, port=a.porta, timeout=2)
    seq, ultimo, t_envio, ihm_ok = 0, None, 0.0, None
    log.info("Lendo IHM %s:%s -> enviando ao ESP32 %s:%s", a.ihm, a.porta, a.esp, a.porta_esp)

    while True:
        inicio = time.time()

        # ---- 1. ler a IHM
        dados, status = [0] * protocolo.N_DADOS, 0
        try:
            if not cli.connected:
                cli.connect()
            r = cli.read_holding_registers(mapa.ENDERECO_DS1, mapa.N_REGISTRADORES, slave=mapa.UNIT_ID)
            if not r.isError():
                dados, status = mapa.registradores_para_bytes(r.registers), 1
        except Exception as e:
            log.debug("erro Modbus: %s", e)
        if status == 0:
            cli.close()                        # força reconectar na próxima volta
        if status != ihm_ok:
            log.info("IHM %s", "respondendo" if status else "SEM RESPOSTA")
            ihm_ok = status

        # ---- 2. enviar se mudou ou se passou o tempo do "estou vivo"
        atual = (status, tuple(dados))
        if atual != ultimo or inicio - t_envio >= VIVO_A_CADA:
            linha = protocolo.montar_linha(MAQUINA, status, seq, dados)
            if enviar(a.esp, a.porta_esp, linha, seq):
                if atual != ultimo:
                    log.info("mudança entregue ao ESP32 (seq %d)", seq)
                ultimo, t_envio = atual, inicio      # só marca como enviado se o ESP32 confirmou
                seq = (seq + 1) & 0xFFFF

        time.sleep(max(0.0, PERIODO - (time.time() - inicio)))


if __name__ == "__main__":
    main()
