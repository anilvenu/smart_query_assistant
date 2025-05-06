// Global variables
let isNew = false;
let queryId = '';
let tablesUsed = [];
let questions = [];
let followUps = [];
let queryOptions = [];
let currentQuery = null;

document.addEventListener('DOMContentLoaded', function() {
    // Determine if this is a new query or editing an existing one
    const pathParts = window.location.pathname.split('/');
    isNew = pathParts.includes('new');
    const findMatchSection = document.getElementById('find-match-section');
    
    if (!isNew) {
        queryId = pathParts[pathParts.length - 2]; // URL format: /admin/verified_query/{id}/edit
        findMatchSection.style.display = 'none';     // Show/hide find match section based on isNew
    }

    // Initialize form
    initForm();
    
    // Setup event listeners
    setupEventListeners();
});v

async function initForm() {
    // Load query options for follow-ups
    await loadQueryOptions();
    
    if (isNew) {
        // Set default values for new query
        document.getElementById('query-verified-by').value = 'data_analyst';
    } else {
        // Load existing query data
        await loadQueryData();
    }
}

async function loadQueryOptions() {
    try {
        const response = await fetch('/api/verified_queries/options');
        if (!response.ok) {
            throw new Error(`Failed to fetch query options: ${response.status}`);
        }
        
        queryOptions = await response.json();
        
        // Populate the follow-up select dropdown
        const select = document.getElementById('followup-select');
        
        // Clear existing options (except the first placeholder)
        while (select.options.length > 1) {
            select.remove(1);
        }
        
        // Add new options
        queryOptions.forEach(option => {
            if (option.id !== queryId) { // Don't include the current query in options
                const optionElement = document.createElement('option');
                optionElement.value = option.id;
                optionElement.textContent = `${option.name} (${option.id})`;
                select.appendChild(optionElement);
            }
        });
    } catch (error) {
        console.error('Error loading query options:', error);
        showNotification('Failed to load follow-up options', 'error');
    }
}

async function loadQueryData() {
    try {
        const response = await fetch(`/api/verified_query/${queryId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch query: ${response.status}`);
        }
        
        currentQuery = await response.json();
        
        // Populate form fields
        document.getElementById('query-id').value = currentQuery.id;
        document.getElementById('query-name').value = currentQuery.name;
        document.getElementById('query-verified-by').value = currentQuery.verified_by;
        document.getElementById('query-explanation').value = currentQuery.query_explanation;
        document.getElementById('query-sql').value = currentQuery.sql;
        document.getElementById('query-instructions').value = currentQuery.instructions || '';
        
        // Set tables used
        tablesUsed = currentQuery.tables_used || [];
        renderTables();
        
        // Set questions
        if (currentQuery.questions && currentQuery.questions.length > 0) {
            questions = currentQuery.questions.map(q => q.text);
            renderQuestions();
        }
        
        // Set follow-ups
        if (currentQuery.follow_ups && currentQuery.follow_ups.length > 0) {
            followUps = currentQuery.follow_ups;
            renderFollowUps();
        }
    } catch (error) {
        console.error('Error loading query data:', error);
        showNotification('Failed to load query data', 'error');
    }
}

function setupEventListeners() {
    // Back and Cancel buttons
    document.getElementById('back-btn').addEventListener('click', function() {
        window.location.href = isNew ? '/admin/verified_queries' : `/admin/verified_query/${queryId}`;
    });
    
    document.getElementById('cancel-btn').addEventListener('click', function() {
        window.location.href = isNew ? '/admin/verified_queries' : `/admin/verified_query/${queryId}`;
    });
    
    // Find matching query button
    document.getElementById('find-match-btn').addEventListener('click', findMatchingQuery);

    // Run test query button
    document.getElementById('run-query-btn').addEventListener('click', runTestQuery);

    // Save button
    document.getElementById('save-btn').addEventListener('click', saveQuery);
    
    // Tables input
    const tablesInput = document.getElementById('tables-input');
    tablesInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const table = tablesInput.value.trim();
            if (table && !tablesUsed.includes(table)) {
                tablesUsed.push(table);
                renderTables();
                tablesInput.value = '';
            }
        }
    });
    
    // Questions input
    const questionInput = document.getElementById('question-input');
    questionInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const question = questionInput.value.trim();
            if (question && !questions.includes(question)) {
                questions.push(question);
                renderQuestions();
                questionInput.value = '';
            }
        }
    });
    
    // Add follow-up button
    document.getElementById('add-followup-btn').addEventListener('click', function() {
        const select = document.getElementById('followup-select');
        const selectedId = select.value;
        
        if (selectedId && !followUps.includes(selectedId)) {
            followUps.push(selectedId);
            renderFollowUps();
            select.value = ''; // Reset select
        }
    });
}

function renderTables() {
    const container = document.getElementById('tables-container');
    container.innerHTML = '';
    
    tablesUsed.forEach(table => {
        const tag = document.createElement('div');
        tag.className = 'tag';
        tag.innerHTML = `
            ${table}
            <span class="remove-btn" data-table="${table}">×</span>
        `;
        container.appendChild(tag);
    });
    
    // Update hidden input
    document.getElementById('tables-used').value = JSON.stringify(tablesUsed);
    
    // Add event listeners to remove buttons
    document.querySelectorAll('#tables-container .remove-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const table = this.getAttribute('data-table');
            tablesUsed = tablesUsed.filter(t => t !== table);
            renderTables();
        });
    });
}

function renderQuestions() {
    const container = document.getElementById('questions-container');
    container.innerHTML = '';
    
    questions.forEach((question, index) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `
            <div class="item-content">${question}</div>
            <span class="remove-btn" data-index="${index}">×</span>
        `;
        container.appendChild(item);
    });
    
    // Update hidden input with questions as objects with 'text' property
    const questionsJson = questions.map(q => ({ text: q }));
    document.getElementById('questions').value = JSON.stringify(questionsJson);
    
    // Add event listeners to remove buttons
    document.querySelectorAll('#questions-container .remove-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            questions.splice(index, 1);
            renderQuestions();
        });
    });
}

function renderFollowUps() {
    const container = document.getElementById('followups-container');
    container.innerHTML = '';
    
    followUps.forEach((followUpId, index) => {
        // Find the name for this follow-up ID
        const option = queryOptions.find(opt => opt.id === followUpId);
        const name = option ? option.name : followUpId;
        
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `
            <div class="item-content">${name} (${followUpId})</div>
            <span class="remove-btn" data-index="${index}">×</span>
        `;
        container.appendChild(item);
    });
    
    // Update hidden input
    document.getElementById('follow-ups').value = JSON.stringify(followUps);
    
    // Add event listeners to remove buttons
    document.querySelectorAll('#followups-container .remove-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            followUps.splice(index, 1);
            renderFollowUps();
        });
    });
}

async function findMatchingQuery() {
    const queryText = document.getElementById('match-query-input').value.trim();
    if (!queryText) {
        showNotification('Please enter a query description', 'error');
        return;
    }
    
    // Only show the find match section on new query creation
    if (!isNew) {
        showNotification('Find match is only available when creating a new query', 'error');
        return;
    }
    
    try {
        setMatchResultLoading('Searching for matching query...');
        
        // Call the API
        const response = await fetch(`/api/find_matching_query?query_text=${encodeURIComponent(queryText)}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (!result.found) {
            setMatchResultNotFound('No matching query found. Please try a different description.');
            return;
        }
        
        // Show the match result
        setMatchResultFound(result);
        
    } catch (error) {
        console.error('Error finding match:', error);
        setMatchResultError(`Error: ${error.message}`);
    }
}

function setMatchResultLoading(message) {
    const resultElement = document.getElementById('match-result');
    resultElement.innerHTML = `<div class="loading">${message}</div>`;
    resultElement.classList.remove('hidden');
}

function setMatchResultNotFound(message) {
    const resultElement = document.getElementById('match-result');
    resultElement.innerHTML = `<div class="not-found">${message}</div>`;
    resultElement.classList.remove('hidden');
}

function setMatchResultError(message) {
    const resultElement = document.getElementById('match-result');
    resultElement.innerHTML = `<div class="error">${message}</div>`;
    resultElement.classList.remove('hidden');
}

function setMatchResultFound(result) {
    const resultElement = document.getElementById('match-result');
    const query = result.query;
    
    resultElement.innerHTML = `
        <div class="match-found">
            <p>Found matching query: <strong>${query.name}</strong></p>
            <p>Confidence: ${(result.confidence * 100).toFixed(1)}%</p>
            <p>Matched question: "${result.matched_question}"</p>
            <button type="button" id="use-match-btn" class="admin-btn primary">Use This Template</button>
        </div>
    `;
    resultElement.classList.remove('hidden');
    
    // Add event listener to the use template button
    document.getElementById('use-match-btn').addEventListener('click', function() {
        // Populate the form with the matching query data
        document.getElementById('query-name').value = document.getElementById('match-query-input').value;
        document.getElementById('query-verified-by').value = query.verified_by;
        document.getElementById('query-explanation').value = query.query_explanation;
        document.getElementById('query-sql').value = query.sql;
        document.getElementById('query-instructions').value = query.instructions || '';
        
        // Set tables used
        tablesUsed = query.tables_used || [];
        renderTables();
        
        // Set questions - use the original question text
        questions = [document.getElementById('match-query-input').value];
        renderQuestions();
        
        // Set follow-ups
        followUps = query.follow_ups || [];
        renderFollowUps();
        
        // Hide the match result
        resultElement.classList.add('hidden');
        
        // Show a success notification
        showNotification('Template applied successfully', 'success');
    });
}

async function runTestQuery() {
    const sql = document.getElementById('query-sql').value.trim();
    if (!sql) {
        showNotification('Please enter a SQL query', 'error');
        return;
    }
    
    try {
        // Show loading state
        const statusElement = document.getElementById('query-status');
        statusElement.innerHTML = '<span class="loading-spinner"></span> Running query...';
        statusElement.className = 'status-running';
        
        // Hide previous results
        document.getElementById('query-results').classList.add('hidden');
        
        // Call the API
        const response = await fetch('/api/run_test_query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ sql })
        });
        
        const result = await response.json();
        
        if (result.status === 'error') {
            // Show error
            statusElement.textContent = `Error: ${result.message}`;
            statusElement.className = 'status-error';
            return;
        }
        
        // Show success
        statusElement.textContent = 'Query executed successfully';
        statusElement.className = 'status-success';
        
        // Display the results
        displayQueryResults(result.results);
        
    } catch (error) {
        console.error('Error running query:', error);
        const statusElement = document.getElementById('query-status');
        statusElement.textContent = `Error: ${error.message}`;
        statusElement.className = 'status-error';
    }
}

function displayQueryResults(results) {
    const resultsElement = document.getElementById('query-results');
    
    // Create the table
    let html = `
        <h4>Query Results</h4>
        <p>Rows: ${results.rows.length}</p>
        <div class="results-table-container">
            <table class="results-table">
                <thead>
                    <tr>
                        ${results.columns.map(col => `<th>${col}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
    `;
    
    // Add rows
    if (results.rows.length === 0) {
        html += `<tr><td colspan="${results.columns.length}" class="no-results">No results found</td></tr>`;
    } else {
        results.rows.forEach(row => {
            html += '<tr>';
            results.columns.forEach(col => {
                html += `<td>${row[col] !== null ? row[col] : ''}</td>`;
            });
            html += '</tr>';
        });
    }
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    resultsElement.innerHTML = html;
    resultsElement.classList.remove('hidden');
}

async function saveQuery() {
    try {
        // Validate form
        const form = document.getElementById('query-form');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // Get form data
        const formData = {
            id: document.getElementById('query-id').value.trim(),
            name: document.getElementById('query-name').value.trim(),
            verified_by: document.getElementById('query-verified-by').value.trim(),
            query_explanation: document.getElementById('query-explanation').value.trim(),
            sql: document.getElementById('query-sql').value.trim(),
            instructions: document.getElementById('query-instructions').value.trim(),
            tables_used: tablesUsed,
            questions: questions.map(q => ({ text: q })),
            follow_ups: followUps
        };
        
        // Determine if this is a create or update
        const url = isNew ? '/api/verified_query' : `/api/verified_query/${queryId}`;
        const method = isNew ? 'POST' : 'PUT';
        
        // Send request
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
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
        
        // Show success notification
        showNotification(`Query ${isNew ? 'created' : 'updated'} successfully`, 'success');
        
        // Redirect to detail view
        setTimeout(() => {
            window.location.href = `/admin/verified_query/${result.id}`;
        }, 1000);
    } catch (error) {
        console.error('Error saving query:', error);
        showNotification(`Failed to save query: ${error.message}`, 'error');
    }
}

function showNotification(message, type) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    
    // Remove 'hidden' class to show notification
    setTimeout(() => {
        notification.classList.remove('hidden');
    }, 10);
    
    // Hide notification after 3 seconds
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}