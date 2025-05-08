// Global variable to store the current query
let currentQuery = null;

document.addEventListener('DOMContentLoaded', function() {
    // Get query ID from URL
    const pathParts = window.location.pathname.split('/');
    const queryId = pathParts[pathParts.length - 1];
    
    // Load query details
    loadQueryDetails(queryId);
    
    // Setup event listeners
    document.getElementById('back-btn').addEventListener('click', function() {
        window.location.href = '/admin/verified_queries';
    });
    
    document.getElementById('edit-query-btn').addEventListener('click', function() {
        window.location.href = `/admin/verified_query/${queryId}/edit`;
    });
    
    // Setup delete confirmation
    document.getElementById('delete-query-btn').addEventListener('click', function() {
        if (confirm(`Are you sure you want to delete this query? This action cannot be undone.`)) {
            deleteVerifiedQuery(queryId);
        }
    });
});

async function loadQueryDetails(queryId) {
    try {
        const response = await fetch(`/api/verified_query/${queryId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch query details: ${response.status}`);
        }
        
        const query = await response.json();
        currentQuery = query;
        displayQueryDetails(query);
    } catch (error) {
        console.error('Error loading query details:', error);
        document.querySelector('.query-detail-container').innerHTML = `
            <div class="error-message">
                Failed to load query details. Please try again later.
            </div>
        `;
    }
}

function displayQueryDetails(query) {
    // Display basic information
    document.getElementById('query-name').textContent = query.name;
    document.getElementById('query-id').textContent = query.id;
    document.getElementById('query-verified-by').textContent = query.verified_by;
    
    // Format and display verified_at date
    const verifiedAt = new Date(query.verified_at);
    document.getElementById('query-verified-at').textContent = verifiedAt.toLocaleDateString() + ' ' + 
                                                             verifiedAt.toLocaleTimeString();
    
    // Display explanation
    document.getElementById('query-explanation').textContent = query.query_explanation;
    
    // Display SQL with syntax highlighting
    const sqlElement = document.getElementById('query-sql');
    sqlElement.textContent = query.sql;
    hljs.highlightElement(sqlElement);
    
    // Display instructions
    document.getElementById('query-instructions').textContent = query.instructions || 'No instructions provided.';
    
    // Display tables used
    const tablesContainer = document.getElementById('query-tables');
    if (query.tables_used && query.tables_used.length > 0) {
        tablesContainer.innerHTML = query.tables_used.map(table => 
            `<span class="tag">${table}</span>`
        ).join('');
    } else {
        tablesContainer.textContent = 'No tables specified.';
    }
    
    // Display questions
    const questionsContainer = document.getElementById('query-questions');
    if (query.questions && query.questions.length > 0) {
        questionsContainer.innerHTML = query.questions.map(question => 
            `<li>${question.text}</li>`
        ).join('');
    } else {
        questionsContainer.innerHTML = '<li class="no-data">No questions available.</li>';
    }
    
    // Display follow-ups
    const followupsContainer = document.getElementById('query-followups');
    if (query.follow_ups && query.follow_ups.length > 0) {
        // For now, just display the IDs. In Phase 2, we'll fetch the names.
        followupsContainer.innerHTML = query.follow_ups.map(followupId => 
            `<li onclick="viewQuery('${followupId}')">${followupId}</li>`
        ).join('');
    } else {
        followupsContainer.innerHTML = '<li class="no-data">No follow-up queries available.</li>';
    }
}

function viewQuery(queryId) {
    window.location.href = `/admin/verified_query/${queryId}`;
}

async function deleteVerifiedQuery(queryId) {
    try {
        const response = await fetch(`/api/verified_query/${queryId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to delete query');
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            // Show success notification
            showNotification('Query deleted successfully', 'success');
            
            // Redirect to queries list after a brief delay
            setTimeout(() => {
                window.location.href = '/admin/verified_queries';
            }, 1500);
        } else {
            throw new Error(result.detail || 'Failed to delete query');
        }
        
    } catch (error) {
        console.error('Error deleting query:', error);
        showNotification(`Error: ${error.message}`, 'error');
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
    

    
}