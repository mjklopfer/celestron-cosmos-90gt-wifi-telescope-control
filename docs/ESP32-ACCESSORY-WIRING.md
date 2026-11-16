# Proposed ESP32 accessory: breakout-board wiring concept

Concept only, not a connector pinout or verified COSMOS circuit. Assemble from
breakout boards and a small buffer/perfboard circuit; no custom PCB required.
Choose GPIO assignments after selecting the exact ESP32 board.

```text
TELESCOPE SIDE                     ESP32                     SENSOR SIDE

AUX connector                 +---------------+          +------------------+
  nominal 12 V --[12V->5V]-----| 5V/VIN        |   +5V----| M10-25Q GPS      |
                      +5V     | onboard 3V3   |          |                  |
                              | regulator     |          | GPS TX ----------+-->
  AUX data in --[5V-tolerant]--| AUX UART RX   |          | GPS RX <---------+---
               [3V3 output ]  |               |          +------------------+
                              | GPS UART RX <-+--- GPS TX (voltage verified)
  AUX data out <--[HCT/AHCT125]| AUX UART TX   | GPS UART TX ---> GPS RX
                    ^         |               |   Separate UART from AUX
                 TX enable <--| GPIO          |
                              |               |          +------------------+
  AUX BUSY/arbitration <------>| GPIOs through |          | QMC5883L compass |
       safe assertion/release | AUX interface |          | on GPS board     |
       and protected sensing  |               |          | SDA / SCL        |
                              | I2C SDA/SCL <-+--+-------+------------------+
                              |               |  |       conditional I2C
                              | 3V3 output ---+--|---+   level converter*
                              +---------------+  |   |
                                                 |   +-- DS3231 VCC
                                                 +------ DS3231 SDA/SCL
                                                         battery backup

All module grounds, converter ground and AUX ground connect together.
5 V rail powers ESP32 VIN, M10-25Q and 5 V HCT/AHCT buffers.
3.3 V rail powers the compatible DS3231 breakout and low-voltage pull-ups.
```

* Put a BSS138-style bidirectional I2C converter ONLY between voltage domains
that require it. ESP32/DS3231 can share a 3.3 V I2C bus directly when their boards
have compatible pull-ups. If the compass board pulls I2C to 5 V, place its branch
on the converter's HV side; LV goes to 3.3 V. Do not connect a 3.3 V-only compass
signal to HV just because the GPS board takes 5 V power. Check the actual board.
UART voltage translation is also conditional on measured/specified logic levels;
use a suitable directional translator when needed, not an assumed I2C solution.

For AUX, prefer a proven 74HCT125 circuit; SN74AHCT125N is a plausible TTL-input,
tri-state-output alternative, not a complete interface by itself. Provide disabled
outputs during boot/reset, correct BUSY assertion/release, and 3.3 V-safe receive
signals. A 5 V-powered buffer output is not safe directly into ESP32 inputs.
A generic transistor level-converter board does not provide bus ownership or
transmit enable. Keep fast buffer wiring short and decouple each IC. Match the
firmware's arbitration behavior to the chosen circuit. Shared BUSY must not be
actively driven high against another device asserting low. Do not pull an ESP32
GPIO up to 5 V through the output-enable control circuit.

Verify connector orientation, cable continuity, port power capacity and actual
logic levels before connecting AUX. Avoid backfeeding the PC's USB 5 V rail while
externally powering the ESP32; follow the chosen development board's power scheme.
Use the actual breakout schematics for battery charging, pull-ups and regulator
behavior. A magnetometer is not a full tilt-sensing IMU; add tilt sensing if needed.

Sources:
- [TI SN74AHCT125](https://www.ti.com/product/SN74AHCT125)
- [TI SN74HCT125](https://www.ti.com/product/SN74HCT125)
- [TI SN74LVC125A, example 5 V-tolerant receiver at 3.3 V](https://www.ti.com/product/SN74LVC125A)
- [DS3231 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/DS3231.pdf)
- [SEQURE module manual](https://flymod.net/download/sequre_m10_12_m10_18_m10_25q_gps_manual)
- [HomeBrew Gen3 author build notes](https://www.cloudynights.com/forums/topic/854327-homebrew-gen3-pcb-wifibtgpsmusbrelay/)
