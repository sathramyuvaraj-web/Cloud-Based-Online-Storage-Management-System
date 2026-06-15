from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import os
import hashlib

class FileEncryptor:
    def __init__(self, key=None):
        # If no key is provided, generate a random one
        if key is None:
            self.key = get_random_bytes(32)  # 256-bit key for AES-256
        else:
            # If key is a string or hex string, convert it to bytes and hash it to get 32 bytes
            if isinstance(key, str):
                # Try to decode as hex first
                try:
                    key_bytes = bytes.fromhex(key.strip())
                    # If the key is not 32 bytes, hash it
                    if len(key_bytes) != 32:
                        self.key = hashlib.sha256(key_bytes).digest()
                    else:
                        self.key = key_bytes
                except ValueError:
                    # If not hex, treat as regular string
                    self.key = hashlib.sha256(key.encode()).digest()
            elif isinstance(key, bytes):
                # If key is bytes but not 32 bytes long, hash it
                if len(key) != 32:
                    self.key = hashlib.sha256(key).digest()
                else:
                    self.key = key
            else:
                raise ValueError("Key must be a string, hex string, or bytes")
    
    def get_key(self):
        """Get the encryption key in bytes"""
        return self.key
    
    def get_key_hex(self):
        """Get the encryption key as a hex string"""
        return ''.join(f'{b:02x}' for b in self.key)
    
    def encrypt_file(self, input_file_path, output_file_path=None):
        """
        Encrypt a file using AES-256-CBC
        
        Args:
            input_file_path: Path to the file to encrypt
            output_file_path: Path where to save the encrypted file (default: input_file_path + '.enc')
            
        Returns:
            Path to the encrypted file
        """
        if output_file_path is None:
            output_file_path = input_file_path + '.enc'
        
        # Generate a random IV (Initialization Vector)
        iv = get_random_bytes(16)
        
        # Create cipher object
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        
        try:
            # Read the entire file into memory
            with open(input_file_path, 'rb') as infile:
                data = infile.read()
            
            # Pad the data
            padded_data = pad(data, AES.block_size)
            
            # Encrypt the data
            encrypted_data = cipher.encrypt(padded_data)
            
            # Write IV and encrypted data
            with open(output_file_path, 'wb') as outfile:
                outfile.write(iv)
                outfile.write(encrypted_data)
            
            return output_file_path
        
        except Exception as e:
            if os.path.exists(output_file_path):
                os.remove(output_file_path)
            raise
    
    def decrypt_file(self, input_file_path, output_file_path=None):
        """
        Decrypt a file using AES-256-CBC
        
        Args:
            input_file_path: Path to the encrypted file
            output_file_path: Path where to save the decrypted file
                            (default: remove .enc extension if present or add .dec)
            
        Returns:
            Path to the decrypted file
        """
        if output_file_path is None:
            # Remove .enc extension if present
            if input_file_path.endswith('.enc'):
                output_path = input_file_path[:-4]
            else:
                output_path = input_file_path + '.dec'
        else:
            output_path = output_file_path
        
        try:
            # Read the entire file
            with open(input_file_path, 'rb') as infile:
                # Read the IV from the beginning of the file
                iv = infile.read(16)
                # Read the rest of the file
                encrypted_data = infile.read()
            
            # Create cipher object for decryption
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            
            # Decrypt and unpad the data
            decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
            
            # Write the decrypted data
            with open(output_path, 'wb') as outfile:
                outfile.write(decrypted_data)
            
            return output_path
        
        except Exception as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise 