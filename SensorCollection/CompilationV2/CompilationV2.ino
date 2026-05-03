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

  Wire.setTimeout(3000, true);
  Wire.begin(15);
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

float calibrate(float raw_val, float cal_max, float cal_min){
  return (((raw_val - cal_min) * (9.81 - (-9.81))) / (cal_max - cal_min)) + -9.81;
}

struct myIMU {
float ax, ay, az;
float gx, gy, gz;
int dis, str, tem;
};

myIMU sensorBuffer;

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
    sensorBuffer.ax = calibrate(a.acceleration.x, 9.8, -9.61);
    sensorBuffer.ay = calibrate(a.acceleration.y, 9.86, -9.85);
    sensorBuffer.az = calibrate(a.acceleration.z, 10.9, -8.8);
    sensorBuffer.gx = (g.gyro.x - calibration_gx);
    sensorBuffer.gy = (g.gyro.y - calibration_gy);
    sensorBuffer.gz = (g.gyro.z - calibration_gz);
  }
  if (distance >= 0) {
    sensorBuffer.dis = distance;
    sensorBuffer.str = strength;
    sensorBuffer.tem = temperature;
  }
}

volatile byte currentCommand;

void receiveHandler(int x){
  while(Wire.available()){
    currentCommand = Wire.read();
  }
}

void requestHandler(){
  if(currentCommand == 0x01){
    Wire.write((byte*)&sensorBuffer.ax,12);
  } else if(currentCommand == 0x02){
    Wire.write((byte*)&sensorBuffer.gx,12);  
  } else if(currentCommand == 0x03){
    Wire.write((byte*)&sensorBuffer.dis,6);
  } else {
    Wire.write(0x00);
  }
  
}
