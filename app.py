import os
import uuid
import zipfile
import shutil
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from mask_processor import process_preview, generate_export_previews, process_export

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__name__)), 'temp_uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and file.filename.endswith('.3mf'):
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(session_dir, filename)
        file.save(filepath)
        
        return jsonify({'session_id': session_id, 'filename': filename})
        
    return jsonify({'error': 'Invalid file type. Only .3mf allowed.'}), 400

@app.route('/api/preview/<session_id>', methods=['POST'])
def preview(session_id):
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf')]
    if not files: return jsonify({'error': 'No 3mf file found'}), 404
        
    try:
        previews = process_preview(os.path.join(session_dir, files[0]))
        return jsonify({'previews': previews})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview_export/<session_id>', methods=['POST'])
def preview_export(session_id):
    data = request.json
    axes_to_render = data.get('axes', [])
    split_depths = bool(data.get('split_depths', False))
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf')]
    if not files: return jsonify({'error': 'No 3mf file found'}), 404
        
    try:
        layers = generate_export_previews(os.path.join(session_dir, files[0]), axes_to_render, split_depths)
        return jsonify({'layers': layers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/resolume_preview/<session_id>', methods=['POST'])
def resolume_preview(session_id):
    from mask_processor import get_resolume_polygon_data
    data = request.json
    selected_layer_ids = data.get('selected_layers', [])
    width = int(data.get('width', 1920))
    height = int(data.get('height', 1080))
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf')]
    if not files: return jsonify({'error': 'No 3mf file found'}), 404
        
    try:
        polygon_data = get_resolume_polygon_data(os.path.join(session_dir, files[0]), selected_layer_ids, width, height)
        return jsonify({'polygons': polygon_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<session_id>', methods=['POST'])
def export_masks(session_id):
    data = request.json
    layer_configs = data.get('layer_configs', [])
    width = int(data.get('width', 1920))
    height = int(data.get('height', 1080))
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf')]
    if not files: return jsonify({'error': 'No 3mf file found'}), 404
        
    filepath = os.path.join(session_dir, files[0])
    base_name = os.path.splitext(files[0])[0]
    
    export_dir = os.path.join(session_dir, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    
    try:
        exported_files = process_export(filepath, layer_configs, width, height, export_dir, base_name=base_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    zip_filename = f"{base_name}_masks.zip"
    zip_filepath = os.path.join(session_dir, zip_filename)
    
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in exported_files:
            zipf.write(f, os.path.basename(f))
            
    return send_file(zip_filepath, as_attachment=True, download_name=zip_filename)

@app.route('/api/resolume_proxy', methods=['POST'])
def resolume_proxy():
    import urllib.request
    import urllib.error
    import json
    data = request.json
    url = data.get('url', 'http://127.0.0.1:8080/api/v1/composition')
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = response.read()
            return jsonify(json.loads(res_data))
    except urllib.error.URLError as e:
        return jsonify({"error": f"Failed to connect to Resolume: {e.reason}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
