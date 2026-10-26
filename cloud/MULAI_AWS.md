# AWS untuk SORA: mulai dari akun baru

Status: kode disiapkan. Belum ada deployment AWS atau hasil uji cloud asli.

## 1. Buat akun sendiri

Buka https://aws.amazon.com/free/ lalu pilih Create account.
Pilih Free plan jika tersedia dan kamu memenuhi syarat. Ikuti verifikasi yang muncul;
metode pembayaran/telepon dapat diminta sesuai jalur pendaftaran. Jangan kirim
password, OTP, kartu, access key, atau session token ke chat atau repositori.
Selesaikan aktivasi dan pastikan bisa masuk AWS Console. Jika ditawarkan upgrade
berbayar, jangan menganggapnya wajib untuk SORA; periksa akses layanan terlebih dulu.

SORA menggunakan Lambda, CloudFormation, IAM, dan CloudWatch Logs. Kamera tetap lokal.
Tidak memerlukan EC2, GPU, Bedrock, API Gateway, database, atau endpoint publik.
Paket gratis/kredit mengikuti ketentuan akun; pada paket berbayar penggunaan dapat
menimbulkan biaya. Jangan beralih paket hanya untuk mengikuti tutorial.

## 2. Setelah akun aktif: login dari Windows

Pasang AWS CLI v2 dari panduan resmi:
https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
Versi minimal untuk browser login: 2.32.0. Tutup dan buka PowerShell setelah instalasi.
Gunakan identitas development yang mempunyai izin deployment; jangan buat root access key.
IAM user/role memerlukan SignInLocalDevelopmentAccess untuk browser login.
IAM Identity Center menggunakan aws configure sso, bukan alur login di bawah.

Jalankan dari folder PROJECT 2 - SORA:

```powershell
.\.venv\Scripts\python.exe -m pip install -r cloud\requirements.txt
aws --version
aws login --profile sora --region ap-southeast-1
.\.venv\Scripts\python.exe cloud\deploy.py identity --profile sora --region ap-southeast-1
```

Browser akan meminta login/otorisasi. Isi sendiri. Kredensial sementara disimpan
oleh AWS di profil lokal, tidak di kode aplikasi. Paket awscrt diperlukan agar
Boto3 bisa membaca browser-login profile.

## 3. Deployment setelah akun dan izin benar

Lihat cloud/template.json. Deployment membuat satu Lambda 128 MB / timeout 3 detik,
satu execution role dengan izin menulis log fungsi itu saja, serta log group dengan
retensi 7 hari. Identitas deployment perlu CloudFormation, Lambda, IAM create/pass role,
dan CloudWatch Logs. Identitas runtime cukup lambda:InvokeFunction untuk fungsi SORA.

Ganti ACCOUNT_ID dengan nomor akun yang ditampilkan perintah identity:

```powershell
.\.venv\Scripts\python.exe cloud\deploy.py deploy --profile sora --account ACCOUNT_ID --region ap-southeast-1
```

Delapan pemanggilan Lambda nyata memeriksa pengingat awal, menunggu, tawaran jeda,
batas eskalasi, quiet mode, meeting, data visual hilang, dan resolved.
Jika semuanya berhasil, script menulis cloud/deployment_receipt.json dan mengaktifkan
cloud_config.json. Receipt berisi request ID, respons, dan waktu panggilan. Data uji
sintetis ini bukan pengukuran akurasi kamera. Jangan sertakan profil AWS atau kredensial
dalam arsip submission. ARN/receipt juga mengandung nomor akun; tinjau sebelum publikasi.

## 4. Bukti integrasi aplikasi

Tutup SORA sepenuhnya, lalu buka Start Sora UI Demo.bat. Kalibrasi dan jalankan sesi.
Saat pengingat postur muncul otomatis, buka Agent activity. Pastikan sumber keputusan
adalah aws dan status AWS policy connected. Unduh trace. Rekam perubahan postur,
pengingat, eskalasi bila posisi tetap rendah, dan pemulihan saat kembali ke referensi.
Beri label Demo mode - shortened reminder interval.

Tes gangguan koneksi setelah koneksi AWS berhasil. Observasi baru yang memerlukan
keputusan cloud harus beralih ke local_fallback bila AWS gagal, tanpa menghentikan kamera.
Jangan mengklaim uji ini selesai sebelum benar-benar direkam/dijalankan.

## 5. Setelah penjurian

Hapus hanya stack SORA yang sudah ditinjau:

```powershell
.\.venv\Scripts\python.exe cloud\deploy.py delete --profile sora --account ACCOUNT_ID --region ap-southeast-1
```

Script mengembalikan konfigurasi ke mode lokal. Restart SORA setelah perubahan mode.

## Bahan narasi arsitektur (finalkan setelah deployment diverifikasi)

Kamera -> OpenCV 5 dan indikator visual lokal -> ringkasan kondisi + tahap tujuan
-> AWS Lambda memilih tindakan -> desktop menampilkan CAMY -> observasi ulang.

AWS menerima goal, stage, serta lima boolean; tidak menerima gambar, audio, atau
landmark mentah. Agent adalah kebijakan deterministik, bukan LLM. Human controls
dan pemeriksaan bukti tetap diterapkan lokal. CloudWatch hanya mencatat tindakan.
Jangan menyebut memakai Bedrock, COOL, atau LLM jika komponen itu tidak digunakan.

Referensi resmi:
- https://aws.amazon.com/free/
- https://aws.amazon.com/resources/create-account/
- https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html
- https://docs.aws.amazon.com/sdkref/latest/guide/feature-login-credentials.html
