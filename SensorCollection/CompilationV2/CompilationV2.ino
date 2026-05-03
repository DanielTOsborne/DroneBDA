#include <TFminiS.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>


// Setup MPU6050
Adafruit_MPU6050 mpu;
// Create calibration 
double calibration_gx, calibration_gy, calibration_gz;
int calibration_count;

// Setup TFminiS device
#define tfSerial Serial1
TFminiS tfmini(tfSerial);

void setup() {
  Serial.begin(115200);

  Wire.begin(5);
  Wire.onReceive(receiveHandler);
  Wire.onRequest(requestHandler);
  
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
  calibration_gx = 0;
  calibration_gy = 0;
  calibration_gz = 0;
}

double calibrate(double raw_val, double cal_max, double cal_min){
  return (((raw_val - cal_min) * (9.81 - (-9.81))) / (cal_max - cal_min)) + -9.81;
}

double ax, ay, az, gx, gy, gz;
int dis, str, tem;

void loop() {
  tfmini.readSensor();

  int distance = tfmini.getDistance();
  int strength = tfmini.getStrength();
  int temperature = tfmini.getTemperature();

/* Get new sensor events with the readings */
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

   if (calibration_count < 1000){
    calibration_gx += g.gyro.x;
    calibration_gy += g.gyro.y;
    calibration_gz += g.gyro.z;
    calibration_count += 1;
  } else if (calibration_count == 1000){
    calibration_gx /= 1000;
    calibration_gy /= 1000;
    calibration_gz /= 1000;
    calibration_count += 1;
  } else {
    /* Record the values */
    ax = calibrate(a.acceleration.x, 9.8, -9.61);
    ay = calibrate(a.acceleration.y, 9.86, -9.85);
    az = calibrate(a.acceleration.z, 10.9, -8.8);
    gx = (g.gyro.x - calibration_gx);
    gy = (g.gyro.y - calibration_gy);
    gz = (g.gyro.z - calibration_gz);
  }
  if (distance >= 0) {
    dis = distance;
    str = strength;
    tem = temperature;
  }
}


void receiveHandler(int x){
  while(Wire.available()){
    char c = Wire.read();
    Serial.print(c);
  }
}

void requestHandler(){
  Wire.write("Hello, World!");
}
