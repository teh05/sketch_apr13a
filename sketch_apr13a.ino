#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// --- KONFIGURASI ---
const char* ssid = "wifi-mamat"; 
const char* password = "naginata124568910"; 
const char* mqtt_server = "192.168.43.130"; 
const int mqtt_port = 1883;
const char* mqtt_topic = "s2/water/monitoring";

WiFiClient espClient;
PubSubClient client(espClient);

// --- PIN & SENSOR ---
const int pinSensorSuhu = 4;   
const int pinSensorPH   = 34;  
const int pinSensorTDS  = 35;  

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
OneWire oneWire(pinSensorSuhu);
DallasTemperature sensorSuhu(&oneWire);

float voltPH4 = 3.100; 
float voltPH9 = 2.730; 
unsigned long lastSend = 0; 

void setup_wifi() {
  delay(100);
  display.clearDisplay();
  display.setCursor(0,10); display.println("CONNECTING WIFI...");
  display.display();

  WiFi.begin(ssid, password);
  // Set daya WiFi ke minimum agar tidak menyedot banyak listrik di awal
  WiFi.setTxPower(WIFI_POWER_11dBm); 

  int counter = 0;
  while (WiFi.status() != WL_CONNECTED && counter < 20) {
    delay(500);
    Serial.print(".");
    counter++;
  }
  
  if(WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Terhubung!");
  } else {
    Serial.println("\nWiFi Gagal/Timeout!");
  }
}

void reconnect() {
  if (!client.connected()) {
    String clientId = "ESP32_S2_" + String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      client.setKeepAlive(30);
    }
  }
}

void setup() {
  Serial.begin(115200);
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) for(;;);
  
  display.clearDisplay();
  display.setTextSize(1);             
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 25); display.println("SYSTEM STARTING...");
  display.display();

  setup_wifi(); 
  client.setServer(mqtt_server, mqtt_port);
  sensorSuhu.begin();
  delay(1000); 
}

void loop() {
  // Hanya jalankan MQTT jika WiFi terhubung
  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) reconnect();
    client.loop();
  }

  unsigned long now = millis();
  if (now - lastSend > 5000) { 
    lastSend = now;

    // BACA SENSOR
    sensorSuhu.requestTemperatures(); 
    float suhuC = sensorSuhu.getTempCByIndex(0);
    int rawTDS = analogRead(pinSensorTDS);
    float vTDS = (rawTDS * 3.3) / 4095.0;
    float nTDS = (133.42 * pow(vTDS, 3) - 255.86 * pow(vTDS, 2) + 857.39 * vTDS) * 0.5;

    long pH_sum = 0;
    for(int i=0; i<10; i++) { pH_sum += analogRead(pinSensorPH); delay(5); }
    float vPH = ( (pH_sum/10.0) * 3.3) / 4095.0;
    float nPH = ((9.01 - 4.01) / (voltPH9 - voltPH4)) * (vPH - voltPH4) + 4.01;

    // UPDATE OLED
    display.clearDisplay();
    display.setCursor(0, 0);  display.println("--- MONITOR S2 ---");
    display.setCursor(0, 20); display.printf("Suhu : %.1f C", suhuC);
    display.setCursor(0, 35); display.printf("pH   : %.2f", nPH);
    display.setCursor(0, 50); display.printf("TDS  : %.0f ppm", nTDS);
    display.display();

    // KIRIM MQTT (Hanya jika terkoneksi)
    if (client.connected()) {
      String payload = "{\"suhu\":"+String(suhuC,1)+",\"ph\":"+String(nPH,2)+",\"tds\":"+String(nTDS,0)+"}";
      client.publish(mqtt_topic, payload.c_str());
    }
  }
}