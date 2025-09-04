// JavaScript for file upload and UI interactions

document.addEventListener('DOMContentLoaded', function() {
    
    // File upload drag and drop functionality
    initializeFileUpload();
    
    // Form validation
    initializeFormValidation();
    
    // Auto-hide alerts
    autoHideAlerts();
    
    // Initialize tooltips if Bootstrap tooltips are used
    initializeTooltips();
});

function initializeFileUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(function(input) {
        const form = input.closest('form');
        if (!form) return;
        
        // Add drag and drop functionality
        form.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            form.classList.add('dragover');
        });
        
        form.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            form.classList.remove('dragover');
        });
        
        form.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            form.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                input.files = files;
                updateFileInputLabel(input, files[0].name);
            }
        });
        
        // Update label when file is selected
        input.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                updateFileInputLabel(input, e.target.files[0].name);
            }
        });
    });
}

function updateFileInputLabel(input, filename) {
    const label = input.nextElementSibling;
    if (label && label.classList.contains('form-label')) {
        label.textContent = `Selected: ${filename}`;
    }
}

function initializeFormValidation() {
    // Add client-side validation for forms
    const forms = document.querySelectorAll('form');
    
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            // File upload validation
            const fileInputs = form.querySelectorAll('input[type="file"][required]');
            fileInputs.forEach(function(input) {
                if (!input.files.length) {
                    e.preventDefault();
                    showAlert('Please select a file to upload.', 'warning');
                    return false;
                }
                
                const file = input.files[0];
                
                // Check file type
                if (!file.name.toLowerCase().endsWith('.pdf')) {
                    e.preventDefault();
                    showAlert('Please select a PDF file.', 'danger');
                    return false;
                }
                
                // Check file size (16MB limit)
                const maxSize = 16 * 1024 * 1024;
                if (file.size > maxSize) {
                    e.preventDefault();
                    showAlert('File size must be less than 16MB.', 'danger');
                    return false;
                }
            });
            
            // Add loading state to submit buttons
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.classList.add('loading');
                submitBtn.disabled = true;
                
                // Add spinner - using safe DOM manipulation
                const originalContent = submitBtn.cloneNode(true);
                
                // Clear button content safely
                while (submitBtn.firstChild) {
                    submitBtn.removeChild(submitBtn.firstChild);
                }
                
                // Create spinner element safely
                const spinner = document.createElement('span');
                spinner.className = 'spinner-border spinner-border-sm me-2';
                submitBtn.appendChild(spinner);
                
                const text = document.createTextNode('Processing...');
                submitBtn.appendChild(text);
                
                // Reset button state if form submission fails
                setTimeout(function() {
                    if (submitBtn.classList.contains('loading')) {
                        submitBtn.classList.remove('loading');
                        submitBtn.disabled = false;
                        
                        // Restore original content safely
                        while (submitBtn.firstChild) {
                            submitBtn.removeChild(submitBtn.firstChild);
                        }
                        
                        // Clone original content back
                        while (originalContent.firstChild) {
                            submitBtn.appendChild(originalContent.firstChild);
                        }
                    }
                }, 10000); // Reset after 10 seconds
            }
        });
    });
}

function autoHideAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(function(alert) {
        // Auto-hide success alerts after 5 seconds
        if (alert.classList.contains('alert-success')) {
            setTimeout(function() {
                if (alert && alert.parentNode) {
                    alert.style.transition = 'opacity 0.5s';
                    alert.style.opacity = '0';
                    setTimeout(function() {
                        if (alert.parentNode) {
                            alert.parentNode.removeChild(alert);
                        }
                    }, 500);
                }
            }, 5000);
        }
    });
}

function initializeTooltips() {
    // Initialize Bootstrap tooltips if available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

function showAlert(message, type = 'info') {
    // Create and show a dynamic alert
    const alertContainer = document.querySelector('.container');
    if (!alertContainer) return;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    
    // Create message text safely
    const messageText = document.createTextNode(message);
    
    // Create close button
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'alert');
    
    alertDiv.appendChild(messageText);
    alertDiv.appendChild(closeBtn);
    
    // Insert after the first element in container (usually after nav)
    alertContainer.insertBefore(alertDiv, alertContainer.firstChild);
    
    // Auto-hide after 5 seconds
    setTimeout(function() {
        if (alertDiv && alertDiv.parentNode) {
            alertDiv.style.transition = 'opacity 0.5s';
            alertDiv.style.opacity = '0';
            setTimeout(function() {
                if (alertDiv.parentNode) {
                    alertDiv.parentNode.removeChild(alertDiv);
                }
            }, 500);
        }
    }, 5000);
}

// Utility functions for AJAX calls (if needed later)
function makeAjaxRequest(url, method = 'GET', data = null) {
    return fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: data ? JSON.stringify(data) : null
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    });
}

// Format currency for display
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// Debounce function for search inputs
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = function() {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}