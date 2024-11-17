from O365 import Account
from O365 import Account
from config import ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_BASE_PATH
import os

class CloudStorage:
    def __init__(self):
        self.credentials = (ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET)
        self.account = Account(self.credentials)
        
        # Authenticate on first use
        if not self.account.is_authenticated:
            self.account.authenticate()
        
        self.storage = self.account.storage()
        self.drive = self.storage.get_default_drive()
        
        # Ensure base folder exists
        self._ensure_base_folder()

    def _ensure_base_folder(self):
        """Ensure the base folder exists in OneDrive."""
        try:
            self.drive.get_item_by_path(ONEDRIVE_BASE_PATH)
        except:
            parent = self.drive.root
            for folder in ONEDRIVE_BASE_PATH.strip('/').split('/'):
                try:
                    parent = parent.get_item_by_path(folder)
                except:
                    parent = parent.create_folder(folder)

    def upload_file(self, file_obj, folder_path, filename):
        """Upload a file to OneDrive with token refresh."""
        try:
            return super().upload_file(file_obj, folder_path, filename)
        except Exception as e:
            if 'token expired' in str(e).lower():
                self.refresh_token()
                return super().upload_file(file_obj, folder_path, filename)
            raise

    def download_file(self, file_path):
        """Download a file from OneDrive."""
        full_path = os.path.join(ONEDRIVE_BASE_PATH, file_path)
        try:
            item = self.drive.get_item_by_path(full_path)
            return item.download()
        except Exception as e:
            print(f"Error downloading from OneDrive: {e}")
            raise

    def delete_file(self, file_path):
        """Delete a file from OneDrive."""
        full_path = os.path.join(ONEDRIVE_BASE_PATH, file_path)
        try:
            item = self.drive.get_item_by_path(full_path)
            item.delete()
        except Exception as e:
            print(f"Error deleting from OneDrive: {e}")
            raise    
    
    def delete_file(self, file_path):
        """Delete a file from OneDrive."""
        full_path = os.path.join(ONEDRIVE_BASE_PATH, file_path)
        try:
            item = self.drive.get_item_by_path(full_path)
            item.delete()
        except Exception as e:
            print(f"Error deleting from OneDrive: {e}")
            raise

    def refresh_token(self):
        """Refresh the OAuth token if expired."""
        if self.account.connection.token_backend.token:
            new_token = self.account.connection.refresh_token()
            if new_token:
                session['onedrive_token'] = new_token['access_token']
                session['onedrive_refresh_token'] = new_token.get('refresh_token')