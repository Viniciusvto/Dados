"""
protocolo.py  -  Formato da mensagem Raspberry -> ESP32 -> servidor.
(O mesmo arquivo é usado no Raspberry e no servidor.)

Raspberry -> ESP32 (TCP, porta 5000), uma linha de texto:
    D;<maquina>;<status>;<seq>;<64 hex>;<CRC16 4 hex>\n
ESP32 -> servidor (USB), a mesma linha SEM o CRC:
    D;<maquina>;<status>;<seq>;<64 hex>
Linhas começando com '#' são mensagens informativas do ESP32.

  maquina : 1 = GR06
  status  : 1 = leitura da IHM OK | 0 = Raspberry vivo, IHM sem resposta
  seq     : contador 0..65535 (pulo = mensagem perdida)
  64 hex  : os 32 bytes do Data Set 1
  CRC16   : CRC-16/MODBUS do texto antes do último ';' (confere se chegou íntegro)
"""
N_DADOS = 32


def crc16(dados: bytes) -> int:
    """CRC-16/MODBUS: o mesmo cálculo do Modbus RTU (e do ESP32)."""
    crc = 0xFFFF
    for b in dados:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def montar_linha(maquina: int, status: int, seq: int, dados) -> str:
    """Linha que o Raspberry envia ao ESP32 (com CRC e '\\n')."""
    corpo = f"D;{maquina};{status};{seq & 0xFFFF};{bytes(dados).hex().upper()}"
    return f"{corpo};{crc16(corpo.encode('ascii')):04X}\n"


def ler_linha(linha: str):
    """Abre uma linha 'D;...' (com ou sem CRC). Devolve (maquina, status, seq, dados) ou None."""
    partes = linha.strip().split(";")
    if len(partes) == 6:                                   # veio com CRC: confere
        corpo = ";".join(partes[:5])
        try:
            if int(partes[5], 16) != crc16(corpo.encode("ascii")):
                return None
        except ValueError:
            return None
        partes = partes[:5]
    if len(partes) != 5 or partes[0] != "D" or len(partes[4]) != 2 * N_DADOS:
        return None
    try:
        return int(partes[1]), int(partes[2]), int(partes[3]), list(bytes.fromhex(partes[4]))
    except ValueError:
        return None
