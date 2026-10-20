"""MP2886A Page 0 PMBus command catalog transcribed from datasheet pages 33-36."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Register:
    code: int
    name: str
    access: str
    width: int

    @property
    def can_read(self):
        return self.access in ("r", "r/w")

    @property
    def can_write(self):
        return self.access in ("w", "r/w")


_ROWS = (
    (0x00, "PAGE", "r/w", 1),
    (0x01, "OPERATION", "r/w", 1),
    (0x03, "CLEAR_FAULTS", "Send", 0),
    (0x04, "MFR_USER_PWD", "w", 2),
    (0x05, "BUF_REG_UPD", "Send", 0),
    (0x06, "MFR_EEPROM_CTRL", "r/w", 1),
    (0x13, "WRITE_PROTECT", "r/w", 1),
    (0x15, "STORE_USER_ALL", "Send", 0),
    (0x16, "RESTORE_USER_ALL", "Send", 0),
    (0x1C, "MFR_DROOP_CMPN1", "r/w", 2),
    (0x1D, "MFR_DROOP_CMPN2", "r/w", 2),
    (0x1E, "MFR_IDROOP_CTRL", "r/w", 1),
    (0x1F, "VOUT_MIN", "r/w", 2),
    (0x21, "VOUT_COMMAND", "r/w", 2),
    (0x23, "VOUT_OFFSET", "r/w", 2),
    (0x24, "VOUT_MAX", "r/w", 2),
    (0x25, "VOUT_MARGIN_HIGH", "r/w", 2),
    (0x26, "VOUT_MARGIN_LOW", "r/w", 2),
    (0x27, "VENDOR_ID_USER", "r/w", 1),
    (0x28, "PRODUCT_ID_USER", "r/w", 1),
    (0x29, "PRODUCT_REV_USER", "r/w", 1),
    (0x2A, "MFR_DC_DIV_SET", "r/w", 2),
    (0x2B, "MFR_IDROOP_OFFSET", "r/w", 1),
    (0x2C, "MFR_OVUV_SEL", "r/w", 2),
    (0x2D, "MFR_RSAMP_OFFSET", "r/w", 1),
    (0x2E, "MFR_VFB_DIGI_GAIN", "r/w", 2),
    (0x2F, "MFR_IMON_DIGI_GAIN", "r/w", 2),
    (0x30, "MFR_DC_LOOP_CTRL", "r/w", 2),
    (0x31, "MFR_CB_LOOP_CTRL", "r/w", 1),
    (0x32, "MFR_FS_LOOP_CTRL", "r/w", 2),
    (0x34, "MFR_T_ALERT_CTRL", "r/w", 2),
    (0x35, "VIN_ON", "r/w", 2),
    (0x36, "VIN_OFF", "r/w", 2),
    (0x38, "IOUT_CAL_GAIN", "r/w", 2),
    (0x39, "IOUT_CAL_OFFSET", "r/w", 2),
    (0x3A, "MFR_PROTECT_DIS", "r/w", 2),
    (0x3B, "MFR_PS_FORCE", "r/w", 2),
    (0x3D, "MFR_SLOPE_ADV", "r/w", 2),
    (0x3F, "MFR_PWM_LIMIT", "r/w", 2),
    (0x40, "MFR_OSR_SET", "r/w", 2),
    (0x43, "MFR_T_ALERT_CTRL2", "r/w", 2),
    (0x44, "MFR_SYS_CONFIG", "r/w", 2),
    (0x45, "MFR_VR_CONFIG3", "r/w", 2),
    (0x46, "CONFIG_ID", "r/w", 2),
    (0x47, "CONFIG_REV_MPS", "r/w", 2),
    (0x4A, "IOUT_OC_WARN_LIMIT", "r/w", 2),
    (0x4C, "MFR_CS_OFFSET1", "r/w", 2),
    (0x4D, "MFR_CS_OFFSET2", "r/w", 2),
    (0x4E, "MFR_CS_OFFSET3", "r/w", 2),
    (0x51, "OT_WARN_LIMIT", "r/w", 2),
    (0x55, "VIN_OV_FAULT_LIMIT", "r/w", 2),
    (0x58, "VIN_UV_WARN_LIMIT", "r/w", 2),
    (0x5D, "MFR_DELAY_SET", "r/w", 2),
    (0x5E, "POWER_GOOD_ON", "r/w", 2),
    (0x5F, "POWER_GOOD_OFF", "r/w", 2),
    (0x60, "TON_DELAY", "r/w", 2),
    (0x64, "TOFF_DELAY", "r/w", 2),
    (0x6A, "POUT_OP_WARN_LIMIT", "r/w", 2),
    (0x6B, "START_CATCH_AVE", "Send", 0),
    (0x73, "READ_CS1_2", "r", 2),
    (0x74, "READ_CS3_4", "r", 2),
    (0x75, "READ_CS5_6", "r", 2),
    (0x76, "READ_CS7_8", "r", 2),
    (0x77, "READ_CS9_10", "r", 2),
    (0x78, "STATUS_BYTE", "r", 1),
    (0x79, "STATUS_WORD", "r", 2),
    (0x7A, "STATUS_VOUT", "r", 1),
    (0x7B, "STATUS_IOUT", "r", 1),
    (0x7C, "STATUS_INPUT", "r", 1),
    (0x7D, "STATUS_TEMPERATURE", "r", 1),
    (0x7E, "STATUS_CML", "r", 1),
    (0x88, "READ_VIN", "r", 2),
    (0x8B, "READ_VOUT", "r", 2),
    (0x8C, "READ_IOUT", "r", 2),
    (0x8D, "READ_TEMPERATURE", "r", 2),
    (0x95, "READ_EFFICIENCY", "r", 2),
    (0x96, "READ_POUT", "r", 2),
    (0x97, "READ_PIN", "r", 2),
    (0xA3, "MFR_APS_FS_LIMIT1", "r/w", 2),
    (0xA4, "MFR_APS_FS_LIMIT2", "r/w", 2),
    (0xA5, "MFR_APS_FS_LIMIT3", "r/w", 2),
    (0xA6, "MFR_APS_FS_LIMIT4", "r/w", 2),
    (0xA7, "MFR_APS_FS_CTRL1", "r/w", 2),
    (0xA8, "MFR_APS_FS_CTRL2", "r/w", 2),
    (0xA9, "MFR_PHASE_SHED_CTRL", "r/w", 2),
    (0xAA, "MFR_LOW_PHASE_CNT", "r/w", 2),
    (0xAB, "MFR_APS_CTRL", "r/w", 2),
    (0xAD, "MFR_REPORT_CTRL", "r/w", 2),
    (0xAE, "MFR_PWMVID_TARGET_CTRL", "r/w", 2),
    (0xAF, "MFR_PWMVID_UP_COMP", "r/w", 2),
    (0xB0, "MFR_PWMVID_MAX_DUTY", "r/w", 2),
    (0xB1, "MFR_PWMVID_FLTR_CTRL1", "r/w", 2),
    (0xB2, "MFR_PWMVID_FLTR_CTRL2", "r/w", 2),
    (0xB3, "MFR_DUTY_TO_VID_GAIN", "r/w", 2),
    (0xB4, "MFR_PARM_VOUT_MIN", "r/w", 2),
    (0xB5, "MFR_PARM_RC_CONST", "r/w", 2),
    (0xB6, "MFR_PARM_VBOOT_DUTY", "r/w", 2),
    (0xB7, "MFR_PARM_SLEW_TRAN", "r/w", 2),
    (0xB8, "MFR_PARM_BOOT_TRAN", "r/w", 2),
    (0xB9, "MFR_BOOT_SR", "r/w", 2),
    (0xBA, "MFR_SLEW_SR", "r/w", 2),
    (0xBB, "MFR_VBOOT", "r/w", 2),
    (0xBC, "MFR_VID_SD", "r/w", 2),
    (0xBD, "MFR_FS", "r/w", 2),
    (0xBE, "MFR_PMBUS_ADDR", "r/w", 1),
    (0xBF, "MFR_VIN_SENSE_OFFSET", "r/w", 2),
    (0xC0, "MFR_VIN_SCALE_LOOP", "r/w", 1),
    (0xC1, "MFR_TEMP_GAIN_OFFSET", "r/w", 2),
    (0xC2, "MFR_CUR_GAIN", "r/w", 2),
    (0xC5, "MFR_BLANK_TIME", "r/w", 2),
    (0xC6, "MFR_SLOPE_SR_DCM", "r/w", 2),
    (0xC7, "MFR_SLOPE_CNT_DCM", "r/w", 2),
    (0xC8, "MFR_SLOPE_SR_10P", "r/w", 2),
    (0xC9, "MFR_SLOPE_CNT_10P", "r/w", 2),
    (0xCA, "MFR_SLOPE_SR_9P", "r/w", 2),
    (0xCB, "MFR_SLOPE_CNT_9P", "r/w", 2),
    (0xCC, "MFR_SLOPE_SR_8P", "r/w", 2),
    (0xCD, "MFR_SLOPE_CNT_8P", "r/w", 2),
    (0xCE, "MFR_SLOPE_SR_7P", "r/w", 2),
    (0xCF, "MFR_SLOPE_CNT_7P", "r/w", 2),
    (0xD0, "MFR_SLOPE_SR_6P", "r/w", 2),
    (0xD1, "MFR_SLOPE_CNT_6P", "r/w", 2),
    (0xD2, "MFR_SLOPE_SR_5P", "r/w", 2),
    (0xD3, "MFR_SLOPE_CNT_5P", "r/w", 2),
    (0xD4, "MFR_SLOPE_SR_4P", "r/w", 2),
    (0xD5, "MFR_SLOPE_CNT_4P", "r/w", 2),
    (0xD6, "MFR_SLOPE_SR_3P", "r/w", 2),
    (0xD7, "MFR_SLOPE_CNT_3P", "r/w", 2),
    (0xD8, "MFR_SLOPE_SR_2P", "r/w", 2),
    (0xD9, "MFR_SLOPE_CNT_2P", "r/w", 2),
    (0xDA, "MFR_SLOPE_SR_1P", "r/w", 2),
    (0xDB, "MFR_SLOPE_CNT_1P", "r/w", 2),
    (0xDD, "MFR_SLOPE_TRIM1", "r/w", 2),
    (0xDE, "MFR_SLOPE_TRIM2", "r/w", 2),
    (0xDF, "MFR_SLOPE_TRIM3", "r/w", 2),
    (0xE0, "MFR_SLOPE_TRIM4", "r/w", 2),
    (0xE1, "MFR_VR_CONFIG1", "r/w", 2),
    (0xE2, "MFR_VR_CONFIG2", "r/w", 1),
    (0xE3, "MFR_APS_LEVEL1", "r/w", 2),
    (0xE4, "MFR_APS_LEVEL2", "r/w", 2),
    (0xE5, "MFR_APS_LEVEL3", "r/w", 2),
    (0xE6, "MFR_APS_LEVEL4", "r/w", 2),
    (0xE7, "MFR_APS_LEVEL5", "r/w", 2),
    (0xE8, "MFR_APS_HYS", "r/w", 1),
    (0xE9, "MFR_TSNS_OT_SET", "r/w", 2),
    (0xEA, "MFR_VTEMP_OT_SET", "r/w", 2),
    (0xEC, "MFR_OCP_TOTAL", "r/w", 2),
    (0xED, "MFR_OCP_PHASE", "r/w", 1),
    (0xEE, "MFR_OVP_UVP_SET", "r/w", 2),
    (0xF8, "MFR_FAULTS1", "r", 2),
    (0xF9, "MFR_FAULTS2", "r", 2),
    (0xFA, "MFR_FAULTS3", "r", 2),
    (0xFB, "MFR_FAULTS4", "r", 2),
    (0xFF, "CLEAR_EEPROM_FAULTS", "Send", 0),
)

PAGE0_REGISTERS = tuple(Register(*row) for row in _ROWS)
REGISTERS_BY_CODE = {register.code: register for register in PAGE0_REGISTERS}
READABLE_PAGE0_REGISTERS = tuple(register for register in PAGE0_REGISTERS if register.can_read)


def description_for(register):
    name = register.name
    if name == "PAGE":
        return "PMBus sayfa seçicisi; toplu okuma yalnızca 00h üzerinde yapılır."
    if name == "OPERATION":
        return "Çıkış çalışma/kapalı ve margin kontrolü; bu araç ham kodu gösterir."
    if name == "MFR_EEPROM_CTRL":
        return "EEPROM erişimi, fault kaydı ve EEPROM CRC koruma denetimleri."
    if name in {"VOUT_MIN", "VOUT_COMMAND", "VOUT_MAX", "VOUT_MARGIN_HIGH", "VOUT_MARGIN_LOW", "POWER_GOOD_ON", "POWER_GOOD_OFF"}:
        return "VID biçimli gerilim ayarı; datasheet çözünürlüğü 6.25 mV/LSB."
    if name == "MFR_VBOOT":
        return "PWM-VID modunda açılış gerilimi; VID biçimi, 6.25 mV/LSB."
    if name == "MFR_FS":
        return "PWM switching frequency; alt 9 bit 10 kHz/LSB, üst bitler ayrılmıştır."
    if name in {"VIN_OV_FAULT_LIMIT", "VIN_UV_WARN_LIMIT"}:
        return "Giriş gerilimi OVP fault / UV warning eşiği; fixed exponent -3, 0.125 V/LSB."
    if name == "IOUT_OC_WARN_LIMIT":
        return "Çıkış toplam akım uyarı eşiği; 44h bit 3 çözünürlüğüne göre 1 A veya 2 A/LSB."
    if name == "MFR_OCP_TOTAL":
        return "Toplam çıkış aşırı akım koruması; limit 1 A veya 2 A/LSB, ayrıca mod ve deglitch alanları içerir."
    if name == "OT_WARN_LIMIT":
        return "VTEMP sıcaklık uyarı eşiği; alt 8 bit 1 °C/LSB. OTP kapatma eşiği değildir."
    if name == "MFR_VTEMP_OT_SET":
        return "VTEMP sensör OTP cutoff kontrol register'ı; eşik/mod/histerezis alanları decimal register kodu olarak gösterilir."
    if name == "MFR_TSNS_OT_SET":
        return "TSNS pin OTP kontrol register'ı; eşik/mod/histerezis alanları decimal register kodu olarak gösterilir."
    if name == "VOUT_OFFSET":
        return "İşaretli 8-bit VID ofseti; 6.25 mV/LSB, bit 7 işaret bitidir."
    if name.startswith("STATUS_") or name.startswith("MFR_FAULTS"):
        return "Durum/fault bayrakları; ham bit alanı aşağıda gösterilir."
    if name.startswith("READ_"):
        return "Anlık ölçüm/telemetri; ham değer datasheet kayıt formatına göre yorumlanmalıdır."
    if name.startswith("MFR_"):
        return "MPS üretici alanı; decimal register kodu. Fiziksel ölçek/bit anlamı doğrulanmadıysa tahmin edilmez."
    if name.startswith("VIN_") or name.startswith("IOUT_") or name.startswith("OT_") or name.startswith("POWER_GOOD_"):
        return "PMBus limit/uyarı ayarı; mevcut register değeri gösterilir."
    if register.access == "Send":
        return "İşlem komutu; veri byte'ı yoktur ve toplu okumaya dahil edilmez."
    return "Datasheet Page 0 komut tablosundaki register."


VID_VOLTAGE_CODES = {0x1F, 0x21, 0x24, 0x25, 0x26, 0x5E, 0x5F}
STATUS_FLAG_NAMES = {
    0x78: {
        1: "PMBus / bellek / lojik hatası (CML)",
        2: "Sıcaklık arızası veya uyarısı",
        3: "Giriş düşük gerilim arızası",
        4: "Çıkış aşırı akım arızası",
        5: "Çıkış aşırı gerilim arızası",
        6: "Çıkış kapalı (OFF)",
    },
    0x79: {
        1: "PMBus / bellek / lojik hatası (CML)",
        2: "Sıcaklık arızası veya uyarısı",
        3: "Giriş düşük gerilim arızası",
        4: "Çıkış aşırı akım arızası",
        5: "Çıkış aşırı gerilim arızası",
        6: "Çıkış kapalı (OFF)",
        8: "İzleme hesaplama watchdog taşması",
        11: "POWER_GOOD: çıkış eşiği geçti ve gecikme tamamlandı",
        12: "Ortalama ölçüm verisi hazır",
        13: "Giriş gerilimi/akımı/gücü status bayrağı set",
        14: "Çıkış akımı/gücü status bayrağı set",
        15: "Çıkış gerilimi status bayrağı set",
    },
    0x7A: {
        7: "Çıkış aşırı gerilim (OVP)",
        5: "Çıkış düşük gerilim uyarısı",
        4: "Çıkış düşük gerilim arızası (UVP)",
        3: "VOUT_COMMAND / margin değeri VOUT_MIN-MAX dışına çıktı",
        1: "EEPROM restore sırasında VOSEN remote-sense hattı boşta",
        0: "Soft-start sırasında VOSEN ile VDIFF farkı 0.5 V'u aştı",
    },
    0x7B: {
        7: "Çıkış aşırı akım arızası (OCP)",
        6: "OCP ve OVP birlikte oluştu (OC_UV fault)",
        5: "Çıkış aşırı akım uyarısı",
        0: "Çıkış aşırı güç uyarısı (POUT OPP)",
    },
    0x7C: {
        7: "Giriş aşırı gerilim arızası (VIN OVP)",
        5: "Giriş düşük gerilim uyarısı",
        4: "VIN_OFF eşiği görüldü; VR kapandı (UVLO latch)",
    },
    0x7D: {
        7: "VTEMP aşırı sıcaklık arızası (OTP)",
        6: "VTEMP sıcaklık uyarısı",
    },
    0x7E: {
        7: "Desteklenmeyen PMBus komutu alındı",
        6: "Geçersiz veya desteklenmeyen veri / fazla byte",
        5: "PMBus PEC/CRC hatası",
        4: "EEPROM restore CRC uyuşmazlığı; VR başlamayabilir",
        3: "PMBus yazma koruması parola eşleşme durumu",
        2: "Koruma kapanışı EEPROM fault kaydını başlattı",
        1: "PMBus iletişiminde eksik/fazla bit veya byte",
        0: "EEPROM signature eşleşmedi; restore durdu",
    },
}


FAULT_STATUS_CODES = (0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E)
MFR_FAULT_SNAPSHOT_CODES = (0xF8, 0xF9, 0xFA, 0xFB)


def status_flags_for(code, value):
    return [
        name
        for bit, name in STATUS_FLAG_NAMES.get(code, {}).items()
        if value & (1 << bit)
    ]


def interpretation_for(register, value):
    if register.code == 0x00:
        return {0: "PAGE 0: normal operating registers", 2: "PAGE 2: test registers", 0x28: "PAGE 28: EEPROM registers", 0x29: "PAGE 29: EEPROM registers"}.get(value, "Datasheet'te ayrılmış başka bir PAGE")
    if register.code == 0x01:
        if value & 0xC0 == 0x00:
            return "Hi-Z off: PWM çıkışları kapalı"
        if value & 0xC0 == 0x40:
            return "Soft off: yumuşak kapatma"
        if value & 0xF0 == 0x80:
            return "Normal on: çıkış çalışması isteniyor"
        if value & 0xF0 == 0x90:
            return "Margin low modu"
        if value & 0xF0 == 0xA0:
            return "Margin high modu"
        return "OPERATION kodu tanınmıyor"
    if register.code in VID_VOLTAGE_CODES:
        if value & 0xFE00:
            return f"VID format hatası: 15:9 ayrılmış bitler sıfır olmalı (ham 0x{value:04X})"
        millivolts = (value & 0x01FF) * 6.25
        return f"VID: {millivolts:.2f} mV (6.25 mV/LSB; alt 9 bit)"
    if register.code in (0x35, 0x36):
        if value & 0xFF00 != 0xE800:
            return f"VIN format hatası: üst byte 0xE8 olmalı (ham 0x{value:04X})"
        threshold = (value & 0xFF) * 0.125
        label = "VIN açılma/soft-start eşiği" if register.code == 0x35 else "VIN kapanma eşiği"
        return f"{label}: {threshold:.3f} V (fixed exponent -3; 0.125 V/LSB)"
    if register.code == 0x88:
        if value & 0xFC00 != 0xEC00:
            return f"READ_VIN format hatası: üst 6 bit 111011 olmalı (ham 0x{value:04X})"
        return f"Ölçülen giriş gerilimi: {(value & 0x03FF) * 0.03125:.3f} V (0.03125 V/LSB)"
    if register.code == 0x23:
        offset = value & 0xFF
        if offset & 0x80:
            offset -= 0x100
        return f"VID ofseti: {offset * 6.25:.2f} mV (6.25 mV/LSB; signed 8-bit)"
    if register.code in (0x55, 0x58):
        if value & 0xFF00 != 0xE800:
            return f"VIN limit format hatası: üst byte 0xE8 olmalı (ham 0x{value:04X})"
        name = "Giriş aşırı gerilim fault" if register.code == 0x55 else "Giriş düşük gerilim uyarı"
        return f"{name}: {(value & 0xFF) * 0.125:.3f} V (0.125 V/LSB)"
    if register.code == 0x51:
        if value & 0xFF00:
            return f"OT_WARN_LIMIT ayrılmış bitleri sıfır değil (ham 0x{value:04X})"
        return f"VTEMP sıcaklık uyarı eşiği: {value & 0xFF} °C (1 °C/LSB; OTP cutoff değil)"
    if register.code == 0xBD:
        if value & 0xFE00:
            return f"MFR_FS ayrılmış bitleri sıfır değil (ham 0x{value:04X})"
        return f"PWM switching frequency: {(value & 0x01FF) * 10} kHz (10 kHz/LSB)"
    if register.code == 0xBB:
        if value & 0xFE00:
            return f"MFR_VBOOT VID ayrılmış bitleri sıfır değil (ham 0x{value:04X})"
        return f"PWM-VID boot voltage: {(value & 0x01FF) * 6.25:.2f} mV (6.25 mV/LSB)"
    if register.code == 0x78:
        names = status_flags_for(register.code, value)
        return "Status bayrakları: " + (", ".join(names) if names else "hiçbir bayrak set değil")
    if register.code == 0x79:
        names = status_flags_for(register.code, value)
        return "Status bayrakları: " + (", ".join(names) if names else "hiçbir bayrak set değil")
    if register.code in STATUS_FLAG_NAMES:
        names = status_flags_for(register.code, value)
        return "Status bayrakları: " + (", ".join(names) if names else "hiçbir bayrak set değil")
    if register.code == 0xE1:
        phases = value & 0x07
        phase_names = ("1-phase DCM", "1-phase CCM", "2-phase", "3-phase", "4-phase", "5-phase", "6-phase", "code 7")
        control = "PMBus" if value & 0x10 else "PWM-VID"
        aps = "açık" if value & 0x20 else "kapalı"
        osr = "açık" if value & 0x40 else "kapalı"
        current_balance = "açık" if value & 0x80 else "kapalı"
        return f"Faz: {phase_names[phases]}; gerilim kontrolü: {control}; APS: {aps}; OSR: {osr}; current balance: {current_balance}"
    if register.code == 0xE2:
        vboot_source = "TSNS/BOOT pini" if value & (1 << 2) else "VOUT_COMMAND"
        slew_mode = "R-C filter" if value & 0x01 else "linear"
        return f"VBOOT kaynağı: {vboot_source}; boot/DVID slew: {slew_mode}"
    return description_for(register)


def telemetry_display_for(code, value, total_current_half_resolution=None):
    raw_note = f"{REGISTERS_BY_CODE[code].name} · raw 0x{value:04X}"
    if code == 0x88:
        if value & 0xFC00 != 0xEC00:
            raise ValueError("READ_VIN üst 6 bit biçimi 111011 değil")
        return f"{(value & 0x03FF) * 0.03125:.3f} V", f"{raw_note} · 31.25 mV/LSB"
    if code == 0x8B:
        if value & 0xF000:
            raise ValueError("READ_VOUT ayrılmış bitleri sıfır değil")
        return f"{(value & 0x0FFF) / 1000:.3f} V", f"{raw_note} · 1 mV/LSB"
    if code in (0x8C, 0x96, 0x97) and total_current_half_resolution is None:
        raise ValueError("MFR_VR_CONFIG3 (45h) bit 3 okunamadı")
    if code == 0x8C:
        if value & 0xF000 != 0xE000:
            raise ValueError("READ_IOUT üst 4 bit biçimi 1110 değil")
        lsb = 0.5 if total_current_half_resolution else 0.25
        return f"{(value & 0x0FFF) * lsb:.2f} A", f"{raw_note} · {lsb:g} A/LSB"
    if code == 0x8D:
        if value & 0xF800:
            raise ValueError("READ_TEMPERATURE ayrılmış bitleri sıfır değil")
        return f"{(value & 0x07FF) * 0.1:.1f} °C", f"{raw_note} · 0.1 °C/LSB"
    if code == 0x95:
        if value & 0xFE00:
            raise ValueError("READ_EFFICIENCY ayrılmış bitleri sıfır değil")
        return f"{(value & 0x01FF) * 0.195:.2f} %", f"{raw_note} · 0.195 %/LSB"
    if code in (0x96, 0x97):
        if value & 0xF800:
            raise ValueError(f"{REGISTERS_BY_CODE[code].name} ayrılmış bitleri sıfır değil")
        lsb = 1.0 if total_current_half_resolution else 0.5
        return f"{(value & 0x07FF) * lsb:.1f} W", f"{raw_note} · {lsb:g} W/LSB"
    raise ValueError(f"Desteklenmeyen telemetri komutu: {code:02X}h")