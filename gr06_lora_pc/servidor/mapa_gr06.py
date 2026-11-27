"""
mapa_gr06.py  -  Mapa REAL do gateway da GR06 (tirado do Upload de 18/11/2026).

Fonte: Report do Flexi Soft Designer, seção "GMOD - Routing", Data Set 1.
Cada sinal = (byte, bit) dentro do Data Set 1 (32 bytes).

Atenção: o GMOD da GR06 está no modo "Gateway writes to tag/file"
(ele ESCREVE os dados na IHM 192.168.1.11). Ainda não sabemos se ele
também responde a leituras. O diagnostico_gr06.py serve para descobrir.
"""

IP_GMOD = "192.168.1.10"
IP_IHM = "192.168.1.11"          # NUNCA use este IP no notebook
UNIT_ID = 1
N_REGISTRADORES = 16              # Data Set 1 = 32 bytes = 16 registradores

# Endereço inicial do Data Set 1 (base 0). O Report diz 400001 -> 0.
# O diagnóstico confirma no dia; ajuste aqui se ele indicar outro.
ENDERECO_DS1 = 0
BYTE_PAR_NA_PARTE_BAIXA = True    # o diagnóstico também confirma isso

MAPA = {
    # ---------------- Byte 4 - XTIO[1] entradas ----------------
    "EMERG_SERIE": (4, 0),               # botões de emergência (2 canais) - 1 = soltos
    "TRAVAS_PORTAS": (4, 2),             # 1 = travadas
    "SEG_MOTOR_1A": (4, 4), "SEG_MOTOR_1B": (4, 5),
    "CORTINA_1": (4, 6),                 # 1 = livre
    # ---------------- Byte 5 - XTIO[2] entradas ----------------
    "CORTINA_2": (5, 0), "CORTINA_3": (5, 2),
    "BTN_GIRA_HOR": (5, 4), "BTN_GIRA_ANTI": (5, 5),
    "SEG_MOTOR_2A": (5, 6), "SEG_MOTOR_2B": (5, 7),
    # ---------------- Byte 6 - XTIO[3] entradas ----------------
    "SEG_MOVIDA_1A": (6, 0), "SEG_MOVIDA_1B": (6, 1),
    "TRAVA_1": (6, 2), "TRAVA_2": (6, 3),
    "EMERG_1_DIR": (6, 4), "EMERG_2_DIR": (6, 5),          # contatos NA: sentido a confirmar
    "EMERG_3_ESQ": (6, 6), "EMERG_4_ESQ": (6, 7),
    # ---------------- Byte 7 - XTIO[4] entradas ----------------
    "EMERG_5_PAINEL": (7, 0), "INVERSOR_OK": (7, 1),
    "RESET_COMANDO": (7, 2), "RESET_EXTERNO": (7, 3),
    "MON_EMERG_INV": (7, 4), "LIBERA_OPERADOR": (7, 5),
    "MON_HABILITA_FREIO": (7, 6), "TERMICOS_OK": (7, 7),
    # ---------------- Byte 8 - XTIO[5] entradas ----------------
    "BTN_LIB_PORTA_1": (8, 0), "BTN_LIB_PORTA_2": (8, 1),
    "MON_CONT_GIRADOR": (8, 2), "MON_MOTOR_GIRADOR": (8, 3),
    "LIM_GIRO_HOR": (8, 4), "LIM_GIRO_ANTI": (8, 5),
    "SEG_MOVIDA_2A": (8, 6), "SEG_MOVIDA_2B": (8, 7),
    # ---------------- Bytes 16-20 - saídas ----------------
    "SAIDA_EMERG_INVERSOR": (16, 0), "HABILITA_INVERSOR": (16, 1),
    "LIBERA_FREIO": (16, 2), "SINALIZ_MOVIMENTO": (16, 3),
    "LED_RESET_COMANDO": (17, 0), "LED_RESET_EXTERNO": (17, 1),
    "CONTATORES_POTENCIA": (17, 2), "RESET_INVERSOR": (17, 3),
    "COL_PRONTO": (18, 0), "COL_OPERACAO": (18, 1),
    "COL_INCAPAZ": (18, 2), "ALARME_SONORO": (18, 3),
    "CONT_GIRA_HOR": (19, 0), "CONT_GIRA_ANTI": (19, 1),
    "LIB_PORTA_1": (20, 0), "LIB_PORTA_2": (20, 1),
    # ---------------- Bytes 28-31 - montados pela página "IHM" ----------------
    "IHM_IDX_MOTOR_1": (28, 0), "IHM_IDX_MOTOR_2": (28, 1),
    "IHM_IDX_MOVIDA_1": (28, 2), "IHM_IDX_MOVIDA_2": (28, 3),
    "IHM_TRAVA_1": (28, 4), "IHM_TRAVA_2": (28, 5),
    "IHM_CORTINA_1": (28, 6), "IHM_CORTINA_2": (28, 7),
    "IHM_CORTINA_3": (29, 0),
    "IHM_EMERG_1": (29, 1), "IHM_EMERG_2": (29, 2), "IHM_EMERG_3": (29, 3),
    "IHM_EMERG_4": (29, 4), "IHM_EMERG_5": (29, 5),
    "IHM_BTN_GIRA_HOR": (29, 6), "IHM_BTN_GIRA_ANTI": (29, 7),
    "IHM_LIBERA_OPERADOR": (30, 0), "IHM_MON_HAB_FREIO": (30, 1),
    "IHM_LIM_HOR": (30, 2), "IHM_LIM_ANTI": (30, 3),
    "IHM_ALGUM_BTN_GIRO": (30, 4), "AGUARDA_RESET": (30, 5),
    "IHM_TRAVAS_A": (30, 6), "IHM_TRAVAS_B": (30, 7),
    "IHM_BTN_LIB_PORTA_1": (31, 0), "IHM_BTN_LIB_PORTA_2": (31, 1),
    "IHM_GIRA_HOR": (31, 2), "IHM_GIRA_ANTI": (31, 3),
    "HABILITA_OK": (31, 4), "IHM_EMERG_SERIE": (31, 5),
    "IHM_LIBERA_OPERADOR_2": (31, 6), "INVERSOR_E_TERMICOS_OK": (31, 7),
}

# Sinais usados como "prova de vida" no dia do teste
SINAIS_CHAVE = ["EMERG_SERIE", "CORTINA_1", "CORTINA_2", "CORTINA_3", "TRAVAS_PORTAS",
                "INVERSOR_OK", "COL_PRONTO", "COL_OPERACAO", "COL_INCAPAZ",
                "HABILITA_OK", "AGUARDA_RESET"]


def registradores_para_bytes(regs, par_na_baixa=None):
    if par_na_baixa is None:
        par_na_baixa = BYTE_PAR_NA_PARTE_BAIXA
    dados = []
    for r in regs:
        baixo, alto = r & 0xFF, r >> 8
        dados += [baixo, alto] if par_na_baixa else [alto, baixo]
    return dados


def bytes_para_registradores(dados, par_na_baixa=None):
    if par_na_baixa is None:
        par_na_baixa = BYTE_PAR_NA_PARTE_BAIXA
    regs = []
    for i in range(0, len(dados), 2):
        par, impar = dados[i], dados[i + 1]
        regs.append((impar << 8) | par if par_na_baixa else (par << 8) | impar)
    return regs


def bytes_para_sinais(dados):
    return {n: (dados[b] >> bit) & 1 for n, (b, bit) in MAPA.items() if b < len(dados)}


def sinais_para_bytes(sinais, tamanho=32):
    dados = [0] * tamanho
    for n, v in sinais.items():
        b, bit = MAPA[n]
        if v:
            dados[b] |= 1 << bit
    return dados
