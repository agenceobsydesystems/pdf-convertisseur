#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import os
import uuid
from datetime import datetime, timedelta
import io
import base64
from functools import wraps
import mimetypes
import unicodedata
import re
import requests
import json

app = Flask(__name__)
CORS(app)

# Configuration
PRIMARY_API_KEY = os.environ.get('PRIMARY_API_KEY', 'pk_live_mega_converter_primary_key_2024_super_secure_token_xyz789')
SECONDARY_API_KEY = os.environ.get('SECONDARY_API_KEY', 'sk_live_mega_converter_secondary_key_2024_ultra_secure_token_abc456')
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 180 * 1024 * 1024))
FILE_EXPIRY_HOURS = int(os.environ.get('FILE_EXPIRY_HOURS', 24))
BASE_URL = os.environ.get('BASE_URL', 'https://pdf-converter-server-production.up.railway.app')

# Stockage sur disque persistant
DATA_DIR = '/data/files'
METADATA_FILE = '/data/metadata.json'
os.makedirs(DATA_DIR, exist_ok=True)

def load_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Erreur lecture metadata: {e}")
            return {}
    return {}

def save_metadata(metadata):
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Erreur sauvegarde metadata: {e}")

# Tous les formats acceptés
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'ico', 'svg', 'tiff', 'tif',
    'pdf', 'txt', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp',
    'html', 'htm', 'css', 'js', 'json', 'xml',
    'csv', 'md', 'rtf', 'tex',
    'zip', 'rar', '7z', 'tar', 'gz',
    'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'm4v',
    'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a',
    'exe', 'dmg', 'apk', 'deb', 'rpm'
}

def sanitize_filename(filename):
    if '.' in filename:
        name, ext = filename.rsplit('.', 1)
    else:
        name, ext = filename, ''
    
    name = unicodedata.normalize('NFKD', name)
    name = ''.join([c for c in name if not unicodedata.combining(c)])
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '_', name)
    name = name[:50]
    
    if ext:
        return f"{name}.{ext}"
    return name

def cleanup_old_files():
    metadata = load_metadata()
    expired = []
    
    for file_id, data in metadata.items():
        try:
            expiry = datetime.fromisoformat(data['expiry'])
            if datetime.now() > expiry:
                expired.append(file_id)
                if os.path.exists(data['file_path']):
                    os.remove(data['file_path'])
                    print(f"[DELETE] Fichier expire supprime: {file_id}")
        except Exception as e:
            print(f"[ERROR] Erreur cleanup {file_id}: {e}")
    
    for key in expired:
        del metadata[key]
    
    if expired:
        save_metadata(metadata)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            api_key = request.args.get('api_key')
        if not api_key and request.form:
            api_key = request.form.get('api_key')
        
        if api_key not in [PRIMARY_API_KEY, SECONDARY_API_KEY]:
            return jsonify({
                "error": "Clé API invalide ou manquante",
                "message": "Utilisez une des deux clés API valides"
            }), 401
        
        request.api_key_type = "primary" if api_key == PRIMARY_API_KEY else "secondary"
        return f(*args, **kwargs)
    return decorated_function

def store_file(content, filename, content_type=None):
    cleanup_old_files()
    
    file_id = str(uuid.uuid4())
    expiry = datetime.now() + timedelta(hours=FILE_EXPIRY_HOURS)
    clean_filename = sanitize_filename(filename)
    
    print(f"[INFO] Nom original: {filename}")
    print(f"[INFO] Nom nettoye: {clean_filename}")
    
    if not content_type:
        content_type = mimetypes.guess_type(clean_filename)[0] or 'application/octet-stream'
    
    file_path = os.path.join(DATA_DIR, f"{file_id}_{clean_filename}")
    
    try:
        with open(file_path, 'wb') as f:
            f.write(content if isinstance(content, bytes) else content.encode())
        print(f"[OK] Fichier sauvegarde: {file_path}")
    except Exception as e:
        print(f"[ERROR] Erreur sauvegarde fichier: {e}")
        raise
    
    metadata = load_metadata()
    metadata[file_id] = {
        'filename': clean_filename,
        'original_filename': filename,
        'content_type': content_type,
        'expiry': expiry.isoformat(),
        'created': datetime.now().isoformat(),
        'size': len(content),
        'file_path': file_path
    }
    save_metadata(metadata)
    
    return f"{BASE_URL}/download/{file_id}"

def get_file_extension(filename):
    if not filename or '.' not in filename:
        return None
    return filename.rsplit('.', 1)[1].lower()

@app.route('/')
def home():
    cleanup_old_files()
    
    return jsonify({
        "service": "[FILE] Storage API - Stockage de fichiers avec URLs",
        "version": "1.3",
        "status": "[OK] Operationnel",
        "storage_type": "persistent_disk",
        "description": "Upload n'importe quel fichier et obtenez une URL de telechargement",
        "features": {
            "file_storage": "[OK] Stockage persistant sur disque",
            "temporary_urls": "[OK] URLs temporaires securisees",
            "all_formats": "[OK] Images, PDF, videos, documents, etc.",
            "url_download": "[OK] Telechargement depuis URL externe",
            "return_binary": "[OK] Option retour binaire direct",
            "dual_api_keys": "[OK] Primary & Secondary keys",
            "auto_cleanup": f"[OK] Suppression apres {FILE_EXPIRY_HOURS}h",
            "max_file_size": f"[OK] Jusqu'a {MAX_FILE_SIZE / (1024*1024)}MB"
        },
        "endpoints": {
            "POST /upload": "Upload un fichier",
            "POST /upload-from-url": "Telecharger depuis URL externe",
            "POST /convert": "Upload un fichier (alias)",
            "GET /download/{id}": "Telecharger un fichier",
            "GET /info/{id}": "Infos sur un fichier",
            "GET /health": "Verification sante",
            "GET /status": "Statut du service"
        }
    })

@app.route('/health')
def health():
    metadata = load_metadata()
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage_count": len(metadata)
    })

@app.route('/upload', methods=['POST'])
@app.route('/convert', methods=['POST'])
@require_api_key
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier fourni"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nom de fichier vide"}), 400
        
        file_content = file.read()
        if len(file_content) > MAX_FILE_SIZE:
            return jsonify({
                "error": "Fichier trop volumineux",
                "max_size_mb": MAX_FILE_SIZE / (1024 * 1024)
            }), 413
        
        filename = file.filename
        file_ext = get_file_extension(filename)
        
        if file_ext and file_ext not in ALLOWED_EXTENSIONS:
            print(f"[WARNING] Extension non standard: {file_ext}")
        
        download_url = store_file(file_content, filename, file.content_type)
        
        file_info = {
            "success": True,
            "filename": sanitize_filename(filename),
            "original_filename": filename,
            "download_url": download_url,
            "direct_url": download_url,
            "file_id": download_url.split('/')[-1],
            "format": file_ext or "unknown",
            "size_bytes": len(file_content),
            "size_mb": round(len(file_content) / (1024 * 1024), 2),
            "content_type": file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "uploaded_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=FILE_EXPIRY_HOURS)).isoformat(),
            "expiry_hours": FILE_EXPIRY_HOURS,
            "api_key_used": request.api_key_type,
            "message": f"[OK] Fichier uploade! URL valide pendant {FILE_EXPIRY_HOURS}h"
        }
        
        return jsonify(file_info)
        
    except Exception as e:
        print(f"[ERROR] Erreur upload: {e}")
        return jsonify({"error": f"Erreur: {str(e)}"}), 500

@app.route('/upload-from-url', methods=['POST'])
@require_api_key
def upload_from_url():
    try:
        content_type = request.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        if not data or 'url' not in data:
            return jsonify({"error": "URL manquante"}), 400
        
        file_url = data['url']
        return_binary = data.get('return_binary', False)
        if isinstance(return_binary, str):
            return_binary = return_binary.lower() in ['true', '1', 'yes']
        
        if not file_url.startswith(('http://', 'https://')):
            return jsonify({"error": "URL invalide"}), 400
        
        print(f"[INFO] Telechargement depuis URL: {file_url}")
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(file_url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        filename = 'download'
        if 'content-disposition' in response.headers:
            match = re.search(r'filename[^;=\n]*=([\'\"]?)([^\'\"\n]*)\1', response.headers['content-disposition'])
            if match:
                filename = match.group(2)
        
        if filename == 'download':
            url_path = file_url.split('?')[0]
            url_filename = url_path.split('/')[-1]
            if url_filename and '.' in url_filename:
                filename = url_filename
        
        if 'filename' in data and data['filename']:
            filename = data['filename']
        
        content = response.content
        if len(content) > MAX_FILE_SIZE:
            return jsonify({"error": "Fichier trop volumineux"}), 413
        
        content_type = response.headers.get('content-type', 'application/octet-stream')
        
        if return_binary:
            return Response(
                content,
                mimetype=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{sanitize_filename(filename)}"',
                    'Content-Type': content_type
                }
            )
        
        download_url = store_file(content, filename, content_type)
        file_ext = get_file_extension(filename)
        
        return jsonify({
            "success": True,
            "source_url": file_url,
            "filename": sanitize_filename(filename),
            "original_filename": filename,
            "download_url": download_url,
            "file_id": download_url.split('/')[-1],
            "format": file_ext or "unknown",
            "size_bytes": len(content),
            "size_mb": round(len(content) / (1024 * 1024), 2),
            "content_type": content_type,
            "uploaded_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=FILE_EXPIRY_HOURS)).isoformat(),
            "message": f"[OK] Fichier telecharge! Valide {FILE_EXPIRY_HOURS}h"
        })
        
    except Exception as e:
        print(f"[ERROR] Erreur upload-from-url: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<file_id>')
def download(file_id):
    cleanup_old_files()
    metadata = load_metadata()
    
    if file_id not in metadata:
        return jsonify({"error": "Fichier non trouvé ou expiré"}), 404
    
    file_data = metadata[file_id]
    
    expiry = datetime.fromisoformat(file_data['expiry'])
    if datetime.now() > expiry:
        if os.path.exists(file_data['file_path']):
            os.remove(file_data['file_path'])
        del metadata[file_id]
        save_metadata(metadata)
        return jsonify({"error": "Fichier expiré"}), 404
    
    if not os.path.exists(file_data['file_path']):
        return jsonify({"error": "Fichier physique non trouvé"}), 404
    
    try:
        with open(file_data['file_path'], 'rb') as f:
            content = f.read()
        
        return Response(
            content,
            mimetype=file_data['content_type'],
            headers={
                'Content-Disposition': f'attachment; filename="{file_data["filename"]}"',
                'Content-Type': file_data['content_type']
            }
        )
    except Exception as e:
        print(f"[ERROR] Erreur lecture fichier: {e}")
        return jsonify({"error": "Erreur lecture fichier"}), 500

@app.route('/info/<file_id>')
def file_info(file_id):
    metadata = load_metadata()
    
    if file_id not in metadata:
        return jsonify({"error": "Fichier non trouvé"}), 404
    
    file_data = metadata[file_id]
    expiry = datetime.fromisoformat(file_data['expiry'])
    time_left = expiry - datetime.now()
    
    return jsonify({
        "filename": file_data['filename'],
        "original_filename": file_data.get('original_filename', file_data['filename']),
        "content_type": file_data['content_type'],
        "size_bytes": file_data['size'],
        "size_mb": round(file_data['size'] / (1024 * 1024), 2),
        "created": file_data['created'],
        "expires_at": file_data['expiry'],
        "expires_in_hours": max(0, time_left.total_seconds() / 3600),
        "download_url": f"{BASE_URL}/download/{file_id}"
    })

@app.route('/status')
def status():
    cleanup_old_files()
    metadata = load_metadata()
    total_size = sum(data['size'] for data in metadata.values())
    
    files_list = []
    for file_id, data in list(metadata.items())[:20]:
        expiry = datetime.fromisoformat(data['expiry'])
        time_left = expiry - datetime.now()
        files_list.append({
            "id": file_id,
            "filename": data['filename'],
            "size_mb": round(data['size'] / (1024 * 1024), 2),
            "type": data['content_type'],
            "expires_in_hours": max(0, time_left.total_seconds() / 3600)
        })
    
    return jsonify({
        "status": "operational",
        "version": "1.3",
        "storage": {
            "type": "persistent_disk",
            "files_count": len(metadata),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": files_list
        },
        "limits": {
            "max_file_size_mb": MAX_FILE_SIZE / (1024 * 1024),
            "file_expiry_hours": FILE_EXPIRY_HOURS
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/qrcode', methods=['POST'])
@require_api_key
def qrcode_compat():
    return jsonify({
        "error": "Cette fonctionnalité n'est plus disponible",
        "message": "Utilisez /upload pour stocker n'importe quel fichier"
    }), 501

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint non trouvé"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Erreur serveur interne"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    
    print("="*60)
    print("[FILE] STORAGE SERVER - Serveur stockage persistant")
    print("="*60)
    print(f"[OK] Port: {port}")
    print(f"[OK] Taille max: {MAX_FILE_SIZE / (1024*1024)} MB")
    print(f"[OK] Expiration: {FILE_EXPIRY_HOURS} heures")
    print(f"[OK] URL de base: {BASE_URL}")
    print("="*60)
    print("[VOLUME] Verification du volume /data")
    if os.path.exists('/data'):
        print(f"[OK] Volume /data monte correctement")
        print(f"[OK] Dossier files: {DATA_DIR}")
        if os.path.exists(DATA_DIR):
            files = os.listdir(DATA_DIR)
            print(f"[OK] {len(files)} fichiers existants")
    else:
        print(f"[ERROR] Volume /data NON TROUVÉ!")
    print("="*60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
