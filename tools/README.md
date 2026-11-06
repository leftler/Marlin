# Remote firmware flashing (Ender-3 over OctoPi)

Flash a freshly built Marlin `.bin` without moving the SD card.

```
pio run -e STM32F103RE_creality
python tools/flash_remote.py .pio/build/STM32F103RE_creality/firmware-<stamp>.bin --yes
```

`flash_remote.py` (PC side) checks the printer is idle with heaters below 50 C, copies the
firmware and `fw_upload_pi.py` to the Pi, disconnects OctoPrint, runs the upload, then
reconnects OctoPrint. `fw_upload_pi.py` (Pi side) deletes old `.bin` files from the SD card,
uploads the new image under a fresh 8.3 name with Marlin's binary file transfer, sends `M997`
and checks `M115` for a new build time.

Needs in the firmware that is running: `BINARY_FILE_TRANSFER`, `CUSTOM_FIRMWARE_UPLOAD` and
`DO_LIST_BIN_FILES` (so `M20 F` can see `.bin` files; 2.1.2.8 only sets it for ProUI).
Needs on the Pi: pyserial in the OctoPrint venv (`~/oprint/bin/python`). The OctoPrint API key
is read from `~/.claude/octoprint_app_key`, or the file named by `OCTOPRINT_KEY_FILE`.
Host, user and baud (`--baud`, default 115200) are at the top of `flash_remote.py`.

The bootloader ignores a file name it has already flashed, which is why every upload gets a
random name. Leftover `.bin` files on the card can make it skip the new one.
