#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Deklarasi layar OLED. Angka -1 berarti OLED ini tidak memiliki pin Reset khusus.
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

void setup() {
  Serial.begin(115200);
  
  // Beri waktu 2 detik agar ESP32 dan OLED siap menerima daya sepenuhnya
  delay(2000); 
  
  Serial.println("\n==================================");
  Serial.println("Memulai Tes Layar OLED...");

  // MENGUJI ALAMAT 0x3C
  Serial.println("Mencoba koneksi di alamat 0x3C...");
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("GAGAL di 0x3C!");
    
    // MENGUJI ALAMAT 0x3D JIKA 0x3C GAGAL
    Serial.println("Mencoba koneksi di alamat 0x3D...");
    if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println("GAGAL TOTAL! Layar tidak ditemukan di 0x3C maupun 0x3D.");
      Serial.println("SOLUSI: 1. Cek apakah kabel SDA & SCL terbalik.");
      Serial.println("        2. Cek apakah kabel kendor di expansion board.");
      for(;;); // Berhenti di sini selamanya (program freeze)
    } else {
      Serial.println("BERHASIL! Layar Anda menggunakan alamat 0x3D.");
    }
  } else {
    Serial.println("BERHASIL! Layar Anda menggunakan alamat 0x3C.");
  }

  // Jika berhasil melewati cek di atas, jalankan ini:
  Serial.println("Mengirim gambar ke layar...");
  
  display.clearDisplay();
  display.setTextSize(1);             
  display.setTextColor(SSD1306_WHITE);

  // Membuat kotak di sekeliling layar
  display.drawRect(0, 0, 128, 64, SSD1306_WHITE);

  // Menulis teks di dalam kotak
  display.setCursor(10, 15);            
  display.println("TEST OLED SUKSES!");
  
  display.setCursor(10, 35);            
  display.println("Sistem S2 Berjalan");

  display.display(); 
  Serial.println("Selesai. Layar harusnya menyala sekarang.");
  Serial.println("==================================");
}

void loop() {
  // Tidak ada yang diulang, biarkan teks tetap di layar.
}