# GR06 via LoRa – lado do PC

```
[IHM] ─Modbus─ [Raspberry + E32] ~~LoRa~~ [E32 + ESP32] ─USB─ [PC: supervisório + dash]
```

| Pasta | O que é |
|---|---|
| `esp32/lora_receptor_gr06/` | firmware do ESP32 receptor (Arduino IDE, placa "ESP32 Dev Module") |
| `servidor/` | supervisório (FastAPI) + dash (`static/index.html`) + histórico SQLite |

O código do Raspberry (`coletor_lora.py`) fica em outro lugar.

## Rodar
1. Gravar `lora_receptor_gr06.ino` no ESP32 e fechar o Monitor Serial.
2. `cd servidor`
3. `pip install -r requirements.txt`
4. `python supervisorio_gr06.py --serial COMx`
5. Abrir http://localhost:8000

## Protocolo
- LoRa (Pi → ESP32): `G<status><seq 4 hex><32 bytes base64><CRC16 4 hex>\n` (55 bytes). Confirmação: `K<seq>\n`.
- USB (ESP32 → PC): `D;<maquina>;<status>;<seq>;<64 hex>`. Linhas com `#` são informativas.
- Leitura da IHM somente leitura (Modbus FC03).
