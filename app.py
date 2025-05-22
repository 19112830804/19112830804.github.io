import os
import uuid
import secrets
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, abort, render_template_string
from werkzeug.utils import secure_filename
from flask_cors import CORS

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'pptx', 'zip', 'rar'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB，可根据需要调整
CODE_LENGTH = 8  # 取件码长度

# 创建应用
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
CORS(app)  # 允许跨域请求

# 确保上传目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 模拟数据库
files_db = {}

# 允许的文件类型检查
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 生成唯一取件码
def generate_retrieval_code():
    while True:
        code = secrets.token_hex(CODE_LENGTH // 2).upper()
        if code not in files_db:
            return f"FV-{code}"

# 格式化文件大小
def format_file_size(bytes):
    if bytes == 0:
        return "0 Bytes"
    size_names = ("Bytes", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return f"{s} {size_names[i]}"

# 上传文件
@app.route('/api/upload', methods=['POST'])
def upload_file():
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    # 检查文件是否选择
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # 检查文件类型
    if file and allowed_file(file.filename):
        # 生成唯一文件名和取件码
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())
        stored_filename = f"{unique_id}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
        retrieval_code = generate_retrieval_code()
        
        # 保存文件
        file.save(file_path)
        
        # 记录文件信息
        file_info = {
            'id': unique_id,
            'filename': filename,
            'stored_filename': stored_filename,
            'code': retrieval_code,
            'size': os.path.getsize(file_path),
            'uploadDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'expireDate': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        files_db[retrieval_code] = file_info
        
        return jsonify({
            'success': True,
            'code': retrieval_code,
            'filename': filename
        })
    else:
        return jsonify({"error": "File type not allowed"}), 400

# 获取文件信息
@app.route('/api/file/<code>', methods=['GET'])
def get_file_info(code):
    file_info = files_db.get(code)
    if not file_info:
        abort(404)
    
    # 检查文件是否存在
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_filename'])
    if not os.path.exists(file_path):
        # 文件不存在，从数据库中删除记录
        del files_db[code]
        abort(404)
    
    return jsonify({
        'filename': file_info['filename'],
        'size': format_file_size(file_info['size']),
        'uploadDate': file_info['uploadDate'],
        'expireDate': file_info['expireDate']
    })

# 下载文件
@app.route('/api/download/<code>', methods=['GET'])
def download_file(code):
    file_info = files_db.get(code)
    if not file_info:
        abort(404)
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_filename'])
    if not os.path.exists(file_path):
        del files_db[code]
        abort(404)
    
    return send_file(file_path, as_attachment=True, download_name=file_info['filename'])

# 预览文件
@app.route('/api/view/<code>', methods=['GET'])
def view_file(code):
    file_info = files_db.get(code)
    if not file_info:
        abort(404)
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_filename'])
    if not os.path.exists(file_path):
        del files_db[code]
        abort(404)
    
    # 对于图片类型，直接返回文件内容
    file_ext = file_info['filename'].split('.')[-1].lower()
    if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'svg']:
        return send_file(file_path, mimetype=f'image/{file_ext}')
    
    # 对于文本类型，尝试显示内容
    elif file_ext in ['txt']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return render_template_string('''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{{ filename }}</title>
                    <style>
                        body { font-family: monospace; padding: 20px; white-space: pre-wrap; }
                    </style>
                </head>
                <body>
                    <h1>{{ filename }}</h1>
                    <pre>{{ content }}</pre>
                </body>
                </html>
            ''', filename=file_info['filename'], content=content)
        except:
            pass
    
    # 对于PDF，尝试显示预览
    elif file_ext == 'pdf':
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>{{ filename }}</title>
            </head>
            <body>
                <h1>{{ filename }}</h1>
                <embed src="{{ url_for('download_file', code=code) }}" width="100%" height="800px" type="application/pdf">
            </body>
            </html>
        ''', filename=file_info['filename'], code=code)
    
    # 其他类型，提供下载链接
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ filename }}</title>
        </head>
        <body>
            <h1>{{ filename }}</h1>
            <p>无法在线预览此文件类型。</p>
            <a href="{{ url_for('download_file', code=code) }}">点击下载文件</a>
        </body>
        </html>
    ''', filename=file_info['filename'], code=code)

# 获取最近上传的文件
@app.route('/api/recent', methods=['GET'])
def get_recent_files():
    # 获取最近上传的10个文件
    recent_files = sorted(files_db.values(), key=lambda x: x['uploadDate'], reverse=True)[:10]
    
    # 确保文件存在
    valid_files = []
    for file in recent_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file['stored_filename'])
        if os.path.exists(file_path):
            valid_files.append({
                'filename': file['filename'],
                'code': file['code'],
                'uploadDate': file['uploadDate']
            })
    
    return jsonify(valid_files)

# 获取统计数据
@app.route('/api/stats', methods=['GET'])
def get_stats():
    # 清理不存在的文件
    codes_to_delete = []
    for code, file_info in files_db.items():
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_filename'])
        if not os.path.exists(file_path):
            codes_to_delete.append(code)
    
    for code in codes_to_delete:
        del files_db[code]
    
    # 统计数据
    stats = {
        'files': len(files_db),
        'downloads': 0,  # 简化版本，实际应记录下载次数
        'users': 0,      # 简化版本，实际应统计用户数
        'countries': 0   # 简化版本，实际应统计国家数
    }
    
    return jsonify(stats)

# 清理过期文件（可作为定时任务运行）
def cleanup_expired_files():
    now = datetime.now()
    codes_to_delete = []
    
    for code, file_info in files_db.items():
        expire_date = datetime.strptime(file_info['expireDate'], '%Y-%m-%d %H:%M:%S')
        if expire_date < now:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
            codes_to_delete.append(code)
    
    for code in codes_to_delete:
        del files_db[code]
    
    return len(codes_to_delete)

# 运行应用
if __name__ == '__main__':
    app.run(debug=True)    