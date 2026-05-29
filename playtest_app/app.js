(function () {
  const POSITION_ORDER = ["GK", "DEF", "MID", "FWD"];
  const POSITION_LIMITS = {
    GK: [1, 1],
    DEF: [3, 5],
    MID: [3, 5],
    FWD: [1, 3],
  };
  const POINT_RULE_LABELS = {
    starts: "Started",
    plays_60: "Played 60+",
    goal: "Goal",
    assist: "Assist",
    clean_sheet: "Clean sheet",
    goalkeeper_saves: "GK 3+ saves",
    yellow_card: "Yellow card",
    red_card: "Red card",
    own_goal: "Own goal",
  };
  const POINT_RULE_ORDER = [
    "starts",
    "plays_60",
    "goal",
    "assist",
    "clean_sheet",
    "goalkeeper_saves",
    "yellow_card",
    "red_card",
    "own_goal",
  ];

  const dom = {
    fixtureCount: document.getElementById("fixture-count"),
    playerCount: document.getElementById("player-count"),
    teamName: document.getElementById("team-name"),
    teamId: document.getElementById("team-id"),
    selectionTotal: document.getElementById("selection-total"),
    positionCounts: document.getElementById("position-counts"),
    selectedList: document.getElementById("selected-list"),
    selectionStatus: document.getElementById("selection-status"),
    clearSelection: document.getElementById("clear-selection"),
    matchFilter: document.getElementById("match-filter"),
    positionFilter: document.getElementById("position-filter"),
    playerSearch: document.getElementById("player-search"),
    playerGrid: document.getElementById("player-grid"),
    riskCategory: document.getElementById("risk-category"),
    riskClaim: document.getElementById("risk-claim"),
    riskMatch: document.getElementById("risk-match"),
    riskFields: document.getElementById("risk-fields"),
    strategySummary: document.getElementById("strategy-summary"),
    payloadPreview: document.getElementById("payload-preview"),
    downloadPayload: document.getElementById("download-payload"),
    submitPayload: document.getElementById("submit-payload"),
    saveStatus: document.getElementById("save-status"),
    scoreResult: document.getElementById("score-result"),
    leaderboardBody: document.getElementById("leaderboard-body"),
    rulesList: document.getElementById("rules-list"),
  };

  let state = null;
  let selectedPlayers = [];
  let playerByRecordId = new Map();
  let matchById = new Map();

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function generateTeamId() {
    if (window.crypto && window.crypto.getRandomValues) {
      const values = new Uint32Array(1);
      window.crypto.getRandomValues(values);
      return `TEAM-${values[0].toString(36).slice(0, 6).toUpperCase()}`;
    }
    return `TEAM-${Date.now().toString(36).toUpperCase()}`;
  }

  function setupTeamDefaults() {
    const storedId = localStorage.getItem("fantasyCupPlaytestTeamId");
    const storedName = localStorage.getItem("fantasyCupPlaytestTeamName");
    dom.teamId.value = storedId || generateTeamId();
    dom.teamName.value = storedName || "";
    localStorage.setItem("fantasyCupPlaytestTeamId", dom.teamId.value);
  }

  function claimLabel(claimId) {
    return claimId
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function matchLabel(match) {
    return `${match.home_team.name} vs ${match.away_team.name}`;
  }

  function fullMatchLabel(match) {
    return `${match.id} - ${matchLabel(match)}`;
  }

  function positionClass(position) {
    return `position-${String(position || "").toLowerCase()}`;
  }

  function selectedRecordIds() {
    return new Set(selectedPlayers.map((player) => player.record_id));
  }

  function positionCounts() {
    const counts = Object.fromEntries(POSITION_ORDER.map((position) => [position, 0]));
    selectedPlayers.forEach((player) => {
      if (counts[player.position] !== undefined) {
        counts[player.position] += 1;
      }
    });
    return counts;
  }

  function selectionErrors() {
    const errors = [];
    const counts = positionCounts();
    if (selectedPlayers.length !== 11) {
      errors.push(`Select exactly 11 players; current total is ${selectedPlayers.length}.`);
    }
    POSITION_ORDER.forEach((position) => {
      const [min, max] = POSITION_LIMITS[position];
      if (counts[position] < min || counts[position] > max) {
        errors.push(`${position} must be ${min === max ? min : `${min}-${max}`}; current total is ${counts[position]}.`);
      }
    });
    return errors;
  }

  function riskErrors() {
    const errors = [];
    const claimId = dom.riskClaim.value;
    if (!claimId) {
      return errors;
    }
    const capability = state.truth.capabilities.risk_claims[claimId];
    if (!capability) {
      errors.push("Risk claim is not supported.");
      return errors;
    }
    if (!dom.riskMatch.value) {
      errors.push("Risk match is required.");
    }
    (capability.required_fields || []).forEach((field) => {
      if (field === "match_id") {
        return;
      }
      const input = document.getElementById(`risk-${field.replace("_", "-")}`);
      if (!input || input.value === "") {
        errors.push(`${claimLabel(field)} is required.`);
      }
    });
    return errors;
  }

  function buildRiskPlay() {
    const claimId = dom.riskClaim.value;
    if (!claimId) {
      return null;
    }

    const capability = state.truth.capabilities.risk_claims[claimId];
    const riskPlay = {
      claim_id: claimId,
      category: capability.category,
      match_id: dom.riskMatch.value,
    };

    (capability.required_fields || []).forEach((field) => {
      if (field === "match_id") {
        return;
      }
      const input = document.getElementById(`risk-${field.replace("_", "-")}`);
      if (!input) {
        return;
      }
      if (field === "home_score" || field === "away_score") {
        riskPlay[field] = input.value === "" ? null : Number(input.value);
        return;
      }
      riskPlay[field] = input.value;
    });

    return riskPlay;
  }

  function buildPayload() {
    return {
      team_id: dom.teamId.value.trim(),
      team_name: dom.teamName.value.trim(),
      answers: {
        fantasy_xi: selectedPlayers.map((player) => player.record_id),
        risk_play: buildRiskPlay(),
        strategy_summary: dom.strategySummary.value.trim(),
      },
    };
  }

  function canSubmit() {
    return Boolean(dom.teamName.value.trim() && dom.teamId.value.trim()) &&
      selectionErrors().length === 0 &&
      riskErrors().length === 0;
  }

  function renderMatchOptions() {
    const matches = state.truth.matches || [];
    dom.matchFilter.innerHTML = [
      '<option value="">All matches</option>',
      ...matches.map((match) => `<option value="${escapeHtml(match.id)}">${escapeHtml(fullMatchLabel(match))}</option>`),
    ].join("");
    dom.riskMatch.innerHTML = matches
      .map((match) => `<option value="${escapeHtml(match.id)}">${escapeHtml(fullMatchLabel(match))}</option>`)
      .join("");
  }

  function renderRiskClaimOptions() {
    const capabilities = state.truth.capabilities.risk_claims || {};
    const options = Object.entries(capabilities)
      .sort((left, right) => {
        const leftValue = `${left[1].category}-${left[0]}`;
        const rightValue = `${right[1].category}-${right[0]}`;
        return leftValue.localeCompare(rightValue);
      })
      .map(([claimId, capability]) => {
        const label = `${claimLabel(claimId)} (${capability.category})`;
        return `<option value="${escapeHtml(claimId)}">${escapeHtml(label)}</option>`;
      });
    dom.riskClaim.innerHTML = ['<option value="">No risk play</option>', ...options].join("");
  }

  function renderRiskFields() {
    const claimId = dom.riskClaim.value;
    const match = matchById.get(dom.riskMatch.value) || state.truth.matches[0];
    if (!claimId) {
      dom.riskCategory.textContent = "Skipped";
      dom.riskFields.innerHTML = "";
      updatePreview();
      return;
    }

    const capability = state.truth.capabilities.risk_claims[claimId];
    dom.riskCategory.textContent = capability.category.toUpperCase();
    const fields = [];
    (capability.required_fields || []).forEach((field) => {
      if (field === "match_id") {
        return;
      }
      if (field === "team_id") {
        fields.push(renderRiskTeamField(match));
      } else if (field === "player_id") {
        fields.push(renderRiskPlayerField(match));
      } else if (field === "home_score" || field === "away_score") {
        fields.push(renderRiskScoreField(field, match));
      }
    });
    dom.riskFields.innerHTML = fields.join("");
    dom.riskFields.querySelectorAll("input, select").forEach((input) => {
      input.addEventListener("input", updatePreview);
      input.addEventListener("change", updatePreview);
    });
    updatePreview();
  }

  function renderRiskTeamField(match) {
    if (!match) {
      return "";
    }
    return `
      <label>
        Team
        <select id="risk-team-id">
          <option value="${escapeHtml(match.home_team.id)}">${escapeHtml(match.home_team.name)}</option>
          <option value="${escapeHtml(match.away_team.id)}">${escapeHtml(match.away_team.name)}</option>
        </select>
      </label>
    `;
  }

  function renderRiskPlayerField(match) {
    if (!match) {
      return "";
    }
    const players = (state.truth.players || [])
      .filter((player) => String(player.match_id) === String(match.id))
      .sort((left, right) => `${left.team}-${left.name}`.localeCompare(`${right.team}-${right.name}`));
    return `
      <label>
        Player
        <select id="risk-player-id">
          ${players
            .map(
              (player) =>
                `<option value="${escapeHtml(player.id)}">${escapeHtml(player.name)} - ${escapeHtml(player.team)}</option>`
            )
            .join("")}
        </select>
      </label>
    `;
  }

  function renderRiskScoreField(field, match) {
    const teamName = field === "home_score" ? match?.home_team?.name || "Home" : match?.away_team?.name || "Away";
    return `
      <label>
        ${escapeHtml(teamName)} goals
        <input id="risk-${field.replace("_", "-")}" type="number" min="0" step="1" value="0" />
      </label>
    `;
  }

  function filteredPlayers() {
    const query = dom.playerSearch.value.trim().toLowerCase();
    const matchId = dom.matchFilter.value;
    const position = dom.positionFilter.value;
    return (state.truth.players || [])
      .filter((player) => !matchId || String(player.match_id) === matchId)
      .filter((player) => !position || player.position === position)
      .filter((player) => {
        if (!query) {
          return true;
        }
        return `${player.name} ${player.team}`.toLowerCase().includes(query);
      })
      .sort((left, right) => {
        const leftMatch = matchById.get(String(left.match_id));
        const rightMatch = matchById.get(String(right.match_id));
        const leftKey = `${leftMatch ? matchLabel(leftMatch) : left.match_id}-${POSITION_ORDER.indexOf(left.position)}-${left.team}-${left.name}`;
        const rightKey = `${rightMatch ? matchLabel(rightMatch) : right.match_id}-${POSITION_ORDER.indexOf(right.position)}-${right.team}-${right.name}`;
        return leftKey.localeCompare(rightKey);
      });
  }

  function renderPlayers() {
    const chosen = selectedRecordIds();
    const cards = filteredPlayers().map((player) => {
      const match = matchById.get(String(player.match_id));
      const isSelected = chosen.has(player.record_id);
      const disabled = !isSelected && selectedPlayers.length >= 11;
      return `
        <article class="player-card ${isSelected ? "selected" : ""}">
          <div>
            <div class="player-name">${escapeHtml(player.name)}</div>
            <div class="player-meta">${escapeHtml(player.team)} | ${escapeHtml(match ? matchLabel(match) : player.match_id)}</div>
          </div>
          <div class="tag-row">
            <span class="tag ${positionClass(player.position)}">${escapeHtml(player.position)}</span>
            <span class="tag">ID ${escapeHtml(player.id)}</span>
          </div>
          <button type="button" data-record="${escapeHtml(player.record_id)}" ${disabled ? "disabled" : ""}>
            ${isSelected ? "Remove" : "Add"}
          </button>
        </article>
      `;
    });
    dom.playerGrid.innerHTML = cards.join("") || '<p class="muted">No players match the filters.</p>';
  }

  function renderSelected() {
    const counts = positionCounts();
    dom.selectionTotal.textContent = `${selectedPlayers.length}/11`;
    dom.positionCounts.innerHTML = POSITION_ORDER.map((position) => {
      const [min, max] = POSITION_LIMITS[position];
      return `<span>${position} ${counts[position]} (${min === max ? min : `${min}-${max}`})</span>`;
    }).join("");

    dom.selectedList.innerHTML = selectedPlayers
      .map((player) => {
        const match = matchById.get(String(player.match_id));
        return `
          <li>
            <strong>${escapeHtml(player.name)}</strong>
            <div class="player-meta">${escapeHtml(player.position)} | ${escapeHtml(player.team)}</div>
            <div class="player-meta">${escapeHtml(match ? matchLabel(match) : player.match_id)}</div>
            <button type="button" data-remove="${escapeHtml(player.record_id)}">Remove</button>
          </li>
        `;
      })
      .join("");

    const errors = selectionErrors();
    dom.selectionStatus.className = `status-line ${errors.length ? "bad" : "good"}`;
    dom.selectionStatus.textContent = errors.length ? errors[0] : "XI is valid.";
  }

  function renderLeaderboard(leaderboard) {
    const teams = leaderboard?.teams || [];
    if (!teams.length) {
      dom.leaderboardBody.innerHTML = '<tr><td colspan="4" class="muted">No scored teams yet.</td></tr>';
      return;
    }
    dom.leaderboardBody.innerHTML = teams
      .map((team) => {
        const dayPoints = Number(team.fantasy_points || 0) + Number(team.risk_points || 0);
        return `
          <tr>
            <td>${escapeHtml(team.rank || "")}</td>
            <td>${escapeHtml(team.team_name || team.team_id)}</td>
            <td>${formatPoints(team.total_points)}</td>
            <td>${signedPoints(dayPoints)}</td>
          </tr>
        `;
      })
      .join("");
  }

  function renderResult(resultsPayload) {
    const results = resultsPayload?.results || [];
    const teamId = dom.teamId.value.trim();
    const result = results.find((item) => item.team_id === teamId);
    if (!result) {
      dom.scoreResult.innerHTML = '<p class="muted">No submission scored for this team yet.</p>';
      return;
    }
    const fantasyErrors = result.fantasy.errors || [];
    const riskErrorsList = result.risk.errors || [];
    const fantasyTotals = fantasyBreakdownTotals(result.fantasy.players);
    const riskPoints = Number(result.risk_points || 0);
    dom.scoreResult.innerHTML = `
      <div class="score-card">
        <strong>Fantasy XI</strong>
        <span>${formatPoints(result.fantasy_points)} net points</span>
        <div class="mini-grid">
          <span>Earned ${signedPoints(fantasyTotals.earned)}</span>
          <span>Lost ${signedPoints(fantasyTotals.lost)}</span>
        </div>
        ${fantasyErrors.length ? `<p class="muted">${escapeHtml(fantasyErrors[0])}</p>` : ""}
      </div>
      <div class="score-card">
        <strong>Risk Play</strong>
        <span>${escapeHtml(result.risk.outcome)} | <span class="${pointClass(riskPoints)}">${signedPoints(riskPoints)}</span></span>
        <div class="mini-grid">
          <span>Category ${escapeHtml(result.risk.category || "none")}</span>
          <span>Stake ${formatPoints(result.risk.stake || 0)}</span>
        </div>
        ${riskErrorsList.length ? `<p class="muted">${escapeHtml(riskErrorsList[0])}</p>` : ""}
      </div>
      <div class="score-card">
        <strong>Total</strong>
        <span>${formatPoints(result.previous_total_points)} to ${formatPoints(result.new_total_points)}</span>
      </div>
      <div class="score-card score-card-wide">
        <strong>Player Breakdown</strong>
        ${renderPlayerBreakdown(result.fantasy.players)}
      </div>
    `;
  }

  function formatPoints(value) {
    const number = Number(value || 0);
    return Number.isInteger(number) ? String(number) : number.toFixed(2);
  }

  function signedPoints(value) {
    const number = Number(value || 0);
    const text = formatPoints(number);
    return number > 0 ? `+${text}` : text;
  }

  function pointClass(value) {
    return Number(value || 0) < 0 ? "points-negative" : "points-positive";
  }

  function renderPointRules() {
    const rules = state.truth.point_rules || {};
    dom.rulesList.innerHTML = POINT_RULE_ORDER.filter((key) => rules[key] !== undefined)
      .map((key) => {
        const value = Number(rules[key] || 0);
        return `
          <div class="rule-chip ${value < 0 ? "negative" : ""}">
            <span>${escapeHtml(POINT_RULE_LABELS[key] || claimLabel(key))}</span>
            <strong>${signedPoints(value)}</strong>
          </div>
        `;
      })
      .join("");
  }

  function fantasyBreakdownTotals(players) {
    return (players || []).reduce(
      (totals, player) => {
        (player.breakdown || []).forEach((item) => {
          const points = Number(item.points || 0);
          if (points >= 0) {
            totals.earned += points;
          } else {
            totals.lost += points;
          }
        });
        return totals;
      },
      { earned: 0, lost: 0 }
    );
  }

  function renderBreakdownItem(item) {
    const points = Number(item.points || 0);
    return `
      <li class="breakdown-line">
        <span>${escapeHtml(item.label)}</span>
        <strong class="${pointClass(points)}">${signedPoints(points)}</strong>
      </li>
    `;
  }

  function renderPlayerBreakdown(players) {
    if (!players || !players.length) {
      return '<p class="muted">No player details available.</p>';
    }

    return `
      <div class="player-breakdown">
        ${players
          .map((player) => {
            const breakdown = player.breakdown || [];
            return `
              <article class="breakdown-player">
                <div class="breakdown-player-head">
                  <div>
                    <strong>${escapeHtml(player.name)}</strong>
                    <span>${escapeHtml(player.position)} | ${escapeHtml(player.team)}</span>
                  </div>
                  <strong class="${pointClass(player.points)}">${signedPoints(player.points)}</strong>
                </div>
                <ul class="breakdown-list">
                  ${
                    breakdown.length
                      ? breakdown.map(renderBreakdownItem).join("")
                      : '<li class="breakdown-line muted"><span>No scoring events</span><strong>0</strong></li>'
                  }
                </ul>
              </article>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function updatePreview() {
    const payload = buildPayload();
    dom.payloadPreview.textContent = JSON.stringify(payload, null, 2);
    const errors = [...selectionErrors(), ...riskErrors()];
    dom.submitPayload.disabled = !canSubmit();
    dom.downloadPayload.disabled = !payload.team_id;
    if (!dom.teamName.value.trim()) {
      dom.saveStatus.textContent = "Team name needed";
    } else if (errors.length) {
      dom.saveStatus.textContent = errors[0];
    } else {
      dom.saveStatus.textContent = "Ready";
    }
  }

  function togglePlayer(recordId) {
    const existing = selectedPlayers.find((player) => player.record_id === recordId);
    if (existing) {
      selectedPlayers = selectedPlayers.filter((player) => player.record_id !== recordId);
    } else if (selectedPlayers.length < 11) {
      const player = playerByRecordId.get(recordId);
      if (player) {
        selectedPlayers = [...selectedPlayers, player];
      }
    }
    renderSelected();
    renderPlayers();
    updatePreview();
  }

  async function submitPayload() {
    const payload = buildPayload();
    dom.saveStatus.textContent = "Saving...";
    dom.submitPayload.disabled = true;
    const response = await fetch("submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Could not save submission.");
    }
    state.submissions = body.submissions;
    state.matchday_results = body.matchday_results;
    state.leaderboard = body.leaderboard;
    dom.saveStatus.textContent = body.rotated_batch ? "Saved in fresh batch" : "Saved";
    renderResult(state.matchday_results);
    renderLeaderboard(state.leaderboard);
    updatePreview();
  }

  function downloadPayload() {
    const payload = buildPayload();
    const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${payload.team_id || "team"}.submission.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function wireEvents() {
    [
      dom.teamName,
      dom.teamId,
      dom.strategySummary,
      dom.playerSearch,
      dom.positionFilter,
      dom.matchFilter,
    ].forEach((input) => {
      input.addEventListener("input", () => {
        if (input === dom.teamName) {
          localStorage.setItem("fantasyCupPlaytestTeamName", dom.teamName.value);
        }
        if (input === dom.teamId) {
          localStorage.setItem("fantasyCupPlaytestTeamId", dom.teamId.value);
        }
        renderPlayers();
        updatePreview();
      });
      input.addEventListener("change", () => {
        renderPlayers();
        updatePreview();
      });
    });

    dom.riskClaim.addEventListener("change", renderRiskFields);
    dom.riskMatch.addEventListener("change", renderRiskFields);
    dom.clearSelection.addEventListener("click", () => {
      selectedPlayers = [];
      renderSelected();
      renderPlayers();
      updatePreview();
    });
    dom.playerGrid.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-record]");
      if (button) {
        togglePlayer(button.dataset.record);
      }
    });
    dom.selectedList.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-remove]");
      if (button) {
        togglePlayer(button.dataset.remove);
      }
    });
    dom.submitPayload.addEventListener("click", () => {
      submitPayload().catch((error) => {
        dom.saveStatus.textContent = "Save failed";
        dom.scoreResult.innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
        updatePreview();
      });
    });
    dom.downloadPayload.addEventListener("click", downloadPayload);
  }

  async function loadState() {
    const response = await fetch("state");
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Could not load playtest state.");
    }
    state = body;
    playerByRecordId = new Map((state.truth.players || []).map((player) => [player.record_id, player]));
    matchById = new Map((state.truth.matches || []).map((match) => [String(match.id), match]));

    dom.fixtureCount.textContent = `${state.truth.matches.length} matches`;
    dom.playerCount.textContent = `${state.truth.players.length} players`;

    renderPointRules();
    renderMatchOptions();
    renderRiskClaimOptions();
    renderRiskFields();
    renderSelected();
    renderPlayers();
    renderResult(state.matchday_results);
    renderLeaderboard(state.leaderboard);
    updatePreview();
  }

  setupTeamDefaults();
  wireEvents();
  loadState().catch((error) => {
    dom.saveStatus.textContent = "Load failed";
    dom.scoreResult.innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
  });
})();
