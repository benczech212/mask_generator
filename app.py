import os
import uuid
import zipfile
import shutil
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from mask_processor import generate_export_previews, process_export, get_scene_hierarchy

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
        
    if file and (file.filename.endswith('.3mf') or file.filename.endswith('.obj') or file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(session_dir, filename)
        file.save(filepath)
        
        try:
            hierarchy = get_scene_hierarchy(filepath)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Failed to parse scene: {str(e)}'}), 500
            
        return jsonify({'session_id': session_id, 'filename': filename, 'hierarchy': hierarchy})
        
    return jsonify({'error': 'Invalid file type. Only .3mf, .obj, and .step allowed.'}), 400



@app.route('/api/preview_export/<session_id>', methods=['POST'])
def preview_export(session_id):
    data = request.json
    selected_nodes = data.get('selected_nodes', [])
    hidden_groups = data.get('hidden_groups', [])
    hidden_bodies = data.get('hidden_bodies', [])
    camera_settings = data.get('camera_settings', None)
    ortho_settings = data.get('ortho_settings', None)
    cull_backfaces = data.get('cull_backfaces', True)
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf') or f.endswith('.obj') or f.endswith('.step') or f.endswith('.stp')]
    if not files: return jsonify({'error': 'No model file found'}), 404
        
    try:
        layers = generate_export_previews(os.path.join(session_dir, files[0]), selected_nodes, hidden_groups, hidden_bodies, camera_settings, ortho_settings=ortho_settings, cull_backfaces=cull_backfaces)
        return jsonify({'layers': layers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/resolume_preview/<session_id>', methods=['POST'])
def resolume_preview(session_id):
    from mask_processor import get_resolume_polygon_data
    data = request.json
    selected_nodes = data.get('selected_nodes', [])
    width = int(data.get('width', 1920))
    height = int(data.get('height', 1080))
    hidden_groups = data.get('hidden_groups', [])
    hidden_bodies = data.get('hidden_bodies', [])
    camera_settings = data.get('camera_settings', None)
    ortho_settings = data.get('ortho_settings', None)
    cull_backfaces = data.get('cull_backfaces', True)
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf') or f.endswith('.obj') or f.endswith('.step') or f.endswith('.stp')]
    if not files: return jsonify({'error': 'No model file found'}), 404
    
    try:
        polygon_data = get_resolume_polygon_data(os.path.join(session_dir, files[0]), selected_nodes, width, height, hidden_groups, hidden_bodies, camera_settings, is_layer_ids=True, ortho_settings=ortho_settings, cull_backfaces=cull_backfaces)
        return jsonify({'polygons': polygon_data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<session_id>', methods=['POST'])
def export_masks(session_id):
    data = request.json
    layer_configs = data.get('layer_configs', [])
    width = int(data.get('width', 1920))
    height = int(data.get('height', 1080))
    hidden_groups = data.get('hidden_groups', [])
    hidden_bodies = data.get('hidden_bodies', [])
    camera_settings = data.get('camera_settings', None)
    ortho_settings = data.get('ortho_settings', None)
    cull_backfaces = data.get('cull_backfaces', True)
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
        
    files = [f for f in os.listdir(session_dir) if f.endswith('.3mf') or f.endswith('.obj') or f.endswith('.step') or f.endswith('.stp')]
    if not files: return jsonify({'error': 'No model file found'}), 404
        
    filepath = os.path.join(session_dir, files[0])
    base_name = os.path.splitext(files[0])[0]
    
    export_dir = os.path.join(session_dir, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    
    try:
        exported_files = process_export(filepath, layer_configs, width, height, export_dir, base_name=base_name, hidden_groups=hidden_groups, hidden_bodies=hidden_bodies, camera_settings=camera_settings, ortho_settings=ortho_settings, cull_backfaces=cull_backfaces)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
        
    export_type = data.get('export_type', 'all')
    try:
        if export_type == 'xml':
            zip_filename = f"{base_name}_masks_xml.zip"
            files_to_zip = [f for f in exported_files if f.endswith('.xml')]
        elif export_type == 'png':
            zip_filename = f"{base_name}_masks_png.zip"
            files_to_zip = [f for f in exported_files if f.endswith('.png')]
        else:
            zip_filename = f"{base_name}_masks.zip"
            files_to_zip = exported_files

        zip_filepath = os.path.join(session_dir, zip_filename)
        
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f in files_to_zip:
                if os.path.exists(f):
                    zipf.write(f, os.path.basename(f))
                else:
                    print(f"Warning: Expected exported file {f} was not found on disk.")
                
        return send_file(zip_filepath, as_attachment=True, download_name=zip_filename)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"Failed to compress export files: {str(e)}"}), 500

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
    app.run(debug=True, port=5000, threaded=False)
