#!/usr/bin/env python
import os
import sys
import argparse
from server.encryption import FileEncryptor

def main():
    parser = argparse.ArgumentParser(description='Test AES encryption/decryption')
    parser.add_argument('action', choices=['encrypt', 'decrypt'], help='Action to perform')
    parser.add_argument('file_path', help='Path to the file to encrypt/decrypt')
    parser.add_argument('--output', '-o', help='Output file path (optional)')
    parser.add_argument('--key', '-k', help='Hex encryption key (required for decryption)')
    
    args = parser.parse_args()
    
    if args.action == 'encrypt':
        # Create encryptor (generates a random key)
        encryptor = FileEncryptor()
        
        # Encrypt the file
        output_path = encryptor.encrypt_file(args.file_path, args.output)
        
        # Print the key for later decryption
        print(f"Encrypted file saved to: {output_path}")
        print(f"Encryption key (save this for decryption): {encryptor.get_key_hex()}")
    
    elif args.action == 'decrypt':
        if not args.key:
            print("Error: Decryption requires a key (use --key)")
            sys.exit(1)
        
        try:
            # Create encryptor with the provided key
            decryptor = FileEncryptor(args.key)
            
            # Decrypt the file
            output_path = decryptor.decrypt_file(args.file_path, args.output)
            
            print(f"Decrypted file saved to: {output_path}")
        
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    main() 