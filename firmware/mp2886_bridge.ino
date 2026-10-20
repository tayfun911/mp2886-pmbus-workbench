#include <Wire.h>

#ifndef MP2886_SDA_PIN
#define MP2886_SDA_PIN 4
#endif

#ifndef MP2886_SCL_PIN
#define MP2886_SCL_PIN 5
#endif

static constexpr uint32_t DEFAULT_I2C_HZ = 100000;
static constexpr uint8_t STORE_USER_ALL = 0x15;
static constexpr uint8_t RESTORE_USER_ALL = 0x16;
static bool pecEnabled = false;
static const char *lastBusError = "I2C_ERROR";
static uint8_t lastExpectedPec = 0;
static uint8_t lastReceivedPec = 0;

static char inputLine[96];
static size_t inputLength = 0;

bool validAddress(unsigned int address) {
  return address >= 0x03 && address <= 0x77;
}

void printError(const char *message) {
  Serial.print("ERR ");
  Serial.println(message);
}

uint8_t updatePec(uint8_t crc, uint8_t value) {
  crc ^= value;
  for (uint8_t bit = 0; bit < 8; ++bit) {
    crc = (crc & 0x80) ? static_cast<uint8_t>((crc << 1) ^ 0x07) : static_cast<uint8_t>(crc << 1);
  }
  return crc;
}

uint8_t commandPec(uint8_t address, uint8_t command) {
  uint8_t crc = updatePec(0, static_cast<uint8_t>(address << 1));
  return updatePec(crc, command);
}

bool sendCommand(uint8_t address, uint8_t command) {
  Wire.beginTransmission(address);
  Wire.write(command);
  if (pecEnabled) {
    Wire.write(commandPec(address, command));
  }
  const bool success = Wire.endTransmission() == 0;
  lastBusError = success ? "I2C_ERROR" : "I2C_COMMAND_FAILED";
  return success;
}

bool readValue(uint8_t address, uint8_t command, uint8_t count, uint16_t &value) {
  Wire.beginTransmission(address);
  Wire.write(command);
  if (Wire.endTransmission(false) != 0) {
    lastBusError = "I2C_READ_FAILED";
    return false;
  }

  uint8_t crc = updatePec(0, static_cast<uint8_t>(address << 1));
  crc = updatePec(crc, command);
  crc = updatePec(crc, static_cast<uint8_t>((address << 1) | 1));
  const uint8_t expectedCount = count + (pecEnabled ? 1 : 0);
  if (Wire.requestFrom(address, expectedCount, static_cast<uint8_t>(true)) != expectedCount) {
    while (Wire.available()) {
      Wire.read();
    }
    lastBusError = pecEnabled ? "PEC_BYTE_MISSING" : "I2C_READ_FAILED";
    return false;
  }

  const uint8_t lowByte = Wire.read();
  crc = updatePec(crc, lowByte);
  value = lowByte;
  if (count == 2) {
    const uint8_t highByte = Wire.read();
    crc = updatePec(crc, highByte);
    value |= static_cast<uint16_t>(highByte) << 8;
  }
  if (pecEnabled) {
    lastExpectedPec = crc;
    lastReceivedPec = Wire.read();
    if (lastReceivedPec != lastExpectedPec) {
      lastBusError = "PEC_MISMATCH";
      return false;
    }
  }
  lastBusError = "I2C_ERROR";
  return true;
}

bool writeValue(uint8_t address, uint8_t command, uint8_t count, uint16_t value) {
  Wire.beginTransmission(address);
  Wire.write(command);
  const uint8_t lowByte = static_cast<uint8_t>(value & 0xFF);
  Wire.write(lowByte);
  uint8_t crc = updatePec(0, static_cast<uint8_t>(address << 1));
  crc = updatePec(crc, command);
  crc = updatePec(crc, lowByte);
  if (count == 2) {
    const uint8_t highByte = static_cast<uint8_t>((value >> 8) & 0xFF);
    Wire.write(highByte);
    crc = updatePec(crc, highByte);
  }
  if (pecEnabled) {
    Wire.write(crc);
  }
  const bool success = Wire.endTransmission() == 0;
  lastBusError = success ? "I2C_ERROR" : "I2C_WRITE_FAILED";
  return success;
}

void scanBus() {
  Serial.print("OK ");
  bool found = false;
  for (uint8_t address = 0x03; address <= 0x77; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      if (found) {
        Serial.print(',');
      }
      Serial.printf("%02X", address);
      found = true;
    }
  }
  if (!found) {
    Serial.print("NONE");
  }
  Serial.println();
}

void handleLine(char *line) {
  char operation[12] = {0};
  unsigned int address = 0;
  unsigned int command = 0;
  unsigned int value = 0;
  unsigned long frequency = 0;

  if (strcmp(line, "PING") == 0) {
    Serial.println("OK MP2886_BRIDGE 2");
    return;
  }
  if (strcmp(line, "PEC ON") == 0 || strcmp(line, "PEC OFF") == 0) {
    pecEnabled = strcmp(line, "PEC ON") == 0;
    Serial.println(pecEnabled ? "OK PEC_ON" : "OK PEC_OFF");
    return;
  }
  if (strcmp(line, "SCAN") == 0) {
    scanBus();
    return;
  }
  if (sscanf(line, "FREQ %lu", &frequency) == 1) {
    if (frequency < 10000 || frequency > 1000000) {
      printError("FREQ_RANGE_10000_1000000");
      return;
    }
    Wire.setClock(frequency);
    Serial.println("OK");
    return;
  }

  const int fields = sscanf(line, "%11s %x %x %x", operation, &address, &command, &value);
  if (fields < 2 || !validAddress(address)) {
    printError("BAD_COMMAND_OR_ADDRESS");
    return;
  }

  const bool byteRead = strcmp(operation, "RB") == 0;
  const bool wordRead = strcmp(operation, "RW") == 0;
  if (byteRead || wordRead) {
    if (fields < 3 || command > 0xFF) {
      printError("COMMAND_RANGE");
      return;
    }
    const uint8_t count = byteRead ? 1 : 2;
    uint16_t result = 0;
    if (!readValue(address, command, count, result)) {
      if (strcmp(lastBusError, "PEC_MISMATCH") == 0) {
        Serial.printf("ERR PEC_MISMATCH DATA=%04X EXPECTED=%02X RECEIVED=%02X\n", result, lastExpectedPec, lastReceivedPec);
        return;
      }
      printError(lastBusError);
      return;
    }
    Serial.printf("OK %0*X", count * 2, result);
    if (pecEnabled) {
      Serial.print(" PEC_OK");
    }
    Serial.println();
    return;
  }

  if (strcmp(operation, "WB") == 0 || strcmp(operation, "WW") == 0) {
    if (fields < 4 || command > 0xFF || value > 0xFFFF ||
        (strcmp(operation, "WB") == 0 && value > 0xFF)) {
      printError("VALUE_RANGE");
      return;
    }
    const uint8_t count = strcmp(operation, "WB") == 0 ? 1 : 2;
    if (!writeValue(address, command, count, value)) {
      printError(lastBusError);
      return;
    }
    Serial.println(pecEnabled ? "OK PEC_TX_ACK" : "OK");
    return;
  }

  if (strcmp(operation, "CMD") == 0) {
    if (fields < 3 || command > 0xFF) {
      printError("COMMAND_RANGE");
      return;
    }
    if (!sendCommand(address, command)) {
      printError(lastBusError);
      return;
    }
    if (command == STORE_USER_ALL) {
      delay(250);
    }
    Serial.println(pecEnabled ? "OK PEC_TX_ACK" : "OK");
    return;
  }

  printError("UNKNOWN_OPERATION");
}

void setup() {
  Serial.begin(115200);
  Wire.begin(MP2886_SDA_PIN, MP2886_SCL_PIN);
  Wire.setClock(DEFAULT_I2C_HZ);
}

void loop() {
  while (Serial.available()) {
    const char character = static_cast<char>(Serial.read());
    if (character == '\n') {
      inputLine[inputLength] = '\0';
      if (inputLength > 0 && inputLine[inputLength - 1] == '\r') {
        inputLine[inputLength - 1] = '\0';
      }
      handleLine(inputLine);
      inputLength = 0;
    } else if (inputLength < sizeof(inputLine) - 1) {
      inputLine[inputLength++] = character;
    } else {
      inputLength = 0;
      printError("LINE_TOO_LONG");
    }
  }
}