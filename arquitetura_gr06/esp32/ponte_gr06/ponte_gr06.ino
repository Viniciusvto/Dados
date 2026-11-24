/*
  ponte_gr06.ino  -  ESP2: recebe do Raspberry pela rede GBMX e entrega ao servidor pela USB.

  Base: teste_tcp_5000.ino (comprovado em 24/11/2026 com o enviar_teste_esp32.py).
  Mesma rede, mesmo MAC, mesmo IP, mesma porta. O que foi acrescentado:
    - aceita conexão SÓ do IP do Raspberry;
    - confere a linha (formato + CRC16);
    - responde "OK <seq>" ao Raspberry (ou "ERRO <motivo>");
    - escreve na USB a linha SEM o CRC:  D;<maquina>;<status>;<seq>;<64 hex>
  Linhas começando com '#' são informativas.

  SEGURANÇA - "mão única": o programa NUNCA lê a USB.
  Arduino IDE: placa "ESP32 Dev Module", Monitor Serial 115200. Sem biblioteca externa.
*/
#include <WiFi.h>
#include <esp_wifi.h>

// ===================== CONFIGURAÇÃO (igual ao teste que funcionou) =====================
const char* WIFI_NOME  = "GBMX";
const char* WIFI_SENHA = "12345678";

uint8_t MAC_ESP2[6] = {0x88, 0x13, 0xBF, 0x00, 0xB9, 0x44};   // 88:13:BF:00:B9:44
IPAddress IP_ESP2 (192, 168, 80, 5);
IPAddress GATEWAY (192, 168, 80, 1);
IPAddress MASCARA (255, 255, 255, 0);
IPAddress DNS1    (8, 8, 8, 8);
const uint16_t PORTA = 5000;

IPAddress IP_RASPBERRY (192, 168, 80, 4);   // só aceita conexões deste IP
// =======================================================================================

WiFiServer servidor(PORTA);
unsigned long t_status = 0;
unsigned long aceitas = 0, rejeitadas = 0;

uint16_t crc16(const uint8_t* d, size_t n) {          // CRC-16/MODBUS (igual ao protocolo.py)
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= d[i];
    for (int b = 0; b < 8; b++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

void conectar() {                                       // idêntico ao teste comprovado
  WiFi.mode(WIFI_STA);
  esp_err_t r = esp_wifi_set_mac(WIFI_IF_STA, MAC_ESP2);
  Serial.printf("# troca de MAC: %s\n", r == ESP_OK ? "OK" : "FALHOU");
  WiFi.config(IP_ESP2, GATEWAY, MASCARA, DNS1);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  Serial.printf("# conectando em '%s'", WIFI_NOME);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 25000) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("# Wi-Fi OK  IP=%s  MAC=%s  sinal=%d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.macAddress().c_str(), WiFi.RSSI());
  else
    Serial.printf("# Wi-Fi FALHOU (codigo %d): 1=rede nao encontrada, 4=senha errada\n", (int)WiFi.status());
}

// Confere a linha "D;maq;status;seq;HEX64;CRC". Devolve "" se OK, ou o motivo da recusa.
// Se OK, preenche 'corpo' (linha sem o CRC) e 'seq'.
String validar(const String& linha, String& corpo, String& seq) {
  if (!linha.startsWith("D;")) return "formato";
  int p[5], n = 0;                                      // posições dos 5 ';'
  for (int i = 0; i < (int)linha.length() && n <= 5; i++)
    if (linha[i] == ';') { if (n < 5) p[n] = i; n++; }
  if (n != 5) return "campos";
  corpo = linha.substring(0, p[4]);
  String hex = linha.substring(p[3] + 1, p[4]);
  String crc_txt = linha.substring(p[4] + 1);
  seq = linha.substring(p[2] + 1, p[3]);
  if (hex.length() != 64) return "tamanho";
  if (crc_txt.length() != 4) return "crc";
  uint16_t crc_rx = (uint16_t)strtoul(crc_txt.c_str(), NULL, 16);
  if (crc_rx != crc16((const uint8_t*)corpo.c_str(), corpo.length())) return "crc";
  return "";
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("# ponte_gr06 iniciando");
  conectar();
  servidor.begin();
  Serial.printf("# servidor TCP na porta %u, aceitando so %s\n", PORTA, IP_RASPBERRY.toString().c_str());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {                 // reconecta se cair
    Serial.println("# Wi-Fi caiu, reconectando");
    WiFi.disconnect();
    conectar();
    return;
  }

  WiFiClient cliente = servidor.available();
  if (cliente) {
    IPAddress origem = cliente.remoteIP();
    if (origem != IP_RASPBERRY) {                      // filtro de origem
      rejeitadas++;
      Serial.printf("# conexao recusada de %s\n", origem.toString().c_str());
      cliente.stop();
    } else {
      cliente.setTimeout(3000);
      String linha = cliente.readStringUntil('\n');
      linha.trim();
      String corpo, seq;
      String erro = validar(linha, corpo, seq);
      if (erro.length() == 0) {
        aceitas++;
        Serial.println(corpo);                         // -> servidor (USB)
        cliente.printf("OK %s\n", seq.c_str());        // -> Raspberry
      } else {
        rejeitadas++;
        Serial.printf("# linha rejeitada (%s): %s\n", erro.c_str(), linha.c_str());
        cliente.printf("ERRO %s\n", erro.c_str());
      }
      delay(10);
      cliente.stop();
    }
  }

  if (millis() - t_status > 30000) {                   // sinal de vida a cada 30 s
    t_status = millis();
    Serial.printf("# vivo IP=%s MAC=%s sinal=%d dBm aceitas=%lu rejeitadas=%lu\n",
                  WiFi.localIP().toString().c_str(), WiFi.macAddress().c_str(), WiFi.RSSI(),
                  aceitas, rejeitadas);
  }
}
