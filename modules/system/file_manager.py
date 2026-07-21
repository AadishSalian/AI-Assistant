import os
import shutil
import time
import fnmatch
import logging

logger = logging.getLogger("sweetie.file_manager")

class FileManager:
    def __init__(self, config):
        self.config = config.get('files', {})
        self.search_dirs = self.config.get('search_directories', [os.path.expanduser("~")])
        self.auto_organize_confirm = self.config.get('auto_organize_confirm', True)

        self.categories = {
            'Images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'],
            'Documents': ['.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls', '.pptx', '.ppt', '.csv'],
            'Executables': ['.exe', '.msi', '.bat', '.ps1'],
            'Archives': ['.zip', '.rar', '.tar', '.gz', '.7z'],
            'Audio': ['.mp3', '.wav', '.flac', '.ogg'],
            'Video': ['.mp4', '.mkv', '.avi', '.mov']
        }

    def open_folder(self, folder_path):
        """Opens a folder in Windows Explorer."""
        if not os.path.exists(folder_path):
            return False, f"Folder {folder_path} does not exist."
        try:
            os.startfile(folder_path)
            return True, f"Opened {os.path.basename(folder_path)}."
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")
            return False, "Failed to open the folder."

    def search_files(self, query=None, extension=None, days_ago=None):
        """Searches for files matching criteria across configured directories."""
        results = []
        now = time.time()
        
        for search_dir in self.search_dirs:
            if not os.path.exists(search_dir):
                continue
                
            for root, dirs, files in os.walk(search_dir):
                # Skip hidden directories to speed up search
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    # Filter by extension
                    if extension and not file.lower().endswith(extension.lower()):
                        continue
                        
                    # Filter by query
                    if query and query.lower() not in file.lower():
                        continue
                        
                    filepath = os.path.join(root, file)
                    
                    # Filter by date
                    if days_ago:
                        try:
                            mtime = os.path.getmtime(filepath)
                            if (now - mtime) / (24 * 3600) > days_ago:
                                continue
                        except Exception:
                            continue
                            
                    results.append(filepath)
                    
                    # Cap at 50 results to avoid massive TTS readouts
                    if len(results) >= 50:
                        return results
        return results

    def organize_folder(self, folder_path, execute=False):
        """Sorts files in a folder into subfolders based on extension."""
        if not os.path.exists(folder_path):
            return False, f"Cannot organize. Folder not found: {folder_path}"

        moves = []
        try:
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if not os.path.isfile(item_path):
                    continue
                    
                _, ext = os.path.splitext(item)
                ext = ext.lower()
                
                # Determine target category
                target_cat = "Others"
                for cat, exts in self.categories.items():
                    if ext in exts:
                        target_cat = cat
                        break
                        
                target_dir = os.path.join(folder_path, target_cat)
                moves.append((item_path, os.path.join(target_dir, item)))
        except Exception as e:
            return False, f"Failed to scan folder: {e}"

        if not moves:
            return True, "Folder is already clean. Nothing to organize."

        if not execute:
            cats = {}
            for _, dest in moves:
                c = os.path.basename(os.path.dirname(dest))
                cats[c] = cats.get(c, 0) + 1
            
            summary = ", ".join([f"{v} {k}" for k, v in cats.items()])
            return True, f"I will move files into: {summary}. Shall I proceed?"

        # Execute
        try:
            for src, dest in moves:
                target_dir = os.path.dirname(dest)
                os.makedirs(target_dir, exist_ok=True)
                # Handle filename collisions
                if os.path.exists(dest):
                    base, ext = os.path.splitext(dest)
                    dest = f"{base}_{int(time.time())}{ext}"
                shutil.move(src, dest)
            return True, f"Successfully organized {len(moves)} files."
        except Exception as e:
            logger.error(f"Failed to organize: {e}")
            return False, "An error occurred while organizing the folder."

    def bulk_operation(self, action, source_dir, extension=None, destination_dir=None, execute=False):
        """Bulk move or delete files matching an extension in a directory."""
        if not os.path.exists(source_dir):
            return False, f"Source folder not found: {source_dir}"
            
        if action == "move" and destination_dir and not os.path.exists(destination_dir) and execute:
            os.makedirs(destination_dir, exist_ok=True)

        targets = []
        try:
            for item in os.listdir(source_dir):
                item_path = os.path.join(source_dir, item)
                if os.path.isfile(item_path):
                    if extension:
                        if item.lower().endswith(extension.lower()):
                            targets.append(item_path)
                    else:
                        targets.append(item_path)
        except Exception as e:
            return False, f"Failed to scan folder: {e}"

        if not targets:
            return True, "No files found matching that criteria."

        if not execute:
            op = "move" if action == "move" else "delete"
            return True, f"I found {len(targets)} files to {op}. Shall I proceed?"

        # Execute
        try:
            for src in targets:
                if action == "delete":
                    os.remove(src)
                elif action == "move" and destination_dir:
                    dest = os.path.join(destination_dir, os.path.basename(src))
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(dest)
                        dest = f"{base}_{int(time.time())}{ext}"
                    shutil.move(src, dest)
            
            op = "moved" if action == "move" else "deleted"
            return True, f"Successfully {op} {len(targets)} files."
        except Exception as e:
            logger.error(f"Bulk operation failed: {e}")
            return False, "Failed during bulk operation."
