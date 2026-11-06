#!/usr/bin/env python3
"""Runs ON the OctoPi. Uploads a Marlin .bin to the printer's SD card over the
serial port (Marlin binary file transfer), triggers M997 and verifies the new
build time. OctoPrint must be disconnected from the printer first.

usage: fw_upload_pi.py <firmware.bin> [baud] [serial-port]
Expects MarlinBinaryProtocol.py in the same directory (copied from the Marlin repo).
"""
import sys, os, time, random, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial
import MarlinBinaryProtocol as MBP

binfile = sys.argv[1]
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
dev = sys.argv[3] if len(sys.argv) > 3 else '/dev/ttyUSB0'

def ascii_cmd(port, cmd, wait=3.0, until=None):
    port.reset_input_buffer()
    port.write((cmd + '\n').encode())
    out = []; end = time.time() + wait
    while time.time() < end:
        l = port.readline().decode(errors='replace').strip()
        if not l: continue
        if l.startswith('T:') or 'busy:' in l: continue
        out.append(l)
        if until and until(l): break
        if not until and l.startswith('ok'): break
    return out

def fw_name(port):
    for l in ascii_cmd(port, 'M115', 5):
        m = re.search(r'FIRMWARE_NAME:(.*?) SOURCE_CODE_URL', l)
        if m: return m.group(1)
    return None

# 1. current firmware + housekeeping on the SD card
port = serial.Serial(dev, baud, timeout=0.5, write_timeout=0)
time.sleep(1); port.reset_input_buffer()
before = fw_name(port)
print('Running now :', before)
if not before: sys.exit('No response from printer (wrong baud or port busy?)')
if not any('SD card ok' in l for l in ascii_cmd(port, 'M21', 4, lambda l: 'SD card ok' in l or 'init fail' in l)):
    sys.exit('SD card not readable in the printer')
listing = ascii_cmd(port, 'M20 F', 5, lambda l: 'End file list' in l)
old = [l.split()[0] for l in listing if '/' not in l and '.BIN' in l.upper() and not l.startswith(('Begin', 'End'))]
for name in old:
    r = ascii_cmd(port, 'M30 /' + name, 4, lambda l: 'deleted' in l or 'Error' in l or 'ok' in l)
    print('Removed old', name, '->', 'ok' if any('deleted' in x for x in r) else r)
port.close()

# 2. binary upload under a fresh 8.3 name (bootloader ignores a repeated name)
target = 'fw-' + ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=5)) + '.BIN'
print('Uploading', os.path.basename(binfile), '->', target, '(%d bytes)' % os.path.getsize(binfile))
proto = MBP.Protocol(dev, baud, 512, 0.0, 1000)
proto.connect()
ft = MBP.FileTransferProtocol(proto)
ok = ft.copy(binfile, target, True, False)
proto.disconnect()
if not ok:
    proto.shutdown(); sys.exit('Transfer failed; old firmware untouched')
proto.send_ascii('M117 Firmware uploaded')
time.sleep(1)
proto.send_ascii('M21')
print('Triggering firmware update (M997)...')
proto.send_ascii('M997', True)
proto.shutdown()

# 3. wait for bootloader flash + reboot, then verify
time.sleep(10)
after = None
deadline = time.time() + 120
while time.time() < deadline:
    try:
        port = serial.Serial(dev, baud, timeout=0.5, write_timeout=0)
        time.sleep(1)
        after = fw_name(port)
        port.close()
        if after: break
    except Exception as e:
        pass
    time.sleep(3)
print('Running now :', after)
if not after: sys.exit('Printer did not come back within 2 minutes')
if after == before:
    print('RESULT: build time UNCHANGED - same build, or the bootloader skipped the file')
    sys.exit(2)
print('RESULT: flashed OK')
