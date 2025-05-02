const ws = new WebSocket(`ws://${location.host}/ws`);
let currentQuestion = "";
let currentQuestionEnhanced = "";
let verifiedQuery = null;
let modifications = null;
let finalSQL = null;
let stopped = false;

const chat = document.getElementById("chat");

function appendMessage(content, role = 'assistant') {
  const msg = document.createElement("div");
  msg.classList.add("message", role);
  msg.innerHTML = content;
  chat.appendChild(msg);
  scrollToBottomIfNeeded();
  document.querySelectorAll('pre code').forEach(hljs.highlightElement);
}

function setWorking(message = '') {
  const el = document.getElementById("working-indicator");
  el.innerText = message;
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

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log("WS message received:", msg);

  if (msg.status === "stopped") {
    setWorking("");
    appendMessage("<div class='message stopped'><em>Execution stopped by user.</em></div>");
    stopped = true;
    return;
  }
  if (msg.status === "error") {
    setWorking("");
    appendMessage(`<div class="message error"><b>Error:</b> ${msg.message}</div>`);
    return;
  }
  if (stopped) return;


  if (msg.step === "intent_clarifications") {
    setWorking("");
    
    // Create a message for clarification options
    let clarificationsHtml = `
      <div class="step">
        <b>I noticed your question could be interpreted in different ways. Which of these best matches your intent?</b>
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
        const selectedQuestion = decodeURIComponent(btn.getAttribute("data-question"));
        currentQuestion = selectedQuestion;
        
        // Append the selected clarification as a message
        appendMessage(`<strong>User clarified:</strong> ${selectedQuestion}`, 'user');
        
        // Send the selected clarification to the server
        setWorking("Searching for best query...");
        ws.send(JSON.stringify({ 
          action: "select_clarification", 
          selected_question: selectedQuestion,
          original_question: msg.original_question
        }));
      });
    });
  }


  else if (msg.step === "best_query") {
    setWorking("Generating SQL recommendations...");
    verifiedQuery = msg.verified_query;
    appendMessage(`
      <details class="step">
        <summary><b>Verified SQL</b></summary>
        <pre><code class="sql">${verifiedQuery.sql}</code></pre>
      </details>
    `);
    ws.send(JSON.stringify({ action: "get_recommendations", question: currentQuestion, verified_query: verifiedQuery }));
  }

  else if (msg.step === "recommendations") {
    const modText = msg.modifications.map((mod, i) => `${i + 1}. [${mod.type}] ${mod.description}\nImpact: ${mod.sql_impact}`).join('\n\n');
    modifications = msg.modifications;
    currentQuestionEnhanced = msg.enhanced_question;

    setWorking("");

    appendMessage(`<div class="step">${currentQuestionEnhanced}</div>`);

    appendMessage(`
      <details class="step">
        <summary><b>SQL Modifications</b></summary>
        <pre><code class="sql">${modText}</code></pre>
      </details>
    `);

    if (msg.modifications_needed) {
      setWorking("Modifying query...");
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
    setWorking(`${msg.message}`);
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
      reviewStatus = `<p class="review-status success">SQL adjusted based on review.</p>`;
    } else if (msg.is_valid === false) {
      reviewStatus = `<p class="review-status warning">SQL may have issues: ${msg.review_message}</p>`;
    } else if (msg.max_iterations_reached) {
      reviewStatus = `<p class="review-status info">Maximum review iterations completed.</p>`;
    } else if (msg.review_message) {
      reviewStatus = `<p class="review-status success">${msg.review_message}</p>`;
    }
    
    appendMessage(`
      <details class="step">
        <summary><b>Modified SQL</b></summary>
        ${reviewStatus}
        <pre><code class="sql">${finalSQL}</code></pre>
      </details>
    `);
    
    sendRunQuery();
  }

  else if (msg.step === "query_results") {
    setWorking("");

    const results = msg.results;
    if (msg.narrative) {
        appendMessage(`<div class="step">${msg.narrative}</div>`);
    }

    //if (results.rows.length) {
    //    appendMessage(`<div class="step"><b>Rows:</b> ${results.rows.length}</div>`);
    //}
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

    setWorking("Retrieving follow-up suggestions...");
    ws.send(JSON.stringify({ action: "get_follow_ups", query_id: verifiedQuery.id, query_name: verifiedQuery.name, question: currentQuestionEnhanced }));
    setWorking("");
    }

    else if (msg.step === "follow_ups") {
        if (!msg.follow_ups.length) return;

        const list = msg.follow_ups.map((fu, idx) => {
            const text = fu.questions?.[0]?.text || '(No question text)';
            return `<button class="follow-up-btn" data-question="${encodeURIComponent(text)}">${text}</button>`;
        }).join('');

        appendMessage(`<div class="follow-up">
                        <b>Suggested Follow-up Questions</b>
                        <br/>
                        ${list}
                       </div>`);

        // Attach event listeners for follow-up buttons
        document.querySelectorAll(".follow-up-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const text = decodeURIComponent(btn.getAttribute("data-question"));
            currentQuestion = text;
            document.getElementById("question-input").value = '';
            appendMessage(`<strong>User:</strong> ${text}`, 'user');

            setWorking("Searching for best query...");
            ws.send(JSON.stringify({ action: "get_best_query", question: text }));
            setWorking("");
        });
        });
    }



};

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
  setWorking("Searching for best query...");
  ws.send(JSON.stringify({ action: "get_best_query", question: q }));
};

document.getElementById("stop-btn").onclick = () => {
  ws.send(JSON.stringify({ action: "stop" }));
};
