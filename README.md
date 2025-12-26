# FuckEnc

## Instalasi

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Buat script executable (opsional):
```bash
chmod +x FuckEnc
```

## Penggunaan

### Enkripsi File
```bash
./FuckEnc encrypt -f file.txt -p password123
```

### Dekripsi File
```bash
./FuckEnc decrypt -f file.txt.encrypted -p password123
```

### Enkripsi Folder (Rekursif)
```bash
./FuckEnc encrypt -d /path/to/folder -p password123
```

### Enkripsi Folder (Non-Rekursif)
```bash
./FuckEnc encrypt -d /path/to/folder -p password123 --no-recursive
```

### Dekripsi Folder (Rekursif)
```bash
./FuckEnc decrypt -d /path/to/folder -p password123
```

### Enkripsi dari File List
```bash
./FuckEnc encrypt -l file_list.txt -p password123
```

### Dekripsi dari File List
```bash
./FuckEnc decrypt -l file_list.txt -p password123
```

### List File Terenkripsi (Current Directory)
```bash
./FuckEnc list
```

### List File Terenkripsi (Folder Tertentu)
```bash
./FuckEnc list -d /path/to/folder
```

### List File Terenkripsi (Non-Rekursif)
```bash
./FuckEnc list -d /path/to/folder --no-recursive
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
