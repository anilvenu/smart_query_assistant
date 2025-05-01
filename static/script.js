const ws = new WebSocket(`ws://${location.host}/ws`);
let currentQuestion = "";
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

  if (msg.step === "best_query") {
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
    setWorking("");
    appendMessage(`
      <details class="step">
        <summary><b>SQL Modifications</b></summary>
        <pre><code class="sql">${modText}</code></pre>
      </details>
    `);
    if (msg.modifications_needed) {
      setWorking("Modifying query...");
      ws.send(JSON.stringify({ action: "modify_query", sql: verifiedQuery.sql, modifications }));
    } else {
      finalSQL = verifiedQuery.sql;
      sendRunQuery();
    }
  }

  else if (msg.step === "modified_sql") {
    finalSQL = msg.final_sql;
    appendMessage(`
      <details class="step">
        <summary><b>Modified SQL</b></summary>
        <pre><code class="sql">${finalSQL}</code></pre>
      </details>
    `);
    sendRunQuery();
  }

  else if (msg.step === "query_results") {
    setWorking("");

    const results = msg.results;
    if (msg.narrative) {
        appendMessage(`<div class="step"><b>Summary:</b><br>${msg.narrative}</div>`);
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
                    <b>Query Results:</b>
                    <table>
                        <thead>${headers}</thead>
                        <tbody>${rows}</tbody>
                    </table>
                   </div>`);

    setWorking("Retrieving follow-up suggestions...");
    ws.send(JSON.stringify({ action: "get_follow_ups", query_id: verifiedQuery.id, query_name: verifiedQuery.name, question: currentQuestion }));
    setWorking("");
    }

    else if (msg.step === "follow_ups") {
        if (!msg.follow_ups.length) return;

        const list = msg.follow_ups.map((fu, idx) => {
            const text = fu.questions?.[0]?.text || '(No question text)';
            return `<button class="follow-up-btn" data-question="${encodeURIComponent(text)}">${text}</button>`;
        }).join('');

        appendMessage(`<div class="follow-up">
                        <b>Follow-up Suggestions:</b>
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
