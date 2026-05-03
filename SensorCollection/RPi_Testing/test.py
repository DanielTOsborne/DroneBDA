import struct
from smbus2 import SMBus
import time

DEVICE_ADDRESS = 0x0f


with SMBus(1) as bus:	
	time.sleep(0.1)

		
#	bus.write_byte_data(DEVICE_ADDRESS, 0, 1)
	data = bus.read_i2c_block_data(DEVICE_ADDRESS, 1, 12)
	print(struct.unpack('>fff',bytes(data)))
	#myfloat = struct.unpack('f', bytes(data))
#	data = bus.read_byte_data(DEVICE_ADDRESS, 0)
	#print(myfloat)	

#	bus.write_byte_data(DEVICE, 0, 2)
#	time.sleep(0.2)
#	data = bus.read_i2c_block_data(DEVICE, 0, 24)
#	print(data)

#	bus.write_byte_data(DEVICE, 0, 3)
#	time.sleep(0.2)
#	data = bus.read_i2c_block_data(device, 0, 6)
#	print(data)
