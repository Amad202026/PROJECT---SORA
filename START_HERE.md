# Mulai dari sini - Sora 1.7

1. Ekstrak ZIP ke folder baru. Jangan campur dengan versi sebelumnya.
2. Jalankan **Setup Sora UI.bat**; tunggu pemasangan dependensi selesai.
3. Jalankan **Start Sora UI Demo.bat** untuk uji cepat, atau **Start Sora UI.bat** untuk interval normal.
4. Tekan Start session dan lakukan kalibrasi kepala/bahu dalam posisi referensi.
5. Buka **Agent activity** untuk melihat keputusan dan hasil pengamatan agen.

Notifikasi tetap berbahasa Inggris, dengan GIF asli, satu caption dan simbol
× (dismiss), ✓ (aksi sesuai pengingat), Ⅱ (snooze). Pengingat postur/jarak dapat
berubah menjadi satu tawaran istirahat jika belum ada pemulihan yang terlihat.
Klik dismiss tidak dianggap bukti bahwa postur atau kondisi sudah membaik.

Automatic meeting detection ada di Settings dan awalnya mati. Ini perkiraan
rapat dari penggunaan mikrofon, bukan membaca percakapan. Override tersedia di
Agent activity. Experimental straw assist juga awalnya mati; uji dahulu karena
garis lain bisa salah dianggap sedotan. Tombol I drank dan Undo tetap tersedia.

Normal: postur 20 menit; air 1 jam; gerak 1 jam; jeda layar 2 jam; batas sesi
24 jam; warm-up isyarat kantuk 3 jam. Semua itu pengaturan produk, bukan resep
medis. Demo memperpendek waktu dan ditandai di tampilan. Timer sesi menghitung
kehadiran yang teramati, tidak menyimpulkan berapa lama kamu benar-benar terjaga.

## Isi paket penting
- README.md: perilaku dan batas sistem.
- VALIDATION.md: hasil pengujian yang benar-benar dijalankan.
- evaluation/: skenario, jejak agen dan panduan uji video nyata.
- cloud/: paket AWS yang siap dipasang, belum deployment aktif.
- submission/technical_report.pdf: laporan teknis Inggris.
- submission/architecture.svg: diagram arsitektur.
- submission/DEVPOST.md: draft Project Story dan testing instructions.
- submission/DEMO_SCRIPT.md: alur rekaman tim + demo 4 menit 30 detik.
- submission/FINAL_TEAM_STEPS_ID.md: bantuan tim yang diperlukan terakhir.

**Belum boleh dianggap selesai submit:** akun/deployment AWS, pengujian kamera
nyata, dan rekaman/unggahan tim harus diselesaikan dengan data serta akun asli.
Jangan kirim credential ke chat. Kamera tidak dinyalakan otomatis oleh paket ini.
