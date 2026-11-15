#include <assert.h>
#include <stdio.h>
#include "simulator/aux_simulator.h"

size_t request(AuxSimulator &mount, uint8_t dest, uint8_t cmd,
               const uint8_t *payload, size_t length, uint8_t *out) {
  uint8_t frame[32] = {0x3b, (uint8_t)(length + 3), 0x20, dest, cmd};
  uint8_t sum = frame[1] + frame[2] + frame[3] + frame[4];
  for (size_t i = 0; i < length; ++i) { frame[5 + i] = payload[i]; sum += payload[i]; }
  frame[5 + length] = -sum;
  size_t n = mount.reply(frame, length + 6, out);
  if (n) {
    assert(out[0] == 0x3b && out[1] + 3u == n && out[2] == dest && out[3] == 0x20 && out[4] == cmd);
    uint8_t checksum = 0;
    for (size_t i = 1; i < n; ++i) checksum += out[i];
    assert(checksum == 0);
  }
  return n;
}

int main() {
  AuxSimulator mount;
  uint8_t out[32];
  assert(request(mount, 0x10, 0xfe, nullptr, 0, out) == 8);
  assert(out[5] == 5 && out[6] == 24);
  assert(request(mount, 0x11, 1, nullptr, 0, out) == 9);
  assert(AuxSimulator::read24(out + 5) == 1398101);
  uint8_t rate = 9;
  assert(request(mount, 0x10, 0x24, &rate, 1, out) == 7);
  mount.tick(.5);
  assert(AuxSimulator::count(mount.position[0]) > 69000);
  rate = 0;
  request(mount, 0x10, 0x24, &rate, 1, out);
  double stopped = mount.position[0]; mount.tick(.5);
  assert(mount.position[0] == stopped);
  uint8_t target[3] = {0, 0, 1};
  request(mount, 0x10, 0x02, target, 3, out);
  request(mount, 0x10, 0x13, nullptr, 0, out); assert(out[5] == 0);
  mount.tick(.9);
  request(mount, 0x10, 0x13, nullptr, 0, out); assert(out[5] == 0xff);
  assert(AuxSimulator::count(mount.position[0]) == 1);
  rate = 9; request(mount, 0x11, 0x25, &rate, 1, out);
  mount.stop(); assert(mount.speed[1] == 0 && !mount.movingTo[1]);
  assert(request(mount, 0xbd, 0xfe, nullptr, 0, out) == 0);
  assert(request(mount, 0x10, 0x99, nullptr, 0, out) == 0);
  assert(AuxSimulator::count(-1) == 16777215);
  puts("PASS simulated versions, positions, rates, stop, GoTo, checksum and unsupported modules");
}
