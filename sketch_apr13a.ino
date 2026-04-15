#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ================= 1. PENGATURAN PIN =================
const int pinSensorSuhu = 4;   // DS18B20 di Pin P4
const int pinTurbidity  = 32;  // Kekeruhan di Pin P32 (Via Resistor!)
const int pinSensorPH   = 34;  // pH Meter (PO) di Pin P34
const int pinSensorTDS  = 35;  // TDS di Pin P35

// ================= 2. PENGATURAN OLED =================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ================= 3. INISIALISASI SENSOR =================
OneWire oneWire(pinSensorSuhu);
DallasTemperature sensorSuhu(&oneWire);

void setup() {
  Serial.begin(115200);
  delay(2000); 
  
  Serial.println("\n--- Sistem S2: Memulai Semua Sensor ---");

  // Inisialisasi OLED (Menggunakan alamat 0x3C yang sudah sukses)
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("GAGAL! Layar OLED tidak merespons.");
    for(;;); 
  }
  
  display.clearDisplay();
  display.setTextSize(1);             
  display.setTextColor(SSD1306_WHITE);
  display.drawRect(0, 0, 128, 64, SSD1306_WHITE);
  display.setCursor(10, 25);            
  display.println("MEMUAT SEMUA SENSOR");
  display.display();

  // Menyalakan Sensor Suhu
  sensorSuhu.begin();
  delay(2000); 
}

void loop() {
  // ================= BACA SUHU & TDS =================
  sensorSuhu.requestTemperatures(); 
  float suhuC = sensorSuhu.getTempCByIndex(0);

  int nilaiAnalogTDS = analogRead(pinSensorTDS);
  float teganganTDS = (nilaiAnalogTDS * 3.3) / 4095.0;
  
  // Kompensasi Suhu untuk TDS
  float suhuKompensasi = (suhuC > 0 && suhuC < 80) ? suhuC : 25.0; 
  float koefisienKompensasi = 1.0 + 0.02 * (suhuKompensasi - 25.0);
  float teganganKompensasi = teganganTDS / koefisienKompensasi;
  float nilaiTDS = (133.42 * pow(teganganKompensasi, 3) - 255.86 * pow(teganganKompensasi, 2) + 857.39 * teganganKompensasi) * 0.5;
  if (nilaiTDS < 0 || nilaiAnalogTDS < 10) nilaiTDS = 0;

  // ================= BACA KEKERUHAN (TURBIDITY) =================
// ================= BACA KEKERUHAN (TURBIDITY) =================
  int nilaiAnalogKeruh = analogRead(pinTurbidity);
  float teganganPinKeruh = (nilaiAnalogKeruh * 3.3) / 4095.0;
  
  // Menggunakan pengali 2.0 karena pakai 2 resistor 4.7k
  float teganganAsliKeruh = teganganPinKeruh * 2.0; 
  
  float persentaseKekeruhan = 0;

  // Kalibrasi berdasarkan data Anda: 
  // Jika tegangan asli di atas 4.2V, itu air sangat bening (0%)
  // Jika tegangan asli di bawah 2.5V, itu mulai sangat keruh
  if(teganganAsliKeruh >= 4.20) {
    persentaseKekeruhan = 0;
  } else if (teganganAsliKeruh <= 2.50) {
    persentaseKekeruhan = 100;
  } else {
    // Memetakan sisa rentang antara 4.2V sampai 2.5V ke 0% sampai 100%
    persentaseKekeruhan = (4.20 - teganganAsliKeruh) / (4.20 - 2.50) * 100.0;
  }
  // ================= BACA SENSOR pH =================
  int nilaiAnalogPH = analogRead(pinSensorPH);
  float teganganPH = (nilaiAnalogPH * 3.3) / 4095.0;
  
  // ⚠️ GANTI RUMUS DI BAWAH INI JIKA SUDAH KALIBRASI!
  float nilaiPH = -5.70 * teganganPH + 21.34; 
  
  if(nilaiPH < 0) nilaiPH = 0;
  if(nilaiPH > 14) nilaiPH = 14;

  // ================= TAMPILKAN KE SERIAL MONITOR =================
  Serial.print("Suhu: "); Serial.print(suhuC); Serial.print("C | ");
  Serial.print("TDS: "); Serial.print((int)nilaiTDS); Serial.print("ppm | ");
  Serial.print("pH: "); Serial.print(nilaiPH, 2); Serial.print(" (Volt: "); Serial.print(teganganPH, 3); Serial.print(") | ");
  Serial.print("Keruh: "); Serial.print((int)persentaseKekeruhan); 
  Serial.print("% (Volt ESP: "); Serial.print(teganganPinKeruh, 2); 
  Serial.print("V, Asli: "); Serial.print(teganganAsliKeruh, 2); Serial.println("V)");

  // ================= TAMPILKAN KE LAYAR OLED =================
  display.clearDisplay();

  // Header
  display.setCursor(0, 0);
  display.println("--- MONITOR S2 ---");

  // Kolom Kiri
  display.setCursor(0, 16);
  display.print("Suhu : "); display.print(suhuC, 1); display.print(" C");
  
  display.setCursor(0, 28);
  display.print("pH   : "); display.print(nilaiPH, 1);

  // Kolom Kanan / Bawah
  display.setCursor(0, 40);
  display.print("TDS  : "); display.print((int)nilaiTDS); display.print(" ppm");

  display.setCursor(0, 52);
  display.print("Keruh: "); display.print((int)persentaseKekeruhan); display.print(" %");

  display.display();

  delay(2000); // Jeda 2 detik agar pembacaan stabil
}