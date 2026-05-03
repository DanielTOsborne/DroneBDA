#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_MPU6050.h>

/* Assign a unique ID to this sensor at the same time */
//Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);

Adafruit_MPU6050 mpu;

float AccelMinX = 0;
float AccelMaxX = 0;
float AccelMinY = 0;
float AccelMaxY = 0;
float AccelMinZ = 0;
float AccelMaxZ = 0;


void setup(void) 
{
  Serial.begin(9600);
  Serial.println("MPU6050 Accelerometer Calibration"); 
  Serial.println("");
  
  Wire1.setSDA(24);
  Wire1.setSCL(25);

  if (!mpu.begin(0x68, &Wire1)) {
    Serial.println("Failed to find MPU6050 chip");
    while (1) {
      delay(10);
    }
  }
}

void loop(void)
{
    Serial.println("Type key when ready..."); 
    while (!Serial.available()){}  // wait for a character
    
    /* Get a new sensor event */ 
    //sensors_event_t accelEvent;  
    //mpu.getEvent(&accelEvent);
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    
    if (a.acceleration.x < AccelMinX) AccelMinX = a.acceleration.x;
    if (a.acceleration.x > AccelMaxX) AccelMaxX = a.acceleration.x;
    
    if (a.acceleration.y < AccelMinY) AccelMinY = a.acceleration.y;
    if (a.acceleration.y > AccelMaxY) AccelMaxY = a.acceleration.y;
  
    if (a.acceleration.z < AccelMinZ) AccelMinZ = a.acceleration.z;
    if (a.acceleration.z > AccelMaxZ) AccelMaxZ = a.acceleration.z;
  
    Serial.print("Accel Minimums: "); Serial.print(AccelMinX); Serial.print("  ");Serial.print(AccelMinY); Serial.print("  "); Serial.print(AccelMinZ); Serial.println();
    Serial.print("Accel Maximums: "); Serial.print(AccelMaxX); Serial.print("  ");Serial.print(AccelMaxY); Serial.print("  "); Serial.print(AccelMaxZ); Serial.println();

    while (Serial.available())
    {
      Serial.read();  // clear the input buffer
    }
}
