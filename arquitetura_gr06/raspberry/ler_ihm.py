"""
ler_ihm.py  -  Leitura didática da IHM da GR06, mostrando CADA etapa.
SOMENTE LEITURA (função 03). Uma leitura por execução.

Máquina:  python ler_ihm.py
Em casa:  python ler_ihm.py --ip 127.0.0.1 --porta 5020   (com o gmod_falso rodando)
"""
import argparse

from pymodbus.client import ModbusTcpClient

import mapa_gr06 as mapa

p = argparse.ArgumentParser()
p.add_argument("--ip", default="192.168.1.11")
p.add_argument("--porta", type=int, default=502)
a = p.parse_args()

# ETAPA 1 - Abrir a conexão TCP (a "ligação telefônica" para IP:porta)
c = ModbusTcpClient(a.ip, port=a.porta, timeout=2)
if not c.connect():
    raise SystemExit(f"ETAPA 1 falhou: {a.ip}:{a.porta} não atendeu (cabo, IP do notebook, ping)")
print(f"ETAPA 1  conectado em {a.ip}:{a.porta}")

# ETAPA 2 - Fazer a pergunta: função 03, a partir do endereço 0 (=400001), 16 registradores, Unit ID 1
r = c.read_holding_registers(0, 16, slave=1)
c.close()
if r.isError():
    raise SystemExit(f"ETAPA 2 falhou: a IHM respondeu com erro -> {r}")
print("\nETAPA 2  resposta = 16 registradores (cada um tem 16 bits = 2 bytes)")
for i, reg in enumerate(r.registers):
    print(f"   4{i + 1:05d}  (endereço {i:2d}) = {reg:5d}   hex {reg:04X}   bits {reg:016b}")

# ETAPA 3 - Separar cada registrador em 2 bytes (byte par = parte BAIXA, confirmado em campo)
dados = mapa.registradores_para_bytes(r.registers)
print("\nETAPA 3  32 bytes (o Data Set 1 do Flexi Soft)")
for i in range(0, 32, 8):
    print("   " + "  ".join(f"B{j:02d}={dados[j]:08b}" for j in range(i, i + 8)))

# ETAPA 4 - Dar nome aos bits usando o mapa (byte, bit) -> sinal
s = mapa.bytes_para_sinais(dados)
print("\nETAPA 4  sinais principais")
for nome in mapa.SINAIS_CHAVE:
    b, bit = mapa.MAPA[nome]
    print(f"   {nome:<16} byte {b:2d}.{bit}  = {s[nome]}")
