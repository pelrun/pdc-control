MCU appears to be a GD32F130C8 (STM32F030? clone, but with fewer errata)

All messages:

Report data:

(these are just a vendor HID report ID):
data[0] = 0xFF
data[1] = 0x55

data[2:7] are essentially gibberish calculated from the system tick counter and ignored, except:

data[4] high bit set if response needed from device

data[8] = command ID
data[9:61] command specific payload
data[62] = sum of bytes 8-61
data[63] = sum of bytes 0-61

Commands:
    FAIL_RESPONSE = 0x01,
    OK_RESPONSE = 0x02, (sent by unit as a success code for commands 3,4,5,0x17)
    UPGRADE_MODE = 0x03, (returns OK if we're in the bootloader)
    LOCK_FW = 0x04,
    UNLOCK_FW = 0x05, (needed before doing flash erase or write)
    LOCK_RDP/UNLOCK_RDP = 0x06/0x07, don't call these!
    FLASH_ERASE = 0x08, erases a full flash block
    FLASH_WRITE = 0x09,
    FLASH_READ = 0x0a, (8-bit length, must fit in one report)
    FLASH_READ_LARGE = 0x0b, (16-bit length, unit sends multiple reports)
    RESTART = 0x17,

Read commands can return any memory area, including the bootloader, all data is sent unencrypted!

Unit configuration is done entirely by reading/writing flash contents of certain fixed addresses

0x08003800: 16 byte firmware name, or gibberish depending on loaded fw

Only a firmware that has "PCCTL" in it's name uses the configuration data area.

0x0800FC00: 0x34 byte configuration data area, not overwritten by flashing a fw

Message1 and Message3 response:
data[11] - selected mode
- 0xa0 - min
- 0xa1 - max
- 0xa2 - rotate
- 0x00 - first (5V)
- ...


Message content (without header)

content[0] = 0xA0  // always?
content[1] - selected mode (see above)
content[2] = 0x88  // selected voltage, low (if variable mode is selected)
content[3] = 0x13  // selected voltage, hi
content[4] = 0x01  // ?
content[5] = mode count
content[6] = 0x00  // ?
// 4B per mode