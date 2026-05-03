#include "VMA208.h"

VMA208::VMA208(TwoWire &wire)
  : VMA208(DEFAULT_ADDRESS, wire) {
}

VMA208::VMA208(TwoWire &wire, uint8_t address)
  : VMA208(address, wire) {
}

VMA208::VMA208(uint8_t address, TwoWire &wire)
  : _wire(&wire),
    _address(address),
    _range(RANGE_2G),
    _dataRate(ODR_100HZ),
    _lastError(ERROR_NONE) {
}

bool VMA208::begin(Range range, DataRate dataRate, bool startWire) {
  if (!validRange(range) || !validDataRate(dataRate)) {
    _lastError = ERROR_INVALID_ARGUMENT;
    return false;
  }

  if (startWire) {
    _wire->begin();
  }

  if (!detectAt(_address)) {
    const uint8_t originalAddress = _address;

    if (originalAddress == DEFAULT_ADDRESS && detectAt(ALTERNATE_ADDRESS)) {
      _address = ALTERNATE_ADDRESS;
    } else {
      _address = originalAddress;
      _lastError = ERROR_BAD_ID;
      return false;
    }
  }

  if (!standby()) {
    return false;
  }

  if (!writeRegister(REG_XYZ_DATA_CFG, static_cast<uint8_t>(range))) {
    return false;
  }

  if (!writeRegister(REG_CTRL_REG1, static_cast<uint8_t>(static_cast<uint8_t>(dataRate) << 3))) {
    return false;
  }

  _range = range;
  _dataRate = dataRate;

  return active();
}

bool VMA208::isConnected() {
  uint8_t id = 0;

  if (!readRegisterChecked(REG_WHO_AM_I, id)) {
    return false;
  }

  if (id != EXPECTED_WHO_AM_I) {
    _lastError = ERROR_BAD_ID;
    return false;
  }

  return true;
}

uint8_t VMA208::address() const {
  return _address;
}

void VMA208::setAddress(uint8_t address) {
  _address = address;
}

uint8_t VMA208::whoAmI() {
  return readRegister(REG_WHO_AM_I);
}

uint8_t VMA208::status() {
  return readRegister(REG_STATUS);
}

bool VMA208::available() {
  uint8_t value = 0;

  if (!readRegisterChecked(REG_STATUS, value)) {
    return false;
  }

  return (value & STATUS_ZYXDR) != 0;
}

bool VMA208::isActive() {
  bool activeState = false;
  readActiveState(activeState);
  return activeState;
}

bool VMA208::standby() {
  return setActive(false);
}

bool VMA208::active() {
  return setActive(true);
}

bool VMA208::setActive(bool enabled) {
  uint8_t ctrl = 0;

  if (!readRegisterChecked(REG_CTRL_REG1, ctrl)) {
    return false;
  }

  if (enabled) {
    ctrl |= CTRL_REG1_ACTIVE;
  } else {
    ctrl &= static_cast<uint8_t>(~CTRL_REG1_ACTIVE);
  }

  return writeRegister(REG_CTRL_REG1, ctrl);
}

bool VMA208::reset(uint16_t timeoutMs) {
  if (!writeRegister(REG_CTRL_REG2, CTRL_REG2_RESET)) {
    return false;
  }

  const unsigned long start = millis();

  while (millis() - start < timeoutMs) {
    uint8_t ctrl2 = 0;

    if (readRegisterChecked(REG_CTRL_REG2, ctrl2) && ((ctrl2 & CTRL_REG2_RESET) == 0)) {
      return true;
    }

    delay(1);
  }

  _lastError = ERROR_SHORT_READ;
  return false;
}

bool VMA208::setRange(Range range) {
  if (!validRange(range)) {
    _lastError = ERROR_INVALID_ARGUMENT;
    return false;
  }

  bool wasActive = false;

  if (!enterStandby(wasActive)) {
    return false;
  }

  uint8_t cfg = 0;
  bool ok = readRegisterChecked(REG_XYZ_DATA_CFG, cfg);

  if (ok) {
    cfg &= static_cast<uint8_t>(~XYZ_DATA_CFG_RANGE_MASK);
    cfg |= static_cast<uint8_t>(range);
    ok = writeRegister(REG_XYZ_DATA_CFG, cfg);
  }

  if (ok) {
    _range = range;
  }

  return restoreActive(wasActive) && ok;
}

VMA208::Range VMA208::range() const {
  return _range;
}

float VMA208::countsPerG() const {
  switch (_range) {
    case RANGE_4G:
      return 512.0f;
    case RANGE_8G:
      return 256.0f;
    case RANGE_2G:
    default:
      return 1024.0f;
  }
}

float VMA208::rawToG(int16_t raw) const {
  return static_cast<float>(raw) / countsPerG();
}

bool VMA208::setDataRate(DataRate dataRate) {
  if (!validDataRate(dataRate)) {
    _lastError = ERROR_INVALID_ARGUMENT;
    return false;
  }

  bool wasActive = false;

  if (!enterStandby(wasActive)) {
    return false;
  }

  uint8_t ctrl = 0;
  bool ok = readRegisterChecked(REG_CTRL_REG1, ctrl);

  if (ok) {
    ctrl &= static_cast<uint8_t>(~CTRL_REG1_DATA_RATE_MASK);
    ctrl |= static_cast<uint8_t>(static_cast<uint8_t>(dataRate) << 3);
    ok = writeRegister(REG_CTRL_REG1, ctrl);
  }

  if (ok) {
    _dataRate = dataRate;
  }

  return restoreActive(wasActive) && ok;
}

VMA208::DataRate VMA208::dataRate() const {
  return _dataRate;
}

bool VMA208::setHighPassOutput(bool enabled) {
  bool wasActive = false;

  if (!enterStandby(wasActive)) {
    return false;
  }

  uint8_t cfg = 0;
  bool ok = readRegisterChecked(REG_XYZ_DATA_CFG, cfg);

  if (ok) {
    if (enabled) {
      cfg |= XYZ_DATA_CFG_HPF_OUT;
    } else {
      cfg &= static_cast<uint8_t>(~XYZ_DATA_CFG_HPF_OUT);
    }

    ok = writeRegister(REG_XYZ_DATA_CFG, cfg);
  }

  return restoreActive(wasActive) && ok;
}

bool VMA208::readRaw(int16_t &x, int16_t &y, int16_t &z) {
  uint8_t buffer[6] = {0, 0, 0, 0, 0, 0};

  if (!readRegisters(REG_OUT_X_MSB, buffer, sizeof(buffer))) {
    return false;
  }

  x = combine12Bit(buffer[0], buffer[1]);
  y = combine12Bit(buffer[2], buffer[3]);
  z = combine12Bit(buffer[4], buffer[5]);

  return true;
}

VMA208::RawReading VMA208::readRaw() {
  RawReading reading = {0, 0, 0};
  readRaw(reading.x, reading.y, reading.z);
  return reading;
}

bool VMA208::readG(float &x, float &y, float &z) {
  int16_t rawX = 0;
  int16_t rawY = 0;
  int16_t rawZ = 0;

  if (!readRaw(rawX, rawY, rawZ)) {
    return false;
  }

  x = rawToG(rawX);
  y = rawToG(rawY);
  z = rawToG(rawZ);

  return true;
}

VMA208::Reading VMA208::readG() {
  Reading reading = {0.0f, 0.0f, 0.0f};
  readG(reading.x, reading.y, reading.z);
  return reading;
}

bool VMA208::readMilliG(int16_t &x, int16_t &y, int16_t &z) {
  int16_t rawX = 0;
  int16_t rawY = 0;
  int16_t rawZ = 0;

  if (!readRaw(rawX, rawY, rawZ)) {
    return false;
  }

  const int16_t counts = static_cast<int16_t>(countsPerG());
  x = static_cast<int16_t>(static_cast<long>(rawX) * 1000L / counts);
  y = static_cast<int16_t>(static_cast<long>(rawY) * 1000L / counts);
  z = static_cast<int16_t>(static_cast<long>(rawZ) * 1000L / counts);

  return true;
}

uint8_t VMA208::lastError() const {
  return _lastError;
}

uint8_t VMA208::readRegister(uint8_t reg) {
  uint8_t value = 0;
  readRegisterChecked(reg, value);
  return value;
}

bool VMA208::writeRegister(uint8_t reg, uint8_t value) {
  _wire->beginTransmission(_address);
  _wire->write(reg);
  _wire->write(value);
  _lastError = _wire->endTransmission();

  return _lastError == ERROR_NONE;
}

bool VMA208::readRegisters(uint8_t reg, uint8_t *buffer, size_t length) {
  if (buffer == 0 || length == 0 || length > 255) {
    _lastError = ERROR_INVALID_ARGUMENT;
    return false;
  }

  _wire->beginTransmission(_address);
  _wire->write(reg);
  _lastError = _wire->endTransmission(false);

  if (_lastError != ERROR_NONE) {
    return false;
  }

  const size_t received = _wire->requestFrom(_address, static_cast<uint8_t>(length));

  if (received != length) {
    while (_wire->available()) {
      _wire->read();
    }

    _lastError = ERROR_SHORT_READ;
    return false;
  }

  for (size_t i = 0; i < length; ++i) {
    buffer[i] = static_cast<uint8_t>(_wire->read());
  }

  _lastError = ERROR_NONE;
  return true;
}

bool VMA208::detectAt(uint8_t address) {
  const uint8_t previousAddress = _address;
  _address = address;

  const bool connected = isConnected();

  if (!connected) {
    _address = previousAddress;
  }

  return connected;
}

bool VMA208::readRegisterChecked(uint8_t reg, uint8_t &value) {
  return readRegisters(reg, &value, 1);
}

bool VMA208::readActiveState(bool &activeState) {
  uint8_t ctrl = 0;

  if (!readRegisterChecked(REG_CTRL_REG1, ctrl)) {
    return false;
  }

  activeState = (ctrl & CTRL_REG1_ACTIVE) != 0;
  return true;
}

bool VMA208::enterStandby(bool &wasActive) {
  if (!readActiveState(wasActive)) {
    return false;
  }

  if (wasActive) {
    return standby();
  }

  return true;
}

bool VMA208::restoreActive(bool wasActive) {
  if (wasActive) {
    return active();
  }

  return true;
}

bool VMA208::validRange(Range range) const {
  return range == RANGE_2G || range == RANGE_4G || range == RANGE_8G;
}

bool VMA208::validDataRate(DataRate dataRate) const {
  return dataRate <= ODR_1_56HZ;
}

int16_t VMA208::combine12Bit(uint8_t msb, uint8_t lsb) const {
  uint16_t value = static_cast<uint16_t>((static_cast<uint16_t>(msb) << 8) | lsb);
  value >>= 4;

  if (value & 0x0800) {
    return static_cast<int16_t>(value - 0x1000);
  }

  return static_cast<int16_t>(value);
}
