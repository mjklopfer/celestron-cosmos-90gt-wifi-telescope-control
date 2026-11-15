#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>

// Pure in-memory simulator. No pins, UARTs or upstream telescope connections.
class AuxSimulator {
public:
  double position[2] = {0, 1398101.333333}; // AZ 0 degrees, ALT 30 degrees.
  double speed[2] = {0, 0}; // Encoder counts per second.
  double target[2] = {0, 0};
  bool movingTo[2] = {false, false};
  static uint32_t count(double value) {
    int64_t v = (int64_t)value % 16777216;
    return (uint32_t)(v < 0 ? v + 16777216 : v);
  }
  static uint32_t read24(const uint8_t *data) {
    return ((uint32_t)data[0] << 16) | ((uint32_t)data[1] << 8) | data[2];
  }
  void stop() {
    for (int i = 0; i < 2; ++i) { speed[i] = 0; movingTo[i] = false; }
  }
  void tick(double seconds) {
    if (seconds < 0 || seconds > 1) return;
    for (int i = 0; i < 2; ++i) {
      if (movingTo[i]) {
        double delta = target[i] - position[i];
        if (delta > 8388608) delta -= 16777216;
        if (delta < -8388608) delta += 16777216;
        double step = 139810.133333 * seconds; // 3 deg/s, simulated only.
        if (fabs(delta) <= step) {
          position[i] = target[i]; movingTo[i] = false; speed[i] = 0;
        } else position[i] += delta > 0 ? step : -step;
      } else position[i] += speed[i] * seconds;
      position[i] = fmod(position[i] + 16777216, 16777216);
    }
  }
  // Input must already have framing/checksum verified. Output includes checksum.
  size_t reply(const uint8_t *frame, size_t length, uint8_t *out) {
    if (length < 6 || frame[1] + 3u != length) return 0;
    uint8_t source = frame[2], destination = frame[3], command = frame[4];
    if (destination != 0x10 && destination != 0x11) return 0;
    int axis = destination - 0x10;
    const uint8_t *data = frame + 5;
    size_t n = length - 6, size = 0;
    uint8_t payload[8] = {};
    if (command == 0xfe && n == 0) {
      payload[0] = 5; payload[1] = 24; size = 2;
    } else if (command == 0x05 && n == 0) {
      payload[0] = 0x15; payload[1] = 0x83; size = 2;
    } else if (command == 0x01 && n == 0) {
      uint32_t v = count(position[axis]);
      payload[0] = v >> 16; payload[1] = v >> 8; payload[2] = v; size = 3;
    } else if (command == 0x13 && n == 0) {
      payload[0] = movingTo[axis] ? 0 : 0xff; size = 1;
    } else if ((command == 0x24 || command == 0x25) && n == 1 && data[0] <= 9) {
      const double degrees[] = {0, .004178, .008356, .016712, .033424, .1, .5, 1, 2, 3};
      movingTo[axis] = false;
      speed[axis] = degrees[data[0]] * 16777216.0 / 360.0 * (command == 0x24 ? 1 : -1);
      payload[0] = 1; size = 1;
    } else if ((command == 0x02 || command == 0x17) && n == 3) {
      target[axis] = read24(data); movingTo[axis] = true; speed[axis] = 0;
      payload[0] = 1; size = 1;
    } else if (command == 0x04 && n == 3) {
      position[axis] = read24(data); movingTo[axis] = false; speed[axis] = 0;
      payload[0] = 1; size = 1;
    } else if ((command == 0x06 || command == 0x07) && n == 3) {
      // Approximate variable-rate tracking; not a physical-controller calibration.
      movingTo[axis] = false;
      speed[axis] = read24(data) / 1024.0 * (command == 0x06 ? 1 : -1);
      payload[0] = 1; size = 1;
    } else if ((command == 0x40 || command == 0x23) && n == 0) {
      payload[0] = 0; size = 1;
    } else if (command == 0xfc && n == 0) {
      payload[0] = axis; size = 1;
    } else if (command == 0x21 && n == 0) {
      payload[0] = 0x0a; payload[1] = 0xbd; payload[2] = 0x0c; payload[3] = 0xb2; size = 4;
    } else return 0; // No fictional responses for GPS, StarSense, or other modules.
    out[0] = 0x3b; out[1] = size + 3;
    out[2] = destination; out[3] = source; out[4] = command;
    uint8_t sum = out[1] + out[2] + out[3] + out[4];
    for (size_t i = 0; i < size; ++i) { out[5 + i] = payload[i]; sum += payload[i]; }
    out[5 + size] = -sum;
    return size + 6;
  }
};
