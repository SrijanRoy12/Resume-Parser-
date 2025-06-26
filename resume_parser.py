import streamlit as st
import PyPDF2
import docx2txt
import re
from io import BytesIO
import time
from typing import Dict, List, Optional
import json

# Try to import streamlit_lottie with fallback
try:
    from streamlit_lottie import st_lottie
    import requests
    LOTTIE_ENABLED = True
except ImportError:
    LOTTIE_ENABLED = False

# ======================
# FUNCTION DEFINITIONS
# ======================

def extract_text(file) -> str:
    """Extract text from uploaded file with robust error handling"""
    text = ""
    try:
        if file.type == "application/pdf":
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = docx2txt.process(BytesIO(file.read()))
        elif file.type == "text/plain":
            text = str(file.read(), "utf-8", errors="replace")
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""

def extract_personal_info(text: str) -> Dict[str, str]:
    """Extract personal information from resume text"""
    info = {
        "name": "Not found",
        "email": [],
        "phone": "Not found",
        "linkedin": "Not found",
        "github": "Not found",
        "portfolio": "Not found"
    }
    
    # Name extraction patterns
    name_patterns = [
        r'^([A-Z][A-Z\s]+)\n',
        r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'(?<=\n)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?=\n)'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            info["name"] = match.group(1).title()
            break
    
    # Extract emails
    info["email"] = list(set(re.findall(r'[\w\.-]+@[\w\.-]+', text)))
    
    # Extract phone number
    phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phone_match:
        info["phone"] = phone_match.group(0)
    
    # Extract URLs
    urls = re.findall(r'(https?://[^\s]+)', text)
    for url in urls:
        url = url.rstrip('.,)')
        if 'linkedin.com' in url:
            info["linkedin"] = url
        elif 'github.com' in url:
            info["github"] = url
        elif any(x in url.lower() for x in ['portfolio', 'personal']):
            info["portfolio"] = url
    
    return info

def extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education information from resume text"""
    education = []
    
    # Find education section
    edu_section = re.search(
        r'EDUCATION.*?(\n.*?)(?=(?:EXPERIENCE|PROJECTS|CERTIFICATIONS|SKILLS|$))', 
        text, 
        re.DOTALL | re.IGNORECASE
    )
    
    if edu_section:
        entries = re.split(r'\n(?=[A-Z][a-z])', edu_section.group(1))
        for entry in entries:
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
                
            edu_entry = {
                "institution": lines[0],
                "degree": "",
                "dates": "",
                "details": [],
                "gpa": ""
            }
            
            for line in lines[1:]:
                # Extract dates
                date_match = re.search(r'([A-Za-z]+\s+\d{4}\s*-\s*[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{4}\s*-\s*Present)', line)
                if date_match:
                    edu_entry["dates"] = date_match.group(1)
                    line = line.replace(date_match.group(1), "").strip()
                
                # Extract GPA
                gpa_match = re.search(r'(CGPA|GPA|Score)\s*[:•]?\s*([\d\.]+)', line, re.IGNORECASE)
                if gpa_match:
                    edu_entry["gpa"] = f"{gpa_match.group(1)}: {gpa_match.group(2)}"
                    line = line.replace(gpa_match.group(0), "").strip()
                
                # Extract degree
                degree_match = re.search(r'(Bachelor|B\.?Tech|B\.?E|Master|M\.?Tech|Ph\.?D)', line, re.IGNORECASE)
                if degree_match and not edu_entry["degree"]:
                    edu_entry["degree"] = line.strip()
                    continue
                
                # Extract coursework
                if 'coursework' in line.lower():
                    courses = re.split(r'[:,]', line, maxsplit=1)
                    if len(courses) > 1:
                        edu_entry["details"].append(f"<strong>Coursework:</strong> {courses[1].strip()}")
                    continue
                
                # Add remaining lines as details
                if line and not any(x in line.lower() for x in ['page', 'http']):
                    edu_entry["details"].append(line)
            
            education.append(edu_entry)
    
    return education if education else [{"institution": "Education information not found"}]

def extract_experience(text: str) -> List[Dict[str, str]]:
    """Extract work experience/projects from resume text"""
    projects = []
    
    # Find experience section
    exp_section = re.search(
        r'(?:EXPERIENCE|PROJECTS|WORK HISTORY).*?(\n.*?)(?=(?:CERTIFICATIONS|SKILLS|EDUCATION|$))', 
        text, 
        re.DOTALL | re.IGNORECASE
    )
    
    if exp_section:
        # Split projects by title pattern
        raw_projects = re.split(r'\n(?=[A-Z][a-z])', exp_section.group(1))
        for proj in raw_projects:
            if not proj.strip():
                continue
                
            lines = [line.strip() for line in proj.split('\n') if line.strip()]
            if not lines:
                continue
                
            projects.append({
                "title": lines[0],
                "description": [re.sub(r'^[•→\-]\s*', '', line) for line in lines[1:] 
                               if line and not re.search(r'page \d+', line.lower())]
            })
    
    return projects if projects else [{"title": "Work experience not found"}]

def extract_certifications(text: str) -> Dict[str, List[str]]:
    """Extract certifications and internships from resume text"""
    result = {
        'certifications': [],
        'internships': []
    }
    
    # Find certifications section
    cert_section = re.search(
        r'(?:CERTIFICATIONS|INTERNSHIPS|TRAINING).*?(\n.*?)(?=(?:SKILLS|EDUCATION|$))', 
        text, 
        re.DOTALL | re.IGNORECASE
    )
    
    if cert_section:
        current = None
        for line in cert_section.group(1).split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers
            if 'CERTIFICATIONS' in line.upper():
                current = 'certifications'
                continue
            elif 'INTERNSHIPS' in line.upper():
                current = 'internships'
                continue
            
            # Process bullet points
            if line.startswith(('•', '-', '*')):
                line = line[1:].strip()
            
            # Clean and format
            line = re.sub(r'\s+', ' ', line)
            line = line.rstrip('.,')
            
            # Add to appropriate list
            if current and line:
                result[current].append(line)
    
    return result

def extract_skills(text: str) -> Dict[str, List[str]]:
    """Extract skills from resume text"""
    skills = {
        "Programming Languages": [],
        "Database": [],
        "Problem Solving": [],
        "Technologies": [],
        "Other": []
    }
    
    # Find skills section
    skills_section = re.search(
        r'(?:SKILLS|TECHNICAL SKILLS).*?(\n.*?)(?=(?:CERTIFICATIONS|EDUCATION|$))', 
        text, 
        re.DOTALL | re.IGNORECASE
    )
    
    if skills_section:
        current_category = "Other"
        for line in skills_section.group(1).split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Detect category lines
            if ' - ' in line:
                category, items = line.split(' - ', 1)
                current_category = category.strip()
                items = [item.strip() for item in re.split(r'[,;]', items) if item.strip()]
                skills[current_category] = items
            elif ':' in line:
                category, items = line.split(':', 1)
                current_category = category.strip()
                items = [item.strip() for item in re.split(r'[,;]', items) if item.strip()]
                skills[current_category] = items
            else:
                # Add to current category
                items = [item.strip() for item in re.split(r'[,;]', line) if item.strip()]
                skills[current_category].extend(items)
    
    # Remove empty categories
    return {k: v for k, v in skills.items() if v}

def display_personal_info(info: Dict[str, str]):
    """Display personal information section"""
    with st.container():
        st.markdown("""
        <div class="card animate-fade" style="animation-delay: 0.1s">
            <h2>👤 Personal Information</h2>
        """, unsafe_allow_html=True)
        
        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"**Name:** {info['name']}")
            st.markdown(f"**Email:** {' | '.join(info['email'])}")
        with cols[1]:
            st.markdown(f"**Phone:** {info['phone']}")
            if info['linkedin'] != "Not found":
                st.markdown(f"**LinkedIn:** [🔗 Link]({info['linkedin']})")
            if info['github'] != "Not found":
                st.markdown(f"**GitHub:** [🐱 Link]({info['github']})")
            if info['portfolio'] != "Not found":
                st.markdown(f"**Portfolio:** [🌐 Link]({info['portfolio']})")
        
        st.markdown("</div>", unsafe_allow_html=True)

def display_education(education: List[Dict[str, str]]):
    """Display education section with improved formatting"""
    with st.container():
        st.markdown("""
        <div class="card animate-fade" style="animation-delay: 0.2s">
            <h2>🎓 Education</h2>
        """, unsafe_allow_html=True)
        
        for edu in education:
            with st.expander(f"**{edu.get('institution', '')}**"):
                if edu.get('degree'):
                    st.markdown(f"*{edu['degree']}*")
                if edu.get('dates'):
                    st.markdown(f"**Period:** {edu['dates']}")
                if edu.get('gpa'):
                    st.markdown(f"**{edu['gpa']}**")
                
                # Display coursework separately
                coursework = [d for d in edu.get('details', []) if 'coursework' in d.lower()]
                other_details = [d for d in edu.get('details', []) if 'coursework' not in d.lower()]
                
                if coursework:
                    st.markdown("\n".join(coursework), unsafe_allow_html=True)
                if other_details:
                    st.markdown("**Highlights:**")
                    for detail in other_details:
                        st.markdown(f"- {detail}")
        
        st.markdown("</div>", unsafe_allow_html=True)

def display_experience(projects: List[Dict[str, str]]):
    """Display experience/projects section with improved formatting"""
    with st.container():
        st.markdown("""
        <div class="card animate-fade" style="animation-delay: 0.3s">
            <h2>💼 Work Experience & Projects</h2>
        """, unsafe_allow_html=True)
        
        for proj in projects:
            title = proj.get('title', '')
            description = proj.get('description', [])
            
            # Skip empty entries
            if not title and not description:
                continue
                
            with st.expander(f"**{title}**" if title else "Project"):
                # Combine bullet points into paragraphs when possible
                full_description = " ".join(desc for desc in description if desc)
                st.markdown(full_description)
                
                # Add GitHub links if found in description
                github_links = [desc for desc in description if 'github.com' in desc.lower()]
                if github_links:
                    st.markdown("**Links:**")
                    for link in github_links:
                        st.markdown(f"[🔗 GitHub Repo]({link})")
        
        st.markdown("</div>", unsafe_allow_html=True)

def display_certifications(certifications: List[str], internships: List[str]):
    """Display certifications and internships with improved formatting"""
    with st.container():
        st.markdown("""
        <div class="card animate-fade" style="animation-delay: 0.4s">
            <h2>📜 Certifications & Internships</h2>
        """, unsafe_allow_html=True)
        
        cols = st.columns(2)
        
        with cols[0]:
            if certifications:
                st.markdown("**Certifications**")
                for cert in certifications:
                    # Clean up certification text
                    cert = re.sub(r'^\d+\s*[\.\)]\s*', '', cert)  # Remove numbering
                    cert = cert.strip('•- ')
                    st.markdown(f"- {cert}")
            else:
                st.markdown("No certifications found")
                
        with cols[1]:
            if internships:
                st.markdown("**Internships**")
                for intern in internships:
                    # Clean up internship text
                    intern = re.sub(r'^\d+\s*[\.\)]\s*', '', intern)  # Remove numbering
                    intern = intern.strip('•- ')
                    # Extract duration if present
                    duration_match = re.search(r'(\d+\s+month)', intern)
                    if duration_match:
                        duration = duration_match.group(1)
                        intern = intern.replace(duration_match.group(0), '').strip()
                        st.markdown(f"- {intern} ({duration})")
                    else:
                        st.markdown(f"- {intern}")
            else:
                st.markdown("No internships found")
        
        st.markdown("</div>", unsafe_allow_html=True)

def display_skills(skills: Dict[str, List[str]]):
    """Display skills section with improved formatting"""
    with st.container():
        st.markdown("""
        <div class="card animate-fade" style="animation-delay: 0.5s">
            <h2>🛠 Skills</h2>
        """, unsafe_allow_html=True)
        
        # Group similar skill categories
        skill_groups = {
            "Technical Skills": ["Programming Languages", "Technologies", "Database"],
            "AI/ML": ["Machine Learning", "Artificial Intelligence", "NLP"],
            "Tools & Platforms": ["Frameworks", "Cloud", "DevOps"]
        }
        
        # Create columns for better layout
        cols = st.columns(2)
        col_idx = 0
        
        for group_name, categories in skill_groups.items():
            with cols[col_idx % 2]:
                st.markdown(f"**{group_name}**")
                for category in categories:
                    if category in skills:
                        # Format skills as comma-separated list
                        skills_list = ", ".join(skills[category])
                        st.markdown(f"- *{category}:* {skills_list}")
                st.markdown("")  # Add spacing
            col_idx += 1
        
        # Display remaining skills not in groups
        remaining_categories = [cat for cat in skills.keys() 
                              if cat not in [item for sublist in skill_groups.values() 
                                           for item in sublist]]
        
        if remaining_categories:
            with st.expander("Additional Skills"):
                for category in remaining_categories:
                    skills_list = ", ".join(skills[category])
                    st.markdown(f"**{category}:** {skills_list}")
        
        st.markdown("</div>", unsafe_allow_html=True)

def processing_animation():
    """Show processing animation"""
    with st.spinner('Analyzing your resume...'):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for percent_complete in range(100):
            time.sleep(0.02)
            progress_bar.progress(percent_complete + 1)
            status_text.text(f"Processing... {percent_complete + 1}%")
        
        progress_bar.empty()
        status_text.empty()
        st.success('Analysis complete!')
        st.balloons()

# ======================
# STREAMLIT UI
# ======================

# Set page config
st.set_page_config(
    page_title="Resume Parser Pro",
    layout="wide",
    page_icon="📄",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False

# Background image and styling
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://images.unsplash.com/photo-1555066931-4365d14bab8c?ixlib=rb-4.0.3");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

[data-testid="stSidebar"] {
    background-color: rgba(14, 17, 23, 0.85) !important;
    backdrop-filter: blur(5px);
}

.card {
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.animate-fade {
    animation: fadeIn 0.6s ease forwards;
}

.expander-content {
    padding: 10px !important;
    background-color: rgba(245, 245, 245, 0.9) !important;
    border-radius: 5px !important;
}

[data-testid="stExpander"] {
    margin-bottom: 10px !important;
    border: 1px solid rgba(0,0,0,0.1) !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"]:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
}

.social-links a {
    transition: all 0.3s ease;
    display: inline-block;
}

.social-links a:hover {
    transform: scale(1.2);
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# App header
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📄 Resume Parser Pro")
    st.markdown("""
        <div class="animate-fade">
        <p>Upload a resume to extract key candidate information.</p>
        <span style="color:gray">*Supports PDF, DOCX, and TXT files*</span>
        </div>
        """, unsafe_allow_html=True)
with col2:
    if LOTTIE_ENABLED:
        try:
            lottie_animation = requests.get(
                "https://assets1.lottiefiles.com/packages/lf20_vybwn7df.json"
            ).json()
            st_lottie(lottie_animation, height=100, key="header-animation")
        except:
            st.image("https://cdn-icons-png.flaticon.com/512/3132/3132693.png", width=100)

# File uploader
uploaded_file = st.file_uploader(
    "Choose a resume file", 
    type=["pdf", "docx", "txt"],
    help="Upload your resume in PDF, DOCX or TXT format"
)

# Footer with social links
footer = """
<div class="footer">
    <div class="social-links">
        <a href="https://www.linkedin.com/in/srijan-roy-iemians/" target="_blank" title="LinkedIn">🔗</a>
        <a href="https://github.com/SrijanRoy12" target="_blank" title="GitHub">🐱</a>
        <a href="mailto:roysrijan53@gmail.com" title="Email">✉️</a>
        <a href="https://twitter.com/home" target="_blank" title="Twitter">🐦</a>
        <a href="https://www.instagram.com/its_ur_roy123/" target="_blank" title="Instagram">📸</a>
    </div>
    <div class="copyright">
        © 2025 Srijan's Resume Parser | Powered by Passion — Srijan Roy | All rights reserved
    </div>
</div>

<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: rgba(14, 17, 23, 0.9);
    color: white;
    text-align: center;
    padding: 10px;
    z-index: 1000;
    backdrop-filter: blur(5px);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.social-links {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-bottom: 10px;
}
.social-links a {
    color: white;
    font-size: 20px;
    transition: all 0.3s ease;
}
.social-links a:hover {
    color: #1DA1F2;
    transform: translateY(-3px);
}
.copyright {
    font-size: 12px;
    color: #aaa;
}
</style>
"""
st.markdown(footer, unsafe_allow_html=True)

# When file is uploaded
if uploaded_file is not None:
    processing_animation()
    
    # Extract data
    text = extract_text(uploaded_file)
    personal_info = extract_personal_info(text)
    education = extract_education(text)
    experience = extract_experience(text)
    skills = extract_skills(text)
    certifications_data = extract_certifications(text)
    
    st.session_state.parsed_data = {
        'personal_info': personal_info,
        'education': education,
        'experience': experience,
        'skills': skills,
        'certifications': certifications_data.get('certifications', []),
        'internships': certifications_data.get('internships', []),
        'text': text
    }
    
    st.session_state.processing_complete = True

# Display results
if st.session_state.parsed_data:
    tab1, tab2 = st.tabs(["🎨 Beautiful View", "📋 Raw Data"])
    
    with tab1:
        display_personal_info(st.session_state.parsed_data['personal_info'])
        display_education(st.session_state.parsed_data['education'])
        display_experience(st.session_state.parsed_data['experience'])
        display_certifications(
            st.session_state.parsed_data['certifications'],
            st.session_state.parsed_data['internships']
        )
        display_skills(st.session_state.parsed_data['skills'])
    
    with tab2:
        st.text_area("Extracted Text", 
                   st.session_state.parsed_data['text'], 
                   height=400)

# Sidebar with app info
with st.sidebar:
    st.header("✨ Features")
    st.markdown("""
    - **Smart Parsing**: Extracts all key sections
    - **Beautiful UI**: Modern, animated interface
    - **Export Options**: Save as PDF/JSON
    - **Multi-format**: PDF, DOCX, TXT support
    """)
    
    st.markdown("---")
    
    if st.session_state.parsed_data:
        st.download_button(
            label="📥 Download as JSON",
            data=json.dumps(st.session_state.parsed_data, indent=2),
            file_name="resume_data.json",
            mime="application/json"
        )
    
    st.markdown("---")
    st.markdown("Built with ❤️ using [Streamlit](https://streamlit.io)")