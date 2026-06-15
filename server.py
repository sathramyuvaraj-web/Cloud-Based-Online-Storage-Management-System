import socket
import threading
import os
import json
import sys
import traceback
import time
import ssl
import hashlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from encryption import FileEncryptor
from gdrive import GoogleDriveAPI

class FileServer:
    def __init__(self, host='0.0.0.0', port=5000, upload_dir='uploads', gdrive_enabled=True):
        self.host = host
        self.port = port
        self.upload_dir = upload_dir
        self.gdrive_enabled = gdrive_enabled
        self.sock = None
        self.clients = []
        self.running = False
        
        # SSL Configuration
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.load_cert_chain('server.crt', 'server.key')
        
       
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
        
       
        self.gdrive = None
        if self.gdrive_enabled:
            try:
                self.gdrive = GoogleDriveAPI()
            except Exception as e:
                print(f"Failed to initialize Google Drive API: {e}")
                self.gdrive_enabled = False
    
    def calculate_checksum(self, file_path):
        """Calculate SHA256 checksum of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def start(self):
        """Start the server"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        
        print(f"Server started on {self.host}:{self.port}")
        
        try:
            while self.running:
                client, address = self.sock.accept()
                print(f"Client connected: {address}")
                
                # Wrap socket with SSL
                secure_sock = self.ssl_context.wrap_socket(client, server_side=True)
                self.clients.append(secure_sock)
                
                # Start a new thread to handle the client
                client_thread = threading.Thread(target=self.handle_client, args=(secure_sock, address))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        
      
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        
       
        if self.sock:
            self.sock.close()
        
        print("Server stopped")
    
    def handle_client(self, client, address):
        """Handle client connection"""
        try:
            while self.running:
                try:
                    
                    msg_len_bytes = client.recv(4)
                    if not msg_len_bytes:
                        print(f"Client {address} disconnected")
                        break
                    
                    msg_len = int.from_bytes(msg_len_bytes, byteorder='big')
                    
                   
                    message = b''
                    bytes_received = 0
                    
                    while bytes_received < msg_len:
                        try:
                            chunk = client.recv(min(4096, msg_len - bytes_received))
                            if not chunk:
                                raise ConnectionError("Connection lost while receiving message")
                            message += chunk
                            bytes_received += len(chunk)
                        except socket.timeout:
                            print(f"Timeout while receiving from {address}")
                            continue
                        except ConnectionError as e:
                            print(f"Connection error with {address}: {e}")
                            raise
                    
                    if not message:
                        break
                    
                    try:
                       
                        message_data = json.loads(message.decode('utf-8'))
                        command = message_data.get('command')
                        
                        if command == 'upload':
                            self.handle_upload(client, message_data)
                        elif command == 'download':
                            self.handle_download(client, message_data)
                        elif command == 'list':
                            self.handle_list(client)
                        else:
                            self.send_response(client, {'status': 'error', 'message': 'Unknown command'})
                    
                    except json.JSONDecodeError:
                        self.send_response(client, {'status': 'error', 'message': 'Invalid JSON format'})
                    except Exception as e:
                        print(f"Error handling message from {address}: {e}")
                        traceback.print_exc()
                        self.send_response(client, {'status': 'error', 'message': str(e)})
                
                except ConnectionError as e:
                    print(f"Connection lost with {address}: {e}")
                    break
                except Exception as e:
                    print(f"Error handling client {address}: {e}")
                    traceback.print_exc()
                    try:
                        self.send_response(client, {'status': 'error', 'message': 'Internal server error'})
                    except:
                        pass
                    break
        
        finally:
           
            if client in self.clients:
                self.clients.remove(client)
            try:
                client.close()
            except:
                pass
            print(f"Client disconnected: {address}")
    
    def handle_upload(self, client, message_data):
        """Handle file upload from client"""
        filename = message_data.get('filename')
        file_size = message_data.get('file_size')
        
        if not filename or file_size is None:
            self.send_response(client, {'status': 'error', 'message': 'Missing filename or file_size'})
            return
        
       
        base_name = os.path.basename(filename)
        file_path = os.path.join(self.upload_dir, base_name)
        
        
        self.send_response(client, {'status': 'ready', 'file_path': file_path})
        
       
        with open(file_path, 'wb') as f:
            bytes_received = 0
            
            while bytes_received < file_size:
               
                chunk_size = min(4096, file_size - bytes_received)
                chunk = client.recv(chunk_size)
                
                if not chunk:
                    break
                
                f.write(chunk)
                bytes_received += len(chunk)
        
        
        checksum = self.calculate_checksum(file_path)
        
        
        if bytes_received != file_size:
            self.send_response(client, {'status': 'error', 'message': 'Incomplete file transfer'})
            os.remove(file_path)
            return
        
       
        gdrive_file_id = None
        if self.gdrive_enabled and self.gdrive:
            try:
                
                encryptor = FileEncryptor()
                encrypted_file_path = encryptor.encrypt_file(file_path)
                
                
                gdrive_file_id = self.gdrive.upload_file(encrypted_file_path)
                
                
                os.remove(encrypted_file_path)
                
                
                os.remove(file_path)
                
                self.send_response(client, {
                    'status': 'success',
                    'message': 'File uploaded to Google Drive',
                    'gdrive_file_id': gdrive_file_id,
                    'key': encryptor.get_key().hex(),  
                    'checksum': checksum  
                })
            
            except Exception as e:
                print(f"Error uploading to Google Drive: {e}")
                traceback.print_exc()
                self.send_response(client, {'status': 'error', 'message': f'Error uploading to Google Drive: {str(e)}'})
                return
        else:
            
            self.send_response(client, {
                'status': 'success', 
                'message': 'File uploaded to server',
                'checksum': checksum
            })
    
    def handle_download(self, client, message_data):
        """Handle file download request from client"""
        gdrive_file_id = message_data.get('gdrive_file_id')
        encryption_key = message_data.get('key')
        client_checksum = message_data.get('checksum')
        
        if not gdrive_file_id:
            self.send_response(client, {'status': 'error', 'message': 'Missing gdrive_file_id'})
            return
        
        try:
            
            if encryption_key:
                try:
                    key = bytes.fromhex(encryption_key)
                except ValueError as e:
                    self.send_response(client, {'status': 'error', 'message': f'Invalid encryption key format: {str(e)}'})
                    return
            else:
                key = None
            
          
            if self.gdrive_enabled and self.gdrive:
                try:
                   
                    temp_file_path = os.path.join(self.upload_dir, f"temp_{gdrive_file_id}")
                    self.gdrive.download_file(gdrive_file_id, temp_file_path)
                    
                    
                    if client_checksum:
                        server_checksum = self.calculate_checksum(temp_file_path)
                        if server_checksum != client_checksum:
                            os.remove(temp_file_path)
                            self.send_response(client, {'status': 'error', 'message': 'Checksum mismatch'})
                            return
                    
                    
                    file_size = os.path.getsize(temp_file_path)
                    
                    
                    self.send_response(client, {
                        'status': 'ready',
                        'file_size': file_size,
                        'filename': os.path.basename(temp_file_path),
                        'checksum': self.calculate_checksum(temp_file_path)
                    })
                    
                    
                    with open(temp_file_path, 'rb') as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            client.sendall(chunk)
                    
                    
                    os.remove(temp_file_path)
                    
                    self.send_response(client, {'status': 'success', 'message': 'File downloaded from Google Drive'})
                except Exception as e:
                    print(f"Error downloading from Google Drive: {e}")
                    traceback.print_exc()
                    self.send_response(client, {'status': 'error', 'message': f'Error downloading from Google Drive: {str(e)}'})
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
            else:
                self.send_response(client, {'status': 'error', 'message': 'Google Drive integration not enabled'})
        
        except Exception as e:
            print(f"Error downloading file: {e}")
            traceback.print_exc()
            self.send_response(client, {'status': 'error', 'message': f'Error downloading file: {str(e)}'})
    
    def handle_list(self, client):
        """Handle list files request from client"""
        if self.gdrive_enabled and self.gdrive:
            try:
                files = self.gdrive.list_files()
                self.send_response(client, {'status': 'success', 'files': files})
            except Exception as e:
                print(f"Error listing files: {e}")
                traceback.print_exc()
                self.send_response(client, {'status': 'error', 'message': f'Error listing files: {str(e)}'})
        else:
            self.send_response(client, {'status': 'error', 'message': 'Google Drive integration not enabled'})
    
    def send_response(self, client, response_data):
        """Send a response to the client with retry"""
        max_retries = 3
        retry_delay = 1  
        
        for attempt in range(max_retries):
            try:
                response_json = json.dumps(response_data)
                response_bytes = response_json.encode('utf-8')
                
                
                msg_len = len(response_bytes)
                client.sendall(msg_len.to_bytes(4, byteorder='big'))
                
                
                client.sendall(response_bytes)
                return True
            
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    print(f"Connection error while sending response, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                raise
            except Exception as e:
                print(f"Error sending response: {e}")
                traceback.print_exc()
                break
        
        return False

if __name__ == "__main__":
    server = FileServer()
    server.start()