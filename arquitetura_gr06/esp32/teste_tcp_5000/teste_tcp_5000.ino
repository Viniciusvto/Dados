/*
  teste_tcp_5000.ino  -  ESP2: reproduz o teste que JÁ FUNCIONAVA.

  Objetivo: provar que o caminho Raspberry -> rede GBMX -> ESP2 continua OK,
  usando EXATAMENTE o script antigo do Pi (~/Desktop/enviar_teste_esp32.py),
  que conecta por TCP em 192.168.80.5:5000, envia "Teste Raspberry\n" e espera resposta.

  Rede: mesma ordem do ConectaGBMX.ino (que funciona nessa rede):
        modo STA -> troca de MAC -> IP fixo -> begin

  Arduino IDE: placa "ESP32 Dev Module", Monitor Serial 115200.
  Não usa biblioteca externa.
*/
#include <WiFi.h>
#include <esp_wifi.h>

// ===================== CONFIGURAR =====================
const char* WIFI_NOME  = "GBMX";
const char* WIFI_SENHA = "12345678";              // a mesma do ConectaGBMX.ino

uint8_t MAC_ESP2[6] = {0x88, 0x13, 0xBF, 0x00, 0xB9, 0x44};   // 88:13:BF:00:B9:44
IPAddress IP_ESP2 (192, 168, 80, 5);
IPAddress GATEWAY (192, 168, 80, 1);
IPAddress MASCARA (255, 255, 255, 0);
IPAddress DNS1    (8, 8, 8, 8);
const uint16_t PORTA = 5000;
// ======================================================

WiFiServer servidor(PORTA);
unsigned long t_status = 0;

void conectar() {
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
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("# Wi-Fi OK  IP=%s  MAC=%s  sinal=%d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.macAddress().c_str(), WiFi.RSSI());
  } else {
    Serial.printf("# Wi-Fi FALHOU (codigo %d): 1=rede nao encontrada, 4=senha errada\n", (int)WiFi.status());
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("# teste_tcp_5000 iniciando");
  conectar();
  servidor.begin();
  Serial.printf("# servidor TCP escutando na porta %u\n", PORTA);
}

void loop() {
  // reconecta se cair
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("# Wi-Fi caiu, reconectando");
    WiFi.disconnect();
    conectar();
    return;
  }

  // alguém conectou na porta 5000?
  WiFiClient cliente = servidor.available();
  if (cliente) {
    Serial.printf("# conexao de %s\n", cliente.remoteIP().toString().c_str());
    cliente.setTimeout(3000);
    String msg = cliente.readStringUntil('\n');
    msg.trim();
    Serial.printf("RECEBIDO: %s\n", msg.c_str());
    cliente.printf("OK ESP2 recebeu: %s\n", msg.c_str());
    delay(10);
    cliente.stop();
  }

  // a cada 30 s, um sinal de vida
  if (millis() - t_status > 30000) {
    t_status = millis();
    Serial.printf("# vivo IP=%s MAC=%s sinal=%d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.macAddress().c_str(), WiFi.RSSI());
  }
}
