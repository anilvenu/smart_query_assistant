// Load all prompts when the page loads
document.addEventListener('DOMContentLoaded', function() {
    loadPrompts();
    
    // Setup event listeners
    document.getElementById('search-input').addEventListener('input', filterPrompts);
    document.getElementById('add-prompt-btn').addEventListener('click', function() {
        window.location.href = '/admin/prompts/new';
    });
});

async function loadPrompts() {
    try {
        const response = await fetch('/api/prompts');
        if (!response.ok) {
            throw new Error('Failed to fetch prompts');
        }
        
        const prompts = await response.json();
        displayPrompts(prompts);
    } catch (error) {
        console.error('Error loading prompts:', error);
        document.getElementById('prompts-list').innerHTML = `
            <tr>
                <td colspan="7" class="error-message">
                    Failed to load prompts. Please try again later.
                </td>
            </tr>
        `;
    }
}

function displayPrompts(prompts) {
    const tableBody = document.getElementById('prompts-list');
    
    if (!prompts || prompts.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="no-data">No prompts found.</td>
            </tr>
        `;
        return;
    }
    
    const rows = prompts.map(prompt => {
        // Format the date
        const updatedAt = new Date(prompt.updated_at);
        const formattedDate = updatedAt.toLocaleDateString() + ' ' + 
                              updatedAt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        // Get parameter count
        const paramCount = prompt.parameter_count || 0;
        
        // Format verbose_flag flag
        const verboseText = prompt.verbose_flag ? 'Yes' : 'No';
        const verboseClass = prompt.verbose_flag ? 'status-success' : '';
        
        return `
            <tr data-id="${prompt.id}" data-name="${prompt.name.toLowerCase()}" data-description="${prompt.description.toLowerCase()}">
                <td>${prompt.id}</td>
                <td>${prompt.name}</td>
                <td>${prompt.description}</td>
                <td>${paramCount}</td>
                <td class="${verboseClass}">${verboseText}</td>
                <td>${formattedDate}</td>
                <td>
                    <button class="admin-btn small view-btn" onclick="viewPrompt('${prompt.id}')">View</button>
                    <button class="admin-btn small edit-btn" onclick="editPrompt('${prompt.id}')">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
    
    tableBody.innerHTML = rows;
}

function viewPrompt(promptId) {
    window.location.href = `/admin/prompts/${promptId}`;
}

function editPrompt(promptId) {
    window.location.href = `/admin/prompts/${promptId}/edit`;
}

function filterPrompts() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const rows = document.querySelectorAll('#prompts-list tr');
    
    rows.forEach(row => {
        const id = row.getAttribute('data-id').toLowerCase();
        const name = row.getAttribute('data-name').toLowerCase();
        const description = row.getAttribute('data-description').toLowerCase();
        
        if (id.includes(searchTerm) || name.includes(searchTerm) || description.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
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