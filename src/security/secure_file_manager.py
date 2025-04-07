import os
import shutil
import json
from datetime import datetime

class SecureFileManager:
    def __init__(self):
        self.secure_dir = "secure_backup"
        self.sensitive_files = [
            "credentials.json",
            "service_account.json",
            ".env"
        ]
        self.ensure_secure_dir()

    def ensure_secure_dir(self):
        """Ensure secure backup directory exists."""
        if not os.path.exists(self.secure_dir):
            os.makedirs(self.secure_dir)
            print("Created secure backup directory: {self.secure_dir}")

    def backup_sensitive_files(self):
        """Backup sensitive files to secure directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.secure_dir, f"backup_{timestamp}")
        os.makedirs(backup_dir)

        for file in self.sensitive_files:
            if os.path.exists(file):
                # Create backup
                backup_path = os.path.join(backup_dir, file)
                shutil.copy2(file, backup_path)
                print(f"Backed up {file} to secure location")

                # Create symlink or copy based on OS
                if os.name == 'nt':  # Windows
                    # Windows might need admin privileges for symlinks
                    # So we create a pointer file instead
                    pointer = {
                        "original_file": file,
                        "backup_location": backup_path,
                        "timestamp": timestamp
                    }
                    with open(f"{file}.pointer", "w") as f:
                        json.dump(pointer, f, indent=2)
                    print(f"Created pointer file for {file}")
                else:  # Unix-like
                    # Create symlink
                    if os.path.exists(file):
                        os.remove(file)
                    os.symlink(backup_path, file)
                    print(f"Created symlink for {file}")

    def restore_files(self):
        """Restore files from most recent backup."""
        if not os.path.exists(self.secure_dir):
            print("No backups found")
            return

        # Find most recent backup
        backups = [d for d in os.listdir(self.secure_dir) if d.startswith("backup_")]
        if not backups:
            print("No backups found")
            return

        latest_backup = max(backups)
        backup_dir = os.path.join(self.secure_dir, latest_backup)

        for file in self.sensitive_files:
            backup_path = os.path.join(backup_dir, file)
            if os.path.exists(backup_path):
                if os.path.exists(file):
                    os.remove(file)
                shutil.copy2(backup_path, file)
                print(f"Restored {file} from backup")

    def protect_sensitive_files(self):
        """Protect sensitive files by moving them to secure backup."""
        print("Protecting sensitive files...")
        
        # First, backup existing files
        self.backup_sensitive_files()
        
        # Create placeholder files with warnings
        for file in self.sensitive_files:
            if os.path.exists(file):
                placeholder_content = f"""SECURITY NOTICE

This is a placeholder file. The actual {file} has been moved to a secure location.
Last backup: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

To restore this file:
1. Use secure_file_manager.py to manage sensitive files
2. Never commit this file to version control
3. Keep backups secure

For security reasons, the actual content has been moved to: {self.secure_dir}"""

                with open(file, "w", encoding="utf-8") as f:
                    f.write(placeholder_content)
                print(f"Created secure placeholder for {file}")

    def check_file_status(self):
        """Check status of sensitive files."""
        print("\nSensitive Files Status:")
        print("-" * 50)
        
        for file in self.sensitive_files:
            print(f"\nChecking {file}:")
            
            # Check original file
            if os.path.exists(file):
                print(f"  - File exists in workspace")
                if os.path.getsize(file) < 1000:  # Small file might be placeholder
                    print("  - Might be a placeholder file")
            else:
                print(f"  - File not found in workspace")
            
            # Check pointer
            pointer_file = f"{file}.pointer"
            if os.path.exists(pointer_file):
                with open(pointer_file) as f:
                    pointer = json.load(f)
                print(f"  - Pointer -> {pointer['backup_location']}")
            
            # Check backups
            backups = [d for d in os.listdir(self.secure_dir) if d.startswith("backup_")]
            if backups:
                latest = max(backups)
                backup_path = os.path.join(self.secure_dir, latest, file)
                if os.path.exists(backup_path):
                    print(f"  - Latest backup: {latest}")
                else:
                    print("  - No backup found")
            else:
                print("  - No backups exist")

if __name__ == "__main__":
    manager = SecureFileManager()
    
    print("\nSecure File Manager")
    print("=" * 50)
    print("1. Protect sensitive files")
    print("2. Restore files from backup")
    print("3. Create new backup")
    print("4. Check file status")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == "1":
        manager.protect_sensitive_files()
    elif choice == "2":
        manager.restore_files()
    elif choice == "3":
        manager.backup_sensitive_files()
    elif choice == "4":
        manager.check_file_status()
    else:
        print("Goodbye!") 