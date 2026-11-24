# Coleta GR06 – versão definitiva (base comprovada: TCP 5000, 24/11/2026)

```
[IHM 192.168.1.11] ◀─Modbus─ eth0 [Raspberry 192.168.80.4] ─TCP 5000 (GBMX)─▶ [ESP2 192.168.80.5] ─USB─▶ [Servidor]
```

| Dispositivo | Pasta | Arquivos |
|---|---|---|
| Raspberry | `raspberry/` → `~/Documents/Dados` | `coletor_pi.py`, `protocolo.py`, `mapa_gr06.py`, `ler_ihm.py`, `coletor-gr06.service` |
| ESP2 | `esp32/ponte_gr06/` | `ponte_gr06.ino` (definitivo) · `esp32/teste_tcp_5000/` (teste) |
| Servidor | `servidor/` | `supervisorio_gr06.py`, `protocolo.py`, `mapa_gr06.py`, `banco_gr06.py`, `static/index.html`, `requirements.txt` |

Mensagem Pi → ESP2: `D;<maq>;<status>;<seq>;<64 hex>;<CRC16>` + `\n`. ESP2 responde `OK <seq>`
e manda para a USB a linha sem o CRC. O arquivo `.ino` contém a senha do Wi-Fi: não publicar.

## Testes, nesta ordem
1. Pi: `venv/bin/python coletor_pi.py` → "mudança entregue ao ESP32 (seq 0)".
   Monitor Serial do ESP2 → `D;1;0;0;0000...` (status 0 = IHM fora; normal sem o cabo).
2. Servidor: fechar o Monitor Serial → `python supervisorio_gr06.py --serial COMx` → http://localhost:8000
   → deve mostrar "Raspberry OK, IHM sem resposta".
3. Máquina: cabo da eth0 na porta livre do GMOD → status 1 e a dash com os dados reais.
4. Automático: instalar `coletor-gr06.service` (instruções dentro do arquivo).
