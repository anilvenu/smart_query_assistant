// Session management
let sessionId = localStorage.getItem('sqa_sessionId') || generateSessionId();
let chatHistory = JSON.parse(localStorage.getItem('sqa_chatHistory') || '[]');

// Initialize WebSocket connection
const ws = new WebSocket(`ws://${location.host}/ws?sessionId=${sessionId}`);
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// Initialize global variables
let currentQuestion = "";
let currentQuestionEnhanced = "";
let verifiedQuery = null;
let modifications = null;
let finalSQL = null;
let stopped = false;

const chat = document.getElementById("chat");

// Initial setup of WebSocket handlers
setupWebSocketHandlers(ws);

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  //loadChatHistory();
  //addClearHistoryButton();
});

function generateSessionId() {
  const id = Date.now().toString(36) + Math.random().toString(36).substr(2);
  localStorage.setItem('sqa_sessionId', id);
  return id;
}

// Update appendMessage to save messages
function appendMessage(content, role = 'assistant') {
  const msg = document.createElement("div");
  msg.classList.add("message", role);
  msg.innerHTML = content;
  chat.appendChild(msg);
  scrollToBottomIfNeeded();
  document.querySelectorAll('pre code').forEach(hljs.highlightElement);
  
  // Save message to history
  saveMessageToHistory(content, role);
}

// Function to load chat history on page load
function loadChatHistory() {
  if (chatHistory.length > 0) {
    // Clear existing messages
    chat.innerHTML = '';
    
    // Append each message from history
    chatHistory.forEach(msg => {
      const msgEl = document.createElement("div");
      msgEl.classList.add("message", msg.role);
      msgEl.innerHTML = msg.content;
      chat.appendChild(msgEl);
    });
    
    // Highlight code blocks
    document.querySelectorAll('pre code').forEach(hljs.highlightElement);
    
    // Scroll to bottom
    chat.scrollTop = chat.scrollHeight;
  }
}

// Add button to clear history
function addClearHistoryButton() {
  const clearBtn = document.createElement("button");
  clearBtn.innerText = "Clear History";
  clearBtn.className = "btn clear-history";
  clearBtn.onclick = () => {
    if (confirm("Are you sure you want to clear your chat history?")) {
      chatHistory = [];
      localStorage.setItem('sqa_chatHistory', '[]');
      chat.innerHTML = '';
    }
  };
  
  // Add button to the header or appropriate location
  document.getElementById("header").appendChild(clearBtn);
}

function saveMessageToHistory(content, role) {
  // Add message to history
  chatHistory.push({
    content,
    role,
    timestamp: new Date().toISOString()
  });
  
  // Keep history limited to last 50 messages
  if (chatHistory.length > 50) {
    chatHistory = chatHistory.slice(chatHistory.length - 50);
  }
  
  // Save to localStorage with consistent key
  localStorage.setItem('sqa_chatHistory', JSON.stringify(chatHistory));
}

function setWorking(message = '', progress = 0) {
  const el = document.getElementById("working-indicator");
  
  if (!message) {
    el.innerHTML = '';
    el.classList.remove('active');
    return;
  }
  
  el.classList.add('active');
  
  // Add progress indicator if provided
  if (progress > 0) {
    el.innerHTML = `
      <div class="spinner"></div>
      <div class="message">${message}</div>
      <div class="progress-container">
        <div class="progress-bar" style="width: ${progress}%"></div>
      </div>
    `;
  } else {
    el.innerHTML = `
      <div class="spinner"></div>
      <div class="message">${message}</div>
    `;
  }
}

function scrollToBottomIfNeeded() {
  const threshold = 100;
  const isNearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < threshold;
  if (isNearBottom) {
    chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
    document.getElementById("jump-btn").style.display = "none";
  }
}

chat.addEventListener("scroll", () => {
  const threshold = 100;
  const isNearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < threshold;
  document.getElementById("jump-btn").style.display = isNearBottom ? "none" : "block";
});

document.getElementById("jump-btn").onclick = () => {
  chat.scrollTop = chat.scrollHeight;
  document.getElementById("jump-btn").style.display = "none";
};

function sendRunQuery() {
  setWorking("Running query...");
  ws.send(JSON.stringify({ action: "run_query", sql: finalSQL, question: currentQuestion }));
}

function createChartContainer() {
  // Always create a new container with a unique ID
  const uniqueId = "chart-container-" + Date.now();
  const container = document.createElement("div");
  container.id = uniqueId;
  container.className = "chart-container";
  return { element: container, id: uniqueId };
}

function displayError(title, message, isRecoverable = true) {
  const errorHtml = `
    <div class="message error">
      <h3>${title}</h3>
      <p>${message}</p>
      ${isRecoverable ? '<button class="retry-btn">Try Again</button>' : ''}
    </div>
  `;

  appendMessage(errorHtml);
  
  // Add event listener to retry button if present
  const retryBtn = chat.querySelector(".retry-btn:last-of-type");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      if (currentQuestion) {
        // Re-submit the current question
        appendMessage(`<strong>User:</strong> ${currentQuestion}`, 'user');
        setWorking("Searching for best query...");
        ws.send(JSON.stringify({ action: "get_best_query", question: currentQuestion }));
      }
    });
  }
  
  setWorking("");
}

ws.onclose = (event) => {
  console.log("WebSocket connection closed:", event);
  appendMessage(`<div class="message error"><b>Connection lost</b>: The connection to the server was closed. Please refresh the page to reconnect.</div>`);
  setWorking("");
  // Disable the form inputs to prevent further attempts
  document.getElementById("question-input").disabled = true;
  document.getElementById("ask-btn").disabled = true;
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
  appendMessage(`<div class="message error"><b>Connection error</b>: There was a problem with the connection. Please refresh the page to try again.</div>`);
};

function setupWebSocketHandlers(socket) {
  // Message handler
  socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log("WS message received:", msg); 

    if (msg.status === "stopped") {
      setWorking("");
      appendMessage("<div class='message stopped'><em>Execution stopped by user.</em></div>");
      stopped = true;
      return;
    }
    if (msg.status === "error") {

      let errorTitle = "Error";
      let errorMessage = msg.message;
      let isRecoverable = true;
      
      // Categorize errors for better feedback
      if (errorMessage.includes("syntax error") || errorMessage.includes("SQL")) {
        errorTitle = "SQL Error";
        errorMessage = "There was a problem with the generated SQL query: " + errorMessage;
      } else if (errorMessage.includes("connection")) {
        errorTitle = "Connection Error";
        errorMessage = "Could not connect to the database. Please try again later.";
      } else if (errorMessage.includes("timeout")) {
        errorTitle = "Query Timeout";
        errorMessage = "The query took too long to execute. Try simplifying your question.";
      }
      
      displayError(errorTitle, errorMessage, isRecoverable);
      return;
    }
    if (stopped) return;

    // Message type handlers
    // - intent_clarifications
    // - best_query
    // - recommendations
    // - reviewing_sql
    // - sql_review_results
    // - additional_modifications
    // - modified_sql
    // - narrative_generated
    // - query_results
    // - follow_ups

    // --------------------------------------------------------------------
    // Intent Clarifications
    // --------------------------------------------------------------------
    if (msg.step === "intent_clarifications") {
      setWorking("Waiting for user response...");
      
      // Create a message for clarification options
      let clarificationsHtml = `
        <div class="step">
          <b>Which of these best matches your need?</b>
          <div class="clarification-options">
      `;
      
      // Add each clarification as a button with an explanation tooltip
      msg.clarifications.forEach((clarification, index) => {
        clarificationsHtml += `
          <div class="clarification-option">
            <button class="clarification-btn" data-question="${encodeURIComponent(clarification.text)}" title="${clarification.explanation}">
              ${clarification.text}
            </button>
          </div>
        `;
      });
      
      clarificationsHtml += `
          </div>
        </div>
      `;
      
      appendMessage(clarificationsHtml);
      
      // Event listeners to the clarification buttons
      document.querySelectorAll(".clarification-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          setWorking("");

          const selectedQuestion = decodeURIComponent(btn.getAttribute("data-question"));
          currentQuestion = selectedQuestion;
          
          // Append the selected clarification as a message
          appendMessage(`<strong>User clarified:</strong> ${selectedQuestion}`, 'user');
          
          // Send the selected clarification to the server
          ws.send(JSON.stringify({ 
            action: "select_clarification", 
            selected_question: selectedQuestion,
            original_question: msg.original_question
          }));
          setWorking("Searching for verified queries that we could use...");
        });
      });
    }
  
    // --------------------------------------------------------------------
    // Best Query
    // --------------------------------------------------------------------
    else if (msg.step === "best_query") {
      setWorking("We have found a verified query...");
      verifiedQuery = msg.verified_query;
      appendMessage(`
        <details class="step">
          <summary><b>Verified SQL</b></summary>
          <p class="review-status success">
            <b>Verified SQL:</b>
            <a href="/admin/verified_query/${verifiedQuery.id}" target="_blank" class="verified-query-link">
              ${verifiedQuery.name}
            </a>
          </p>
          <pre>       
            <code class="sql">${verifiedQuery.sql}</code>
          </pre>
        </details>
      `);

      setWorking("Generating instructions for modification...");
      
      ws.send(JSON.stringify({ action: "get_recommendations", question: currentQuestion, verified_query: verifiedQuery }));
    }
  
    // --------------------------------------------------------------------
    // Recommendations for SQL Modifications
    // --------------------------------------------------------------------
    else if (msg.step === "recommendations") {
      const modText = msg.modifications.map((mod, i) => `${i + 1}. [${mod.type}] ${mod.description}\nImpact: ${mod.sql_impact}`).join('\n\n');
      modifications = msg.modifications;
      currentQuestionEnhanced = msg.enhanced_question;
  
      setWorking("");
  
      //appendMessage(`<div class="step">${currentQuestionEnhanced}</div>`);
  
      appendMessage(`
        <details class="step">
          <summary><b>SQL Modifications</b></summary>
          <pre><code class="sql">${modText}</code></pre>
        </details>
      `);
  
      if (msg.modifications_needed) {
        setWorking("Applying recommended modifications...");
        ws.send(JSON.stringify({ 
          action: "modify_query", 
          sql: verifiedQuery.sql, 
          modifications,
          verified_query: verifiedQuery,
          original_question: currentQuestion,
          enhanced_question: currentQuestionEnhanced        
        }));
      } else {
        finalSQL = verifiedQuery.sql;
  
        sendRunQuery();
  
      }
    }
  
    else if (msg.step === "reviewing_sql") {
      const progress = (msg.iteration / msg.max_iterations) * 100;
      setWorking(`${msg.message}`, progress);
    }
  
    else if (msg.step === "sql_review_results") {
      // Display SQL review results
      const reviewHtml = `
        <details class="step">
          <summary><b>SQL Review (Iteration ${msg.iteration}/${msg.max_iterations})</b></summary>
          <p><b>Review Summary:</b> ${msg.review_results.explanation}</p>
          ${msg.review_results.issues.length ? `
            <p><b>Issues Found:</b></p>
            <ul>
              ${msg.review_results.issues.map(issue => `<li>${issue}</li>`).join('')}
            </ul>
          ` : ''}
          ${msg.review_results.suggestions.length ? `
            <p><b>Suggestions:</b></p>
            <ul>
              ${msg.review_results.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
            </ul>
          ` : ''}
          ${msg.review_results.corrected_sql ? `
            <p><b>Corrected SQL:</b></p>
            <pre><code class="sql">${msg.review_results.corrected_sql}</code></pre>
          ` : ''}
        </details>
      `;
      
      appendMessage(reviewHtml);
      
      // If there's a corrected SQL, we'll get a modified_sql message next
      // If there are additional modifications needed, we'll get an additional_modifications message
      setWorking("Processing review feedback...");
    }
  
    else if (msg.step === "additional_modifications") {
      // Display the additional modifications needed
      const modText = msg.modifications.map((mod, i) => 
        `${i + 1}. [${mod.type}] ${mod.description}`).join('\n\n');
      
      appendMessage(`
        <details class="step">
          <summary><b>Additional SQL Adjustments Identified (Iteration ${msg.iteration_count})</b></summary>
          <pre><code>${modText}</code></pre>
        </details>
      `);
      
      setWorking(`Applying Adjustements (Iteration ${msg.iteration_count})...`);
      
      // Send the request to apply additional modifications
      ws.send(JSON.stringify({
        action: "apply_additional_modifications",
        sql: msg.sql,
        modifications: msg.modifications,
        iteration_count: msg.iteration_count,
        verified_query: msg.verified_query,
        original_question: msg.original_question,
        enhanced_question: msg.enhanced_question
      }));
    }
  
  
    else if (msg.step === "modified_sql") {
      finalSQL = msg.final_sql;
      
      let reviewStatus = "";
      if (msg.review_applied) {
        reviewStatus = `<p class="review-status success">SQL adjusted based on review: ${msg.review_message}</p>`;
      } else if (msg.is_valid === false) {
        reviewStatus = `<p class="review-status warning">SQL may have issues: ${msg.review_message}</p>`;
      } else if (msg.max_iterations_reached) {
        reviewStatus = `<p class="review-status info">Maximum review iterations completed. ${msg.review_message || ''}</p>`;
      } else if (msg.review_message) {
        reviewStatus = `<p class="review-status success">${msg.review_message}</p>`;
      }
      
      appendMessage(`
        <details class="step">
          <summary><b>Modified SQL Query</b></summary>
          ${reviewStatus}
          <pre><code class="sql">${finalSQL}</code></pre>
        </details>
      `);
      
      sendRunQuery();
    }
  
    else if (msg.step === "narrative_generated") {
      // Show the narrative first
      if (msg.narrative) {
        appendMessage(`<div class="step">${msg.narrative}</div>`);
      }
      
      // Show working indicator for chart generation
      setWorking(msg.message || "Generating visualization...");
    }
  
  
    else if (msg.step === "query_results") {
      setWorking("");
    
      const results = msg.results;
      
      // If a chart configuration was provided, try to render it
      if (msg.chart_config && msg.chart_config.chart_applicable) {
        try {
          const { element: container, id: containerId } = createChartContainer();
          console.log("Container created:", container, "with ID:", containerId);
          
          // Create div to hold the visualization
          let vizHtml = `<div class="step viz-step">`;
          
          // Add chart generation explanation if available
          if (msg.chart_config.chart_generation_explanation) {
            vizHtml += `
              <details class="chart-explanation">
                <summary>Chart Selection Explanation</summary>
                <p>${msg.chart_config.chart_generation_explanation}</p>
              </details>
            `;
          }
          
          // Add container for the chart
          vizHtml += `<div id="viz-container-${Date.now()}"></div></div>`;
          
          appendMessage(vizHtml);
          
          // Find the viz container and append the chart (using the most recently added viz-container)
          const vizContainers = document.querySelectorAll('[id^="viz-container-"]');
          const vizContainer = vizContainers[vizContainers.length - 1];
          vizContainer.appendChild(container);
          
          // Call renderChart with the unique container ID
          console.log("Attempting to render chart directly");
          if (typeof renderChart === 'function') {
            console.log("renderChart is a function, calling it with containerId:", containerId);
            const success = renderChart(msg.chart_config, containerId);
            console.log("Chart render result:", success);
          } else {
            console.error("renderChart is not available:", typeof renderChart);
            document.getElementById(containerId).innerHTML = 
              '<div class="chart-error"><p>Chart rendering function not available</p></div>';
          }
          
        } catch (error) {
          console.error("Error setting up chart:", error);
          appendMessage(`<div class="chart-error"><p>Unable to set up visualization: ${error.message}</p></div>`);
        }
      }
  
      // Always show the tabular data as a fallback
      if (results.rows && results.rows.length) {
        const headers = results.columns.map(h => `<th>${h}</th>`).join('');
        const rows = results.rows.map(row => {
          const cells = results.columns.map(col => `<td>${row[col]}</td>`).join('');
          return `<tr>${cells}</tr>`;
        }).join('');
  
        appendMessage(`<div class="step">
                        <b>Results</b>
                        <table>
                          <thead>${headers}</thead>
                          <tbody>${rows}</tbody>
                        </table>
                      </div>`);
      }
  
      setWorking("Retrieving follow-up suggestions...");
      ws.send(JSON.stringify({ action: "get_follow_ups", query_id: verifiedQuery.id, query_name: verifiedQuery.name, question: currentQuestionEnhanced }));
      setWorking("");
    }
  
    else if (msg.step === "follow_ups") {
      console.log("Follow-ups received:", msg.follow_ups);
      
      if (!msg.follow_ups || !msg.follow_ups.length) {
        console.log("No follow-ups to display");
        return;
      }
    
      const list = msg.follow_ups.map((fu, idx) => {
        console.log("Processing follow-up:", fu);
        const questions = fu.questions || [];
        const text = questions.length > 0 ? questions[0].text : '(No question text)';
        console.log("Follow-up text:", text);
        return `<button class="follow-up-btn" data-question="${encodeURIComponent(text)}">${text}</button>`;
      }).join('');
    
      console.log("Follow-up HTML:", list);
    
      appendMessage(`<div class="follow-up">
                      <b>Suggested Follow-up Questions</b>
                      <br/><br/>
                      ${list}
                    </div>`);
    
      // Attach event listeners for follow-up buttons
      document.querySelectorAll(".follow-up-btn").forEach(btn => {
        setWorking("");

        btn.addEventListener("click", () => {
          const text = decodeURIComponent(btn.getAttribute("data-question"));
          currentQuestion = text;
          document.getElementById("question-input").value = '';
          appendMessage(`<strong>User:</strong> ${text}`, 'user');
    
          ws.send(JSON.stringify({ action: "get_best_query", question: text }));

          setWorking("Searching for best query...");
        });
      });
    }

  };

  // Connection close handler
  socket.onclose = (event) => {
    console.log("WebSocket connection closed:", event);
    const wasCleanClose = event.wasClean;
    
    appendMessage(`<div class="message error"><b>Connection lost</b>: The connection to the server was ${wasCleanClose ? 'closed' : 'interrupted'}. ${wasCleanClose ? '' : 'Attempting to reconnect...'}</div>`);
    setWorking("");
    
    // Disable the form inputs temporarily
    document.getElementById("question-input").disabled = true;
    document.getElementById("ask-btn").disabled = true;
    document.getElementById("stop-btn").disabled = true;
    
    // Show reconnect button for clean closures, auto-reconnect for failures
    if (wasCleanClose) {
      showReconnectButton();
    } else {
      // Auto-reconnect after a delay for unexpected disconnections
      setTimeout(attemptReconnect, 3000);
    }
  };

  // Connection error handler
  socket.onerror = (error) => {
    console.error("WebSocket error:", error);
    appendMessage(`<div class="message error"><b>Connection error</b>: There was a problem with the connection.</div>`);
  };
}


// Add a reconnection function with retry logic
function attemptReconnect() {
  if (ws.readyState === WebSocket.CLOSED) {
    reconnectAttempts++;
    
    if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      appendMessage(`<div class="message error"><b>Reconnection failed</b>: Maximum reconnection attempts reached. Please refresh the page.</div>`);
      showReconnectButton(); // Show manual reconnect button as last resort
      return;
    }
    
    console.log(`Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
    appendMessage(`<div class="message"><em>Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...</em></div>`);
    
    // Create a new WebSocket connection with sessionId
    const newWs = new WebSocket(`ws://${location.host}/ws?sessionId=${sessionId}`);
    
    // Set up event handlers for the new connection
    setupWebSocketHandlers(newWs);
    
    // Add a special handler for the first reconnection message to overlay the one from setupWebSocketHandlers
    const originalOnMessage = newWs.onmessage;
    newWs.onmessage = (event) => {
      // Re-enable the form after successful reconnection
      document.getElementById("question-input").disabled = false;
      document.getElementById("ask-btn").disabled = false;
      document.getElementById("stop-btn").disabled = false;
      
      // Notify user of successful reconnection
      appendMessage(`<div class="message success"><b>Connection restored</b>: You can continue your session.</div>`);
      
      // Remove any reconnect buttons
      const reconnectBtn = document.querySelector(".reconnect-btn");
      if (reconnectBtn) {
        reconnectBtn.parentNode.removeChild(reconnectBtn);
      }
      
      // Reset reconnect attempts
      reconnectAttempts = 0;
      
      // Update the global ws reference
      ws = newWs;
      
      // Restore the original message handler for subsequent messages
      newWs.onmessage = originalOnMessage;
      
      // Process this first message normally
      originalOnMessage(event);
    };
    
    // Handle connection errors and timeout
    newWs.onerror = (error) => {
      console.error("Error during reconnection attempt:", error);
    };
    
    // Add reconnection failure timeout with exponential backoff
    const connectionTimeout = setTimeout(() => {
      if (newWs.readyState !== WebSocket.OPEN) {
        console.log("Connection attempt timed out");
        
        // Exponential backoff for next retry
        const delay = Math.min(30000, 1000 * Math.pow(2, reconnectAttempts));
        appendMessage(`<div class="message warning"><em>Connection attempt failed. Retrying in ${Math.round(delay/1000)} seconds...</em></div>`);
        
        setTimeout(attemptReconnect, delay);
      }
    }, 5000);
    
    // Clear timeout if connection succeeds
    newWs.onopen = () => {
      clearTimeout(connectionTimeout);
      console.log("Reconnection successful!");
    };
  }
}

// Function to show a reconnect button
function showReconnectButton() {
  // Remove any existing reconnect buttons first
  const existingBtn = document.querySelector(".reconnect-btn");
  if (existingBtn) {
    existingBtn.parentNode.removeChild(existingBtn);
  }
  
  const reconnectBtn = document.createElement("button");
  reconnectBtn.innerText = "Reconnect";
  reconnectBtn.className = "btn reconnect-btn";
  reconnectBtn.onclick = () => {
    reconnectAttempts = 0; // Reset counter for manual reconnection
    reconnectBtn.disabled = true;
    reconnectBtn.innerText = "Connecting...";
    attemptReconnect();
  };
  
  // Insert the button near the form
  const formContainer = document.getElementById("question-form");
  formContainer.insertBefore(reconnectBtn, formContainer.firstChild);
}

document.getElementById("question-form").onsubmit = (e) => {
  e.preventDefault();
  const q = document.getElementById("question-input").value;
  if (!q) return;
  currentQuestion = q;
  verifiedQuery = null;
  modifications = null;
  finalSQL = null;
  stopped = false;
  document.getElementById("question-input").value = ''; // clear input immediately
  appendMessage(`<strong>User:</strong> ${q}`, 'user');
  setWorking("Analyzing...");
  ws.send(JSON.stringify({ action: "get_best_query", question: q }));
};

document.getElementById("stop-btn").onclick = () => {
  ws.send(JSON.stringify({ action: "stop" }));
};
