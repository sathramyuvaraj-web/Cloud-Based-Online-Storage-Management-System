import socket
import os
import json
import sys
import traceback
import time
import ssl
import hashlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server.encryption import FileEncryptor

class FileClient:
    def __init__(self, host='localhost', port=5000, download_dir='downloads'):
        self.host = host
        self.port = port
        self.download_dir = download_dir
        self.sock = None
        self.connected = False
        self.gdrive_files = []
        self.saved_keys = {}  
        
        # SSL 
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.load_verify_locations('server.crt')
        
        
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
    
    def calculate_checksum(self, file_path):
        """Calculate SHA256 checksum of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def connect(self):
        """Connect to the server with retry"""
        max_retries = 3
        retry_delay = 1  
        
        for attempt in range(max_retries):
            try:
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                
                
                plain_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                plain_sock.settimeout(30)
                
                
                self.sock = self.ssl_context.wrap_socket(
                    plain_sock,
                    server_hostname=self.host
                )
                self.sock.connect((self.host, self.port))
                self.connected = True
                print(f"Connected to server at {self.host}:{self.port}")
                return True
            
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Failed to connect, retrying in {retry_delay}s... ({e})")
                    time.sleep(retry_delay)
                    continue
                print(f"Failed to connect after {max_retries} attempts: {e}")
                self.connected = False
                return False
        
        return False
    
    def disconnect(self):
        """Disconnect from the server"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
            self.connected = False
            print("Disconnected from server")
    
    def reconnect(self):
        """Try to reconnect to the server"""
        print("Attempting to reconnect...")
        self.disconnect()
        return self.connect()
    
    def send_message(self, message_data):
        """Send a message to the server with retry"""
        if not self.connected:
            if not self.connect():
                return None
        
        max_retries = 3
        retry_delay = 1  
        
        for attempt in range(max_retries):
            try:
                
                message_json = json.dumps(message_data)
                message_bytes = message_json.encode('utf-8')
                
                
                msg_len = len(message_bytes)
                self.sock.sendall(msg_len.to_bytes(4, byteorder='big'))
                

                self.sock.sendall(message_bytes)
                
                
                return self.receive_response()
            
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    print(f"Connection error, attempting to reconnect... ({e})")
                    if self.reconnect():
                        continue
                print(f"Failed to send message after {max_retries} attempts")
                self.disconnect()
                return None
            
            except Exception as e:
                print(f"Error sending message: {e}")
                traceback.print_exc()
                self.disconnect()
                return None
        
        return None
    
    def receive_response(self):
        """Receive a response from the server with timeout"""
        try:
            
            msg_len_bytes = self.sock.recv(4)
            if not msg_len_bytes:
                raise ConnectionError("Connection closed by server")
            
            msg_len = int.from_bytes(msg_len_bytes, byteorder='big')
            
            
            message = b''
            bytes_received = 0
            
            while bytes_received < msg_len:
                try:
                    chunk = self.sock.recv(min(4096, msg_len - bytes_received))
                    if not chunk:
                        raise ConnectionError("Connection lost while receiving response")
                    message += chunk
                    bytes_received += len(chunk)
                except socket.timeout:
                    print("Timeout while receiving response, retrying...")
                    continue
            
            if not message:
                raise ConnectionError("Empty response received")
            
            
            response_data = json.loads(message.decode('utf-8'))
            return response_data
        
        except Exception as e:
            print(f"Error receiving response: {e}")
            traceback.print_exc()
            self.disconnect()
            return None
    
    def upload_file(self, file_path):
        """Upload a file to the server"""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
        
        file_size = os.path.getsize(file_path)
        checksum = self.calculate_checksum(file_path)
        
        
        response = self.send_message({
            'command': 'upload',
            'filename': os.path.basename(file_path),
            'file_size': file_size,
            'checksum': checksum
        })
        
        if not response or response.get('status') != 'ready':
            print(f"Failed to initiate upload: {response.get('message') if response else 'No response'}")
            return False
        
        try:
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    self.sock.sendall(chunk)
            

            response = self.receive_response()
            
            if not response or response.get('status') != 'success':
                print(f"Upload failed: {response.get('message') if response else 'No response'}")
                return False
            
            print(f"Upload successful: {response.get('message')}")
            
            
            if 'checksum' in response and response['checksum'] != checksum:
                print("Warning: Server checksum doesn't match local checksum")
            
            
            if 'gdrive_file_id' in response and 'key' in response:
                self.saved_keys[response['gdrive_file_id']] = response['key']
                print(f"Saved encryption key for file ID: {response['gdrive_file_id']}")
            
            return True
        
        except Exception as e:
            print(f"Error during upload: {e}")
            traceback.print_exc()
            self.disconnect()
            return False
    
    def download_file(self, gdrive_file_id, output_path=None):
        """Download a file from the server"""
        if not gdrive_file_id:
            print("Missing Google Drive file ID")
            return False
        
        
        encryption_key = self.saved_keys.get(gdrive_file_id)
        if not encryption_key:
            print("Warning: No encryption key found for this file")
        
        
        response = self.send_message({
            'command': 'download',
            'gdrive_file_id': gdrive_file_id,
            'key': encryption_key,
            'checksum': self.saved_keys.get(gdrive_file_id + '_checksum') if encryption_key else None
        })
        
        if not response or response.get('status') != 'ready':
            print(f"Failed to initiate download: {response.get('message') if response else 'No response'}")
            return False
        
        try:
            file_size = response.get('file_size')
            filename = response.get('filename')
            server_checksum = response.get('checksum')
            
            
            temp_path = os.path.join(self.download_dir, f"temp_{filename}")
            
            if not output_path:
                if filename.endswith('.enc'):
                    original_filename = filename[:-4]  
                else:
                    original_filename = filename
                output_path = os.path.join(self.download_dir, original_filename)
            
            print(f"Downloading {os.path.basename(output_path)}...")
            
            
            with open(temp_path, 'wb') as f:
                bytes_received = 0
                
                while bytes_received < file_size:
                    # data in chunks
                    chunk_size = min(4096, file_size - bytes_received)
                    chunk = self.sock.recv(chunk_size)
                    
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    bytes_received += len(chunk)
            
            
            if bytes_received != file_size:
                print("Incomplete file transfer")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            

            if server_checksum:
                local_checksum = self.calculate_checksum(temp_path)
                if local_checksum != server_checksum:
                    print("Checksum verification failed - file may be corrupted")
                    os.remove(temp_path)
                    return False
            
            
            response = self.receive_response()
            
            if not response or response.get('status') != 'success':
                print(f"Download failed: {response.get('message') if response else 'No response'}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            

            if encryption_key:
                try:
                    print("Decrypting file...")

                    decryptor = FileEncryptor(encryption_key)
                    

                    decryptor.decrypt_file(temp_path, output_path)
                    
                    
                    os.remove(temp_path)
                    

                    if 'checksum' in response:
                        decrypted_checksum = self.calculate_checksum(output_path)
                        if decrypted_checksum != response['checksum']:
                            print("Warning: Decrypted file checksum doesn't match expected checksum")
                    
                    print(f"Successfully downloaded and decrypted: {output_path}")
                except Exception as e:
                    print(f"Error decrypting file: {e}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    return False
            else:
                
                os.rename(temp_path, output_path)
                print(f"Warning: No encryption key found. File remains encrypted: {output_path}")
            
            return True
        
        except Exception as e:
            print(f"Error during download: {e}")
            traceback.print_exc()
            self.disconnect()
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
    
    def list_files(self):
        """List files available on the server"""
        response = self.send_message({
            'command': 'list'
        })
        
        if not response or response.get('status') != 'success':
            print(f"Failed to list files: {response.get('message') if response else 'No response'}")
            return []
        
        files = response.get('files', [])
        self.gdrive_files = files
        
        return files
    
    def save_keys_to_file(self, file_path='file_keys.json'):
        """Save encryption keys to a file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(self.saved_keys, f, indent=2)
            print(f"Saved encryption keys to {file_path}")
            return True
        except Exception as e:
            print(f"Error saving encryption keys: {e}")
            return False
    
    def load_keys_from_file(self, file_path='file_keys.json'):
        """Load encryption keys from a file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    self.saved_keys = json.load(f)
                print(f"Loaded encryption keys from {file_path}")
                return True
            else:
                print(f"Keys file not found: {file_path}")
                return False
        except Exception as e:
            print(f"Error loading encryption keys: {e}")
            return False

if __name__ == "__main__":
    client = FileClient()
    client.connect()