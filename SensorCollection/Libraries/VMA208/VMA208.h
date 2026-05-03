#ifndef VMA208_H
#define VMA208_H

#include <Arduino.h>
#include <Wire.h>

class VMA208 {
public:
  static const uint8_t DEFAULT_ADDRESS = 0x1D;
  static const uint8_t ALTERNATE_ADDRESS = 0x1C;
  static const uint8_t EXPECTED_WHO_AM_I = 0x2A;

  static const uint8_t ERROR_NONE = 0;
  static const uint8_t ERROR_SHORT_READ = 100;
  static const uint8_t ERROR_BAD_ID = 101;
  static const uint8_t ERROR_INVALID_ARGUMENT = 102;

  enum Range : uint8_t {
    RANGE_2G = 0,
    RANGE_4G = 1,
    RANGE_8G = 2
  };

  enum DataRate : uint8_t {
    ODR_800HZ = 0,
    ODR_400HZ = 1,
    ODR_200HZ = 2,
    ODR_100HZ = 3,
    ODR_50HZ = 4,
    ODR_12_5HZ = 5,
    ODR_6_25HZ = 6,
    ODR_1_56HZ = 7
  };

  struct RawReading {
    int16_t x;
    int16_t y;
    int16_t z;
  };

  struct Reading {
    float x;
    float y;
    float z;
  };

  explicit VMA208(TwoWire &wire);
  VMA208(TwoWire &wire, uint8_t address);
  explicit VMA208(uint8_t address = DEFAULT_ADDRESS, TwoWire &wire = Wire);

  bool begin(Range range = RANGE_2G, DataRate dataRate = ODR_100HZ, bool startWire = true);
  bool isConnected();

  uint8_t address() const;
  void setAddress(uint8_t address);

  uint8_t whoAmI();
  uint8_t status();
  bool available();
  bool isActive();

  bool standby();
  bool active();
  bool setActive(bool enabled);
  bool reset(uint16_t timeoutMs = 100);

  bool setRange(Range range);
  Range range() const;
  float countsPerG() const;
  float rawToG(int16_t raw) const;

  bool setDataRate(DataRate dataRate);
  DataRate dataRate() const;

  bool setHighPassOutput(bool enabled);

  bool readRaw(int16_t &x, int16_t &y, int16_t &z);
  RawReading readRaw();

  bool readG(float &x, float &y, float &z);
  Reading readG();

  bool readMilliG(int16_t &x, int16_t &y, int16_t &z);

  uint8_t lastError() const;

  uint8_t readRegister(uint8_t reg);
  bool writeRegister(uint8_t reg, uint8_t value);
  bool readRegisters(uint8_t reg, uint8_t *buffer, size_t length);

private:
  static const uint8_t REG_STATUS = 0x00;
  static const uint8_t REG_OUT_X_MSB = 0x01;
  static const uint8_t REG_WHO_AM_I = 0x0D;
  static const uint8_t REG_XYZ_DATA_CFG = 0x0E;
  static const uint8_t REG_CTRL_REG1 = 0x2A;
  static const uint8_t REG_CTRL_REG2 = 0x2B;

  static const uint8_t STATUS_ZYXDR = 0x08;
  static const uint8_t CTRL_REG1_ACTIVE = 0x01;
  static const uint8_t CTRL_REG1_DATA_RATE_MASK = 0x38;
  static const uint8_t CTRL_REG2_RESET = 0x40;
  static const uint8_t XYZ_DATA_CFG_HPF_OUT = 0x10;
  static const uint8_t XYZ_DATA_CFG_RANGE_MASK = 0x03;

  TwoWire *_wire;
  uint8_t _address;
  Range _range;
  DataRate _dataRate;
  uint8_t _lastError;

  bool detectAt(uint8_t address);
  bool readRegisterChecked(uint8_t reg, uint8_t &value);
  bool readActiveState(bool &activeState);
  bool enterStandby(bool &wasActive);
  bool restoreActive(bool wasActive);
  bool validRange(Range range) const;
  bool validDataRate(DataRate dataRate) const;
  int16_t combine12Bit(uint8_t msb, uint8_t lsb) const;
};

#endif
