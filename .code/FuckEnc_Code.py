#!/usr/bin/env python3
"""
Script untuk mengenkripsi dan dekripsi folder dan file
Dengan fitur untuk melihat daftar file/folder yang terenkripsi
"""

import os
import sys
import hashlib
import base64
import time
import shutil
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import argparse

# Try to import tqdm for better progress bar, fallback to custom if not available
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class ProgressBar:
    """Custom progress bar jika tqdm tidak tersedia dengan animasi yang lebih satisfying"""
    def __init__(self, total: int, desc: str = "", unit: str = "file"):
        self.total = total
        self.current = 0
        self.desc = desc
        self.unit = unit
        self.start_time = time.time()
        self.last_update = 0
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
        self.animated_percent = 0.0  # Untuk animasi smooth
        self.is_animating = False  # Flag untuk menandai sedang animasi
        
    def update(self, n: int = 1):
        # Update current count
        old_current = self.current
        self.current += n
        
        # Animasikan progress bar secara bertahap untuk setiap file
        target_percent = (self.current / self.total * 100) if self.total > 0 else 0
        start_percent = (old_current / self.total * 100) if self.total > 0 else 0
        
        # Set flag animasi
        self.is_animating = True
        
        # Animasikan dari start_percent ke target_percent secara bertahap
        steps = 30  # Jumlah step animasi per file (lebih banyak untuk animasi lebih smooth)
        for step in range(steps + 1):
            # Interpolasi linear dengan easing
            progress = step / steps
            # Easing function untuk animasi lebih smooth
            eased = progress * progress * (3.0 - 2.0 * progress)  # Smoothstep
            current_percent = start_percent + (target_percent - start_percent) * eased
            self.animated_percent = current_percent
            self._display(force=True)  # Force display saat animasi
            time.sleep(0.03)  # Delay untuk setiap step animasi (lebih lama)
        
        # Reset flag
        self.is_animating = False
        
    def _display(self, force: bool = False):
        now = time.time()
        # Update lebih sering untuk animasi yang smooth (setiap 0.03 detik)
        # Tapi skip check jika sedang animasi (force=True)
        if not force and now - self.last_update < 0.03 and self.current < self.total:
            return
        self.last_update = now
        
        # Animasi spinner
        spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
        self.spinner_index += 1
        
        # Gunakan animated_percent yang sudah dihitung di update()
        # Tidak perlu kalkulasi lagi di sini
        
        bar_length = 50
        filled = int(bar_length * self.animated_percent / 100) if self.total > 0 else 0
        
        # Buat bar dengan karakter yang lebih variatif untuk efek smooth
        bar_parts = []
        for i in range(bar_length):
            if i < filled:
                # Gradient effect dengan karakter berbeda
                if i < filled - 1:
                    bar_parts.append('█')
                elif filled == bar_length:
                    bar_parts.append('█')
                else:
                    # Karakter transisi untuk efek smooth
                    bar_parts.append('▉')
            elif i == filled and self.animated_percent < 100:
                # Karakter animasi di ujung
                bar_parts.append('░')
            else:
                bar_parts.append('░')
        
        bar = ''.join(bar_parts)
        
        elapsed = now - self.start_time
        if self.current > 0:
            rate = self.current / elapsed
            eta = (self.total - self.current) / rate if rate > 0 else 0
            eta_str = f"ETA: {int(eta)}s" if eta > 0 else "ETA: --"
            speed_str = f"{rate:.1f} {self.unit}/s"
        else:
            rate = 0
            eta_str = "ETA: --"
            speed_str = "0.0 {self.unit}/s"
        
        # Clear line and print progress dengan animasi
        sys.stdout.write(f'\r{spinner} {self.desc} |{bar}| {self.current}/{self.total} ({self.animated_percent:.1f}%) [{speed_str}] [{eta_str}]')
        sys.stdout.flush()
        
    def close(self):
        # Pastikan 100% ditampilkan
        self.animated_percent = 100.0
        bar_length = 50
        bar = '█' * bar_length
        elapsed = time.time() - self.start_time
        speed = self.total / elapsed if elapsed > 0 else 0
        sys.stdout.write(f'\r✓ {self.desc} |{bar}| {self.current}/{self.total} (100.0%) [{speed:.1f} {self.unit}/s] [Selesai!]\n')
        sys.stdout.flush()
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        self.close()


class FileEncryptor:
    def __init__(self, password: str = None):
        """Initialize encryptor dengan password"""
        self.encrypted_ext = '.encrypted'
        self.password = password
        self.fernet = None
        
    def _get_key_from_password(self, password: str, salt: bytes = None) -> tuple:
        """Generate encryption key dari password menggunakan PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def _get_fernet(self, password: str = None, salt: bytes = None) -> Fernet:
        """Get atau create Fernet cipher instance"""
        if password is None:
            password = self.password
        if password is None:
            raise ValueError("Password diperlukan untuk enkripsi/dekripsi")
        
        key, salt = self._get_key_from_password(password, salt)
        return Fernet(key)
    
    def _secure_delete(self, file_path: str, passes: int = 3) -> bool:
        """Hapus file secara aman dengan menimpa data beberapa kali"""
        try:
            if not os.path.exists(file_path):
                return True
            
            file_path = os.path.abspath(file_path)
            file_size = os.path.getsize(file_path)
            
            # Timpa file dengan data random beberapa kali
            for pass_num in range(passes):
                try:
                    with open(file_path, 'r+b') as f:
                        # Tulis data random ke seluruh file
                        f.seek(0)
                        remaining = file_size
                        while remaining > 0:
                            chunk_size = min(1024 * 1024, remaining)  # 1MB chunks
                            random_data = os.urandom(chunk_size)
                            f.write(random_data)
                            remaining -= chunk_size
                        f.flush()
                        os.fsync(f.fileno())  # Force write to disk
                except Exception as e:
                    print(f"⚠️  Warning pada pass {pass_num + 1}: {str(e)}")
            
            # Pastikan file ditutup sebelum dihapus
            # Hapus file
            try:
                os.remove(file_path)
            except PermissionError:
                # Jika permission error, coba lagi setelah sedikit delay
                time.sleep(0.1)
                os.remove(file_path)
            
            # Verifikasi file benar-benar sudah dihapus
            if os.path.exists(file_path):
                # Jika masih ada, coba hapus lagi dengan cara paksa
                try:
                    os.chmod(file_path, 0o777)  # Ubah permission
                    os.remove(file_path)
                except:
                    # Jika masih gagal, gunakan shutil
                    shutil.rmtree(file_path) if os.path.isdir(file_path) else os.remove(file_path)
            
            # Final verification
            if os.path.exists(file_path):
                print(f"⚠️  Warning: File masih ada setelah penghapusan: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            print(f"⚠️  Warning: Secure delete gagal, menggunakan delete biasa: {str(e)}")
            try:
                # Coba hapus dengan berbagai metode
                if os.path.exists(file_path):
                    os.chmod(file_path, 0o777)
                    os.remove(file_path)
                    # Verifikasi
                    if not os.path.exists(file_path):
                        return True
                    else:
                        # Coba dengan shutil sebagai last resort
                        import shutil
                        if os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                        else:
                            os.remove(file_path)
                        return not os.path.exists(file_path)
                return True
            except Exception as e2:
                print(f"❌ Error: Tidak bisa menghapus file {file_path}: {str(e2)}")
                return False
    
    def encrypt_file(self, file_path: str, password: str = None, show_progress: bool = False) -> bool:
        """Enkripsi single file"""
        try:
            file_path = os.path.abspath(file_path)
            if not os.path.exists(file_path):
                # Tidak print saat progress bar aktif
                return False
            
            if file_path.endswith(self.encrypted_ext):
                # Tidak print saat progress bar aktif
                return False
            
            # Generate salt dan key
            salt = os.urandom(16)
            fernet = self._get_fernet(password, salt)
            
            # Baca file original dengan progress untuk file besar
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as f:
                if show_progress and file_size > 1024 * 1024:  # > 1MB
                    # Baca dalam chunks untuk file besar
                    file_data = b''
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        file_data += chunk
                        time.sleep(0.01)  # Small delay untuk animasi
                else:
                    file_data = f.read()
            
            # Enkripsi data dengan sedikit delay untuk animasi
            if show_progress:
                time.sleep(0.05)
            encrypted_data = fernet.encrypt(file_data)
            
            # Tulis file terenkripsi
            encrypted_path = file_path + self.encrypted_ext
            with open(encrypted_path, 'wb') as f:
                # Simpan salt di awal file (16 bytes)
                f.write(salt)
                f.write(encrypted_data)
            
            # Pastikan file terenkripsi sudah ditulis ke disk
            time.sleep(0.05)  # Beri waktu untuk file system sync
            
            # Hapus file original secara aman (secure delete)
            delete_success = self._secure_delete(file_path)
            
            # Verifikasi file original benar-benar sudah dihapus
            if os.path.exists(file_path):
                # Coba hapus lagi dengan cara biasa (tidak print saat progress bar aktif)
                try:
                    os.chmod(file_path, 0o777)
                    os.remove(file_path)
                except Exception as e:
                    # Hapus file terenkripsi yang baru dibuat karena gagal
                    if os.path.exists(encrypted_path):
                        os.remove(encrypted_path)
                    return False
            
            # Tidak perlu metadata, salt sudah disimpan di file terenkripsi
            # Tidak print apapun saat progress bar aktif
            return True
            
        except Exception as e:
            # Tidak print error saat progress bar aktif
            return False
    
    def decrypt_file(self, encrypted_path: str, password: str = None, show_progress: bool = False) -> bool:
        """Dekripsi single file"""
        try:
            encrypted_path = os.path.abspath(encrypted_path)
            if not os.path.exists(encrypted_path):
                # Tidak print saat progress bar aktif
                return False
            
            if not encrypted_path.endswith(self.encrypted_ext):
                # Tidak print saat progress bar aktif
                return False
            
            # Baca salt dari file terenkripsi (salt disimpan di 16 byte pertama)
            with open(encrypted_path, 'rb') as f:
                salt = f.read(16)
            # Path original adalah nama file tanpa extension .encrypted
            original_path = encrypted_path[:-len(self.encrypted_ext)]
            
            # Get Fernet dengan salt yang benar
            fernet = self._get_fernet(password, salt)
            
            # Baca file terenkripsi
            with open(encrypted_path, 'rb') as f:
                f.read(16)  # Skip salt
                encrypted_data = f.read()
            
            # Dekripsi data
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
            except Exception as e:
                # Tidak print saat progress bar aktif
                return False
            
            # Tulis file terdekripsi
            with open(original_path, 'wb') as f:
                f.write(decrypted_data)
            
            # Hapus file terenkripsi
            os.remove(encrypted_path)
            
            # Tidak print apapun saat progress bar aktif
            return True
            
        except Exception as e:
            # Tidak print error saat progress bar aktif
            return False
    
    def encrypt_folder(self, folder_path: str, password: str = None, recursive: bool = True, silent: bool = False) -> int:
        """Enkripsi semua file dalam folder (rekursif termasuk semua subfolder)"""
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            if not silent:
                print(f"❌ Folder tidak ditemukan: {folder_path}")
            return 0
        
        # Kumpulkan semua file yang akan dienkripsi
        files_to_encrypt = []
        
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if not file.endswith(self.encrypted_ext):
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            files_to_encrypt.append(file_path)
        else:
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path) and not file.endswith(self.encrypted_ext):
                    files_to_encrypt.append(file_path)
        
        if not files_to_encrypt:
            if not silent:
                print(f"⚠️  Tidak ada file yang perlu dienkripsi di folder ini")
            return 0
        
        encrypted_count = 0
        
        # Buat progress bar - selalu gunakan custom untuk animasi yang lebih baik
        if not silent:
            pbar = ProgressBar(len(files_to_encrypt), desc="🔒 Enkripsi", unit="file")
        else:
            pbar = None
        
        try:
            for file_path in files_to_encrypt:
                # Proses file
                if self.encrypt_file(file_path, password, show_progress=(pbar is not None)):
                    encrypted_count += 1
                # Update progress bar dengan animasi bertahap
                if pbar:
                    pbar.update(1)  # Animasi sudah ada di dalam update()
        finally:
            if pbar:
                pbar.close()
        
        # Tidak perlu enkripsi metadata, tidak ada metadata file
        
        if not silent:
            print(f"\n✅ Total {encrypted_count} file berhasil dienkripsi dari folder")
        return encrypted_count
    
    def decrypt_folder(self, folder_path: str, password: str = None, recursive: bool = True, silent: bool = False) -> int:
        """Dekripsi semua file dalam folder (rekursif termasuk semua subfolder)"""
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            if not silent:
                print(f"❌ Folder tidak ditemukan: {folder_path}")
            return 0
        
        # Tidak perlu metadata, salt sudah disimpan di file terenkripsi
        
        # Kumpulkan semua file yang akan didekripsi
        files_to_decrypt = []
        
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.endswith(self.encrypted_ext):
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            files_to_decrypt.append(file_path)
        else:
            for file in os.listdir(folder_path):
                if file.endswith(self.encrypted_ext):
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path):
                        files_to_decrypt.append(file_path)
        
        if not files_to_decrypt:
            if not silent:
                print(f"⚠️  Tidak ada file terenkripsi di folder ini")
            return 0
        
        decrypted_count = 0
        
        # Buat progress bar - selalu gunakan custom untuk animasi yang lebih baik
        if not silent:
            pbar = ProgressBar(len(files_to_decrypt), desc="🔓 Dekripsi", unit="file")
        else:
            pbar = None
        
        try:
            for file_path in files_to_decrypt:
                # Proses file
                if self.decrypt_file(file_path, password, show_progress=(pbar is not None)):
                    decrypted_count += 1
                # Update progress bar dengan animasi bertahap
                if pbar:
                    pbar.update(1)  # Animasi sudah ada di dalam update()
        finally:
            if pbar:
                pbar.close()
        
        if not silent:
            print(f"\n✅ Total {decrypted_count} file berhasil didekripsi dari folder")
        return decrypted_count
    
    def list_encrypted(self, folder_path: str = None, recursive: bool = True) -> list:
        """List semua file terenkripsi"""
        if folder_path is None:
            folder_path = os.getcwd()
        
        folder_path = os.path.abspath(folder_path)
        encrypted_files = []
        
        # Tidak menggunakan metadata, hanya scan file .encrypted
        
        if recursive:
            # Cari semua file .encrypted
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.endswith(self.encrypted_ext):
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, folder_path)
                        
                        # Path original adalah nama file tanpa extension .encrypted
                        original_path = file_path[:-len(self.encrypted_ext)]
                        
                        info = {
                            'encrypted_path': file_path,
                            'relative_path': rel_path,
                            'size': os.path.getsize(file_path),
                            'original_path': original_path,
                            'in_metadata': False  # Tidak ada metadata lagi
                        }
                        
                        encrypted_files.append(info)
        else:
            # Hanya file di folder root
            for file in os.listdir(folder_path):
                if file.endswith(self.encrypted_ext):
                    file_path = os.path.join(folder_path, file)
                    rel_path = os.path.relpath(file_path, folder_path)
                    
                    # Path original adalah nama file tanpa extension .encrypted
                    original_path = file_path[:-len(self.encrypted_ext)]
                    
                    info = {
                        'encrypted_path': file_path,
                        'relative_path': rel_path,
                        'size': os.path.getsize(file_path),
                        'original_path': original_path,
                        'in_metadata': False  # Tidak ada metadata lagi
                    }
                    
                    encrypted_files.append(info)
        
        return encrypted_files
    
    def print_encrypted_list(self, folder_path: str = None, recursive: bool = True):
        """Print daftar file terenkripsi dengan format yang rapi"""
        encrypted_files = self.list_encrypted(folder_path, recursive)
        
        if not encrypted_files:
            print("📋 Tidak ada file terenkripsi ditemukan")
            return
        
        print(f"\n📋 Daftar File Terenkripsi ({len(encrypted_files)} file):")
        print("=" * 80)
        
        for i, info in enumerate(encrypted_files, 1):
            print(f"\n{i}. {info['relative_path']}")
            print(f"   Ukuran: {self._format_size(info['size'])}")
            
            if 'original_path' in info:
                print(f"   Path Asli: {info['original_path']}")
        
        print("\n" + "=" * 80)


    def _format_size(self, size_bytes: int) -> str:
        """Format ukuran file menjadi human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def process_file_list(self, list_file: str, password: str = None, operation: str = 'encrypt') -> dict:
        """
        Proses semua file/folder yang ada di file_list.txt
        operation: 'encrypt' atau 'decrypt'
        """
        if not os.path.exists(list_file):
            print(f"❌ File list tidak ditemukan: {list_file}")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        # Baca file list
        items = []
        try:
            with open(list_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip empty lines dan comments
                        items.append(line)
        except Exception as e:
            print(f"❌ Error membaca file list: {str(e)}")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        if not items:
            print("⚠️  File list kosong")
            return {'success': 0, 'failed': 0, 'total': 0}
        
        print(f"\n📋 Memproses {len(items)} item dari {list_file}...")
        print("=" * 80)
        
        # Tidak perlu metadata, salt sudah disimpan di file terenkripsi
        
        success_count = 0
        failed_count = 0
        
        # Buat progress bar untuk process_file_list - selalu gunakan custom untuk animasi yang lebih baik
        pbar = ProgressBar(len(items), desc=f"{'🔒 Enkripsi' if operation == 'encrypt' else '🔓 Dekripsi'}", unit="item")
        
        try:
            for i, item_path in enumerate(items, 1):
                item_path = item_path.strip()
                if not item_path:
                    pbar.update(1)
                    continue
                
                # Resolve path (bisa relative atau absolute)
                if not os.path.isabs(item_path):
                    # Jika relative, cari dari current directory atau dari folder script
                    abs_path = os.path.abspath(item_path)
                else:
                    abs_path = item_path
                
                # Progress bar akan menampilkan animasi saat update
                
                try:
                    # Untuk dekripsi, jika file tidak ditemukan, coba dengan extension .encrypted
                    if operation == 'decrypt' and not os.path.exists(abs_path):
                        encrypted_path = abs_path + self.encrypted_ext
                        if os.path.exists(encrypted_path):
                            # Tidak print saat progress bar aktif
                            abs_path = encrypted_path
                    
                    if os.path.isfile(abs_path):
                        # Proses file
                        if operation == 'encrypt':
                            if abs_path.endswith(self.encrypted_ext):
                                # Skip tanpa print saat progress bar aktif
                                pbar.update(1)
                                continue
                            result = self.encrypt_file(abs_path, password, show_progress=True)
                            # Progress bar akan diupdate di finally block dengan animasi
                        else:  # decrypt
                            # Pastikan file memiliki extension .encrypted
                            if not abs_path.endswith(self.encrypted_ext):
                                encrypted_path = abs_path + self.encrypted_ext
                                if os.path.exists(encrypted_path):
                                    abs_path = encrypted_path
                                    # Tidak print saat progress bar aktif
                                else:
                                    # Tidak print saat progress bar aktif
                                    failed_count += 1
                                    pbar.update(1)
                                    continue
                            result = self.decrypt_file(abs_path, password, show_progress=True)
                            # Progress bar akan diupdate di finally block dengan animasi
                        
                        if result:
                            success_count += 1
                        else:
                            failed_count += 1
                            
                    elif os.path.isdir(abs_path):
                        # Proses folder (rekursif - semua file dan subfolder)
                        # Tidak print info saat progress bar aktif
                        if operation == 'encrypt':
                            count = self.encrypt_folder(abs_path, password, recursive=True, silent=True)
                            if count > 0:
                                success_count += count
                        else:  # decrypt
                            count = self.decrypt_folder(abs_path, password, recursive=True, silent=True)
                            if count > 0:
                                success_count += count
                            # Progress bar akan diupdate di finally block dengan animasi
                    else:
                        # Tidak print saat progress bar aktif
                        failed_count += 1
                        
                except Exception as e:
                    # Tidak print error saat progress bar aktif, hanya increment failed count
                    failed_count += 1
                finally:
                    pbar.update(1)
        finally:
            pbar.close()
        print("\n" + "=" * 80)
        
        # Tidak perlu enkripsi metadata, tidak ada metadata file
        
        print(f"\n✅ Selesai! Berhasil: {success_count}, Gagal: {failed_count}, Total: {len(items)}")
        
        return {
            'success': success_count,
            'failed': failed_count,
            'total': len(items)
        }


def main():
    parser = argparse.ArgumentParser(
        description='Script untuk mengenkripsi dan dekripsi folder dan file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  # Enkripsi file
  python FuckEnc.py encrypt -f file.txt -p password123
  
  # Dekripsi file
  python FuckEnc.py decrypt -f file.txt.encrypted -p password123
  
  # Enkripsi folder (rekursif)
  python FuckEnc.py encrypt -d /path/to/folder -p password123
  
  # Dekripsi folder (rekursif)
  python FuckEnc.py decrypt -d /path/to/folder -p password123
  
  # Enkripsi semua file/folder dari file list
  python FuckEnc.py encrypt -l file_list.txt -p password123
  
  # Dekripsi semua file/folder dari file list
  python FuckEnc.py decrypt -l file_list.txt -p password123
  
  # List file terenkripsi
  python FuckEnc.py list
  
  # List file terenkripsi di folder tertentu
  python FuckEnc.py list -d /path/to/folder
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command yang akan dijalankan')
    
    # Encrypt command
    encrypt_parser = subparsers.add_parser('encrypt', help='Enkripsi file atau folder')
    encrypt_parser.add_argument('-f', '--file', help='Path ke file yang akan dienkripsi')
    encrypt_parser.add_argument('-d', '--dir', help='Path ke folder yang akan dienkripsi')
    encrypt_parser.add_argument('-l', '--list', help='Path ke file list yang berisi daftar file/folder yang akan dienkripsi')
    encrypt_parser.add_argument('-p', '--password', required=True, help='Password untuk enkripsi')
    encrypt_parser.add_argument('--no-recursive', action='store_true', help='Tidak enkripsi subfolder (hanya untuk folder)')
    
    # Decrypt command
    decrypt_parser = subparsers.add_parser('decrypt', help='Dekripsi file atau folder')
    decrypt_parser.add_argument('-f', '--file', help='Path ke file yang akan didekripsi')
    decrypt_parser.add_argument('-d', '--dir', help='Path ke folder yang akan didekripsi')
    decrypt_parser.add_argument('-l', '--list', help='Path ke file list yang berisi daftar file/folder yang akan didekripsi')
    decrypt_parser.add_argument('-p', '--password', required=True, help='Password untuk dekripsi')
    decrypt_parser.add_argument('--no-recursive', action='store_true', help='Tidak dekripsi subfolder (hanya untuk folder)')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List file terenkripsi')
    list_parser.add_argument('-d', '--dir', help='Path ke folder yang akan dicari (default: current directory)')
    list_parser.add_argument('--no-recursive', action='store_true', help='Tidak cari di subfolder')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    encryptor = FileEncryptor()
    
    if args.command == 'encrypt':
        if not args.file and not args.dir and not args.list:
            print("❌ Harus spesifikasi file (-f), folder (-d), atau file list (-l)")
            sys.exit(1)
        
        recursive = not args.no_recursive
        
        if args.list:
            encryptor.process_file_list(args.list, args.password, operation='encrypt')
        elif args.file:
            encryptor.encrypt_file(args.file, args.password)
        elif args.dir:
            encryptor.encrypt_folder(args.dir, args.password, recursive)
    
    elif args.command == 'decrypt':
        if not args.file and not args.dir and not args.list:
            print("❌ Harus spesifikasi file (-f), folder (-d), atau file list (-l)")
            sys.exit(1)
        
        recursive = not args.no_recursive
        
        if args.list:
            encryptor.process_file_list(args.list, args.password, operation='decrypt')
        elif args.file:
            encryptor.decrypt_file(args.file, args.password)
        elif args.dir:
            encryptor.decrypt_folder(args.dir, args.password, recursive)
    
    elif args.command == 'list':
        recursive = not args.no_recursive
        encryptor.print_encrypted_list(args.dir, recursive)


if __name__ == '__main__':
    main()

