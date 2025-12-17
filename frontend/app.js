const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000';

const form = document.getElementById('upload-form');
const statusEl = document.getElementById('status');
const downloadLink = document.getElementById('download-link');
const metadataSection = document.getElementById('metadata');
const metadataContent = document.getElementById('metadata-content');

let activeObjectUrl = null;

function setStatus(message, type = 'info') {
  statusEl.textContent = message;
  statusEl.dataset.type = type;
}

function parseContentDisposition(headerValue) {
  if (!headerValue) {
    return null;
  }
  const match = headerValue.match(/filename\*?=([^;]+)/i);
  if (!match) {
    return null;
  }
  const value = match[1].trim().replace(/^"|"$/g, '');
  try {
    return decodeURIComponent(value.replace(/UTF-8''/, ''));
  } catch (error) {
    return value;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  downloadLink.classList.add('hidden');
  metadataSection.classList.add('hidden');
  metadataContent.textContent = '';
  setStatus('Processing…');

  const modelFile = document.getElementById('model-file').files[0];
  if (!modelFile) {
    setStatus('Please choose an OBJ or DAE file.', 'error');
    submitButton.disabled = false;
    return;
  }

  const formData = new FormData();
  formData.append('file', modelFile);

  const mtlFile = document.getElementById('mtl-file').files[0];
  if (mtlFile) {
    formData.append('mtl', mtlFile);
  }

  formData.append('unit', document.getElementById('unit').value);
  formData.append('part', document.getElementById('part').value);
  formData.append('max_dim_limit', document.getElementById('max_dim_limit').value || '');
  formData.append('scale', document.getElementById('scale').value || '');
  formData.append('default_color', document.getElementById('default_color').value || '');
  formData.append('color_mode', document.getElementById('color_mode').value || 'none');

  const surface = document.getElementById('surface_thickness_mm').value;
  if (surface) {
    formData.append('surface_thickness_mm', surface);
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/process`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let detail = 'Processing failed.';
      try {
        const payload = await response.json();
        if (payload?.detail) {
          detail = payload.detail;
        }
      } catch (error) {
        // Ignore JSON parse errors and use default detail.
      }
      throw new Error(detail);
    }

    const metadataHeader = response.headers.get('X-Legoizer-Metadata');
    if (metadataHeader) {
      try {
        const metadata = JSON.parse(metadataHeader);
        metadataSection.classList.remove('hidden');
        metadataContent.textContent = JSON.stringify(metadata, null, 2);
      } catch (error) {
        // Metadata header is optional; ignore malformed content.
      }
    }

    const blob = await response.blob();
    if (activeObjectUrl) {
      URL.revokeObjectURL(activeObjectUrl);
    }
    activeObjectUrl = URL.createObjectURL(blob);
    downloadLink.href = activeObjectUrl;

    const filename = parseContentDisposition(response.headers.get('Content-Disposition')) || 'legoizer_result.mpd';
    downloadLink.download = filename;
    downloadLink.classList.remove('hidden');
    setStatus('Conversion complete.');
  } catch (error) {
    setStatus(error.message || 'Unexpected error.', 'error');
  } finally {
    submitButton.disabled = false;
  }
});

window.addEventListener('beforeunload', () => {
  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
  }
});
