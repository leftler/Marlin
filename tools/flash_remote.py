#!/usr/bin/env python3
"""Flash a Marlin .bin to the Ender-3 over OctoPi - no SD card shuffling.

usage: python flash_remote.py <firmware.bin> [--baud 115200] [--yes]

Steps: check the printer is idle -> copy bin + helper to the Pi -> disconnect
OctoPrint -> upload over serial (Marlin binary transfer) and M997 -> verify the
new build time -> reconnect OctoPrint. Needs BINARY_FILE_TRANSFER and
CUSTOM_FIRMWARE_UPLOAD in the firmware that is currently running.
"""
import argparse, json, os, subprocess, sys, time, urllib.request

HOST = 'octopi.local'; USER = 'pi'
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROTO = os.path.join(REPO, 'buildroot', 'share', 'scripts', 'MarlinBinaryProtocol.py')
# The OctoPrint API key stays out of the repo; point OCTOPRINT_KEY_FILE elsewhere to override.
KEY = open(os.path.expanduser(os.environ.get('OCTOPRINT_KEY_FILE', os.path.join('~', '.claude', 'octoprint_app_key')))).read().strip()

def api(path, data=None):
    req = urllib.request.Request('http://%s/api/%s' % (HOST, path),
        data=json.dumps(data).encode() if data is not None else None,
        headers={'X-Api-Key': KEY, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read()
        return json.loads(body) if body else {}

ap = argparse.ArgumentParser()
ap.add_argument('bin'); ap.add_argument('--baud', type=int, default=115200)
ap.add_argument('--yes', action='store_true', help='skip the confirmation prompt')
a = ap.parse_args()
if not os.path.isfile(a.bin): sys.exit('No such file: ' + a.bin)

st = api('printer')
flags = st['state']['flags']
if flags.get('printing') or flags.get('paused') or flags.get('pausing'):
    sys.exit('Printer is busy (printing/paused) - not flashing.')
hot = {k: v['actual'] for k, v in st['temperature'].items() if v['actual'] and v['actual'] > 50}
if hot: sys.exit('Heaters are hot %s - let them cool first.' % hot)
if not a.yes and input('Flash %s to the printer now? [y/N] ' % os.path.basename(a.bin)).lower() != 'y':
    sys.exit('Cancelled.')

def run(cmd, **kw): return subprocess.run(cmd, check=True, **kw)
remote_bin = 'fw_to_flash.bin'
# explicit remote names: scp would otherwise keep the Windows path in the filename
for src, dst in ((a.bin, remote_bin), (PROTO, 'MarlinBinaryProtocol.py'), (os.path.join(HERE, 'fw_upload_pi.py'), 'fw_upload_pi.py')):
    run(['scp', '-q', src, '%s@%s:%s' % (USER, HOST, dst)])

api('connection', {'command': 'disconnect'}); time.sleep(3)
rc = 1
try:
    rc = subprocess.run(['ssh', '%s@%s' % (USER, HOST),
        'cd ~ && ~/oprint/bin/python fw_upload_pi.py %s %d' % (remote_bin, a.baud)]).returncode
finally:
    api('connection', {'command': 'connect', 'port': '/dev/ttyUSB0', 'baudrate': a.baud})
    time.sleep(6)
    print('OctoPrint:', api('connection')['current']['state'])
    subprocess.run(['ssh', '%s@%s' % (USER, HOST), 'rm -f %s' % remote_bin])
sys.exit(rc)
