const API = {
  parse:    '/api/parse',
  tailor:   '/api/tailor',
  download: (id, fmt) => `/api/download/${id}?format=${fmt}`,
  preview:  (id)      => `/api/preview/${id}`,
};

let state = {
  sessionId: null,
  tailoredId: null,
  file: null,
};

// --- elements ---
const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const dropText     = document.getElementById('drop-text');
const fileName     = document.getElementById('file-name');
const parseBtn     = document.getElementById('parse-btn');
const parseResult  = document.getElementById('parse-result');
const parseError   = document.getElementById('parse-error');
const parseLoading = document.getElementById('parse-loading');

const step2 = document.getElementById('step-2');
const step3 = document.getElementById('step-3');

const tailorBtn     = document.getElementById('tailor-btn');
const tailorLoading = document.getElementById('tailor-loading');
const tailorError   = document.getElementById('tailor-error');

const summaryBox   = document.getElementById('summary-box');
const scoresBox    = document.getElementById('scores-box');
const downloadDocx = document.getElementById('download-docx');
const downloadPdf  = document.getElementById('download-pdf');
const previewBtn   = document.getElementById('preview-btn');
const previewContainer = document.getElementById('preview-container');
const previewFrame = document.getElementById('preview-frame');
const tailorAnother = document.getElementById('tailor-another');

// --- file upload ---

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  const allowed = ['.pdf', '.docx'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showError(parseError, 'Only PDF and DOCX files are supported.');
    return;
  }
  state.file = file;
  dropText.classList.add('hidden');
  fileName.textContent = file.name;
  fileName.classList.remove('hidden');
  dropZone.classList.add('has-file');
  parseBtn.disabled = false;
  hide(parseError);
}

// --- parse ---

parseBtn.addEventListener('click', async () => {
  if (!state.file) return;

  setLoading(true, parseLoading, parseBtn);
  hide(parseResult);
  hide(parseError);

  const form = new FormData();
  form.append('file', state.file);

  try {
    const res = await fetch(API.parse, { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) {
      showError(parseError, data.detail || 'Failed to parse CV.');
      return;
    }

    state.sessionId = data.session_id;
    parseResult.textContent = data.message;
    parseResult.classList.remove('hidden');

    // move to step 2 after short delay
    setTimeout(() => {
      step2.classList.remove('hidden');
      step2.scrollIntoView({ behavior: 'smooth' });
    }, 800);

  } catch (e) {
    showError(parseError, 'Network error. Is the server running?');
  } finally {
    setLoading(false, parseLoading, parseBtn);
  }
});

// --- tailor ---

tailorBtn.addEventListener('click', async () => {
  const jobTitle       = document.getElementById('job-title').value.trim();
  const companyName    = document.getElementById('company-name').value.trim();
  const jobDescription = document.getElementById('job-description').value.trim();

  if (!jobTitle || !companyName || !jobDescription) {
    showError(tailorError, 'Please fill in all fields.');
    return;
  }

  setLoading(true, tailorLoading, tailorBtn);
  hide(tailorError);

  const payload = {
    session_id:        state.sessionId,
    job_title:         jobTitle,
    company_name:      companyName,
    job_description:   jobDescription,
    top_n_experience:  parseInt(document.getElementById('top-n-experience').value),
    top_n_projects:    parseInt(document.getElementById('top-n-projects').value),
  };

  try {
    const res = await fetch(API.tailor, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(tailorError, data.detail || 'Failed to tailor CV.');
      return;
    }

    state.tailoredId = data.tailored_session_id;
    renderResults(data);
    step3.classList.remove('hidden');
    step3.scrollIntoView({ behavior: 'smooth' });

  } catch (e) {
    showError(tailorError, 'Network error. Is the server running?');
  } finally {
    setLoading(false, tailorLoading, tailorBtn);
  }
});

// --- results ---

function renderResults(data) {
  // summary
  if (data.tailored_summary) {
    summaryBox.textContent = data.tailored_summary;
    summaryBox.classList.remove('hidden');
  }

  // relevance scores
  scoresBox.innerHTML = '';
  data.scores.forEach(item => {
    const div = document.createElement('div');
    div.className = 'score-item';

    const scoreClass = item.score >= 7 ? 'score-high'
                     : item.score >= 4 ? 'score-mid'
                     : 'score-low';

    div.innerHTML = `
      <div class="score-badge ${scoreClass}">${item.score}</div>
      <div>
        <div class="score-name">${item.name} <span class="score-type">${item.type}</span></div>
        <div class="score-reason">${item.reason}</div>
      </div>
    `;
    scoresBox.appendChild(div);
  });
}

// --- downloads ---

downloadDocx.addEventListener('click', () => {
  window.location.href = API.download(state.tailoredId, 'docx');
});

downloadPdf.addEventListener('click', () => {
  window.location.href = API.download(state.tailoredId, 'pdf');
});

// --- preview ---

previewBtn.addEventListener('click', () => {
  if (previewContainer.classList.contains('hidden')) {
    previewFrame.src = API.preview(state.tailoredId);
    previewContainer.classList.remove('hidden');
    previewBtn.textContent = 'Hide preview';
  } else {
    previewContainer.classList.add('hidden');
    previewFrame.src = '';
    previewBtn.textContent = 'Preview';
  }
});

// --- tailor another job ---

tailorAnother.addEventListener('click', () => {
  step3.classList.add('hidden');
  document.getElementById('job-title').value = '';
  document.getElementById('company-name').value = '';
  document.getElementById('job-description').value = '';
  previewContainer.classList.add('hidden');
  previewFrame.src = '';
  previewBtn.textContent = 'Preview';
  step2.scrollIntoView({ behavior: 'smooth' });
});

// --- helpers ---

function hide(el) { el.classList.add('hidden'); }

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove('hidden');
}

function setLoading(isLoading, loadingEl, btn) {
  if (isLoading) {
    loadingEl.classList.remove('hidden');
    btn.disabled = true;
  } else {
    loadingEl.classList.add('hidden');
    btn.disabled = false;
  }
}