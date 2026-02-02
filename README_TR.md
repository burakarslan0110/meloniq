<div align="center">
  <img src="assets/logo.png" alt="Meloniq Logo" width="128" height="128">
</div>

# Meloniq - Müzik Analiz Aracı

Meloniq, müzik analizi yapmak için geliştirilmiş güçlü bir masaüstü uygulamasıdır. Çeşitli ses kaynaklarından ton tespiti, BPM tahmini ve ölçü analizi sağlar.

![Meloniq Ekran Görüntüsü](assets/screenshot.png)

[English Documentation](README.md)

## Özellikler

-   **Çoklu Kaynak Analizi**:
    -   📁 **Dosya**: Sürükle-bırak ile ses dosyalarını (MP3, WAV, FLAC vb.) analiz edin.
    -   ▶️ **YouTube**: YouTube linklerinden direkt indirme ve analiz (Playlist ve Radyo linkleri filtrelenir).
    -   🔊 **Sistem Sesi**: Bilgisayarın dahili sesini kaydedip analiz edin (Loopback).
    -   🎤 **Mikrofon**: Harici ses kaynaklarını kaydedip analiz edin.
-   **Gelişmiş Analiz**:
    -   Global BPM (Tempo) tahmini.
    -   Ton (Key) tespiti (Major/Minor).
    -   Ölçü (Meter) tahmini.
-   **Kullanıcı Arayüzü**:
    -   Modern ve sade PyQt6 arayüzü.
    -   Çift Dil Desteği (Türkçe / İngilizce).
    -   Gerçek zamanlı görselleştirmeler.

## Kurulum

### Kaynak Koddan Çalıştırma

1.  **Depoyu klonlayın**:
    ```bash
    git clone https://github.com/burakarslan0110/meloniq.git
    cd meloniq
    ```

2.  **Başlatma Scriptini Çalıştırın**:
    `start_meloniq.bat` dosyasına çift tıklayın veya komut satırından çalıştırın:
    ```cmd
    start_meloniq.bat
    ```
    *Bu dosya sanal ortamı (venv) otomatik oluşturur, kütüphaneleri yükler ve projeyi başlatır.*

### Hazır Kurulum (EXE)

[`Meloniq_Setup.exe`](https://github.com/burakarslan0110/meloniq/releases/latest) dosyasını kullanarak kurulum yapabilirsiniz.

## Gereksinimler

-   Python 3.8+
-   FFmpeg
-   İnternet bağlantısı (YouTube modülü için)

## Lisans

MIT Lisansı. Detaylar için LICENSE dosyasına bakın.
