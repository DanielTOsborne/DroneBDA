#include <TFminiS.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <math.h>


// I2C address used by the Raspberry Pi reader.
const uint8_t I2C_ADDRESS = 15;

// Calibration and Kalman tuning. Increase measurement noise for smoother output;
// increase process noise for faster response to real motion.
const int CALIBRATION_SAMPLES = 2000;
const float DEFAULT_SAMPLE_DT_SECONDS = 0.02f;
const float ACCEL_PROCESS_NOISE = 0.08f;
const float ACCEL_MEASUREMENT_NOISE = 0.37f;
const float GYRO_PROCESS_NOISE = 0.06f;
const float GYRO_MEASUREMENT_NOISE = 0.08f;
const float DISTANCE_PROCESS_NOISE = 2.0f;
const float DISTANCE_MEASUREMENT_NOISE = 20.0f;
const float STRENGTH_PROCESS_NOISE = 25.0f;
const float STRENGTH_MEASUREMENT_NOISE = 300.0f;
const float TEMPERATURE_PROCESS_NOISE = 0.02f;
const float TEMPERATURE_MEASUREMENT_NOISE = 1.0f;


class ScalarKalmanFilter {
public:
  ScalarKalmanFilter(float processNoise, float measurementNoise)
    : q(processNoise),
      r(measurementNoise),
      estimate(0.0f),
      errorCovariance(1.0f),
      initialized(false) {
  }

  float update(float measurement, float dtSeconds) {
    if (!initialized) {
      reset(measurement);
      return estimate;
    }

    errorCovariance += q * dtSeconds;

    const float kalmanGain = errorCovariance / (errorCovariance + r);
    estimate += kalmanGain * (measurement - estimate);
    errorCovariance *= (1.0f - kalmanGain);

    return estimate;
  }

  void reset(float value) {
    estimate = value;
    errorCovariance = 1.0f;
    initialized = true;
  }

private:
  float q;
  float r;
  float estimate;
  float errorCovariance;
  bool initialized;
};


struct myIMU {
  float ax, ay, az;
  float gx, gy, gz;
  int16_t dis, str, tem;
};


// Setup MPU6050
Adafruit_MPU6050 mpu;

// Setup TFminiS device
#define tfSerial Serial1
TFminiS tfmini(tfSerial);

// Calibration state
float calibration_gx = 0.0f;
float calibration_gy = 0.0f;
float calibration_gz = 0.0f;
float calibration_ax = 0.0f;
float calibration_ay = 0.0f;
float calibration_az = 0.0f;
float accel_offset_x = 0.0f;
float accel_offset_y = 0.0f;
float accel_offset_z = 0.0f;
int calibration_count = 0;

// Kalman filters
ScalarKalmanFilter accelXFilter(ACCEL_PROCESS_NOISE, ACCEL_MEASUREMENT_NOISE);
ScalarKalmanFilter accelYFilter(ACCEL_PROCESS_NOISE, ACCEL_MEASUREMENT_NOISE);
ScalarKalmanFilter accelZFilter(ACCEL_PROCESS_NOISE, ACCEL_MEASUREMENT_NOISE);
ScalarKalmanFilter gyroXFilter(GYRO_PROCESS_NOISE, GYRO_MEASUREMENT_NOISE);
ScalarKalmanFilter gyroYFilter(GYRO_PROCESS_NOISE, GYRO_MEASUREMENT_NOISE);
ScalarKalmanFilter gyroZFilter(GYRO_PROCESS_NOISE, GYRO_MEASUREMENT_NOISE);
ScalarKalmanFilter distanceFilter(DISTANCE_PROCESS_NOISE, DISTANCE_MEASUREMENT_NOISE);
ScalarKalmanFilter strengthFilter(STRENGTH_PROCESS_NOISE, STRENGTH_MEASUREMENT_NOISE);
ScalarKalmanFilter temperatureFilter(TEMPERATURE_PROCESS_NOISE, TEMPERATURE_MEASUREMENT_NOISE);

volatile byte currentCommand = 0x04;
int ledState = LOW;
myIMU sensorBuffer;
unsigned long lastSampleMicros = 0;


float sampleDeltaSeconds() {
  const unsigned long now = micros();

  if (lastSampleMicros == 0) {
    lastSampleMicros = now;
    return DEFAULT_SAMPLE_DT_SECONDS;
  }

  const unsigned long elapsedMicros = now - lastSampleMicros;
  lastSampleMicros = now;

  const float dtSeconds = elapsedMicros / 1000000.0f;
  if (dtSeconds <= 0.0f || dtSeconds > 1.0f) {
    return DEFAULT_SAMPLE_DT_SECONDS;
  }

  return dtSeconds;
}


int16_t roundToInt16(float value) {
  if (value > 32767.0f) {
    return 32767;
  }
  if (value < -32768.0f) {
    return -32768;
  }
  return (int16_t)lroundf(value);
}


void updateCalibration(const sensors_event_t &accel, const sensors_event_t &gyro) {
  if (calibration_count % 100 == 0) {
    ledState = (ledState == LOW) ? HIGH : LOW;
    digitalWrite(LED_BUILTIN, ledState);
  }

  calibration_gx += gyro.gyro.x;
  calibration_gy += gyro.gyro.y;
  calibration_gz += gyro.gyro.z;
  calibration_ax += accel.acceleration.x;
  calibration_ay += accel.acceleration.y;
  calibration_az += accel.acceleration.z;
  calibration_count += 1;
}


void finishCalibration() {
  calibration_gx /= CALIBRATION_SAMPLES;
  calibration_gy /= CALIBRATION_SAMPLES;
  calibration_gz /= CALIBRATION_SAMPLES;

  const float avg_ax = calibration_ax / CALIBRATION_SAMPLES;
  const float avg_ay = calibration_ay / CALIBRATION_SAMPLES;
  const float avg_az = calibration_az / CALIBRATION_SAMPLES;

  accel_offset_x = avg_ax;
  accel_offset_y = avg_ay;
  accel_offset_z = avg_az - 9.81f;

  Serial.print("Accel offset: ");
  Serial.print(accel_offset_x, 4);
  Serial.print(", ");
  Serial.print(accel_offset_y, 4);
  Serial.print(", ");
  Serial.println(accel_offset_z, 4);

  Serial.print("Gyro offset: ");
  Serial.print(calibration_gx, 4);
  Serial.print(", ");
  Serial.print(calibration_gy, 4);
  Serial.print(", ");
  Serial.println(calibration_gz, 4);

  digitalWrite(LED_BUILTIN, LOW);
  calibration_count += 1;
}


void updateFilteredImu(myIMU &updatedBuffer, const sensors_event_t &accel, const sensors_event_t &gyro, float dtSeconds) {
  const float correctedAx = accel.acceleration.x - accel_offset_x;
  const float correctedAy = accel.acceleration.y - accel_offset_y;
  const float correctedAz = accel.acceleration.z - accel_offset_z;
  const float correctedGx = gyro.gyro.x - calibration_gx;
  const float correctedGy = gyro.gyro.y - calibration_gy;
  const float correctedGz = gyro.gyro.z - calibration_gz;

  updatedBuffer.ax = accelXFilter.update(correctedAx, dtSeconds);
  updatedBuffer.ay = accelYFilter.update(correctedAy, dtSeconds);
  updatedBuffer.az = accelZFilter.update(correctedAz, dtSeconds);
  updatedBuffer.gx = gyroXFilter.update(correctedGx, dtSeconds);
  updatedBuffer.gy = gyroYFilter.update(correctedGy, dtSeconds);
  updatedBuffer.gz = gyroZFilter.update(correctedGz, dtSeconds);
}


void updateFilteredDistance(myIMU &updatedBuffer, int distance, int strength, int temperature, float dtSeconds) {
  if (distance < 0) {
    return;
  }

  updatedBuffer.dis = roundToInt16(distanceFilter.update((float)distance, dtSeconds));
  updatedBuffer.str = roundToInt16(strengthFilter.update((float)strength, dtSeconds));
  updatedBuffer.tem = roundToInt16(temperatureFilter.update((float)temperature, dtSeconds));
}


void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  Serial.begin(115200);

  Wire.setTimeout(1000, true);
  Wire.begin(I2C_ADDRESS);
  Wire.onReceive(receiveHandler);
  Wire.onRequest(requestHandler);

  Wire1.setSDA(24);
  Wire1.setSCL(25);
  tfSerial.begin(115200);

  if (!mpu.begin(0x68, &Wire1)) {
    Serial.println("Failed to find MPU6050 chip");
    while (1) {
      delay(10);
    }
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_16_G);
  mpu.setGyroRange(MPU6050_RANGE_250_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.println("");
  Serial.println("Calibrating MPU6050. Keep the sensor still.");
  delay(100);
}


void loop() {
  const float dtSeconds = sampleDeltaSeconds();

  tfmini.readSensor();
  const int distance = tfmini.getDistance();
  const int strength = tfmini.getStrength();
  const int temperature = tfmini.getTemperature();

  sensors_event_t accel, gyro, temp;
  mpu.getEvent(&accel, &gyro, &temp);

  myIMU updatedBuffer = sensorBuffer;
  updateFilteredDistance(updatedBuffer, distance, strength, temperature, dtSeconds);

  if (calibration_count < CALIBRATION_SAMPLES) {
    updateCalibration(accel, gyro);
  } else if (calibration_count == CALIBRATION_SAMPLES) {
    finishCalibration();
  } else {
    updateFilteredImu(updatedBuffer, accel, gyro, dtSeconds);
  }

  noInterrupts();
  sensorBuffer = updatedBuffer;
  interrupts();
}


void receiveHandler(int x) {
  while (Wire.available()) {
    currentCommand = Wire.read();
  }
}


void requestHandler() {
  if (currentCommand == 0x01) {
    Wire.write((uint8_t*)&sensorBuffer.ax, sizeof(sensorBuffer.ax) * 3);
  } else if (currentCommand == 0x02) {
    Wire.write((uint8_t*)&sensorBuffer.gx, sizeof(sensorBuffer.gx) * 3);
  } else if (currentCommand == 0x03) {
    Wire.write((uint8_t*)&sensorBuffer.dis, sizeof(sensorBuffer.dis) * 3);
  } else if (currentCommand == 0x04) {
    // Send all data: 3 floats accel, 3 floats gyro, 3 ints distance
    Wire.write((uint8_t*)&sensorBuffer, sizeof(sensorBuffer));
  } else {
    uint8_t zero = 0;
    Wire.write(&zero, 1);
  }
}
