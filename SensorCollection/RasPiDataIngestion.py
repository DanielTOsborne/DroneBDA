#!/usr/bin/env python3
"""
Raspberry Pi I2C Sensor Reader for Arduino Sensor Collection
Reads accelerometer, gyroscope, and distance sensor data from Arduino via I2C
"""

import smbus
import time
import struct

class ArduinoSensorReader:
    def __init__(self, bus_number=1, arduino_address=0x0F, max_retries=3, retry_delay=0.1):
        """
        Initialize I2C communication with Arduino

        Args:
            bus_number: I2C bus number (usually 1 on Raspberry Pi)
            arduino_address: I2C address of Arduino (15 in decimal = 0x0F in hex)
            max_retries: number of retry attempts for each sensor read
            retry_delay: delay between retries in seconds
        """
        self.bus_number = bus_number
        self.arduino_address = arduino_address
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._open_bus()

    def _open_bus(self):
        self.bus = smbus.SMBus(self.bus_number)

    def _reconnect_bus(self):
        try:
            self.bus.close()
        except Exception:
            pass
        time.sleep(0.1)
        self._open_bus()

    def _read_sensor_data(self, command, length, fmt, description):
        attempts = 0
        while attempts < self.max_retries:
            try:
                data = self.bus.read_i2c_block_data(self.arduino_address, command, length)
                if len(data) != length:
                    raise IOError(f"Expected {length} bytes, got {len(data)}")
                return struct.unpack(fmt, bytes(data))
            except Exception as exc:
                attempts += 1
                print(
                    f"Warning: {description} read failed (attempt {attempts}/{self.max_retries}): {exc}"
                )
                if attempts >= self.max_retries:
                    print(f"Error: {description} read failed after {self.max_retries} attempts.")
                    return None
                self._reconnect_bus()
                time.sleep(self.retry_delay)
        return None

    def read_acceleration(self):
        """
        Read acceleration data (X, Y, Z axes) from MPU6050

        Returns:
            tuple: (ax, ay, az) in m/s², or None if error
        """
        return self._read_sensor_data(0x01, 12, '<fff', 'acceleration')

    def read_gyroscope(self):
        """
        Read gyroscope data (X, Y, Z axes) from MPU6050

        Returns:
            tuple: (gx, gy, gz) in degrees/second, or None if error
        """
        return self._read_sensor_data(0x02, 12, '<fff', 'gyroscope')

    def read_distance_sensor(self):
        """
        Read distance sensor data from TFminiS

        Returns:
            tuple: (distance, strength, temperature) or None if error
        """
        return self._read_sensor_data(0x03, 6, '<hhh', 'distance sensor')

    def read_all_sensors(self):
        """
        Read all sensor data at once

        Returns:
            dict: Dictionary containing all sensor readings
        """
        readings = {}

        accel = self.read_acceleration()
        if accel is not None:
            readings['acceleration_x'] = accel[0]
            readings['acceleration_y'] = accel[1]
            readings['acceleration_z'] = accel[2]

        gyro = self.read_gyroscope()
        if gyro is not None:
            readings['gyroscope_x'] = gyro[0]
            readings['gyroscope_y'] = gyro[1]
            readings['gyroscope_z'] = gyro[2]

        distance = self.read_distance_sensor()
        if distance is not None:
            readings['distance'] = distance[0]
            readings['strength'] = distance[1]
            readings['temperature'] = distance[2]

        return readings

    def close(self):
        """Close the I2C bus"""
        self.bus.close()


def main():
    """Main function to demonstrate sensor reading"""
    print("Arduino Sensor Reader for Raspberry Pi")
    print("=======================================")

    # Initialize sensor reader
    reader = ArduinoSensorReader()

    try:
        print("Starting sensor readings... Press Ctrl+C to stop.\n")

        while True:
            # Read all sensors
            readings = reader.read_all_sensors()

            # Display readings
            print("Sensor Readings:")
            print("-" * 40)

            if 'acceleration_x' in readings:
                print(f"Acceleration X: {readings['acceleration_x']:.2f} m/s²")
                print(f"Acceleration Y: {readings['acceleration_y']:.2f} m/s²")
                print(f"Acceleration Z: {readings['acceleration_z']:.2f} m/s²")

            if 'gyroscope_x' in readings:
                print(f"Gyroscope X: {readings['gyroscope_x']:.2f} °/s")
                print(f"Gyroscope Y: {readings['gyroscope_y']:.2f} °/s")
                print(f"Gyroscope Z: {readings['gyroscope_z']:.2f} °/s")

            if 'distance' in readings:
                print(f"Distance: {readings['distance']} cm")
                print(f"Strength: {readings['strength']}")
                print(f"Temperature: {readings['temperature']}°C")

            print()  # Empty line
            time.sleep(1)  # Read every second

    except KeyboardInterrupt:
        print("\nStopping sensor readings...")

    finally:
        reader.close()
        print("I2C connection closed.")


if __name__ == "__main__":
    main()
