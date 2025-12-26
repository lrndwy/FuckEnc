#!/usr/bin/env python3
"""
FuckEnc Decrypt Version 2 - Auto-Decrypt
Script untuk mendekripsi semua file .encrypted di home directory
"""

import os
import sys
import platform
import base64
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class ProgressBar:
    """Custom progress bar untuk dekripsi"""
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
        # Update lebih jarang untuk performa lebih baik (setiap 0.2 detik)
        if not force and now - self.last_update < 0.2 and self.current < self.total:
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


class FileDecryptor:
    def __init__(self, password: str = None):
        """Initialize decryptor dengan password"""
        self.encrypted_ext = '.encrypted'
        self.password = password
        
    def _get_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Generate decryption key dari password menggunakan PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _get_fernet(self, password: str, salt: bytes) -> Fernet:
        """Get Fernet cipher instance untuk dekripsi"""
        if password is None:
            password = self.password
        if password is None:
            raise ValueError("Password diperlukan untuk dekripsi")
        
        key = self._get_key_from_password(password, salt)
        return Fernet(key)
    
    def decrypt_file(self, encrypted_path: str, password: str = None, show_progress: bool = False) -> bool:
        """Dekripsi single file - Hanya file dengan ekstensi .encrypted
        Optimized untuk kecepatan
        """
        try:
            encrypted_path = os.path.abspath(encrypted_path)
            if not os.path.exists(encrypted_path):
                return False
            
            # HANYA proses file yang berakhiran .encrypted
            if not encrypted_path.endswith(self.encrypted_ext):
                return False
            
            # Pastikan ini adalah file, bukan directory
            if not os.path.isfile(encrypted_path):
                return False
            
            # Baca file terenkripsi sekaligus (lebih cepat)
            with open(encrypted_path, 'rb') as f:
                salt = f.read(16)
                encrypted_data = f.read()
            
            # Path original adalah nama file tanpa extension .encrypted
            original_path = encrypted_path[:-len(self.encrypted_ext)]
            
            # Get Fernet dengan salt yang benar
            fernet = self._get_fernet(password, salt)
            
            # Dekripsi data
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
            except Exception:
                # Password salah atau file corrupt - silent fail untuk kecepatan
                return False
            
            # Tulis file terdekripsi
            with open(original_path, 'wb') as f:
                f.write(decrypted_data)
            
            # Hapus file terenkripsi setelah berhasil didekripsi
            try:
                os.remove(encrypted_path)
            except Exception:
                pass
            
            return True
            
        except Exception:
            # Silent fail untuk kecepatan
            return False
    
    def decrypt_folder(self, folder_path: str, password: str = None, recursive: bool = True, silent: bool = False, skip_hidden: bool = False) -> int:
        """Dekripsi semua file .encrypted dalam folder (rekursif termasuk semua subfolder)
        
        HANYA file dengan ekstensi .encrypted yang akan didekripsi
        Default: skip_hidden=False (include hidden files/folders)
        Karena file terenkripsi mungkin ada di hidden folders
        """
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            return 0
        
        files_to_decrypt = []
        
        def is_hidden(path):
            """Cek apakah file/folder adalah hidden (diawali dengan titik)"""
            basename = os.path.basename(path)
            return basename.startswith('.')
        
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                # Filter out hidden directories untuk os.walk hanya jika skip_hidden=True
                if skip_hidden:
                    dirs[:] = [d for d in dirs if not is_hidden(os.path.join(root, d))]
                # Jika skip_hidden=False, kita akan traverse semua folder termasuk hidden
                
                for file in files:
                    # HANYA proses file yang berakhiran .encrypted
                    if not file.endswith(self.encrypted_ext):
                        continue
                    
                    # Skip file yang diawali dengan titik hanya jika skip_hidden=True
                    if skip_hidden and is_hidden(file):
                        continue
                    
                    file_path = os.path.join(root, file)
                    # Pastikan ini adalah file, bukan directory atau symlink
                    if os.path.isfile(file_path):
                        files_to_decrypt.append(file_path)
        else:
            for file in os.listdir(folder_path):
                # HANYA proses file yang berakhiran .encrypted
                if not file.endswith(self.encrypted_ext):
                    continue
                
                # Skip file yang diawali dengan titik hanya jika skip_hidden=True
                if skip_hidden and is_hidden(file):
                    continue
                
                file_path = os.path.join(folder_path, file)
                # Pastikan ini adalah file, bukan directory atau symlink
                if os.path.isfile(file_path):
                    files_to_decrypt.append(file_path)
        
        if not files_to_decrypt:
            return 0
        
        decrypted_count = 0
        failed_count = 0
        
        if not silent:
            pbar = ProgressBar(len(files_to_decrypt), desc="🔓 Dekripsi", unit="file")
        else:
            pbar = None
        
        try:
            # Proses file tanpa delay untuk kecepatan maksimal
            for i, file_path in enumerate(files_to_decrypt):
                if self.decrypt_file(file_path, password, show_progress=False):
                    decrypted_count += 1
                else:
                    failed_count += 1
                
                # Update progress bar (tanpa delay animasi, update setiap 5 file untuk performa)
                if pbar:
                    pbar.current = i + 1
                    pbar.animated_percent = (pbar.current / pbar.total * 100) if pbar.total > 0 else 0
                    # Update display hanya setiap beberapa file untuk performa lebih baik
                    if (i + 1) % 5 == 0 or (i + 1) == len(files_to_decrypt):
                        pbar._display()
        finally:
            if pbar:
                # Pastikan progress bar menunjukkan nilai akhir yang benar
                pbar.current = len(files_to_decrypt)
                pbar.animated_percent = 100.0
                pbar.close()
        
        if not silent and failed_count > 0:
            print(f"⚠️  {failed_count} file gagal didekripsi (kemungkinan password salah)")
        
        return decrypted_count


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
        home = os.path.expanduser("~")
        drives = []
        for drive in range(ord('C'), ord('Z') + 1):
            drive_path = f"{chr(drive)}:\\"
            if os.path.exists(drive_path):
                drives.append(drive_path)
        return home, drives
    elif system == 'darwin':
        return os.path.expanduser("~"), []
    else:
        return os.path.expanduser("~"), []


def auto_decrypt_home(password: str = None, silent: bool = False, skip_hidden: bool = False, include_root: bool = True):
    """Auto-decrypt semua file .encrypted di home directory dan root directory
    
    Default: skip_hidden=False (include hidden files/folders)
    Default: include_root=True (include root directory juga)
    Karena file terenkripsi mungkin ada di hidden folders seperti .config, .local, dll
    """
    if password is None:
        # Default password
        password = "default_password_123"
    
    # Deteksi OS
    os_info = detect_os()
    
    # Dapatkan home directory
    home_dir, additional_drives = get_home_directory()
    
    # Buat decryptor
    decryptor = FileDecryptor(password=password)
    
    decrypted_total = 0
    
    # Dekripsi home directory
    # Include hidden files/folders secara default (karena file terenkripsi mungkin ada di hidden folders)
    if os.path.exists(home_dir):
        if not silent:
            print(f"🔓 Mendekripsi home directory: {home_dir}")
        count = decryptor.decrypt_folder(
            home_dir, 
            password=password, 
            recursive=True, 
            silent=silent,
            skip_hidden=skip_hidden
        )
        decrypted_total += count
        if not silent:
            print(f"   ✅ {count} file didekripsi dari home directory")
    
    # Dekripsi root directory juga jika include_root=True
    if include_root:
        system = platform.system().lower()
        if system != 'windows':
            # Linux/macOS: root directory adalah /
            root_dir = '/'
            if os.path.exists(root_dir):
                if not silent:
                    print(f"🔓 Mendekripsi root directory: {root_dir}")
                try:
                    count = decryptor.decrypt_folder(
                        root_dir, 
                        password=password, 
                        recursive=True, 
                        silent=silent,
                        skip_hidden=skip_hidden
                    )
                    decrypted_total += count
                    if not silent:
                        print(f"   ✅ {count} file didekripsi dari root directory")
                except PermissionError:
                    if not silent:
                        print(f"   ⚠️  Permission denied untuk root directory (perlu root access)")
                except Exception as e:
                    if not silent:
                        print(f"   ⚠️  Error saat mendekripsi root directory: {str(e)}")
        else:
            # Windows: cek semua drive
            for drive in additional_drives:
                if os.path.exists(drive):
                    if not silent:
                        print(f"🔓 Mendekripsi drive: {drive}")
                    try:
                        count = decryptor.decrypt_folder(
                            drive, 
                            password=password, 
                            recursive=True, 
                            silent=silent,
                            skip_hidden=skip_hidden
                        )
                        decrypted_total += count
                        if not silent:
                            print(f"   ✅ {count} file didekripsi dari {drive}")
                    except PermissionError:
                        if not silent:
                            print(f"   ⚠️  Permission denied untuk {drive}")
                    except Exception as e:
                        if not silent:
                            print(f"   ⚠️  Error saat mendekripsi {drive}: {str(e)}")
    
    return decrypted_total


def main():
    """Main function - Auto-decrypt saat dijalankan"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Dekripsi semua file .encrypted di home directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  # Dekripsi dengan password default (home + root directory)
  python FuckEnc_Decrypt_v2.py
  
  # Dekripsi dengan password custom (home + root directory)
  python FuckEnc_Decrypt_v2.py -p mypassword123
  
  # Dekripsi dengan silent mode (tidak tampilkan progress)
  python FuckEnc_Decrypt_v2.py -p mypassword123 --silent
  
  # Dekripsi hanya di home directory (tidak include root)
  python FuckEnc_Decrypt_v2.py -p mypassword123 --home-only
  
  # Dekripsi skip hidden files
  python FuckEnc_Decrypt_v2.py -p mypassword123 --skip-hidden
        """
    )
    
    parser.add_argument('-p', '--password', 
                       help='Password untuk dekripsi (default: default_password_123)',
                       default='default_password_123')
    parser.add_argument('--silent', 
                       action='store_true',
                       help='Silent mode (tidak tampilkan progress bar)')
    parser.add_argument('--skip-hidden', 
                       action='store_true',
                       help='Skip hidden files/folders (file yang diawali dengan titik). Default: include semua file termasuk hidden')
    parser.add_argument('--home-only', 
                       action='store_true',
                       help='Hanya dekripsi di home directory (tidak include root). Default: include home dan root directory')
    
    args = parser.parse_args()
    
    # Deteksi OS
    os_info = detect_os()
    
    if not args.silent:
        print(f"🖥️  OS Detected: {os_info['system'].upper()} ({os_info['platform']})")
    
    # Dapatkan home directory
    home_dir, additional_drives = get_home_directory()
    
    if not args.silent:
        print(f"📁 Home Directory: {home_dir}")
        if not args.home_only:
            system = platform.system().lower()
            if system != 'windows':
                print(f"📁 Root Directory: / (akan didekripsi juga)")
            else:
                print(f"📁 Additional Drives: {', '.join(additional_drives) if additional_drives else 'None'} (akan didekripsi juga)")
        print(f"📋 Mode: {'Skip hidden files' if args.skip_hidden else 'Include semua file termasuk hidden files/folders'}")
        print(f"🔑 Password: {args.password}")
        print("=" * 80)
    
    # Auto-decrypt home directory dan root directory
    try:
        if not args.silent:
            print("🔓 Memulai dekripsi...")
            print()
        
        count = auto_decrypt_home(
            password=args.password, 
            silent=args.silent,
            skip_hidden=args.skip_hidden,  # Default: False (include hidden files)
            include_root=not args.home_only  # Default: True (include root directory)
        )
        
        if not args.silent:
            print(f"\n✅ Dekripsi selesai! Total {count} file berhasil didekripsi")
        else:
            # Silent mode: hanya print jumlah file
            print(count)
            
    except KeyboardInterrupt:
        if not args.silent:
            print("\n\n⚠️  Dekripsi dibatalkan oleh user")
        sys.exit(1)
    except Exception as e:
        if not args.silent:
            print(f"❌ Error saat dekripsi: {str(e)}")
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

