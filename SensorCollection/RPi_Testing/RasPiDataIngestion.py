#!/usr/bin/env python3
"""
Raspberry Pi I2C Sensor Reader for Arduino Sensor Collection
Reads accelerometer, gyroscope, and distance sensor data from Arduino via I2C
"""

import argparse
import csv
import smbus
import time
import struct
import math
from datetime import datetime


def format_terminal_float(value):
    if value is None:
        return ''

    truncated = math.trunc(value * 100) / 100
    return f"{truncated:.2f}"


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
        Read all sensor data at once using command 0x04

        Returns:
            dict: Dictionary containing all sensor readings
        """
        data = self._read_sensor_data(0x04, 30, '<ffffffhhh', 'all sensors')
        if data is None:
            return {}

        readings = {}
        readings['acceleration_x'] = data[0]
        readings['acceleration_y'] = data[1]
        readings['acceleration_z'] = data[2]
        readings['gyroscope_x'] = data[3]
        readings['gyroscope_y'] = data[4]
        readings['gyroscope_z'] = data[5]
        readings['distance'] = data[6]
        readings['strength'] = data[7]
        readings['temperature'] = data[8]

        return readings

    def close(self):
        """Close the I2C bus"""
        self.bus.close()


def main(output_file='sensor_data.csv', interval=0.25):
    """Main function to perform timestamped sensor ingestion into CSV."""
    print("Arduino Sensor Reader for Raspberry Pi")
    print("=======================================")
    print(f"Logging sensor data to {output_file} every {interval:.2f} seconds.")

    # Initialize sensor reader
    reader = ArduinoSensorReader()
    fieldnames = [
        'sample_count',
        'timestamp',
        'acceleration_x',
        'acceleration_y',
        'acceleration_z',
        'gyroscope_x',
        'gyroscope_y',
        'gyroscope_z',
        'distance',
        'strength',
        'temperature',
    ]

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        try:
            print("Starting sensor readings... Press Ctrl+C to stop.\n")
            next_time = time.perf_counter()
            sample_count = 0

            while True:
                cycle_start = time.perf_counter()
                timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
                readings = reader.read_all_sensors()
                sample_number = sample_count + 1

                row = {
                    'sample_count': sample_number,
                    'timestamp': timestamp,
                    'acceleration_x': readings.get('acceleration_x'),
                    'acceleration_y': readings.get('acceleration_y'),
                    'acceleration_z': readings.get('acceleration_z'),
                    'gyroscope_x': readings.get('gyroscope_x'),
                    'gyroscope_y': readings.get('gyroscope_y'),
                    'gyroscope_z': readings.get('gyroscope_z'),
                    'distance': readings.get('distance'),
                    'strength': readings.get('strength'),
                    'temperature': readings.get('temperature'),
                }
                writer.writerow(row)
                csvfile.flush()

                if sample_count < 50:
                    print(f"[{sample_number:02d}] {timestamp} | "
                          f"ax={format_terminal_float(row['acceleration_x'])} "
                          f"ay={format_terminal_float(row['acceleration_y'])} "
                          f"az={format_terminal_float(row['acceleration_z'])} | "
                          f"gx={format_terminal_float(row['gyroscope_x'])} "
                          f"gy={format_terminal_float(row['gyroscope_y'])} "
                          f"gz={format_terminal_float(row['gyroscope_z'])} | "
                          f"dist={row['distance']} str={row['strength']} temp={row['temperature']}")

                sample_count += 1
                elapsed = time.perf_counter() - cycle_start
                next_time += interval
                sleep_time = next_time - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    next_time = time.perf_counter()

        except KeyboardInterrupt:
            print("\nStopping sensor readings...")

        finally:
            reader.close()
            print("I2C connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Read sensor data from the Arduino over I2C and log it to CSV'
    )
    parser.add_argument(
        '-o', '--output',
        default='sensor_data.csv',
        help='Output CSV filename (default: sensor_data.csv)'
    )
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=0.25,
        help='Minimum polling interval in seconds (default: 0.25)'
    )
    args = parser.parse_args()

    if args.interval <= 0:
        raise SystemExit('Interval must be a positive number')

    main(output_file=args.output, interval=args.interval)
