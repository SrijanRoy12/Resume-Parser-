document.getElementById('parse-btn').addEventListener('click', async function() {
    const fileInput = document.getElementById('resume-upload');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a resume file first');
        return;
    }

    const formData = new FormData();
    formData.append('resume', file);

    try {
        // Show loading state
        this.textContent = 'Processing...';
        this.disabled = true;

        const response = await fetch('/parse', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const data = await response.json();
        displayResults(data);
    } catch (error) {
        console.error('Error:', error);
        alert('Error parsing resume: ' + error.message);
    } finally {
        // Reset button
        this.textContent = 'Parse Resume';
        this.disabled = false;
    }
});

function displayResults(data) {
    document.getElementById('name-result').textContent = data.name;
    
    const skillsList = document.getElementById('skills-result');
    skillsList.innerHTML = data.skills.map(skill => 
        `<li>${skill}</li>`
    ).join('');
    
    // Update other sections similarly
    document.getElementById('education-result').innerHTML = 
        data.education.map(item => `<li>${item}</li>`).join('');
    
    document.getElementById('certifications-result').innerHTML = 
        data.certifications.map(item => `<li>${item}</li>`).join('');
    
    document.getElementById('internships-result').innerHTML = 
        data.internships.map(item => `<li>${item}</li>`).join('');
}