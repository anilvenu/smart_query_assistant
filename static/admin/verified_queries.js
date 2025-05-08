// Load all verified queries when the page loads
document.addEventListener('DOMContentLoaded', function() {
    loadVerifiedQueries();
    
    // Setup event listeners
    document.getElementById('search-input').addEventListener('input', filterQueries);
    document.getElementById('add-query-btn').addEventListener('click', function() {
        window.location.href = '/admin/verified_query/new/edit';
    });
});

async function loadVerifiedQueries() {
    try {
        const response = await fetch('/api/verified_queries');
        if (!response.ok) {
            throw new Error('Failed to fetch queries');
        }
        
        const queries = await response.json();
        displayQueries(queries);
    } catch (error) {
        console.error('Error loading queries:', error);
        document.getElementById('queries-list').innerHTML = `
            <tr>
                <td colspan="7" class="error-message">
                    Failed to load queries. Please try again later.
                </td>
            </tr>
        `;
    }
}

function displayQueries(queries) {
    const tableBody = document.getElementById('queries-list');
    
    if (!queries || queries.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="no-data">No verified queries found.</td>
            </tr>
        `;
        return;
    }
    
    const rows = queries.map(query => {
        // Format the date
        const verifiedAt = new Date(query.verified_at);
        const formattedDate = verifiedAt.toLocaleDateString() + ' ' + 
                              verifiedAt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        // Get question count
        const questionCount = query.questions ? query.questions.length : 0;
        
        // Get follow-up count
        const followUpCount = query.follow_ups ? query.follow_ups.length : 0;
        
        // Format tables used
        const tablesUsed = query.tables_used ? query.tables_used.join(', ') : '-';
        
        return `
            <tr data-id="${query.id}" data-name="${query.name.toLowerCase()}">
                <td>${query.id}</td>
                <td>${query.name}</td>
                <td>${tablesUsed}</td>
                <td>${questionCount}</td>
                <td>${followUpCount}</td>
                <td>${formattedDate}</td>
                <td>
                    <button class="admin-btn small view-btn" onclick="viewQuery('${query.id}')">View</button>
                    <button class="admin-btn small edit-btn" onclick="editQuery('${query.id}')">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
    
    tableBody.innerHTML = rows;
}

function viewQuery(queryId) {
    window.location.href = `/admin/verified_query/${queryId}`;
}
function editQuery(queryId) {
    window.location.href = `/admin/verified_query/${queryId}/edit`;
}

function filterQueries() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const rows = document.querySelectorAll('#queries-list tr');
    
    rows.forEach(row => {
        const id = row.getAttribute('data-id').toLowerCase();
        const name = row.getAttribute('data-name').toLowerCase();
        
        if (id.includes(searchTerm) || name.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}