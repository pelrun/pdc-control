import hidapi
import struct
import sys

vid = 0x0716
pid = 0x5036

class PDCMessage:
    FAIL_RESPONSE = 0x01
    OK_RESPONSE = 0x02
    UPGRADE_MODE = 0x03 # returns OK if we're in the bootloader
    LOCK_FLASH = 0x04
    UNLOCK_FLASH = 0x05 # needed before flash write/erase
    LOCK_RDP = 0x07
    UNLOCK_RDP = 0x07; # !! erases chip !!
    FLASH_ERASE = 0x08
    FLASH_WRITE = 0x09
    FLASH_READ = 0x0a
    FLASH_READ_LARGE = 0x0b
    RESTART = 0x17

    def __init__(self, hidDevice, command, responseNeeded):
        self.hidDevice = hidDevice
        self.report = bytearray(64)
        self.report[0:2] = (0xFF, 0x55)
        self.setCommand(command).setResponseNeeded(responseNeeded)

    def checksum(self, report):
        return (sum(report[8:62])&0xff, sum(report[0:62])&0xff)

    def finaliseMessage(self):
        (self.report[62],self.report[63]) = self.checksum(self.report)
        return self

    def send(self):
        self.hidDevice.write(self.finaliseMessage().report)
        return self

    def setCommand(self, cmd):
        self.report[8] = cmd
        return self

    def setResponseNeeded(self, flag):
        if flag:
            self.report[4] = 0x80
        else:
            self.report[4] = 0
        return self

class PDCMessageBool(PDCMessage):
    def __init__(self, hidDevice, command):
        super().__init__(self, hidDevice, command, True)

    def execute(self):
        self.send()
        return self.hidDevice.read(64, timeout_ms=1000)[8] == PDCMessage.OK_RESPONSE

class UpgradeMode(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(self, hidDevice, PDCMessage.UPGRADE_MODE)

class LockFlash(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(self, hidDevice, PDCMessage.LOCK_FLASH)

class UnlockFlash(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(self, hidDevice, PDCMessage.UNLOCK_FLASH)

class Restart(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(self, hidDevice, PDCMessage.Restart)

class ReadMemory(PDCMessage):
    def __init__(self, hidDevice):
        super().__init__(self, hidDevice, PDCMessage.FLASH_READ, True)

    def execute(self, address, length):
        if length > 0x28:
            length = 0x28
        struct.pack_into("<BIB", self.report, 9, 5, address,length)
        self.send()
        resp = self.hidDevice.read(64, timeout_ms=1000)
        return resp[10:10+resp[9]]

class EraseBlock(PDCMessage):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.FLASH_ERASE, False)

    def execute(self, address):
        struct.pack_into("<BI", self.report, 9, 4, address)
        self.send()

class WriteFlash(PDCMessage):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.FLASH_WRITE, False)

    def execute(self, address, data):
        struct.pack_into("<BIBs", self.report, 9, 5+len(data), address, len(data), data)
        self.send()




def dumpbootloader():
    if UpgradeMode(h).send().check():
        sys.stdout.buffer.write(b''.join([ReadMemory(h).execute(addr,0x20) for addr in range(0x08000000,0x08002c00,0x20)]))

h = hidapi.Device(vendor_id = vid, product_id = pid)

# print(f'Device manufacturer: {h.get_manufacturer_string()}')
# print(f'Product: {h.get_product_string()}')
# print(f'Serial Number: {h.get_serial_number_string()}')

if (UpgradeMode(h).execute()):
    print("woot")
    # print(hex(struct.unpack_from("<I",GetMemory(h).read(0xE0042000,4))[0])) # DBGMCU_IDCODE
    # print(struct.unpack_from("<HH",GetMemory(h).read(0x1ffff7e0,4))) # (flash size, ram size) in kb
    # pid = struct.unpack_from("<IIIIIIII",GetMemory(h).read(0xE00FFFE0,32))
    # print (f"used: {pid[2]&8}")
    # print (f"identity: {((pid[1]&0xF0)>>4) | ((pid[2]&0x7)<<4)}")

