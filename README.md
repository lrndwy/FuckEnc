# Script Enkripsi & Dekripsi File/Folder

Script Python untuk mengenkripsi dan dekripsi file serta folder dengan fitur untuk melihat daftar file yang terenkripsi.

## Instalasi

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Buat script executable (opsional):
```bash
chmod +x FuckEnc.py
```

## Fitur

- ✅ Enkripsi file tunggal
- ✅ Enkripsi folder (dengan opsi rekursif)
- ✅ Dekripsi file tunggal
- ✅ Dekripsi folder (dengan opsi rekursif)
- ✅ List semua file terenkripsi
- ✅ Enkripsi/dekripsi dari file list
- ✅ Progress bar dengan animasi yang smooth
- ✅ Secure delete (file original dihapus secara aman)
- ✅ Menggunakan AES encryption (Fernet) dengan PBKDF2 key derivation
- ✅ Tidak ada metadata file (lebih aman dan sulit ditebak)

## Penggunaan

### Enkripsi File
```bash
python FuckEnc.py encrypt -f file.txt -p password123
```

### Dekripsi File
```bash
python FuckEnc.py decrypt -f file.txt.encrypted -p password123
```

### Enkripsi Folder (Rekursif)
```bash
python FuckEnc.py encrypt -d /path/to/folder -p password123
```

### Enkripsi Folder (Non-Rekursif)
```bash
python FuckEnc.py encrypt -d /path/to/folder -p password123 --no-recursive
```

### Dekripsi Folder (Rekursif)
```bash
python FuckEnc.py decrypt -d /path/to/folder -p password123
```

### Enkripsi dari File List
```bash
python FuckEnc.py encrypt -l file_list.txt -p password123
```

### Dekripsi dari File List
```bash
python FuckEnc.py decrypt -l file_list.txt -p password123
```

### List File Terenkripsi (Current Directory)
```bash
python FuckEnc.py list
```

### List File Terenkripsi (Folder Tertentu)
```bash
python FuckEnc.py list -d /path/to/folder
```

### List File Terenkripsi (Non-Rekursif)
```bash
python FuckEnc.py list -d /path/to/folder --no-recursive
```

## Format File List

File list adalah file teks yang berisi daftar file atau folder yang akan dienkripsi/dekripsi, satu per baris:

```
testing/
file1.txt
folder2/
testing/documents/secret.txt
```

- Baris kosong dan baris yang dimulai dengan `#` akan diabaikan
- Path bisa relative atau absolute
- Folder akan diproses secara rekursif (semua file dan subfolder)

## Catatan Penting

1. **Password**: Simpan password dengan aman! Jika lupa password, file tidak bisa didekripsi.
2. **Backup**: Selalu backup file penting sebelum enkripsi.
3. **File Extension**: File terenkripsi akan memiliki extension `.encrypted`
4. **Tidak Ada Metadata**: Script tidak menyimpan metadata file untuk keamanan lebih baik. Salt disimpan di setiap file terenkripsi.
5. **Original Files**: File original akan dihapus secara aman (secure delete) setelah enkripsi berhasil
6. **Progress Bar**: Progress bar akan menampilkan animasi yang smooth dengan persentase real-time

## Contoh Output

### Progress Bar
```
⠋ 🔒 Enkripsi |████████████████████████░░░░░░░░░░░░░░░░░░░░| 15/20 (75.0%) [2.5 file/s] [ETA: 2s]
```

### List File Terenkripsi
```
📋 Daftar File Terenkripsi (3 file):
================================================================================

1. documents/secret.txt.encrypted
   Ukuran: 2.45 KB
   Path Asli: documents/secret.txt

2. photos/image.jpg.encrypted
   Ukuran: 1.23 MB
   Path Asli: photos/image.jpg

================================================================================
```

## Keamanan

- Menggunakan **Fernet** (symmetric encryption) dari library `cryptography`
- Key derivation menggunakan **PBKDF2** dengan 100,000 iterations
- Salt unik untuk setiap file (disimpan di file terenkripsi)
- File original dihapus secara aman dengan secure delete (3x overwrite)
- **Tidak ada metadata file** - lebih aman dan sulit ditebak
- Setiap file terenkripsi berdiri sendiri dengan salt unik

## Tips

- Gunakan password yang kuat dan unik
- Simpan password di tempat yang aman (password manager)
- Test dekripsi dengan file kecil sebelum mengenkripsi file penting
- Gunakan file list untuk memproses banyak file sekaligus
- Progress bar akan menampilkan animasi yang smooth untuk pengalaman yang lebih baik
