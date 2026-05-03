#include <TFminiS.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>


// Setup MPU6050
Adafruit_MPU6050 mpu;
// Create calibration 
double gx, gy, gz;
int calibration_count;

// Setup TFminiS device
#define tfSerial Serial1
TFminiS tfmini(tfSerial);

void setup() {
  Serial.begin(115200);
  tfSerial.begin(115200);

  Wire1.setSDA(24);
  Wire1.setSCL(25);

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
  gx = 0;
  gy = 0;
  gz = 0;
}

double calibrate(double raw_val, double cal_max, double cal_min){
  return (((raw_val - cal_min) * (9.81 - (-9.81))) / (cal_max - cal_min)) + -9.81;
}

void loop() {
  tfmini.readSensor();

  int distance = tfmini.getDistance();
  int strength = tfmini.getStrength();
  int temperature = tfmini.getTemperature();

/* Get new sensor events with the readings */
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

   if (calibration_count < 1000){
    gx = gx + g.gyro.x;
    gy = gy + g.gyro.y;
    gz = gz + g.gyro.z;
    calibration_count += 1;
  } else if (calibration_count == 1000){
    gx = gx / 1000;
    gy = gy / 1000;
    gz = gz / 1000;
    calibration_count += 1;
  } else {
    /* Print out the values */
    Serial.print("AccelX:");
    Serial.print(calibrate(a.acceleration.x, 9.8, -9.61));
    Serial.print(",");
    Serial.print("AccelY:");
    Serial.print(calibrate(a.acceleration.y, 9.86, -9.85));
    Serial.print(",");
    Serial.print("AccelZ:");
    Serial.print(calibrate(a.acceleration.z, 10.9, -8.8));
    Serial.print(", ");
    Serial.print("GyroX:");
    Serial.print(g.gyro.x - gx);
    Serial.print(",");
    Serial.print("GyroY:");
    Serial.print(g.gyro.y - gy);
    Serial.print(",");
    Serial.print("GyroZ:");
    Serial.print(g.gyro.z - gz);
    Serial.println("");
  }
  if (distance >= 0) {
    // If no errors, print the data.
    Serial.print("Distance:");
    Serial.print(distance);
    Serial.print(", Strength:");
    Serial.print(strength);
    Serial.print(", Temperature:");
    Serial.println(temperature);
  }
}
