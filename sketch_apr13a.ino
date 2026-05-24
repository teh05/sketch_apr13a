#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "mbedtls/sha256.h"

// ===================== KONFIGURASI =====================
const char* ssid         = "wifi-mamat";
const char* password     = "naginata124568910";
const char* mqtt_server  = "192.168.43.130";
const int   mqtt_port    = 1883;
const char* mqtt_topic   = "s2/water/monitoring";
const char* device_id    = "ESP32_S2_TILAPIA";
const char* payload_secret = "tilapia_iot_s2_key";

WiFiClient   espClient;
PubSubClient client(espClient);

// ===================== PIN & SENSOR =====================
const int pinSensorSuhu = 4;
const int pinSensorPH   = 34;
const int pinSensorTDS  = 35;
const int pinBuzzer      = 27;
const int pinLedSafe     = 25;
const int pinLedDanger   = 26;

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
OneWire oneWire(pinSensorSuhu);
DallasTemperature sensorSuhu(&oneWire);

// ===================== KALIBRASI pH (2-Point, sensor 4502C) =====================
const int    PH_SAMPLES   = 20;
const float  PH_SLOPE     = -5.65;
const float  PH_INTERCEPT = 21.12;

// ===================== THRESHOLD NILA (selaras backend/thresholds.py) =====================
const float PH_IDEAL_LOW    = 6.5,  PH_IDEAL_HIGH    = 8.5;
const float PH_WARN_LOW     = 6.0,  PH_WARN_HIGH     = 9.0;
const float PH_DANGER_LOW   = 5.0,  PH_DANGER_HIGH   = 9.5;

const float TDS_IDEAL_LOW   = 100,  TDS_IDEAL_HIGH   = 400;
const float TDS_WARN_LOW    = 50,   TDS_WARN_HIGH    = 500;
const float TDS_DANGER_HIGH = 1000;

const float SUHU_IDEAL_LOW  = 26.0, SUHU_IDEAL_HIGH  = 30.0;
const float SUHU_WARN_LOW   = 22.0, SUHU_WARN_HIGH   = 33.0;
const float SUHU_DANGER_LOW = 20.0, SUHU_DANGER_HIGH = 35.0;

// ===================== BUZZER STATE =====================
bool buzzerActive = false;

// ===================== EDGE FILTER =====================
float lastSuhu = -999, lastPH = -999, lastTDS = -999;
const float DELTA_SUHU = 0.3;
const float DELTA_PH   = 0.05;
const float DELTA_TDS  = 5.0;

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 5000;

// ===================== HELPER: SHA256 =====================
String toHex(const uint8_t* data, size_t len) {
  String hex;
  hex.reserve(len * 2);
  for (size_t i = 0; i < len; i++) {
    if (data[i] < 0x10) hex += "0";
    hex += String(data[i], HEX);
  }
  return hex;
}

String sha256Hex(const String& input) {
  uint8_t hash[32];
  mbedtls_sha256_context ctx;
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts(&ctx, 0);
  mbedtls_sha256_update(&ctx, (const uint8_t*)input.c_str(), input.length());
  mbedtls_sha256_finish(&ctx, hash);
  mbedtls_sha256_free(&ctx);
  return toHex(hash, sizeof(hash));
}

// ===================== STATUS (mirror backend zone_for_value) =====================
// 0=ideal 1=warning 2=danger 3=critical
int zonePh(float ph) {
  if (ph >= PH_IDEAL_LOW  && ph <= PH_IDEAL_HIGH)  return 0;
  if (ph >= PH_WARN_LOW   && ph <= PH_WARN_HIGH)   return 1;
  if (ph >= PH_DANGER_LOW && ph <= PH_DANGER_HIGH) return 2;
  return 3;
}

int zoneTds(float tds) {
  if (tds >= TDS_IDEAL_LOW && tds <= TDS_IDEAL_HIGH) return 0;
  if (tds >= TDS_WARN_LOW  && tds <= TDS_WARN_HIGH)  return 1;
  if (tds >= 0             && tds <= TDS_DANGER_HIGH) return 2;
  return 3;
}

int zoneSuhu(float suhu) {
  if (suhu >= SUHU_IDEAL_LOW  && suhu <= SUHU_IDEAL_HIGH)  return 0;
  if (suhu >= SUHU_WARN_LOW   && suhu <= SUHU_WARN_HIGH)   return 1;
  if (suhu >= SUHU_DANGER_LOW && suhu <= SUHU_DANGER_HIGH) return 2;
  return 3;
}

const char* classifyStatus(float suhu, float ph, float tds) {
  int worst = zonePh(ph);
  worst = max(worst, zoneTds(tds));
  worst = max(worst, zoneSuhu(suhu));
  switch (worst) {
    case 3: return "CRITICAL";
    case 2: return "DANGER";
    case 1: return "WARNING";
    default: return "SAFE";
  }
}

void updateBuzzer(bool isDanger) {
  if (isDanger) {
    if (!buzzerActive) {
      tone(pinBuzzer, 1000, 300);
      buzzerActive = true;
    }
  } else if (buzzerActive) {
    noTone(pinBuzzer);
    digitalWrite(pinBuzzer, LOW);
    buzzerActive = false;
  }
}

bool significantChange(float suhu, float ph, float tds) {
  if (lastSuhu < -900) return true;
  return (abs(suhu - lastSuhu) >= DELTA_SUHU ||
          abs(ph   - lastPH)   >= DELTA_PH   ||
          abs(tds  - lastTDS)  >= DELTA_TDS);
}

// ===================== WIFI =====================
void setup_wifi() {
  display.clearDisplay();
  display.setCursor(0, 10);
  display.println("CONNECTING WIFI...");
  display.display();

  WiFi.begin(ssid, password);
  WiFi.setTxPower(WIFI_POWER_11dBm);

  int counter = 0;
  while (WiFi.status() != WL_CONNECTED && counter < 20) {
    delay(500);
    Serial.print(".");
    counter++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi Failed/Timeout!");
  }
}

void checkWifiSecurity() {
  int n = WiFi.scanNetworks(false, true);
  String connected = WiFi.SSID();
  wifi_auth_mode_t mode = WIFI_AUTH_OPEN;

  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == connected) {
      mode = WiFi.encryptionType(i);
      break;
    }
  }

  Serial.print("[SEC] WiFi encryption: ");
  switch (mode) {
    case WIFI_AUTH_OPEN:         Serial.println("OPEN (INSECURE!)"); break;
    case WIFI_AUTH_WEP:          Serial.println("WEP (WEAK)");       break;
    case WIFI_AUTH_WPA_PSK:      Serial.println("WPA-PSK");          break;
    case WIFI_AUTH_WPA2_PSK:     Serial.println("WPA2-PSK (OK)");    break;
    case WIFI_AUTH_WPA_WPA2_PSK: Serial.println("WPA/WPA2-PSK");     break;
    default:                     Serial.println("OTHER");            break;
  }
}

// ===================== MQTT =====================
void reconnect() {
  if (!client.connected()) {
    String clientId = String(device_id) + "_" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      client.setKeepAlive(30);
      Serial.println("[MQTT] Connected");
    }
  }
}

// ===================== SETUP =====================
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);

  pinMode(pinBuzzer,    OUTPUT);
  pinMode(pinLedSafe,   OUTPUT);
  pinMode(pinLedDanger, OUTPUT);
  digitalWrite(pinBuzzer,    LOW);
  digitalWrite(pinLedSafe,   LOW);
  digitalWrite(pinLedDanger, LOW);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[ERR] OLED init failed");
    for (;;);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 25);
  display.println("SYSTEM STARTING...");
  display.display();

  setup_wifi();
  checkWifiSecurity();

  client.setServer(mqtt_server, mqtt_port);
  sensorSuhu.begin();

  Serial.print("[SYS] Free Heap: ");
  Serial.println(ESP.getFreeHeap());

  delay(1000);
}

// ===================== LOOP =====================
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) reconnect();
    client.loop();
  }

  unsigned long now = millis();
  if (now - lastSend < SEND_INTERVAL) return;
  lastSend = now;

  // --- READ SENSORS ---
  sensorSuhu.requestTemperatures();
  float suhuC = sensorSuhu.getTempCByIndex(0);

  int rawTDS = analogRead(pinSensorTDS);
  float vTDS = (rawTDS * 3.3) / 4095.0;
  float nTDS = (133.42 * pow(vTDS, 3) - 255.86 * pow(vTDS, 2) + 857.39 * vTDS) * 0.5;

  long pH_sum = 0;
  for (int i = 0; i < PH_SAMPLES; i++) {
    pH_sum += analogRead(pinSensorPH);
    delay(10);
  }
  float vPH = (pH_sum / (float)PH_SAMPLES) * (3.3 / 4095.0);
  float nPH = (PH_SLOPE * vPH) + PH_INTERCEPT;

  // --- CLASSIFY ---
  const char* status = classifyStatus(suhuC, nPH, nTDS);
  bool isDanger = (strcmp(status, "DANGER") == 0 || strcmp(status, "CRITICAL") == 0);

  // --- ACTUATORS ---
  digitalWrite(pinLedSafe,   isDanger ? LOW  : HIGH);
  digitalWrite(pinLedDanger,  isDanger ? HIGH : LOW);
  updateBuzzer(isDanger);

  // --- OLED DISPLAY ---
  display.clearDisplay();
  display.setCursor(0, 0);
  display.print("-- TILAPIA S2 [");
  display.print(status);
  display.println("]");
  display.setCursor(0, 14);
  display.printf("Suhu : %.1f C", suhuC);
  display.setCursor(0, 27);
  display.printf("pH   : %.2f", nPH);
  display.setCursor(0, 40);
  display.printf("TDS  : %.0f ppm", nTDS);

  if (isDanger) {
    display.setCursor(0, 54);
    display.println("!! GANTI AIR !!");
  }
  display.display();

  // --- EDGE FILTER: only send if delta significant ---
  if (!significantChange(suhuC, nPH, nTDS)) {
    Serial.println("[EDGE] No significant change, skipping MQTT publish");
    return;
  }
  lastSuhu = suhuC;
  lastPH   = nPH;
  lastTDS  = nTDS;

  // --- BUILD PAYLOAD WITH SIGNATURE ---
  String payload = "{\"suhu\":" + String(suhuC, 1)
                 + ",\"ph\":"  + String(nPH, 2)
                 + ",\"tds\":" + String(nTDS, 0)
                 + ",\"status\":\"" + String(status) + "\""
                 + ",\"device\":\"" + String(device_id) + "\""
                 + "}";

  String sigInput = String(suhuC, 1) + "|" + String(nPH, 2) + "|" + String(nTDS, 0) + "|" + String(payload_secret);
  String sig = sha256Hex(sigInput);

  String fullPayload = payload.substring(0, payload.length() - 1)
                     + ",\"sig\":\"" + sig + "\"}";

  // --- PUBLISH MQTT ---
  if (client.connected()) {
    client.publish(mqtt_topic, fullPayload.c_str());
    Serial.print("[MQTT] Sent: ");
    Serial.println(fullPayload);
  }

  Serial.print("[SYS] Heap: ");
  Serial.println(ESP.getFreeHeap());
}
