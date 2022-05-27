from inspect import getmembers
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
        super().__init__(hidDevice, command, True)

    def execute(self):
        self.send()
        return self.hidDevice.read(64, timeout_ms=1000)[8] == PDCMessage.OK_RESPONSE

class UpgradeMode(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.UPGRADE_MODE)

class LockFlash(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.LOCK_FLASH)

class UnlockFlash(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.UNLOCK_FLASH)

class Restart(PDCMessageBool):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.Restart)

class ReadMemory(PDCMessage):
    def __init__(self, hidDevice):
        super().__init__(hidDevice, PDCMessage.FLASH_READ, True)

    def execute(self, address, length):
        if length > 0x34:
            length = 0x34
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

class PDCFirmware:
    DEFAULT_START = 0x08002c00
    decryptionTable = [
        0x1A, 0xB6, 0xB7, 0xF1, 0x7B, 0x8C, 0xD5, 0x3C, 0x7C, 0x90, 0xD2, 0xF4, 0x35, 0xF2, 0x1B, 0xE9,
        0xDB, 0x12, 0x77, 0x5B, 0x3D, 0x7F, 0x3F, 0xBD, 0x2D, 0x47, 0x2A, 0x50, 0xDC, 0xC3, 0xFF, 0x57,
        0x82, 0x83, 0x60, 0xFC, 0x9B, 0x4E, 0x88, 0xD0, 0x00, 0x5F, 0x2E, 0x59, 0x2B, 0xF9, 0xC6, 0x38,
        0xF0, 0xC8, 0x8E, 0x80, 0x44, 0xFD, 0x73, 0x7E, 0x0B, 0x29, 0x19, 0xAF, 0xD8, 0x96, 0x71, 0xB3,
        0x62, 0xE6, 0xE5, 0x11, 0x91, 0x9C, 0x46, 0x15, 0xC4, 0xC2, 0xA5, 0x52, 0xB9, 0x66, 0xAC, 0xB2,
        0x22, 0x53, 0xEE, 0x54, 0xAA, 0xB4, 0x74, 0xCF, 0xB0, 0x6C, 0x72, 0xA7, 0x92, 0x5A, 0x56, 0xE7,
        0x85, 0xEC, 0xC1, 0x9F, 0xCE, 0x6E, 0xAE, 0x3B, 0x78, 0x8F, 0x5D, 0x4B, 0xE2, 0x64, 0x0C, 0x4C,
        0x13, 0x63, 0xC0, 0x41, 0x4F, 0xBA, 0xE4, 0x10, 0x04, 0xA6, 0x3E, 0x31, 0xE1, 0xB8, 0x48, 0x67,
        0x05, 0xD3, 0x98, 0x69, 0xBF, 0x36, 0x65, 0xBE, 0x06, 0x51, 0x5C, 0xC7, 0x8B, 0x09, 0x37, 0xC5,
        0xA9, 0xA8, 0x70, 0xD4, 0x87, 0x1D, 0xDA, 0x0D, 0xF3, 0x76, 0x30, 0xAD, 0x17, 0x94, 0xE0, 0xB1,
        0x14, 0xED, 0x0E, 0x08, 0x42, 0x9A, 0x33, 0xB5, 0x55, 0xD9, 0x45, 0x39, 0xE3, 0x7D, 0x4D, 0x01,
        0xCB, 0x27, 0xEF, 0x25, 0x6A, 0x3A, 0x7A, 0x79, 0x6D, 0x16, 0x40, 0x61, 0xA4, 0x02, 0xAB, 0x86,
        0x0F, 0x34, 0x6F, 0xEB, 0x6B, 0xF7, 0x28, 0xDE, 0xA3, 0xCC, 0x75, 0x2C, 0xCA, 0x5E, 0x81, 0x0A,
        0xFA, 0x68, 0xF8, 0x07, 0x03, 0x24, 0xCD, 0x1F, 0xA2, 0x2F, 0x32, 0x43, 0x9D, 0xF5, 0xD7, 0xBC,
        0x9E, 0xBB, 0x49, 0x4A, 0xD6, 0x8A, 0x84, 0xA1, 0x21, 0xDF, 0x97, 0xFE, 0x20, 0xD1, 0x1E, 0x93,
        0x1C, 0x8D, 0xFB, 0x26, 0x18, 0x95, 0xF6, 0xC9, 0xDD, 0xEA, 0x99, 0x23, 0xE8, 0xA0, 0x58, 0x89
    ]

    def __init__(self, data):
        (header,) = struct.unpack_from("<I", data);
        if header == 0x56cab67f: # 7fb6 ca56 bb92 9276 is "gzutapp" encrypted
            self.decrypt(data)
        else:
            self.fw = data

    def decrypt(self, data):
        """Import an encrypted pd1s file"""
        self.fw = bytes([self.decryptionTable[x] for x in data])

        if self.fw[0:7] == b'gzutapp':
            self.fw = self.fw[0x30:] # clip the header
        else:
            raise ValueError("Not a valid pd1s file")
    
    def validate(self):
        """Trivial check that the stack and reset pointers go to the right places"""
        return (self.fw[3] == 0x20 and self.fw[7] == 0x08)

    def flash(self, dev, address = DEFAULT_START):
        if not self.validate():
            raise ValueError("FW appears to be invalid")

        if not UpgradeMode(dev).execute():
            raise RuntimeError("Module not in upgrade mode")
        
        # if not UnlockFlash(dev).execute():
        #     raise RuntimeError("Module could not be unlocked")
        
        # erase existing flash
        for block in range(0x08002c00, 0x0800f801, 0x400):
            #EraseBlock(h).execute(block)
            pass

        # flash fw
        pass

class PDCConfig:
    def __init__(self, data):
        self.data = data
        self.pdo = struct.unpack_from("<"+"I"*data[5], data, 7)
    
    def chargerType(self):
        return ((self.data[35]&0xc0) >> 6) + 1

    def mode(self):
        if self.data[1] == 0xa0:
            return "min"
        elif self.data[1] == 0xa1:
            return "max"
        elif self.data[1] == 0xa2:
            return "rotate"
        else:
            return self.data[1]+1
    
    def voltage(self):
        (millivolts,) = struct.unpack_from("<H", self.data, 2)
        return millivolts/1000.0

    def config(self, index):
        pdo = self.pdo[index]
        pdoType = pdo >> 30

        if pdoType == 0:
            # Fixed supply
            return (((pdo>>9) & 0x3ff) * 25 / 1000.0, (pdo & 0x3ff) * 10 / 1000.0)
        elif pdoType == 1:
            # Battery
            return ((pdo>>20) & 0x3ff, (pdo>>10) & 0x3ff, pdo & 0x3ff)
        elif pdoType == 2:
            # Variable supply
            return ((pdo>>20) & 0x3ff, (pdo>>10) & 0x3ff, pdo & 0x3ff)
        else:
            # Augmented PDO
            pass


def dumpbootloader():
    if UpgradeMode(h).send().check():
        sys.stdout.buffer.write(b''.join([ReadMemory(h).execute(addr,0x20) for addr in range(0x08000000,0x08002c00,0x20)]))

h = hidapi.Device(vendor_id = vid, product_id = pid)

# print(f'Device manufacturer: {h.get_manufacturer_string()}')
# print(f'Product: {h.get_product_string()}')
# print(f'Serial Number: {h.get_serial_number_string()}')

# if (UpgradeMode(h).execute()):
#     print("woot")
    # print(hex(struct.unpack_from("<I",GetMemory(h).read(0xE0042000,4))[0])) # DBGMCU_IDCODE
    # print(struct.unpack_from("<HH",GetMemory(h).read(0x1ffff7e0,4))) # (flash size, ram size) in kb
    # pid = struct.unpack_from("<IIIIIIII",GetMemory(h).read(0xE00FFFE0,32))
    # print (f"used: {pid[2]&8}")
    # print (f"identity: {((pid[1]&0xF0)>>4) | ((pid[2]&0x7)<<4)}")

def flashfirmware():
    with open("/home/james.churchill/witrn-pdc002/03_Firmware/PDC002_2.0_200331/PDC002_2.0_PPS_flash.pd1s", "rb") as f:
        fw = PDCFirmware(f.read())

    fw.flash(h)

def readConfig():
    if not UpgradeMode(h).execute():
        raise RuntimeError("Module not in upgrade mode")

    cnf = PDCConfig(ReadMemory(h).execute(0x0800fc00, 0x34))
    print(cnf.chargerType(), cnf.mode(), cnf.voltage(), cnf.config(5))

readConfig()