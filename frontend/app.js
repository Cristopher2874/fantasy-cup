const state = {
  matchdays: [],
  leaderboard: [],
  team: JSON.parse(localStorage.getItem("fantasyCupTeam") || "null"),
  token: localStorage.getItem("fantasyCupToken") || "",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

document.addEventListener("DOMContentLoaded", () => {
  bindTabs();
  bindButtons();
  refreshAll();
});

function bindTabs() {
  $$(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".tab").forEach((tab) => tab.classList.remove("is-active"));
      $$(".view").forEach((view) => view.classList.remove("is-active"));
      button.classList.add("is-active");
      $(`#view-${button.dataset.view}`).classList.add("is-active");
    });
  });
}

function bindButtons() {
  $("#refresh-home").addEventListener("click", refreshAll);
  $("#refresh-leaderboard").addEventListener("click", loadLeaderboard);
  $("#refresh-results").addEventListener("click", loadResults);
  $("#refresh-catalog").addEventListener("click", loadCatalog);
  $("#refresh-team").addEventListener("click", loadTeamDashboard);
  $("#seed-demo").addEventListener("click", seedDemo);
  $("#create-matchday").addEventListener("click", createMatchday);
  $("#build-artifacts").addEventListener("click", buildArtifacts);
  $("#run-agents").addEventListener("click", runAgents);
  $("#publish-matchday").addEventListener("click", publishMatchday);

  $("#register-form").addEventListener("submit", registerTeam);
  $("#login-form").addEventListener("submit", loginTeam);
  $("#zip-form").addEventListener("submit", uploadZip);
  $("#repo-form").addEventListener("submit", submitRepo);
}

async function refreshAll() {
  await Promise.all([loadMatchdays(), loadLeaderboard(), loadCatalog()]);
  renderHome();
  await loadResults();
  await loadTeamDashboard();
}

async function loadMatchdays() {
  state.matchdays = await api("/api/matchdays");
  renderMatchdaySelectors();
  renderStatus();
}

async function loadLeaderboard() {
  state.leaderboard = await api("/api/leaderboard");
  renderLeaderboard("#leaderboard-body", state.leaderboard);
  renderLeaderboard("#home-leaderboard", state.leaderboard.slice(0, 5));
}

async function loadCatalog() {
  const catalog = await api("/api/catalog");
  $("#catalog-content").innerHTML = [
    ...catalog.entities.map(renderCatalogEntity),
    renderCatalogRules(catalog),
  ].join("");
}

async function loadResults() {
  const matchdayId = selectedMatchdayId("results-matchday");
  if (!matchdayId) {
    $("#results-list").innerHTML = empty("No matchdays yet");
    return;
  }
  const payload = await api(`/api/matchdays/${matchdayId}/results`);
  $("#results-list").innerHTML = payload.runs.length
    ? payload.runs.map(renderRunCard).join("")
    : empty("No runs yet");
}

async function loadTeamDashboard() {
  renderTeamSession();
  if (!state.team || !state.token) {
    $("#team-submissions").innerHTML = empty("No active team");
    $("#team-runs").innerHTML = empty("No active team");
    return;
  }

  try {
    const [submissions, runs] = await Promise.all([
      api("/api/team/submissions", { headers: teamHeaders() }),
      api("/api/team/runs", { headers: teamHeaders() }),
    ]);
    $("#team-submissions").innerHTML = submissions.submissions.length
      ? submissions.submissions.map(renderSubmission).join("")
      : empty("No submissions");
    $("#team-runs").innerHTML = runs.runs.length ? runs.runs.map(renderTeamRun).join("") : empty("No runs");
  } catch (error) {
    toast(error.message);
  }
}

function renderHome() {
  const current = state.matchdays[0];
  const leader = state.leaderboard[0];
  const runCount = state.leaderboard.reduce((sum, row) => sum + row.runs, 0);
  $("#home-summary").innerHTML = [
    summaryCard("Matchday", current ? `${current.label} (${current.status})` : "None"),
    summaryCard("Leader", leader ? `${leader.team_name} - ${leader.total_points} pts` : "None"),
    summaryCard("Scored Runs", runCount),
  ].join("");
  renderStatus();
}

function renderLeaderboard(selector, rows) {
  $(selector).innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td>${row.rank}</td>
              <td>${escapeHtml(row.team_name)}</td>
              <td><strong>${row.total_points}</strong></td>
              <td>${row.fantasy_points}</td>
              <td>${row.risk_points}</td>
              <td>${row.risk_record || row.bracket_points}</td>
              ${selector === "#leaderboard-body" ? `<td>${row.runs}</td>` : ""}
            </tr>
          `,
        )
        .join("")
    : `<tr><td colspan="7">No teams yet</td></tr>`;
}

function renderMatchdaySelectors() {
  const options = state.matchdays
    .map((matchday) => `<option value="${matchday.id}">${matchday.label} - ${matchday.status}</option>`)
    .join("");
  $("#results-matchday").innerHTML = options;
  $("#org-matchday").innerHTML = options;
}

function renderStatus() {
  const current = state.matchdays[0];
  $("#active-matchday").textContent = current ? `${current.id} ${current.status}` : "No matchday";
  $("#active-team").textContent = state.team ? `${state.team.id} ${state.team.name}` : "No team";
}

function renderRunCard(run) {
  const fantasy = run.scoring?.fantasy?.players || [];
  const topPlayers = fantasy
    .slice()
    .sort((a, b) => b.points - a.points)
    .slice(0, 5)
    .map((player) => `${escapeHtml(player.name)} (${player.points})`)
    .join(", ");
  const risk = run.scoring?.risk || {};
  return `
    <article class="result-card">
      <h3>${escapeHtml(run.team_name || run.team_id)}</h3>
      <div class="result-meta">
        <span class="badge">Total ${run.total_points}</span>
        <span class="badge">Fantasy ${run.fantasy_points}</span>
        <span class="badge">Risk ${risk.points || 0}</span>
        <span class="badge">${escapeHtml(risk.outcome || "none")}</span>
      </div>
      <p>${escapeHtml(run.strategy_summary || "")}</p>
      <p><strong>Top players:</strong> ${topPlayers || "None"}</p>
      <details>
        <summary>Answers</summary>
        <pre class="code-block">${escapeHtml(JSON.stringify(run.answers, null, 2))}</pre>
      </details>
    </article>
  `;
}

function renderCatalogEntity(entity) {
  return `
    <article class="catalog-card">
      <h3>${escapeHtml(entity.name)}</h3>
      <table>
        <tbody>
          ${entity.fields
            .map(
              (field) => `
                <tr>
                  <td><strong>${escapeHtml(field.name)}</strong><br><span>${escapeHtml(field.type)}</span></td>
                  <td>${escapeHtml(field.description)}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </article>
  `;
}

function renderCatalogRules(catalog) {
  return `
    <article class="catalog-card">
      <h3>Rules</h3>
      <pre class="code-block">${escapeHtml(JSON.stringify({
        positions: catalog.position_rules,
        scoring: catalog.scoring,
      }, null, 2))}</pre>
    </article>
  `;
}

function renderTeamSession() {
  if (!state.team) {
    $("#team-session").innerHTML = "No active team session.";
    renderStatus();
    return;
  }
  $("#team-session").innerHTML = `
    <strong>${escapeHtml(state.team.name)}</strong>
    <span class="badge">${state.team.id}</span>
    <button class="secondary" id="logout-team" type="button">Logout</button>
  `;
  $("#logout-team").addEventListener("click", () => {
    localStorage.removeItem("fantasyCupTeam");
    localStorage.removeItem("fantasyCupToken");
    state.team = null;
    state.token = "";
    loadTeamDashboard();
  });
  renderStatus();
}

function renderSubmission(submission) {
  const status = submission.accepted ? "accepted good" : "rejected bad";
  return `
    <div class="stack-item">
      <strong>${submission.id}</strong>
      <span class="${status.split(" ")[1]}">${status.split(" ")[0]}</span>
      <p>${escapeHtml(submission.source)} ${escapeHtml(submission.created_at)}</p>
      ${submission.errors?.length ? `<p class="bad">${escapeHtml(submission.errors.join(", "))}</p>` : ""}
      ${submission.warnings?.length ? `<p class="warn">${escapeHtml(submission.warnings.join(", "))}</p>` : ""}
    </div>
  `;
}

function renderTeamRun(run) {
  return `
    <div class="stack-item">
      <strong>${run.id}</strong>
      <p>${run.matchday_id} - ${run.status}</p>
      <p>Total ${run.total_points} | Fantasy ${run.fantasy_points} | Risk ${run.risk_points}</p>
      <p>${escapeHtml(run.strategy_summary || "")}</p>
    </div>
  `;
}

async function seedDemo() {
  const payload = await api("/api/org/demo/seed", { method: "POST" });
  $("#organizer-output").textContent = JSON.stringify(payload, null, 2);
  toast("Demo seeded");
  await refreshAll();
}

async function createMatchday() {
  const payload = await api("/api/org/matchdays", {
    method: "POST",
    body: JSON.stringify({}),
  });
  $("#organizer-output").textContent = JSON.stringify(payload, null, 2);
  toast("Matchday created");
  await refreshAll();
}

async function buildArtifacts() {
  const matchdayId = selectedMatchdayId("org-matchday");
  if (!matchdayId) return toast("No matchday selected");
  const payload = await api(`/api/org/matchdays/${matchdayId}/build-artifacts`, { method: "POST" });
  $("#organizer-output").textContent = JSON.stringify(payload, null, 2);
  toast("Artifacts built");
  await refreshAll();
}

async function runAgents() {
  const matchdayId = selectedMatchdayId("org-matchday");
  if (!matchdayId) return toast("No matchday selected");
  const payload = await api(`/api/org/matchdays/${matchdayId}/run`, { method: "POST" });
  $("#organizer-output").textContent = JSON.stringify(payload, null, 2);
  toast("Mock runs scored");
  await refreshAll();
}

async function publishMatchday() {
  const matchdayId = selectedMatchdayId("org-matchday");
  if (!matchdayId) return toast("No matchday selected");
  const payload = await api(`/api/org/matchdays/${matchdayId}/publish`, { method: "POST" });
  $("#organizer-output").textContent = JSON.stringify(payload, null, 2);
  toast("Matchday published");
  await refreshAll();
}

async function registerTeam(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    name: form.get("name"),
    members: String(form.get("members") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
  const result = await api("/api/teams/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  saveTeamSession(result.team, result.token);
  event.currentTarget.reset();
  toast("Team registered");
  await refreshAll();
}

async function loginTeam(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const token = form.get("token");
  const result = await api("/api/team/login", {
    method: "POST",
    body: JSON.stringify({
      team_id: form.get("team_id") || null,
      token,
    }),
  });
  saveTeamSession(result.team, token);
  event.currentTarget.reset();
  toast("Logged in");
  await loadTeamDashboard();
}

async function uploadZip(event) {
  event.preventDefault();
  if (!state.team || !state.token) return toast("Login required");
  const form = new FormData(event.currentTarget);
  const result = await api("/api/team/submission/zip", {
    method: "POST",
    headers: teamHeaders(false),
    body: form,
  });
  toast(result.submission.accepted ? "ZIP accepted" : "ZIP rejected");
  event.currentTarget.reset();
  await loadTeamDashboard();
}

async function submitRepo(event) {
  event.preventDefault();
  if (!state.team || !state.token) return toast("Login required");
  const form = new FormData(event.currentTarget);
  const result = await api("/api/team/submission/repo", {
    method: "POST",
    headers: teamHeaders(),
    body: JSON.stringify({ repo_url: form.get("repo_url") }),
  });
  toast(result.submission.accepted ? "Repo registered" : "Repo rejected");
  event.currentTarget.reset();
  await loadTeamDashboard();
}

function saveTeamSession(team, token) {
  state.team = team;
  state.token = token;
  localStorage.setItem("fantasyCupTeam", JSON.stringify(team));
  localStorage.setItem("fantasyCupToken", token);
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  const isForm = options.body instanceof FormData;
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

function teamHeaders(includeJson = true) {
  return {
    ...(includeJson ? { "Content-Type": "application/json" } : {}),
    "X-Team-Id": state.team.id,
    "X-Team-Token": state.token,
  };
}

function selectedMatchdayId(elementId) {
  return $(`#${elementId}`).value || state.matchdays[0]?.id || "";
}

function summaryCard(label, value) {
  return `<div class="summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
}

function empty(text) {
  return `<div class="stack-item">${escapeHtml(text)}</div>`;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("is-visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => element.classList.remove("is-visible"), 2600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
