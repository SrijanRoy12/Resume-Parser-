from flask import Flask, render_template, request, jsonify
import PyPDF2
import docx2txt
import re
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Create uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx', 'txt'}

def extract_text_from_file(filepath):
    if filepath.endswith('.pdf'):
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = '\n'.join([page.extract_text() for page in reader.pages])
    elif filepath.endswith('.docx'):
        text = docx2txt.process(filepath)
    elif filepath.endswith('.txt'):
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        text = ''
    return text

def extract_name(text):
    # Look for name in the first few lines
    for line in text.split('\n')[:5]:
        name_match = re.search(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', line.strip())
        if name_match:
            return name_match.group(1)
    return "Name not found"

def extract_skills(text):
    skills_keywords = ['python', 'java', 'javascript', 'c++', 'c#', 'sql', 'html', 
                     'css', 'react', 'node.js', 'django', 'flask', 'machine learning']
    found_skills = set()
    for skill in skills_keywords:
        if re.search(rf'\b{re.escape(skill)}\b', text, re.IGNORECASE):
            found_skills.add(skill.capitalize())
    return sorted(found_skills) if found_skills else ["No skills detected"]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse_resume():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            text = extract_text_from_file(filepath)
            os.remove(filepath)  # Clean up
            
            return jsonify({
                'name': extract_name(text),
                'skills': extract_skills(text),
                'education': ["Education information"],  # Implement this
                'certifications': ["Certification details"],  # Implement this
                'internships': ["Internship details"]  # Implement this
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'File type not allowed'}), 400

if __name__ == '__main__':
    app.run(debug=False)  # Production