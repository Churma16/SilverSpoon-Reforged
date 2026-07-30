import os
import sys
import re
import shutil
import subprocess
import threading
import logging
from core.types import TaskStatus
from utils.formatters import format_error_message

class ExtractionManager:
    def __init__(self, tasks, extracted_folders, base_dir, trigger_history_save_callback):
        self.tasks = tasks
        self.extracted_folders = extracted_folders
        self.base_dir = base_dir
        self.trigger_history_save_callback = trigger_history_save_callback

    def check_extraction(self):
        folders = {}
        for task in self.tasks:
            if task.folder_name not in folders:
                folders[task.folder_name] = []
            folders[task.folder_name].append(task)
            
        for folder_name, tasks_in_folder in folders.items():
            if folder_name in self.extracted_folders:
                continue
                
            valid_extraction_statuses = {TaskStatus.FINISHED, TaskStatus.EXTRACTED, TaskStatus.UNPACKING}
            if tasks_in_folder and all(t.status in valid_extraction_statuses for t in tasks_in_folder):
                if all(t.status == TaskStatus.EXTRACTED for t in tasks_in_folder):
                    self.extracted_folders.add(folder_name)
                    continue
                    
                if any(t.status == TaskStatus.UNPACKING for t in tasks_in_folder):
                    continue
                    
                self.extracted_folders.add(folder_name)
                threading.Thread(target=self.extract_folder, args=(tasks_in_folder,), daemon=True).start()

    def extract_folder(self, tasks_in_folder):
        save_dir = tasks_in_folder[0].save_dir
        folder_name = tasks_in_folder[0].folder_name
        
        for t in tasks_in_folder:
            t.status = TaskStatus.UNPACKING
            
        try:
            files = os.listdir(save_dir)
            files.sort()
            
            first_vol = None
            for f in files:
                if re.search(r'\.part0*1\.rar$', f, re.IGNORECASE) or \
                   re.search(r'\.001$', f) or \
                   (f.lower().endswith('.rar') and not re.search(r'\.part\d+\.rar$', f, re.IGNORECASE)):
                    first_vol = os.path.join(save_dir, f)
                    break
                    
            if not first_vol and files:
                first_vol = os.path.join(save_dir, files[0])
                
            if not first_vol:
                for t in tasks_in_folder:
                    t.status = TaskStatus.EXTRACT_ERROR
                    t.error_message = f"No archive file was found in {save_dir}."
                if folder_name in self.extracted_folders:
                    self.extracted_folders.remove(folder_name)
                return
                
            cmd = None
            if sys.platform == 'win32':
                if hasattr(sys, '_MEIPASS'):
                    bundled_7z = os.path.join(sys._MEIPASS, '7z.exe')
                else:
                    bundled_7z = os.path.normpath(os.path.join(self.base_dir, '7z.exe'))
                installed_7z = r"C:\Program Files\7-Zip\7z.exe"
                installed_winrar = r"C:\Program Files\WinRAR\WinRAR.exe"
                if os.path.exists(installed_7z):
                    cmd = [installed_7z, 'x', first_vol, f'-o{save_dir}', '-y']
                elif os.path.exists(installed_winrar):
                    cmd = [installed_winrar, 'x', '-y', first_vol, f'{save_dir}\\']
                elif os.path.exists(bundled_7z):
                    cmd = [bundled_7z, 'x', first_vol, f'-o{save_dir}', '-y']
            else:
                if shutil.which('7z'):
                    cmd = ['7z', 'x', first_vol, f'-o{save_dir}', '-y']
                elif shutil.which('unrar'):
                    cmd = ['unrar', 'x', first_vol, f'{save_dir}/', '-y']
                
            if not cmd:
                for t in tasks_in_folder:
                    t.status = TaskStatus.EXTRACT_ERROR
                    t.error_message = "No supported extractor was found. Install 7-Zip or WinRAR, then retry extraction."
                if folder_name in self.extracted_folders:
                    self.extracted_folders.remove(folder_name)
                return
                
            creationflags = 0x08000000 if sys.platform == 'win32' else 0
            subprocess.run(
                cmd,
                check=True,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            for t in tasks_in_folder:
                t.status = TaskStatus.EXTRACTED
                t.error_message = ""
            self.trigger_history_save_callback()
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Extraction error (subprocess): {e}", exc_info=True)
            for t in tasks_in_folder:
                t.status = TaskStatus.EXTRACT_ERROR
                t.error_message = f"Extractor failed with exit code {e.returncode}. The archive may be corrupt, incomplete, or password-protected."
            if folder_name in self.extracted_folders:
                self.extracted_folders.remove(folder_name)
            self.trigger_history_save_callback()
        except Exception as e:
            logging.error(f"Extraction error: {e}", exc_info=True)
            for t in tasks_in_folder:
                t.status = TaskStatus.EXTRACT_ERROR
                t.error_message = f"Extraction failed: {format_error_message(e)}"
            if folder_name in self.extracted_folders:
                self.extracted_folders.remove(folder_name)
            self.trigger_history_save_callback()
