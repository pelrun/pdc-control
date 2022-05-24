import hidapi
import struct
import sys

vid = 0x0716
pid = 0x5036

def checksum(report):
    return (sum(report[8:62])&0xff, sum(report[0:62])&0xff)

def fixChecksum(data):
    report = bytearray(64)
    report[0:len(data)] = data
    (report[62],report[63]) = checksum(report)
    return report

def send(report):
    h.write(fixChecksum(report))

def upgrade():
    msg = struct.Struct("<HxxBxxxB")
    send(msg.pack(0x55FF,0x80,0x03))
    return h.read(64)[8] == 2

def getmem(address, length):
    msg = struct.Struct("<HxxBxxxBBIB")
    send(msg.pack(0x55FF,0x80,0x0A,5,address,length))
    resp = h.read(64)
    # TODO: check checksum
    (len,) = struct.unpack_from("<9xB", resp)
    return resp[10:10+len]

def dumpbootloader():
    if upgrade():
        sys.stdout.buffer.write(b''.join([getmem(addr,0x20) for addr in range(0x08000000,0x08002c00,0x20)]))

h = hidapi.Device(vendor_id = vid, product_id = pid)

# print(f'Device manufacturer: {h.get_manufacturer_string()}')
# print(f'Product: {h.get_product_string()}')
# print(f'Serial Number: {h.get_serial_number_string()}')

#dumpbootloader()

if (upgrade()):
    print(hex(struct.unpack_from("<I",getmem(0xE0042000,4))[0])) # DBGMCU_IDCODE
    print(struct.unpack_from("<HH",getmem(0x1ffff7e0,4))) # flash size

