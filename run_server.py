#!/usr/bin/env python
import sys
import argparse
from server import FileServer

def main():
    parser = argparse.ArgumentParser(description='Secure File Transfer Server')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host address to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--upload-dir', type=str, default='uploads', help='Directory to store uploaded files')
    parser.add_argument('--no-gdrive', action='store_true', help='Disable Google Drive integration')
    
    args = parser.parse_args()
    
    print(f"Starting server on {args.host}:{args.port}")
    print(f"Upload directory: {args.upload_dir}")
    print(f"Google Drive integration: {'Disabled' if args.no_gdrive else 'Enabled'}")
    
    server = FileServer(
        host=args.host,
        port=args.port,
        upload_dir=args.upload_dir,
        gdrive_enabled=not args.no_gdrive
    )
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    finally:
        server.stop()

if __name__ == "__main__":
    main() 