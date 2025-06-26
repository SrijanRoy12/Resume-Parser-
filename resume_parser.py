import streamlit as st
import pdfplumber
import docx2txt
import re
from io import BytesIO
import time
from typing import Dict, List, Optional, Tuple
import json
import spacy
from dateparser.search import search_dates
import pandas as pd

# Try to import streamlit_lottie with fallback
try:
    from streamlit_lottie import st_lottie
    import requests
    LOTTIE_ENABLED = True
except ImportError:
    LOTTIE_ENABLED = False

# Load English language model for spaCy
try:
    nlp = spacy.load("en_core_web_sm")
except:
    st.warning("spaCy model not found. Installing...")
    import os
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# ======================
# ENHANCED EXTRACTION FUNCTIONS
# ======================

def extract_text(file) -> str:
    """Extract text from uploaded file with robust error handling"""
    text = ""
    try:
        if file.type == "application/pdf":
            with pdfplumber.open(file) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = docx2txt.process(BytesIO(file.read()))
        elif file.type == "text/plain":
            text = str(file.read(), "utf-8", errors="replace")
        return text.strip()
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""

def extract_name(text: str) -> str:
    """Enhanced name extraction using NLP"""
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()
    
    # Fallback to regex if NLP fails
    name_patterns = [
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"(?<=\n)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?=\n)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\n|$)"
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return "Not found"

def extract_personal_info(text: str) -> Dict[str, str]:
    """Extract personal information with enhanced techniques"""
    info = {
        "name": extract_name(text),
        "email": list(set(re.findall(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', text))),
        "phone": extract_phone_numbers(text),
        "linkedin": extract_social_links(text, "linkedin"),
        "github": extract_social_links(text, "github"),
        "portfolio": extract_portfolio_links(text)
    }
    return info

def extract_phone_numbers(text: str) -> str:
    """Extract phone numbers with international support"""
    phone_patterns = [
        r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\+?\d[\d\s-]{7,}\d'
    ]
    phones = []
    for pattern in phone_patterns:
        phones.extend(re.findall(pattern, text))
    return ", ".join(set(phones)) if phones else "Not found"

def extract_social_links(text: str, platform: str) -> str:
    """Extract social media links"""
    patterns = {
        "linkedin": r"(https?://(?:www\.)?linkedin\.com/[^\s]+)",
        "github": r"(https?://(?:www\.)?github\.com/[^\s]+)"
    }
    match = re.search(patterns[platform], text)
    return match.group(0) if match else "Not found"

def extract_portfolio_links(text: str) -> str:
    """Extract portfolio/personal website links"""
    urls = re.findall(r'(https?://[^\s]+)', text)
    for url in urls:
        url = url.rstrip('.,)')
        if any(x in url.lower() for x in ['portfolio', 'personal', 'website']):
            return url
    return "Not found"

def extract_education(text: str) -> List[Dict[str, str]]:
    """Enhanced education extraction with degree detection"""
    education = []
    
    # Find education section using multiple possible headers
    edu_section = find_section(text, ["EDUCATION", "ACADEMIC BACKGROUND", "EDUCATIONAL QUALIFICATION"])
    
    if edu_section:
        # Split by likely education entries (FIXED REGEX)
        entries = re.split(r'\n(?=[A-Z][a-z]+(?: University| Institute| College|\s[A-Z][a-z]+))', edu_section)
        
        for entry in entries:
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
                
            edu_entry = {
                "institution": lines[0],
                "degree": extract_degree(" ".join(lines)),
                "dates": extract_dates(" ".join(lines)),
                "gpa": extract_gpa(" ".join(lines)),
                "details": []
            }
            
            # Extract additional details
            for line in lines[1:]:
                if not any(x in line.lower() for x in ['gpa', 'grade', 'score', 'coursework']):
                    edu_entry["details"].append(line)
            
            education.append(edu_entry)
    
    return education if education else [{"institution": "Education information not found"}]

def extract_degree(text: str) -> str:
    """Extract degree information"""
    degree_patterns = [
        r'(Bachelor[\w\s]*|B\.?[\w\s]*|Master[\w\s]*|M\.?[\w\s]*|Ph\.?D[\w\s]*)',
        r'(Associate[\w\s]*|Diploma[\w\s]*)'
    ]
    for pattern in degree_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""

def extract_dates(text: str) -> str:
    """Extract dates using dateparser"""
    dates = search_dates(text)
    if dates:
        return " - ".join([date[1].strftime("%b %Y") for date in dates[:2]])
    return ""

def extract_gpa(text: str) -> str:
    """Extract GPA information"""
    gpa_match = re.search(r'(GPA|CGPA|Score)\s*[:•]?\s*([\d\.]+/?[\d\.]*)', text, re.IGNORECASE)
    return f"{gpa_match.group(1)}: {gpa_match.group(2)}" if gpa_match else ""

def extract_experience(text: str) -> List[Dict[str, str]]:
    """Enhanced experience extraction with position detection"""
    experience = []
    
    # Find experience section using multiple possible headers
    exp_section = find_section(text, ["EXPERIENCE", "WORK HISTORY", "PROFESSIONAL EXPERIENCE"])
    
    if exp_section:
        # Split by likely job entries
        entries = re.split(r'\n(?=[A-Z][a-z]+(?: at |, |\s-\s|\n))', exp_section)
        
        for entry in entries:
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            if not lines:
                continue
                
            exp_entry = {
                "title": lines[0],
                "company": extract_company(lines[0]),
                "dates": extract_dates(" ".join(lines)),
                "description": []
            }
            
            # Extract bullet points
            for line in lines[1:]:
                if line.strip() and not re.search(r'page \d+', line.lower()):
                    exp_entry["description"].append(re.sub(r'^[•→\-]\s*', '', line))
            
            experience.append(exp_entry)
    
    return experience if experience else [{"title": "Experience information not found"}]

def extract_company(text: str) -> str:
    """Extract company name from position line"""
    separators = [" at ", ", ", " - ", " | "]
    for sep in separators:
        if sep in text:
            return text.split(sep)[-1].strip()
    return ""

def extract_certifications(text: str) -> Dict[str, List[str]]:
    """Enhanced certification extraction"""
    result = {
        'certifications': [],
        'internships': []
    }
    
    # Find certifications section
    cert_section = find_section(text, ["CERTIFICATIONS", "TRAINING", "LICENSES"])
    
    if cert_section:
        current = None
        for line in cert_section.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers
            if any(x in line.upper() for x in ['CERTIFICAT', 'TRAINING', 'LICENSE']):
                current = 'certifications'
                continue
            elif 'INTERNSHIP' in line.upper():
                current = 'internships'
                continue
            
            # Process bullet points
            if line.startswith(('•', '-', '*')):
                line = line[1:].strip()
            
            # Clean and format
            line = re.sub(r'\s+', ' ', line).rstrip('.,')
            
            # Add to appropriate list
            if current and line:
                result[current].append(line)
    
    return result

def extract_skills(text: str) -> Dict[str, List[str]]:
    """Enhanced skills extraction with categorization"""
    skills = {
        "Programming Languages": [],
        "Frameworks & Libraries": [],
        "Databases": [],
        "Tools & Platforms": [],
        "Soft Skills": []
    }
    
    # Find skills section
    skills_section = find_section(text, ["SKILLS", "TECHNICAL SKILLS", "TECHNOLOGIES"])
    
    if skills_section:
        # Categorize skills using keywords
        for line in skills_section.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Skip section headers
            if any(x in line.lower() for x in ['skill', 'technical', 'technology']):
                continue
            
            # Extract individual skills
            items = [item.strip() for item in re.split(r'[,;]', line) if item.strip()]
            
            for item in items:
                # Categorize based on keywords
                if any(x in item.lower() for x in ['python', 'java', 'c++', 'javascript', 'ruby']):
                    skills["Programming Languages"].append(item)
                elif any(x in item.lower() for x in ['react', 'angular', 'django', 'flask', 'spring']):
                    skills["Frameworks & Libraries"].append(item)
                elif any(x in item.lower() for x in ['mysql', 'mongodb', 'postgresql', 'oracle']):
                    skills["Databases"].append(item)
                elif any(x in item.lower() for x in ['docker', 'kubernetes', 'aws', 'azure', 'git']):
                    skills["Tools & Platforms"].append(item)
                else:
                    skills["Soft Skills"].append(item)
    
    # Remove empty categories
    return {k: v for k, v in skills.items() if v}

def find_section(text: str, possible_headers: List[str]) -> str:
    """Find a section by trying multiple possible headers"""
    for header in possible_headers:
        pattern = rf'{header}.*?(\n.*?)(?=(?:{"|".join(possible_headers)}|\n\s*\n|$))'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""

# ======================
# DISPLAY FUNCTIONS
# ======================

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

def display_experience(experience: List[Dict[str, str]]):
    """Display experience/projects section with improved formatting"""
    with st.container():
        st.markdown("""
        <div class="card animate-fade" style="animation-delay: 0.3s">
            <h2>💼 Work Experience</h2>
        """, unsafe_allow_html=True)
        
        for exp in experience:
            with st.expander(f"**{exp.get('title', '')}** at **{exp.get('company', '')}**"):
                if exp.get('dates'):
                    st.markdown(f"**Period:** {exp['dates']}")
                
                if exp.get('description'):
                    st.markdown("**Responsibilities:**")
                    for desc in exp['description']:
                        st.markdown(f"- {desc}")
        
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
                    st.markdown(f"- {cert}")
            else:
                st.markdown("No certifications found")
                
        with cols[1]:
            if internships:
                st.markdown("**Internships**")
                for intern in internships:
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
        
        # Display skills in 2 columns
        skill_items = list(skills.items())
        cols = st.columns(2)
        
        for i, (category, items) in enumerate(skill_items):
            with cols[i % 2]:
                st.markdown(f"**{category}**")
                st.markdown(", ".join(items))
        
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
