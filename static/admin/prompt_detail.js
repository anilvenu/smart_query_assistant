// Global variable to store the current prompt
let currentPrompt = null;

document.addEventListener('DOMContentLoaded', function() {
    // Get prompt ID from URL
    const pathParts = window.location.pathname.split('/');
    const promptId = pathParts[pathParts.length - 1];
    
    // Load prompt details
    loadPromptDetails(promptId);
    
    // Setup event listeners with null checks
    const backBtn = document.getElementById('back-btn');
    if (backBtn) {
        backBtn.addEventListener('click', function() {
            window.location.href = '/admin/prompts';
        });
    } else {
        console.warn("'back-btn' element not found in the DOM");
    }
    
    const editPromptBtn = document.getElementById('edit-prompt-btn');
    if (editPromptBtn) {
        editPromptBtn.addEventListener('click', function() {
            window.location.href = `/admin/prompts/${promptId}/edit`;
        });
    } else {
        console.warn("'edit-prompt-btn' element not found in the DOM");
    }
    
    // Setup delete confirmation with null check
    const deletePromptBtn = document.getElementById('delete-prompt-btn');
    if (deletePromptBtn) {
        deletePromptBtn.addEventListener('click', function() {
            if (confirm(`Are you sure you want to delete this prompt? This action cannot be undone.`)) {
                deletePrompt(promptId);
            }
        });
    } else {
        console.warn("'delete-prompt-btn' element not found in the DOM");
    }
    
    // Setup test prompt button with null check
    const testPromptBtn = document.getElementById('test-prompt-btn');
    if (testPromptBtn) {
        testPromptBtn.addEventListener('click', function() {
            testPrompt(promptId);
        });
    } else {
        console.warn("'test-prompt-btn' element not found in the DOM");
    }
});

async function loadPromptDetails(promptId) {
    try {
        // Show loading state without replacing the entire structure
        const detailContainer = document.querySelector('.query-detail-container');
        
        // Add a loading overlay instead of replacing content
        const loadingOverlay = document.createElement('div');
        loadingOverlay.className = 'loading-overlay';
        loadingOverlay.innerHTML = '<div class="loading-message">Loading prompt details...</div>';
        detailContainer.appendChild(loadingOverlay);
        
        const response = await fetch(`/api/prompts/${promptId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch prompt details: ${response.status}`);
        }
        
        const prompt = await response.json();
        console.log("Received prompt data:", prompt);
        
        // Check if prompt has the expected structure
        if (!prompt || typeof prompt !== 'object') {
            throw new Error("Invalid prompt data received");
        }
        
        // Remove loading overlay
        detailContainer.removeChild(loadingOverlay);
        
        currentPrompt = prompt;
        displayPromptDetails(prompt);
    } catch (error) {
        console.error('Error loading prompt details:', error);
        
        // Show error without replacing the entire structure
        const errorElement = document.createElement('div');
        errorElement.className = 'error-message';
        errorElement.textContent = `Failed to load prompt details: ${error.message}`;
        
        // Remove loading overlay if it exists
        const loadingOverlay = document.querySelector('.loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.parentNode.removeChild(loadingOverlay);
        }
        
        // Add the error message at the top of the container
        const detailContainer = document.querySelector('.query-detail-container');
        detailContainer.insertBefore(errorElement, detailContainer.firstChild);
    }
}

function safeSetElementText(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
        return true;
    }
    console.warn(`Element with ID "${elementId}" not found in the DOM`);
    return false;
}

function displayPromptDetails(prompt) {
    try {
        // Log the prompt to see exactly what data we're working with
        console.log("Prompt data:", prompt);
        
        // Use the safe function for all text content setting
        safeSetElementText('prompt-name', prompt.name);
        safeSetElementText('prompt-id', prompt.id);
        safeSetElementText('prompt-verbose', prompt.verbose_flag ? 'Yes' : 'No');
        
        // Format and display updated_at date
        if (prompt.updated_at) {
            const updatedAt = new Date(prompt.updated_at);
            safeSetElementText('prompt-updated-at', updatedAt.toLocaleDateString() + ' ' + 
                                                  updatedAt.toLocaleTimeString());
        }
        
        // Display description
        safeSetElementText('prompt-description', prompt.description);
        
        // Display prompts with syntax highlighting
        const systemPromptEl = document.getElementById('system-prompt');
        if (systemPromptEl) {
            systemPromptEl.textContent = prompt.system_prompt;
            hljs.highlightElement(systemPromptEl);
        }
        
        const userPromptEl = document.getElementById('user-prompt');
        if (userPromptEl) {
            userPromptEl.textContent = prompt.user_prompt;
            hljs.highlightElement(userPromptEl);
        }
        
        // Display parameters
        const parametersContainer = document.getElementById('prompt-parameters');
        if (parametersContainer) {
            if (prompt.parameters && prompt.parameters.length > 0) {
                parametersContainer.innerHTML = prompt.parameters.map(param => 
                    `<li>
                        <strong>${param.param_name}</strong>
                        ${param.required ? '<span class="tag required">Required</span>' : '<span class="tag optional">Optional</span>'}
                        <div>${param.description}</div>
                        ${param.default_value ? `<div><em>Default: ${param.default_value}</em></div>` : ''}
                    </li>`
                ).join('');
            } else {
                parametersContainer.innerHTML = '<li class="no-data">No parameters available.</li>';
            }
        }
        
        // Generate test parameter form if the function exists
        if (typeof generateTestForm === 'function') {
            generateTestForm(prompt.parameters);
        }
    } catch (error) {
        console.error("Error in displayPromptDetails:", error);
        document.querySelector('.query-detail-container').innerHTML = `
            <div class="error-message">
                Failed to display prompt details: ${error.message}
            </div>
        `;
    }
}

function generateTestForm(parameters) {
    const formContainer = document.getElementById('test-parameters-form');
    if (!formContainer) {
        console.warn("'test-parameters-form' element not found in the DOM");
        return; // Exit early if element doesn't exist
    }
    
    if (!parameters || parameters.length === 0) {
        formContainer.innerHTML = '<p class="no-data">No parameters available for testing.</p>';
        return;
    }
    
    let html = '';
    
    // Generate form fields for each parameter
    parameters.forEach(param => {
        const inputId = `param-${param.param_name}`;
        const isRequired = param.required;
        
        html += `
            <div class="form-group">
                <label for="${inputId}">
                    ${param.param_name}
                    ${isRequired ? '<span class="required-mark">*</span>' : ''}
                </label>
                <div class="parameter-description">${param.description}</div>
        `;
        
        // For complex parameters (JSON objects/arrays), use textarea
        if (param.default_value && (param.default_value.startsWith('{') || param.default_value.startsWith('['))) {
            html += `
                <textarea 
                    id="${inputId}" 
                    name="${param.param_name}" 
                    rows="4" 
                    class="form-control" 
                    ${isRequired ? 'required' : ''}
                    placeholder="${param.default_value ? 'Default: ' + param.default_value : ''}"
                >${param.default_value || ''}</textarea>
            `;
        } else {
            html += `
                <input 
                    type="text" 
                    id="${inputId}" 
                    name="${param.param_name}" 
                    class="form-control" 
                    ${isRequired ? 'required' : ''}
                    placeholder="${param.default_value ? 'Default: ' + param.default_value : ''}"
                    value="${param.default_value || ''}"
                />
            `;
        }
        
        html += '</div>';
    });
    
    formContainer.innerHTML = html;
}

async function testPrompt(promptId) {
    try {
        // Get parameter values from form
        const parameters = {};
        const paramInputs = document.querySelectorAll('#test-parameters-form [name]');
        
        paramInputs.forEach(input => {
            const paramName = input.name;
            let paramValue = input.value.trim();
            
            // Try to parse JSON for object and array parameters
            if (paramValue.startsWith('{') || paramValue.startsWith('[')) {
                try {
                    paramValue = JSON.parse(paramValue);
                } catch (e) {
                    // If not valid JSON, keep as string
                }
            }
            
            parameters[paramName] = paramValue;
        });
        
        // Show loading state
        document.getElementById('test-prompt-btn').textContent = 'Testing...';
        document.getElementById('test-prompt-btn').disabled = true;
        
        // Send request to test endpoint
        const response = await fetch('/api/prompts/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt_id: promptId,
                parameters: parameters
            })
        });
        
        // Reset button state
        document.getElementById('test-prompt-btn').textContent = 'Test Prompt';
        document.getElementById('test-prompt-btn').disabled = false;
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error: ${response.status}`);
        }
        
        const result = await response.json();
        
        // Display the results
        document.getElementById('test-results').classList.remove('hidden');
        
        // Display formatted prompts
        document.getElementById('formatted-system-prompt').textContent = result.formatted_prompt.system_prompt;
        document.getElementById('formatted-user-prompt').textContent = result.formatted_prompt.user_prompt;
        
        // Display the result
        const resultElement = document.getElementById('prompt-test-result');
        
        // Format the result based on type
        if (typeof result.result === 'object') {
            resultElement.textContent = JSON.stringify(result.result, null, 2);
        } else {
            resultElement.textContent = result.result;
        }
        
        // Scroll to results
        document.getElementById('test-results').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error testing prompt:', error);
        showNotification(`Error: ${error.message}`, 'error');
    }
}

async function deletePrompt(promptId) {
    try {
        const response = await fetch(`/api/prompts/${promptId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to delete prompt');
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            // Show success notification
            showNotification('Prompt deleted successfully', 'success');
            
            // Redirect to prompts list after a brief delay
            setTimeout(() => {
                window.location.href = '/admin/prompts';
            }, 1500);
        } else {
            throw new Error(result.detail || 'Failed to delete prompt');
        }
        
    } catch (error) {
        console.error('Error deleting prompt:', error);
        showNotification(`Error: ${error.message}`, 'error');
    }
}

function showNotification(message, type) {
    // Check if notification container exists
    let container = document.getElementById('notification-container');
    
    if (!container) {
        // Create container if it doesn't exist
        container = document.createElement('div');
        container.id = 'notification-container';
        document.body.appendChild(container);
    }
    
    // Create notification
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    // Add to container
    container.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            container.removeChild(notification);
        }, 300);
    }, 3000);
}