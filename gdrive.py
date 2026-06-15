import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

class GoogleDriveAPI:
    def __init__(self, token_path='token.pickle', credentials_path='credentials.json'):
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        creds = None
        # Check if token file exists
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials don't exist or are invalid
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for future use
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build the service
        self.service = build('drive', 'v3', credentials=creds)
    
    def upload_file(self, file_path, folder_id=None):
        """
        Upload a file to Google Drive
        
        Args:
            file_path: Path to the file to upload
            folder_id: ID of the folder to upload to (None for root)
            
        Returns:
            ID of the uploaded file
        """
        if not self.service:
            self.authenticate()
        
        file_metadata = {
            'name': os.path.basename(file_path)
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(file_path, resumable=True)
        
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id')
    
    def download_file(self, file_id, output_path=None):
        """
        Download a file from Google Drive
        
        Args:
            file_id: ID of the file to download
            output_path: Path where to save the downloaded file
            
        Returns:
            Path to the downloaded file
        """
        if not self.service:
            self.authenticate()
        
        # Get file metadata to determine the filename if output_path is not provided
        file_metadata = self.service.files().get(fileId=file_id).execute()
        file_name = file_metadata.get('name', 'downloaded_file')
        
        if not output_path:
            output_path = file_name
        
        request = self.service.files().get_media(fileId=file_id)
        
        with open(output_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        
        return output_path
    
    def delete_file(self, file_id):
        """
        Delete a file from Google Drive
        
        Args:
            file_id: ID of the file to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            self.authenticate()
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            print(f"An error occurred while deleting file: {e}")
            return False
    
    def list_files(self, folder_id=None, query=None):
        """
        List files in Google Drive
        
        Args:
            folder_id: ID of the folder to list files from (None for root)
            query: Query string to filter files
            
        Returns:
            List of files
        """
        if not self.service:
            self.authenticate()
        
        q = ""
        if folder_id:
            q += f"'{folder_id}' in parents"
        
        if query:
            if q:
                q += " and "
            q += query
        
        results = self.service.files().list(
            q=q, 
            pageSize=100, 
            fields="nextPageToken, files(id, name, mimeType, createdTime)"
        ).execute()
        
        return results.get('files', []) 