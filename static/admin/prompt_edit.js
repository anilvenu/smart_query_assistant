// Global variables
let isNew = false;
let promptId = '';
let parameters = [];
let currentPrompt = null;

document.addEventListener('DOMContentLoaded', function() {
    // Determine if this is a new prompt or editing an existing one
    const pathParts = window.location.pathname.split('/');
    isNew = pathParts.includes('new');
    
    if (!isNew) {
        promptId = pathParts[pathParts.length - 2]; // URL format: /admin/prompts/{id}/edit
    } else {
        // Generate a suggested ID based on name
        document.getElementById('prompt-name').addEventListener('blur', function() {
            const nameField = document.getElementById('prompt-name');
            const idField = document.getElementById('prompt-id');
            
            // Only suggest ID if not already filled
            if (idField.value === '' && nameField.value !== '') {
                // Convert name to snake_case
                const suggestedId = nameField.value
                    .toLowerCase()
                    .replace(/[^\w\s]/g, '') // Remove special characters
                    .replace(/\s+/g, '_');   // Replace spaces with underscores
                
                idField.value = suggestedId;
            }
        });
    }

    // Initialize form
    initForm();
    
    // Setup event listeners
    setupEventListeners();
});

async function initForm() {
    if (isNew) {
        // Set default values for new prompt
        document.getElementById('prompt-verbose_flag').checked = false;
    } else {
        // Load existing prompt data
        await loadPromptData();
    }
}

async function loadPromptData() {
    try {
        const response = await fetch(`/api/prompts/${promptId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch prompt: ${response.status}`);
        }
        
        currentPrompt = await response.json();
        
        // Populate form fields
        document.getElementById('prompt-id').value = currentPrompt.id;
        document.getElementById('prompt-name').value = currentPrompt.name;
        document.getElementById('prompt-description').value = currentPrompt.description;
        document.getElementById('prompt-verbose_flag').checked = currentPrompt.verbose_flag;
        document.getElementById('system-prompt').value = currentPrompt.system_prompt;
        document.getElementById('user-prompt').value = currentPrompt.user_prompt;
        
        // Set parameters
        if (currentPrompt.parameters && currentPrompt.parameters.length > 0) {
            parameters = currentPrompt.parameters.map(p => ({
                id: p.id,
                param_name: p.param_name,
                description: p.description,
                default_value: p.default_value,
                required: p.required
            }));
            renderParameters();
        }
    } catch (error) {
        console.error('Error loading prompt data:', error);
        showNotification('Failed to load prompt data', 'error');
    }
}

function setupEventListeners() {
    // Back and Cancel buttons
    document.getElementById('back-btn').addEventListener('click', function() {
        window.location.href = isNew ? '/admin/prompts' : `/admin/prompts/${promptId}`;
    });
    
    document.getElementById('cancel-btn').addEventListener('click', function() {
        window.location.href = isNew ? '/admin/prompts' : `/admin/prompts/${promptId}`;
    });
    
    // Save button
    document.getElementById('save-btn').addEventListener('click', savePrompt);
    
    // Add parameter button
    document.getElementById('add-parameter-btn').addEventListener('click', addParameter);
}

function addParameter() {
    const nameInput = document.getElementById('parameter-name');
    const descInput = document.getElementById('parameter-description');
    const defaultInput = document.getElementById('parameter-default');
    const requiredCheckbox = document.getElementById('parameter-required');
    
    const paramName = nameInput.value.trim();
    const description = descInput.value.trim();
    const defaultValue = defaultInput.value.trim() || null;
    const required = requiredCheckbox.checked;
    
    // Validate parameter name
    if (!paramName) {
        showNotification('Parameter name is required', 'error');
        nameInput.focus();
        return;
    }
    
    // Check for duplicate parameter names
    if (parameters.some(p => p.param_name === paramName)) {
        showNotification('Parameter with this name already exists', 'error');
        nameInput.focus();
        return;
    }
    
    // Add parameter
    parameters.push({
        param_name: paramName,
        description: description || `Parameter ${paramName}`,
        default_value: defaultValue,
        required: required
    });
    
    // Clear inputs
    nameInput.value = '';
    descInput.value = '';
    defaultInput.value = '';
    requiredCheckbox.checked = true;
    
    // Update UI
    renderParameters();
    
    // Focus back on name input for next parameter
    nameInput.focus();
}

function renderParameters() {
    const container = document.getElementById('parameters-container');
    container.innerHTML = '';
    
    if (parameters.length === 0) {
        container.innerHTML = '<div class="no-parameters">No parameters defined. Add parameters above.</div>';
        return;
    }
    
    parameters.forEach((param, index) => {
        const item = document.createElement('div');
        item.className = 'parameter-item';
        
        const requiredTag = param.required 
            ? '<span class="tag required">Required</span>' 
            : '<span class="tag optional">Optional</span>';
        
        const defaultValue = param.default_value 
            ? `<span class="parameter-default">Default: ${param.default_value}</span>` 
            : '';
        
        item.innerHTML = `
            <div class="parameter-header">
                <strong class="parameter-name">${param.param_name}</strong>
                ${requiredTag}
                <button class="admin-btn small remove-btn" data-index="${index}">Remove</button>
            </div>
            <div class="parameter-body">
                <div class="parameter-description">${param.description}</div>
                ${defaultValue}
            </div>
        `;
        
        container.appendChild(item);
    });
    
    // Update hidden input
    document.getElementById('parameters').value = JSON.stringify(parameters);
    
    // Add event listeners to remove buttons
    document.querySelectorAll('#parameters-container .remove-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            parameters.splice(index, 1);
            renderParameters();
        });
    });
}

async function savePrompt() {
    try {
        // Validate form
        const form = document.getElementById('prompt-form');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // Get form data
        const formData = {
            id: document.getElementById('prompt-id').value.trim(),
            name: document.getElementById('prompt-name').value.trim(),
            description: document.getElementById('prompt-description').value.trim(),
            system_prompt: document.getElementById('system-prompt').value.trim(),
            user_prompt: document.getElementById('user-prompt').value.trim(),
            verbose_flag: document.getElementById('prompt-verbose_flag').checked,
            parameters: parameters
        };
        
        // Validate parameters against user prompt
        const userPrompt = formData.user_prompt;
        const templateParams = extractTemplateParams(userPrompt);
        const paramNames = parameters.map(p => p.param_name);
        
        // Check for parameters used in the template but not defined
        const missingParams = templateParams.filter(p => !paramNames.includes(p));
        if (missingParams.length > 0) {
            const warningMessage = `Warning: The following parameters are used in the template but not defined: ${missingParams.join(', ')}`;
            
            if (!confirm(`${warningMessage}\n\nDo you want to continue anyway?`)) {
                return;
            }
        }
        
        // Show saving indicator
        document.getElementById('save-btn').textContent = 'Saving...';
        document.getElementById('save-btn').disabled = true;
        
        // Determine if this is a create or update
        const url = isNew ? '/api/prompts' : `/api/prompts/${promptId}`;
        const method = isNew ? 'POST' : 'PUT';
        
        // Send request
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        // Reset button state
        document.getElementById('save-btn').textContent = 'Save Prompt';
        document.getElementById('save-btn').disabled = false;
        
        let errorMessage = '';
        
        if (!response.ok) {
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || `HTTP error: ${response.status}`;
            } catch (jsonError) {
                // If response is not valid JSON
                errorMessage = `HTTP error: ${response.status}. Response is not valid JSON.`;
            }
            throw new Error(errorMessage);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification('Prompt saved successfully', 'success');
            
            // Redirect to detail view after a brief delay
            setTimeout(() => {
                const savedId = formData.id.replace(/\/$/, '');
                window.location.href = `/admin/prompts/${savedId}`;
            }, 1000);
        } else {
            throw new Error(result.message || 'Failed to save prompt');
        }

    } catch (error) {
        console.error('Error saving prompt:', error);
        showNotification(`Failed to save prompt: ${error.message}`, 'error');
    }
}

// Extract template parameters from a user prompt
function extractTemplateParams(template) {
    const regex = /\{([^{}]*)\}/g;
    const matches = [...template.matchAll(regex)];
    
    // Extract the parameter names without formatting specs
    return matches.map(match => {
        const param = match[1];
        // Handle formatting specs and nested attributes
        return param.split(':')[0].split('.')[0].trim();
    }).filter((value, index, self) => {
        // Remove duplicates
        return self.indexOf(value) === index;
    });
}

function showNotification(message, type) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    
    // Remove 'hidden' class to show notification
    notification.classList.remove('hidden');
    
    // Hide notification after 3 seconds
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}