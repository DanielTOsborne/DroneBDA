#include <TFminiS.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>


// Setup MPU6050
Adafruit_MPU6050 mpu;
// Create calibration 
float calibration_gx, calibration_gy, calibration_gz;
int calibration_count;

// Setup TFminiS device
#define tfSerial Serial1
TFminiS tfmini(tfSerial);

void setup() {
  Serial.begin(115200);

  Wire.setTimeout(1000, true);
  Wire.begin(15);
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
  delay(100);
  calibration_gx = 0;
  calibration_gy = 0;
  calibration_gz = 0;
}

float calibrate(float raw_val, float cal_max, float cal_min){
  return (((raw_val - cal_min) * (9.81 - (-9.81))) / (cal_max - cal_min)) + -9.81;
}

struct myIMU {
  float ax, ay, az;
  float gx, gy, gz;
  int16_t dis, str, tem;
};

myIMU sensorBuffer;

void loop() {
  tfmini.readSensor();

  int distance = tfmini.getDistance();
  int strength = tfmini.getStrength();
  int temperature = tfmini.getTemperature();

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  myIMU updatedBuffer = sensorBuffer;

  if (calibration_count < 1000) {
    calibration_gx += g.gyro.x;
    calibration_gy += g.gyro.y;
    calibration_gz += g.gyro.z;
    calibration_count += 1;
  } else if (calibration_count == 1000) {
    calibration_gx /= 1000;
    calibration_gy /= 1000;
    calibration_gz /= 1000;
    calibration_count += 1;
  } else {
    updatedBuffer.ax = calibrate(a.acceleration.x, 9.8, -9.61);
    updatedBuffer.ay = calibrate(a.acceleration.y, 9.86, -9.85);
    updatedBuffer.az = calibrate(a.acceleration.z, 10.9, -8.8);
    updatedBuffer.gx = (g.gyro.x - calibration_gx);
    updatedBuffer.gy = (g.gyro.y - calibration_gy);
    updatedBuffer.gz = (g.gyro.z - calibration_gz);
  }

  if (distance >= 0) {
    updatedBuffer.dis = distance;
    updatedBuffer.str = strength;
    updatedBuffer.tem = temperature;
  }

  noInterrupts();
  sensorBuffer = updatedBuffer;
  interrupts();
}

volatile byte currentCommand;

void receiveHandler(int x){
  while(Wire.available()){
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
  } else {
    uint8_t zero = 0;
    Wire.write(&zero, 1);
  }
}
