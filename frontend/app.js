const $ = (id) => document.getElementById(id);

let currentStep = 0;

async function getJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function refreshHealth() {
  const health = await getJson("/health");
  $("modeText").textContent = health.real_openai_mode ? "Real OpenAI mode" : "Stub mode";
  $("modeDot").style.background = health.real_openai_mode ? "#0f766e" : "#b45309";
}

async function compressPrompt() {
  const button = $("compressBtn");
  button.disabled = true;
  button.textContent = "Working";
  try {
    const data = await getJson("/compress", {
      method: "POST",
      body: JSON.stringify({ prompt: $("promptInput").value }),
    });
    $("originalTokens").textContent = data.metrics.original_tokens;
    $("compressedTokens").textContent = data.metrics.compressed_tokens;
    $("savedTokens").textContent = data.metrics.saved_tokens;
    $("savingsPercent").textContent = `${data.metrics.savings_percent}%`;
    $("compressedOutput").textContent = data.compressed;
    $("confidenceValue").textContent = `${data.verification.confidence}%`;
    $("confidenceBar").style.width = `${data.verification.confidence}%`;
    $("differences").innerHTML = "";
    const differences = data.verification.differences.length
      ? data.verification.differences
      : ["No meaningful differences detected."];
    for (const difference of differences) {
      const item = document.createElement("li");
      item.textContent = difference;
      $("differences").appendChild(item);
    }
  } finally {
    button.disabled = false;
    button.textContent = "Compress";
  }
}

async function nextAgentStep() {
  if (currentStep >= 5) {
    currentStep = 0;
    $("agentLog").innerHTML = "";
    $("duplicateNotice").textContent = "No duplicate context detected yet.";
    $("duplicateNotice").classList.remove("hot");
  }
  currentStep += 1;
  const data = await getJson("/agent-demo/step", {
    method: "POST",
    body: JSON.stringify({ step: currentStep }),
  });
  $("stepCount").textContent = `${data.current_step}/5`;
  $("contextTokens").textContent = data.context_tokens;
  $("compactedTokens").textContent = data.compacted_context_tokens;
  $("agentSaved").textContent = data.saved_tokens;
  $("agentLog").innerHTML = "";
  for (const entry of data.log) {
    const item = document.createElement("li");
    item.innerHTML = `<strong>${entry.title}</strong><span>${entry.content}</span>`;
    $("agentLog").appendChild(item);
  }
  if (data.redundant_steps_detected.length) {
    $("duplicateNotice").textContent = `Duplicate context detected. Compaction saves ${data.saved_tokens} tokens (${data.savings_percent}%).`;
    $("duplicateNotice").classList.add("hot");
  } else {
    $("duplicateNotice").textContent = "No duplicate context detected yet.";
    $("duplicateNotice").classList.remove("hot");
  }
  $("nextStepBtn").textContent = currentStep >= 5 ? "Restart" : "Next Step";
}

$("compressBtn").addEventListener("click", compressPrompt);
$("nextStepBtn").addEventListener("click", nextAgentStep);
refreshHealth().catch(() => {
  $("modeText").textContent = "Backend unavailable";
});

