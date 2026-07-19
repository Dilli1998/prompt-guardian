const $ = (id) => document.getElementById(id);

let currentStep = 0;
let autoRunTimer = null;
let lastCompression = null;

const samples = {
  architect:
    "You are an expert software architect. Please provide a comprehensive and detailed plan step by step for building a small FastAPI and vanilla JavaScript hackathon demo. Make sure to include backend endpoints, frontend states, README instructions, and a concise pitch script. Please provide a comprehensive and detailed plan step by step for building a small FastAPI and vanilla JavaScript hackathon demo.",
  agent:
    "I would like you to act as a careful coding agent. Please inspect the repository, read every relevant file, explain your plan, implement the smallest safe change, run verification, and summarize the result. Please inspect the repository, read every relevant file, explain your plan, implement the smallest safe change, run verification, and summarize the result.",
  judge:
    "You are an independent evaluator. Kindly compare the original prompt and the compressed prompt. Make sure to identify any missing constraints, changed meaning, output format differences, and hidden assumptions. Return a confidence score from 0 to 100 and a short list of meaningful differences.",
};

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

function setPipeline(activeIndex, doneAll = false) {
  ["stageClean", "stageCompress", "stageVerify", "stageReport"].forEach((id, index) => {
    const node = $(id);
    node.classList.toggle("active", index === activeIndex && !doneAll);
    node.classList.toggle("done", doneAll || index < activeIndex);
  });
}

function renderRemovedTerms(original, compressed) {
  const originalWords = original.toLowerCase().match(/\b[a-z0-9]{4,}\b/g) || [];
  const compressedWords = new Set(compressed.toLowerCase().match(/\b[a-z0-9]{4,}\b/g) || []);
  const removed = [...new Set(originalWords.filter((word) => !compressedWords.has(word)))].slice(0, 10);
  $("removedTerms").innerHTML = "";
  if (!removed.length) {
    $("removedTerms").textContent = "No major terms removed.";
    return;
  }
  for (const word of removed) {
    const chip = document.createElement("span");
    chip.textContent = word;
    $("removedTerms").appendChild(chip);
  }
}

async function checkAnswerImpact() {
  if (!lastCompression) {
    return;
  }
  const button = $("impactBtn");
  button.disabled = true;
  button.textContent = "Checking";
  try {
    const data = await getJson("/answer-impact", {
      method: "POST",
      body: JSON.stringify({
        original: lastCompression.original,
        compressed: lastCompression.compressed,
      }),
    });
    $("answerScore").textContent = `${data.score}%`;
    $("answerVerdict").textContent = data.same_answer_likely
      ? `Likely same answer behavior (${data.mode})`
      : `Possible answer drift (${data.mode})`;
    $("originalPreview").textContent = data.original_preview;
    $("compressedPreview").textContent = data.compressed_preview;
    $("answerRisks").innerHTML = "";
    const risks = data.risks.length ? data.risks : ["No major answer-impact risks detected."];
    for (const risk of risks) {
      const item = document.createElement("li");
      item.textContent = risk;
      $("answerRisks").appendChild(item);
    }
  } finally {
    button.disabled = false;
    button.textContent = "Check";
  }
}

async function runGuardianReview() {
  const button = $("guardianBtn");
  button.disabled = true;
  button.textContent = "Reviewing";
  const context = Array.from(document.querySelectorAll("#agentLog li span"))
    .map((node) => node.textContent)
    .join("\n\n");
  try {
    const data = await getJson("/guardian-agent/review", {
      method: "POST",
      body: JSON.stringify({
        prompt: $("promptInput").value,
        context,
      }),
    });
    $("guardianDecision").textContent = data.decision;
    $("guardianRisk").textContent = `Risk: ${data.risk_level}`;
    $("guardianReasoning").textContent = data.reasoning_summary;
    $("guardianActions").innerHTML = "";
    for (const action of data.actions) {
      const chip = document.createElement("span");
      chip.textContent = action.replaceAll("_", " ");
      $("guardianActions").appendChild(chip);
    }
  } finally {
    button.disabled = false;
    button.textContent = "Run Agent Review";
  }
}

async function compressPrompt() {
  const button = $("compressBtn");
  button.disabled = true;
  button.textContent = "Working";
  setPipeline(0);
  try {
    setTimeout(() => setPipeline(1), 120);
    const data = await getJson("/compress", {
      method: "POST",
      body: JSON.stringify({ prompt: $("promptInput").value }),
    });
    setPipeline(2);
    $("originalTokens").textContent = data.metrics.original_tokens;
    $("compressedTokens").textContent = data.metrics.compressed_tokens;
    $("savedTokens").textContent = data.metrics.saved_tokens;
    $("savingsPercent").textContent = `${data.metrics.savings_percent}%`;
    $("impactLine").textContent = `${data.metrics.saved_tokens} tokens saved from this prompt`;
    $("costSaved").textContent = `Cost saved: $${data.metrics.cost_saved}`;
    $("compressedOutput").textContent = data.compressed;
    $("resultMode").textContent = data.mode;
    lastCompression = data;
    $("impactBtn").disabled = false;
    $("confidenceValue").textContent = `${data.verification.confidence}%`;
    $("confidenceBar").style.width = `${data.verification.confidence}%`;
    renderRemovedTerms(data.original, data.compressed);
    $("differences").innerHTML = "";
    const differences = data.verification.differences.length
      ? data.verification.differences
      : ["No meaningful differences detected."];
    for (const difference of differences) {
      const item = document.createElement("li");
      item.textContent = difference;
      $("differences").appendChild(item);
    }
    setPipeline(0, true);
    checkAnswerImpact();
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
  $("contextMeter").style.width = `${Math.min(100, data.context_tokens * 1.6)}%`;
  $("agentLog").innerHTML = "";
  const duplicateTitles = new Set(data.redundant_steps_detected.map((entry) => entry.title));
  for (const entry of data.log) {
    const item = document.createElement("li");
    if (duplicateTitles.has(entry.title)) {
      item.classList.add("duplicate");
    }
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
$("impactBtn").addEventListener("click", checkAnswerImpact);
$("guardianBtn").addEventListener("click", runGuardianReview);
$("nextStepBtn").addEventListener("click", nextAgentStep);
$("autoRunBtn").addEventListener("click", () => {
  if (autoRunTimer) {
    clearInterval(autoRunTimer);
    autoRunTimer = null;
    $("autoRunBtn").textContent = "Auto Run";
    return;
  }
  currentStep = 0;
  $("agentLog").innerHTML = "";
  nextAgentStep();
  autoRunTimer = setInterval(() => {
    if (currentStep >= 5) {
      clearInterval(autoRunTimer);
      autoRunTimer = null;
      $("autoRunBtn").textContent = "Auto Run";
      return;
    }
    nextAgentStep();
  }, 900);
  $("autoRunBtn").textContent = "Stop";
});

document.querySelectorAll(".sample").forEach((button) => {
  button.addEventListener("click", () => {
    $("promptInput").value = samples[button.dataset.sample];
  });
});
refreshHealth().catch(() => {
  $("modeText").textContent = "Backend unavailable";
});
