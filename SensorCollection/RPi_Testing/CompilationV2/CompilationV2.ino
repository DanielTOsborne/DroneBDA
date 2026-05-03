#include <TFminiS.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>


// Setup MPU6050
Adafruit_MPU6050 mpu;
// Create calibration
float calibration_gx, calibration_gy, calibration_gz;
float calibration_ax, calibration_ay, calibration_az;
float accel_offset_x, accel_offset_y, accel_offset_z;
int calibration_count;

// Setup TFminiS device
#define tfSerial Serial1
TFminiS tfmini(tfSerial);

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

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
  calibration_ax = 0;
  calibration_ay = 0;
  calibration_az = 0;
  accel_offset_x = 0;
  accel_offset_y = 0;
  accel_offset_z = 0;
}

struct myIMU {
  float ax, ay, az;
  float gx, gy, gz;
  int16_t dis, str, tem;
};
int ledState = LOW;
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
    if (calibration_count % 100 == 0) {
      ledState = (ledState == LOW) ? HIGH : LOW;
      digitalWrite(LED_BUILTIN, ledState);
    }

    calibration_gx += g.gyro.x;
    calibration_gy += g.gyro.y;
    calibration_gz += g.gyro.z;
    calibration_ax += a.acceleration.x;
    calibration_ay += a.acceleration.y;
    calibration_az += a.acceleration.z;
    calibration_count += 1;
  } else if (calibration_count == 1000) {
    calibration_gx /= 1000;
    calibration_gy /= 1000;
    calibration_gz /= 1000;

    float avg_ax = calibration_ax / 1000.0;
    float avg_ay = calibration_ay / 1000.0;
    float avg_az = calibration_az / 1000.0;

    accel_offset_x = avg_ax;
    accel_offset_y = avg_ay;
    accel_offset_z = avg_az - 9.81;

    Serial.print("Accel offset: ");
    Serial.print(accel_offset_x, 4);
    Serial.print(", ");
    Serial.print(accel_offset_y, 4);
    Serial.print(", ");
    Serial.println(accel_offset_z, 4);

    calibration_count += 1;
  } else {
    updatedBuffer.ax = a.acceleration.x - accel_offset_x;
    updatedBuffer.ay = a.acceleration.y - accel_offset_y;
    updatedBuffer.az = a.acceleration.z - accel_offset_z;
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
  } else if (currentCommand == 0x04) {
    // Send all data: 3 floats accel, 3 floats gyro, 3 ints distance
    Wire.write((uint8_t*)&sensorBuffer, sizeof(sensorBuffer));
  } else {
    uint8_t zero = 0;
    Wire.write(&zero, 1);
  }
}
