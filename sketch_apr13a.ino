void setup() {
  // put your setup code here, to run once:
  
  // 1. Membuka jalur komunikasi ke laptop dengan kecepatan 115200
  Serial.begin(115200);
  
  // 2. Beri waktu 1 detik agar sistem siap
  delay(1000); 

  // 3. Cetak teks ini SEKALI saja saat ESP32 baru dinyalakan
  Serial.println("==========================================");
  Serial.println("BERHASIL! ESP32 Anda sudah hidup!");
  Serial.println("Proyek IoT Akuarium S2 - Tahap 1 OK.");
  Serial.println("==========================================");
}

void loop() {
  // put your main code here, to run repeatedly:
  
  // 4. Cetak teks ini BERULANG-ULANG selamanya
  Serial.println("Status: ESP32 Aktif. Menunggu sensor dicolok...");
  
  // 5. Beri jeda 3 detik (3000 milidetik) sebelum mengulang
  delay(3000); 
}