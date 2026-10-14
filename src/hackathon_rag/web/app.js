const $ = (id) => document.getElementById(id);
const tokenInput = $("token");
tokenInput.value = sessionStorage.getItem("novacortex_token") || "";
tokenInput.addEventListener("input", () => sessionStorage.setItem("novacortex_token", tokenInput.value));

function headers(json = false) {
  const value = tokenInput.value.trim();
  return { ...(json ? {"Content-Type": "application/json"} : {}), ...(value ? {Authorization: `Bearer ${value}`} : {}) };
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body));
  return body;
}

async function checkHealth() {
  try {
    const data = await api("/api/health");
    $("statusText").textContent = data.index_ready ? "النظام جاهز" : "الفهرس غير جاهز";
    $("statusText").parentElement.classList.toggle("ready", data.index_ready);
  } catch { $("statusText").textContent = "تعذر الاتصال"; }
}

async function loadSources() {
  const box = $("sources");
  box.innerHTML = '<div class="skeleton"></div><div class="skeleton short"></div>';
  try {
    const data = await api("/api/sources", {headers: headers()});
    box.innerHTML = data.sources.length ? data.sources.map((source) =>
      `<label class="source-option"><input type="checkbox" value="${escapeHtml(source)}"><span>${escapeHtml(source)}</span></label>`
    ).join("") : '<p class="hint">لا توجد مصادر مفهرسة.</p>';
  } catch (error) { box.innerHTML = `<p class="hint">${escapeHtml(error.message)}</p>`; }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
}

function selectedSources() {
  return [...document.querySelectorAll("#sources input:checked")].map((item) => item.value);
}

function render(result) {
  $("emptyState").classList.add("hidden");
  $("error").classList.add("hidden");
  $("result").classList.remove("hidden");
  $("answer").textContent = result.answer;
  $("answerBadge").textContent = result.answer_mode === "extractive" ? "نص حرفي من المصدر" : result.supported ? "إجابة موثقة" : "الأدلة غير كافية";
  $("latency").textContent = `${result.latency_ms || 0} ms`;
  const notice = $("privacyNotice");
  notice.textContent = result.privacy_notice || "";
  notice.classList.toggle("hidden", !result.privacy_notice);
  $("warnings").innerHTML = (result.evidence_warnings || []).map((w) => `<div class="warning">${escapeHtml(w)}</div>`).join("");
  $("citations").innerHTML = (result.citations || []).map((c) => {
    const location = [c.source, c.page != null ? `صفحة ${c.page}` : "", c.section || ""].filter(Boolean).join(" · ");
    return `<details class="citation"><summary>${escapeHtml(location)}</summary><blockquote>${escapeHtml(c.quote || "")}</blockquote></details>`;
  }).join("");
}

$("refreshSources").addEventListener("click", loadSources);
$("askForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("send");
  const question = $("question").value.trim();
  if (!question) return;
  button.disabled = true;
  button.querySelector("span").textContent = "جاري البحث";
  $("error").classList.add("hidden");
  try {
    const result = await api("/api/ask", {
      method: "POST", headers: headers(true), body: JSON.stringify({question, sources: selectedSources()})
    });
    render(result);
  } catch (error) {
    $("error").textContent = error.message;
    $("error").classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "إرسال";
  }
});

checkHealth();
loadSources();
