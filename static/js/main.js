document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the results page with a task ID
    const taskIdElement = document.getElementById('task-id');
    if (taskIdElement) {
        const taskId = taskIdElement.getAttribute('data-task-id');
        if (taskId) {
            updateTaskStatus(taskId);
        }
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Form validation
    const scrapeForm = document.getElementById('scrape-form');
    if (scrapeForm) {
        scrapeForm.addEventListener('submit', function(event) {
            if (!scrapeForm.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            scrapeForm.classList.add('was-validated');
        });
    }
});

function updateTaskStatus(taskId) {
    fetch(`/status/${taskId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch task status');
            }
            return response.json();
        })
        .then(data => {
            // Update progress bar
            const progressBar = document.getElementById('progress-bar');
            if (progressBar) {
                const progress = Math.round(data.progress);
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                progressBar.textContent = `${progress}%`;
                
                // Set color based on status
                progressBar.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');
                
                if (data.status === 'completed') {
                    progressBar.classList.add('bg-success');
                } else if (data.status === 'failed') {
                    progressBar.classList.add('bg-danger');
                } else if (data.status === 'running') {
                    progressBar.classList.add('bg-info');
                } else {
                    progressBar.classList.add('bg-warning');
                }
            }
            
            // Update status text
            const statusElement = document.getElementById('status-text');
            if (statusElement) {
                statusElement.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
                
                // Change status color based on state
                statusElement.classList.remove('text-success', 'text-danger', 'text-warning', 'text-info');
                
                if (data.status === 'completed') {
                    statusElement.classList.add('text-success');
                } else if (data.status === 'failed') {
                    statusElement.classList.add('text-danger');
                } else if (data.status === 'running') {
                    statusElement.classList.add('text-info');
                } else {
                    statusElement.classList.add('text-warning');
                }
            }
            
            // Update statistics
            updateStatElement('files-count', data.files_downloaded);
            updateStatElement('total-size', formatBytes(data.total_size));
            
            // Update errors
            const errorsList = document.getElementById('errors-list');
            if (errorsList) {
                errorsList.innerHTML = '';
                
                if (data.errors && data.errors.length > 0) {
                    document.getElementById('errors-container').classList.remove('d-none');
                    
                    data.errors.forEach(error => {
                        const li = document.createElement('li');
                        li.classList.add('list-group-item', 'bg-dark', 'text-danger');
                        li.textContent = error;
                        errorsList.appendChild(li);
                    });
                } else {
                    document.getElementById('errors-container').classList.add('d-none');
                }
            }
            
            // Continue polling if the task is still running
            if (data.status === 'running' || data.status === 'starting') {
                setTimeout(() => updateTaskStatus(taskId), 1000);
            } else {
                // Task is complete or failed, update UI accordingly
                const downloadBtn = document.getElementById('download-btn');
                if (downloadBtn) {
                    downloadBtn.classList.remove('disabled');
                    
                    // Add a title tooltip to explain what the button does
                    const tooltipTitle = (data.status === 'completed') 
                        ? 'View the archived website in a new tab' 
                        : 'View the partially archived website';
                    
                    downloadBtn.setAttribute('title', tooltipTitle);
                    downloadBtn.setAttribute('data-bs-toggle', 'tooltip');
                    downloadBtn.setAttribute('data-bs-placement', 'top');
                    
                    // Initialize the tooltip
                    new bootstrap.Tooltip(downloadBtn);
                }
                
                // Show completion message
                if (data.status === 'completed') {
                    showAlert('Scraping completed successfully!', 'success');
                } else if (data.status === 'failed') {
                    showAlert('Scraping failed. Check the errors below.', 'danger');
                }
            }
        })
        .catch(error => {
            console.error('Error fetching task status:', error);
            showAlert('Failed to update status. Please refresh the page.', 'danger');
        });
}

function updateStatElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function showAlert(message, type) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;
    
    const alert = document.createElement('div');
    alert.classList.add('alert', `alert-${type}`, 'alert-dismissible', 'fade', 'show', 'alert-fixed');
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertContainer.appendChild(alert);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}
