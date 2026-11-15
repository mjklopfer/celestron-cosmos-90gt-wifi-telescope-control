// ESP32-only telescope simulator: captive setup, persistent Wi-Fi modes and AUX replies.
// No mount socket, AUX electrical transport or physical motor outputs are implemented.
// All service state is handled in loop(); recovery must remain reachable after failed joins.
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include "aux_simulator.h"
#include "portal_page.h"

const char *IDENTITY = "COSMOS-SIM-AMW007-0.2.2.0, ESP32 simulator";
const char *AP_PASSWORD = "cosmossetup"; // Bench setup hotspot; no router credentials in source.
WebServer web(80);
DNSServer dns;
Preferences settings;
WiFiServer dataServer(2000), managementServer(3000);
WiFiClient control, manager;
WiFiUDP udp;
AuxSimulator mount;
String apName, savedSSID, savedPassword, serialLine, managementLine, formToken;
String savedMode = "station";
String recoveryReason;
bool recoveryBoot = false;
uint8_t frame[64];
size_t frameUsed = 0;
bool setupAP = false, wasConnected = false, listeners = false, storageOK = false;
bool hadControl = false;
bool scanRequested = false;
uint32_t connectStarted = 0, restartAt = 0, lastTick = 0, lastAdvert = 0;
uint32_t lastControl = 0, lastManager = 0, lastReconnect = 0, packets = 0, unknown = 0;

// Choose the current app-facing IP for status and management replies.
IPAddress activeAddress() {
  return WiFi.status() == WL_CONNECTED ? WiFi.localIP() : WiFi.softAPIP();
}

// Escape configuration text before inserting it into the setup page.
String html(const String &value) {
  String escaped = value;
  escaped.replace("&", "&amp;"); escaped.replace("<", "&lt;");
  escaped.replace(">", "&gt;"); escaped.replace("\"", "&quot;");
  escaped.replace("'", "&#39;"); return escaped;
}

// Report connection and virtual encoder state without printing router credentials.
void printStatus() {
  Serial.printf("STATUS simulator=1 wifi=%d ip=%s setup_ap=%d clients=%d packets=%lu unknown=%lu az=%lu alt=%lu\n",
    (int)WiFi.status(), WiFi.localIP().toString().c_str(), setupAP ? 1 : 0,
    control && control.connected() ? 1 : 0, (unsigned long)packets,
    (unsigned long)unknown, (unsigned long)AuxSimulator::count(mount.position[0]),
    (unsigned long)AuxSimulator::count(mount.position[1]));
  Serial.printf("NETWORK mode=%s ap_ip=%s ap_clients=%d\n", savedMode.c_str(),
    WiFi.softAPIP().toString().c_str(), (int)WiFi.softAPgetStationNum());
}

// Create an explicitly addressed hotspot/DHCP service before binding the portal.
void startSetup() {
  if (setupAP) return;
  WiFi.mode(WIFI_AP_STA);
  WiFi.setSleep(false);
  IPAddress address = savedMode == "hotspot" ? IPAddress(1, 2, 3, 4) : IPAddress(192, 168, 4, 1);
  bool configured = WiFi.softAPConfig(address, address, IPAddress(255, 255, 255, 0));
  if (!configured || !WiFi.softAP(apName.c_str(), AP_PASSWORD, 1, false, 4)) {
    Serial.println("ERROR setup hotspot failed"); return;
  }
  setupAP = true;
  dns.start(53, "*", WiFi.softAPIP());
  web.begin(); // Rebind only after the AP interface and DHCP server exist.
  Serial.printf("SETUP ssid=%s password=%s url=http://%s/\n", apName.c_str(),
    AP_PASSWORD, WiFi.softAPIP().toString().c_str());
}

// Serve mode selection, scan controls and any persistent connection-failure warning.
void portal() {
  String page = "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>COSMOS telescope simulator</title><style>body{font:18px system-ui;max-width:650px;"
    "margin:30px auto;padding:20px;background:#16202b;color:white}input,button{font:inherit;"
    "padding:12px;box-sizing:border-box;width:100%;margin:8px 0}select{font:inherit;width:100%;padding:12px}"
    ".choice{display:block;margin:14px 0}.choice input{width:auto;margin-right:12px}"
    "[hidden]{display:none!important}.scanning{color:#ffcc66}small{color:#b9c9da}</style>"
    "<h1>COSMOS telescope simulator</h1><p>Version 0.2.2. Simulated telescope only. No physical motors are connected.</p>";
  if (recoveryReason.length()) {
    page += "<section role='alert' style='border:2px solid #ff9b87;padding:16px'>"
      "<h2>Wi-Fi connection failed</h2><p>" + html(recoveryReason) + "</p>"
      "<p>Your saved SSID is kept below for correction. Select a network and save to retry.</p></section>";
  }
  if (!storageOK) page += "<p role='alert'>Settings storage is unavailable. Configuration cannot be saved.</p>";
  page += "<p>Wi-Fi: " + String(WiFi.status() == WL_CONNECTED ? "connected" : "disconnected") +
    "<br>Infrastructure IP: <strong>" + WiFi.localIP().toString() + "</strong><br>SkySafari port: 2000</p>";
  page += "<p>Simulated azimuth: " + String(mount.position[0] * 360.0 / 16777216, 3) +
    "&deg;<br>Simulated altitude: " + String(mount.position[1] * 360.0 / 16777216, 3) + "&deg;</p>";
  if (setupAP && storageOK) {
    String form = FPSTR(CONFIG_FORM);
    form.replace("{{TOKEN}}", formToken);
    form.replace("{{SSID}}", html(savedSSID));
    form.replace("{{APNAME}}", apName);
    form.replace("{{HOTSPOT}}", savedMode == "hotspot" ? "checked" : "");
    form.replace("{{STATION}}", savedMode != "hotspot" ? "checked" : "");
    page += form;
  } else page += "<p>To change Wi-Fi, hold the board's BOOT button for 4 seconds, then release. "
    "This opens the setup hotspot and keeps existing settings until replaced.</p>";
  page += "<p><small>Local hotspot: SkySafari Celestron Wi-Fi / Direct Connect, 1.2.3.4:2000. "
    "Router network: Access Point mode using this ESP32's router-assigned IP. "
    "This is a simulated telescope, not a Wi-Fi relay.</small></p>";
  web.sendHeader("Cache-Control", "no-store");
  web.send(200, "text/html; charset=utf-8", page);
  Serial.println("HTTP portal served");
}

// Escape scanned SSIDs as JSON strings rather than executable page content.
String jsonText(const String &value) {
  String result = "\"";
  const char *digits = "0123456789abcdef";
  for (size_t i = 0; i < value.length(); ++i) {
    uint8_t c = value[i];
    if (c == '"' || c == '\\') { result += '\\'; result += (char)c; }
    else if (c < 32) { result += "\\u00"; result += digits[c >> 4]; result += digits[c & 15]; }
    else result += (char)c;
  }
  return result + "\"";
}

// Start or collect a bounded asynchronous scan; expose supported security metadata.
void scanNetworks() {
  if (!setupAP) { web.send(403, "text/plain", "Open the setup hotspot to scan."); return; }
  web.sendHeader("Cache-Control", "no-store");
  if (web.hasArg("start") && !scanRequested) {
    WiFi.scanDelete();
    scanRequested = true;
    int state = WiFi.scanNetworks(true, true);
    if (state < -1) {
      scanRequested = false;
      web.send(503, "text/plain", "Could not start Wi-Fi scan."); return;
    }
    Serial.println("SCAN started");
  }
  int count = WiFi.scanComplete();
  if (!scanRequested || count == -1) {
    web.send(202, "application/json", "{\"scanning\":true}"); return;
  }
  if (count < 0) {
    scanRequested = false;
    web.send(503, "text/plain", "Wi-Fi scan failed. Try again."); return;
  }
  String result = "{\"networks\":[";
  int limit = count < 32 ? count : 32;
  for (int i = 0; i < limit; ++i) {
    int auth = (int)WiFi.encryptionType(i);
    const char *security = "Unsupported security";
    bool supported = false;
    if (auth == 0) { security = "Open"; supported = true; }
    else if (auth == 1) security = "WEP (unsupported)";
    else if (auth == 2) { security = "WPA Personal"; supported = true; }
    else if (auth == 3) { security = "WPA2 Personal"; supported = true; }
    else if (auth == 4) { security = "WPA/WPA2 Personal"; supported = true; }
    else if (auth == 5) security = "Enterprise (unsupported)";
    else if (auth == 6) security = "WPA3 (unsupported in this build)";
    else if (auth == 7) { security = "WPA2/WPA3 Personal (WPA2 compatible)"; supported = true; }
    if (i) result += ',';
    result += "{\"ssid\":" + jsonText(WiFi.SSID(i)) + ",\"rssi\":" + String(WiFi.RSSI(i)) +
      ",\"security\":" + jsonText(security) + ",\"supported\":" + (supported ? "true" : "false") +
      ",\"open\":" + (auth == 0 ? "true" : "false") + "}";
  }
  result += "]}";
  WiFi.scanDelete(); scanRequested = false;
  web.send(200, "application/json", result);
  Serial.printf("SCAN completed count=%d\n", count);
}

// Validate one configuration record, persist it and schedule reboot after responding.
void configure() {
  if (!setupAP || !storageOK || web.arg("token") != formToken) {
    web.send(403, "text/plain", "Setup is unavailable or this form has expired."); return;
  }
  String mode = web.arg("mode");
  if (mode != "hotspot" && mode != "station") {
    web.send(400, "text/plain", "Select a connection mode."); return;
  }
  String ssid = web.arg("ssid"), password = web.arg("password");
  bool valid = ssid.length() > 0 && ssid.length() <= 32 &&
    (password.length() == 0 || (password.length() >= 8 && password.length() <= 63));
  if (password.length() == 64) {
    valid = ssid.length() > 0 && ssid.length() <= 32;
    for (size_t i = 0; i < password.length(); ++i)
      if (!isxdigit((unsigned char)password[i])) valid = false;
  }
  for (size_t i = 0; i < ssid.length(); ++i) if (!ssid[i]) valid = false;
  for (size_t i = 0; i < password.length(); ++i) if (!password[i]) valid = false;
  if (mode == "hotspot") { ssid = ""; password = ""; valid = true; }
  if (!valid) {
    web.send(400, "text/plain", "Check SSID length and Wi-Fi password (8-63 characters, 64 hex digits, or empty)."); return;
  }
  // One versioned blob prevents mixing an old password with a newly written SSID.
  String blob = String("2\n") + mode + "\n" + ssid.length() + "\n" + ssid + password;
  if (settings.putString("config", blob) != blob.length()) {
    web.send(500, "text/plain", "Could not save settings; no reboot."); return;
  }
  if (settings.isKey("recovery") && !settings.remove("recovery")) {
    web.send(500, "text/plain", "Settings written, but recovery state could not be cleared. Please save again."); return;
  }
  String next = mode == "hotspot" ? "Join " + apName +
    " (password: cosmossetup). Open http://1.2.3.4/; use Direct Connect in SkySafari." :
    "Reconnect your phone to that router Wi-Fi. The simulator will join automatically. "
    "Its IP is printed on USB serial and shown by your router. If it cannot connect within 30 seconds, "
    "it reboots once into setup. Rejoin " + apName + " and open http://192.168.4.1/ to see the error and retry.";
  web.send(200, "text/html; charset=utf-8", "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<h1>Saved. Rebooting.</h1><p>" + next + "</p>");
  Serial.println("CONFIG_SAVED reboot pending; credentials not printed");
  restartAt = millis() + 1000;
}

// Release the single app client and stop all in-memory motion.
void closeControl() {
  control.stop(); hadControl = false; frameUsed = 0; mount.stop();
  Serial.println("CLIENT_DISCONNECTED simulated movement stopped");
}

// Persist a failure marker and reboot once into setup; avoid an endless join loop.
void recoverConnection() {
  recoveryReason = "The previous Wi-Fi configuration could not connect within 30 seconds. Please try again.";
  recoveryBoot = true;
  closeControl();
  // The durable marker makes the next boot stay in setup rather than retry/reboot forever.
  if (storageOK && settings.putString("recovery", recoveryReason) == recoveryReason.length()) {
    Serial.println("WIFI_TIMEOUT recovery saved; rebooting once into captive portal");
    restartAt = millis() + 250;
  } else {
    Serial.println("ERROR recovery marker write failed; opening portal without reboot");
    startSetup(); // Remain reachable even if flash storage is faulty.
  }
}

// Reassemble bounded AUX frames, validate checksums, echo and answer virtual commands.
void receiveByte(uint8_t byte) {
  if (!frameUsed && byte != 0x3b) return;
  frame[frameUsed++] = byte;
  if (frameUsed == 2 && (frame[1] < 3 || frame[1] > 32)) { frameUsed = 0; return; }
  if (frameUsed >= 2 && frameUsed == frame[1] + 3u) {
    uint8_t sum = 0;
    for (size_t i = 1; i < frameUsed; ++i) sum += frame[i];
    if (sum == 0) {
      ++packets;
      control.write(frame, frameUsed); // Match the AUX bus echo seen on the real adapter.
      uint8_t response[16];
      size_t length = mount.reply(frame, frameUsed, response);
      if (length) control.write(response, length);
      else {
        ++unknown;
        Serial.printf("UNSUPPORTED destination=%02x command=%02x length=%u\n",
          frame[3], frame[4], (unsigned int)(frameUsed - 6));
      }
    } else Serial.println("BAD_CHECKSUM");
    frameUsed = 0;
  }
}

// Handle limited read-only module-style management; no provisioning writes here.
void serviceManagement() {
  WiFiClient incoming = managementServer.available();
  if (incoming) {
    if (manager && manager.connected()) incoming.stop();
    else { manager = incoming; managementLine = ""; lastManager = millis(); }
  }
  int budget = 256;
  while (manager && manager.available() && budget-- > 0) {
    char c = manager.read(); lastManager = millis();
    if (c == '\n') {
      managementLine.trim();
      String reply = "ERR simulator read-only management";
      if (managementLine == "version") reply = IDENTITY;
      else if (managementLine == "get wifi.mode") reply = savedMode == "hotspot" ? "2" : "1";
      else if (managementLine == "get wlan.dhcp.enabled") reply = "1";
      else if (managementLine == "get wlan.static.ip") reply = activeAddress().toString();
      else if (managementLine == "get softap.ssid") reply = apName;
      else if (managementLine == "get all") reply = "wifi.mode: " + String(savedMode == "hotspot" ? "2" : "1") +
        "\r\nwlan.dhcp.enabled: 1\r\nwlan.static.ip: " + activeAddress().toString();
      else if (managementLine == "exit") { manager.stop(); managementLine = ""; break; }
      manager.print(reply + "\r\n> "); managementLine = "";
    } else if (managementLine.length() < 255) managementLine += c;
    else { manager.stop(); managementLine = ""; break; }
  }
  if (manager && millis() - lastManager > 10000) manager.stop();
}

// Initialize network/storage services and choose saved connection or recovery setup.
void setup() {
  Serial.begin(115200);
  pinMode(0, INPUT_PULLUP);
  WiFi.persistent(false); WiFi.setAutoReconnect(false);
  WiFi.mode(WIFI_STA); WiFi.disconnect(false); WiFi.setSleep(false);
  WiFi.setMinSecurity(WIFI_AUTH_WPA_PSK); // Permit selected legacy WPA as well as stronger Personal modes.
  String mac = WiFi.macAddress(); mac.replace(":", "");
  apName = "Celestron-" + mac.substring(6);
  WiFi.setHostname(apName.c_str());
  formToken = String(esp_random(), HEX) + String(esp_random(), HEX);
  storageOK = settings.begin("cosmos-sim", false);
  if (storageOK) {
    recoveryReason = settings.getString("recovery", "");
    recoveryBoot = recoveryReason.length() > 0;
    String blob = settings.getString("config", "");
    if (blob.startsWith("2\n")) {
      int modeEnd = blob.indexOf('\n', 2);
      if (modeEnd > 2) {
        String mode = blob.substring(2, modeEnd);
        if (mode == "hotspot" || mode == "station") {
          savedMode = mode;
          blob = "1\n" + blob.substring(modeEnd + 1);
        }
      }
    }
    int separator = blob.indexOf('\n', 2);
    if (blob.startsWith("1\n") && separator > 2) {
      int length = blob.substring(2, separator).toInt();
      if (length > 0 && length <= 32 && blob.length() >= (size_t)(separator + 1 + length)) {
        savedSSID = blob.substring(separator + 1, separator + 1 + length);
        savedPassword = blob.substring(separator + 1 + length);
      }
    }
  }
  web.on("/", HTTP_GET, portal);
  web.on("/configure", HTTP_POST, configure);
  web.on("/scan", HTTP_GET, scanNetworks);
  web.onNotFound(portal);
  Serial.println("BOOT COSMOS ESP32 sham telescope v0.2.2 -- no physical telescope connection");
  if (recoveryBoot) Serial.println("RECOVERY_BOOT staying in setup until configuration is corrected");
  if (!recoveryBoot && savedMode != "hotspot" && savedSSID.length()) {
    WiFi.begin(savedSSID.c_str(), savedPassword.c_str());
    connectStarted = millis(); lastReconnect = millis();
    Serial.println("JOIN_SAVED_NETWORK");
  } else startSetup();
  lastTick = millis(); printStatus();
}

// Service networking, recovery deadlines and simulated motion without an AUX interface.
void loop() {
  uint32_t now = millis();
  mount.tick((now - lastTick) / 1000.0); lastTick = now;
  web.handleClient();
  if (setupAP) dns.processNextRequest();
  if (restartAt && (int32_t)(now - restartAt) >= 0) ESP.restart();
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !wasConnected) {
    Serial.printf("WIFI_CONNECTED simulator_ip=%s port=2000\n", WiFi.localIP().toString().c_str());
    if (setupAP) { dns.stop(); WiFi.softAPdisconnect(true); WiFi.mode(WIFI_STA); setupAP = false; }
    // Mode/interface changes can invalidate sockets on older networking cores.
    dataServer.end(); managementServer.end(); udp.stop(); listeners = false;
    web.begin();
  } else if (!connected && wasConnected) {
    closeControl(); manager.stop(); udp.stop();
    dataServer.end(); managementServer.end(); listeners = false;
    connectStarted = now;
    Serial.println("WIFI_LOST; settings retained");
  }
  wasConnected = connected;
  if (!connected && !recoveryBoot && !restartAt && savedMode != "hotspot" &&
      savedSSID.length() && now - connectStarted > 30000) recoverConnection();
  if (!connected && !recoveryBoot && savedMode != "hotspot" && savedSSID.length() && now - lastReconnect > 10000) {
    lastReconnect = now; WiFi.reconnect();
  }
  static uint32_t buttonAt = 0;
  static bool buttonHandled = false;
  if (!digitalRead(0)) {
    if (!buttonAt) buttonAt = now;
    if (!buttonHandled && now - buttonAt > 4000) { startSetup(); buttonHandled = true; }
  } else { buttonAt = 0; buttonHandled = false; }
  int budget = 128;
  while (Serial.available() && budget-- > 0) {
    char c = Serial.read();
    if (c == '\n') {
      serialLine.trim();
      if (serialLine == "STATUS") printStatus();
      else if (serialLine == "SETUP") startSetup();
      else if (serialLine == "RESET_WIFI") {
        if (storageOK && settings.clear()) { Serial.println("WIFI_SETTINGS_CLEARED"); restartAt = now + 200; }
      }
      else if (serialLine == "REBOOT") restartAt = now + 200;
      serialLine = "";
    } else if (serialLine.length() < 80) serialLine += c;
  }
  bool reachable = connected || setupAP;
  if (reachable && !listeners) {
    dataServer.begin(); managementServer.begin(); udp.begin(55555);
    listeners = true; lastAdvert = now - 1000;
    Serial.printf("SIMULATOR_LISTENING ip=%s tcp=2000,3000\n", activeAddress().toString().c_str());
  }
  if (reachable && listeners) {
    if (now - lastAdvert >= 1000) {
      lastAdvert = now;
      IPAddress address = activeAddress();
      IPAddress mask = connected ? WiFi.subnetMask() : IPAddress(255, 255, 255, 0), broadcast;
      for (int i = 0; i < 4; ++i) broadcast[i] = address[i] | ~mask[i];
      String advert = "{\"mac\":\"" + WiFi.macAddress() + "\",\"version\":\"" + IDENTITY + "\"}";
      udp.beginPacket(broadcast, 55555); udp.write((const uint8_t *)advert.c_str(), advert.length()); udp.endPacket();
    }
    WiFiClient incoming = dataServer.available();
    if (incoming) {
      if (control && control.connected()) incoming.stop();
      else {
        mount.stop(); frameUsed = 0; control = incoming; hadControl = true; control.setNoDelay(true);
        lastControl = now; Serial.println("CLIENT_CONNECTED simulated AUX only");
      }
    }
    budget = 256;
    while (control && control.available() && budget-- > 0) {
      lastControl = now; receiveByte(control.read());
    }
    if (hadControl && (!control.connected() || now - lastControl > 15000)) closeControl();
    serviceManagement();
  }
  delay(2);
}
