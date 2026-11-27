/*
  lora_receptor_gr06.ino  -  ESP32 + E32 ligado no PC (o mesmo hardware do Vitor).

  Recebe do Raspberry, pelo LoRa:   G<status><seq 4 hex><base64 44><CRC16 4 hex>\n
  1. confere tamanho e CRC (se falhar, descarta: o Pi manda de novo)
  2. responde ao Pi pelo LoRa:      K<seq 4 hex>\n
  3. manda para o PC pela USB a linha que o supervisório já entende:
        D;1;<status>;<seq>;<64 hex>
  Linhas começando com '#' são só informação (o supervisório mostra e ignora).

  Ligações (ESP32 DevKit <-> E32-433T30D), iguais às do teste:
    E32 VCC -> VIN (5V)     E32 GND -> GND
    E32 TXD -> GPIO16 (RX2) E32 RXD -> GPIO17 (TX2)
    E32 M0  -> GPIO18       E32 M1  -> GPIO19       E32 AUX -> GPIO21
  ANTENA ROSQUEADA ANTES DE LIGAR.
  Arduino IDE: placa "ESP32 Dev Module". USB a 115200.
  O supervisório usa a mesma porta COM: FECHE o Monitor Serial antes de rodá-lo.
*/
#include "mbedtls/base64.h"

// ============ CONFIGURAÇÃO DO RÁDIO (IGUAL À GRAVADA NO E32 DO PI) ============
const uint8_t CANAL     = 0x17;  // 433 MHz
const uint8_t VEL_AR    = 0b010; // 2,4 kbps
const uint8_t POTENCIA  = 0b11;  // 21 dBm
// =============================================================================
const int MAQUINA = 1;           // 1 = GR06

const int PIN_RX2 = 16, PIN_TX2 = 17, PIN_M0 = 18, PIN_M1 = 19, PIN_AUX = 21, PIN_LED = 2;

// ------------------------------------------------------------------ funções do E32
void esperaAux(unsigned long limite = 1000) {          // AUX em 1 = módulo livre
  unsigned long t = millis();
  while (digitalRead(PIN_AUX) == LOW && millis() - t < limite) delay(1);
  delay(2);
}

void modo(int m1, int m0) {                            // 0,0 = normal | 1,1 = configuração
  digitalWrite(PIN_M1, m1);
  digitalWrite(PIN_M0, m0);
  delay(10);
  esperaAux();
  delay(50);
}

int lerResposta(uint8_t* p, int n) {
  unsigned long t = millis();
  int lidos = 0;
  while (lidos < n && millis() - t < 1000)
    if (Serial2.available()) p[lidos++] = Serial2.read();
  return lidos;
}

bool lerParametros(uint8_t* p) {
  modo(1, 1);
  while (Serial2.available()) Serial2.read();
  const uint8_t cmd[3] = {0xC1, 0xC1, 0xC1};
  Serial2.write(cmd, 3);
  int n = lerResposta(p, 6);
  modo(0, 0);
  return n == 6 && p[0] == 0xC0;
}

bool gravarParametros(const uint8_t* p) {
  modo(1, 1);
  while (Serial2.available()) Serial2.read();
  Serial2.write(p, 6);
  uint8_t eco[6];
  int n = lerResposta(eco, 6);
  modo(0, 0);
  return n == 6 && memcmp(eco, p, 6) == 0;
}

void mostrarParametros(const uint8_t* p) {
  const char* vel[] = {"0,3k", "1,2k", "2,4k", "4,8k", "9,6k", "19,2k", "19,2k", "19,2k"};
  const int pot[] = {30, 27, 24, 21};
  Serial.printf("#   canal=%u (%u MHz)  vel_ar=%s bps  potencia=%d dBm\n",
                p[4], 410 + p[4], vel[p[3] & 0x07], pot[p[5] & 0x03]);
}

void configurarE32() {
  const uint8_t desejado[6] = {0xC0, 0x00, 0x00, (uint8_t)(0b00011000 | VEL_AR), CANAL,
                               (uint8_t)(0b01000100 | POTENCIA)};
  uint8_t atual[6];
  if (!lerParametros(atual)) {
    Serial.println("# ERRO: o E32 nao respondeu. Confira fios, M0/M1/AUX e alimentacao.");
    return;
  }
  Serial.println("# configuracao do E32:");
  mostrarParametros(atual);
  if (memcmp(atual, desejado, 6) != 0) {
    Serial.println(gravarParametros(desejado) ? "# configuracao gravada:" : "# ERRO ao gravar a configuracao");
    if (lerParametros(atual)) mostrarParametros(atual);
  }
}

// ------------------------------------------------------------------ protocolo
uint16_t crc16(const uint8_t* d, size_t n) {           // CRC-16/MODBUS (igual ao Python)
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= d[i];
    for (int b = 0; b < 8; b++) crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

bool ehHex(const String& s) {
  for (unsigned i = 0; i < s.length(); i++) if (!isxdigit((unsigned char)s[i])) return false;
  return s.length() > 0;
}

// ------------------------------------------------------------------ programa
const int TAM_PACOTE = 54;     // G(1) + status(1) + seq(4) + base64(44) + CRC(4), sem o '\n'
uint32_t recebidos = 0, invalidos = 0, repetidos = 0;
long ultimoSeq = -1;
unsigned long t_led = 0, t_vivo = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_M0, OUTPUT);
  pinMode(PIN_M1, OUTPUT);
  pinMode(PIN_AUX, INPUT);
  pinMode(PIN_LED, OUTPUT);
  Serial2.begin(9600, SERIAL_8N1, PIN_RX2, PIN_TX2);
  Serial2.setTimeout(300);
  delay(500);
  Serial.println("# lora_receptor_gr06 iniciando");
  configurarE32();
  modo(0, 0);
  Serial.println("# aguardando pacotes do Raspberry...");
}

void loop() {
  if (Serial2.available()) {
    String linha = Serial2.readStringUntil('\n');
    linha.trim();

    // ---- 1. confere formato e CRC
    String erro = "";
    if (linha.length() != TAM_PACOTE || linha[0] != 'G') erro = "tamanho/inicio";
    String corpo = linha.substring(0, TAM_PACOTE - 4);
    String txtCrc = linha.substring(TAM_PACOTE - 4);
    String txtSeq = linha.substring(2, 6);
    if (erro == "" && (!ehHex(txtCrc) || !ehHex(txtSeq))) erro = "hex";
    if (erro == "" && (uint16_t)strtoul(txtCrc.c_str(), NULL, 16) !=
                      crc16((const uint8_t*)corpo.c_str(), corpo.length())) erro = "CRC";

    uint8_t dados[34];
    size_t n = 0;
    if (erro == "") {
      String b64 = linha.substring(6, 50);
      if (mbedtls_base64_decode(dados, sizeof(dados), &n, (const unsigned char*)b64.c_str(), b64.length()) != 0
          || n != 32) erro = "base64";
    }
    if (erro != "") {
      invalidos++;
      Serial.printf("# pacote invalido (%s): %s\n", erro.c_str(), linha.c_str());
      return;
    }

    // ---- 2. confirma para o Pi
    long seq = strtol(txtSeq.c_str(), NULL, 16);
    char status = linha[1];
    esperaAux();
    Serial2.printf("K%04lX\n", seq);

    // ---- 3. entrega ao PC (repetido = o Pi não ouviu nossa confirmação e mandou de novo)
    if (seq == ultimoSeq) {
      repetidos++;
    } else {
      ultimoSeq = seq;
      recebidos++;
      Serial.printf("D;%d;%c;%ld;", MAQUINA, status, seq);
      for (int i = 0; i < 32; i++) Serial.printf("%02X", dados[i]);
      Serial.println();
    }
    digitalWrite(PIN_LED, HIGH);
    t_led = millis();
  }

  if (t_led && millis() - t_led > 200) {
    digitalWrite(PIN_LED, LOW);
    t_led = 0;
  }
  if (millis() - t_vivo > 30000) {                     // resumo a cada 30 s
    t_vivo = millis();
    Serial.printf("# vivo: recebidos=%lu repetidos=%lu invalidos=%lu\n",
                  (unsigned long)recebidos, (unsigned long)repetidos, (unsigned long)invalidos);
  }
}
