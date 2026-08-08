(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const statusBadge = el("status-badge");
  const destinationInput = el("destination-input");
  const bundleCount = el("bundle-count");
  const hooksStatus = el("hooks-status");
  const bundlesTbody = el("bundles-tbody");
  const detailTitle = el("detail-title");
  const detailEmpty = el("detail-empty");
  const detailContent = el("detail-content");
  const detailStats = el("detail-stats");
  const detailPrompts = el("detail-prompts");
  const detailOps = el("detail-ops");
  const toast = el("toast");

  let selectedBundleId = null;
  let toastTimer = null;

  function showToast(message, kind) {
    toast.textContent = message;
    toast.className = "toast" + (kind ? " " + kind : "");
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
  }

  async function api(path, options) {
    const res = await fetch(path, Object.assign({
      headers: { "Content-Type": "application/json" },
    }, options || {}));
    let payload = null;
    try { payload = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      const message = (payload && payload.error) || (res.status + " " + res.statusText);
      throw new Error(message);
    }
    return payload;
  }

  function fmtBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function fmtDate(iso) {
    if (!iso) return "–";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleString();
    } catch (e) {
      return iso;
    }
  }

  async function refreshStatus() {
    try {
      const status = await api("/api/status");
      destinationInput.value = status.destination || "";
      bundleCount.textContent = status.bundle_count;
      if (status.enabled) {
        statusBadge.textContent = "Enabled";
        statusBadge.className = "badge badge-on";
      } else {
        statusBadge.textContent = "Disabled";
        statusBadge.className = "badge badge-off";
      }
    } catch (e) {
      statusBadge.textContent = "Error";
      statusBadge.className = "badge badge-off";
      showToast("Failed to load status: " + e.message, "error");
    }

    try {
      const hooks = await api("/api/hooks-status");
      const installed = hooks.installed_events || [];
      hooksStatus.textContent = installed.length
        ? installed.length + "/4 events (" + installed.join(", ") + ")"
        : "none installed";
    } catch (e) {
      hooksStatus.textContent = "unknown";
    }
  }

  async function refreshBundles() {
    bundlesTbody.innerHTML = '<tr><td colspan="5" class="empty-row">Loading…</td></tr>';
    try {
      const data = await api("/api/bundles");
      const bundles = data.bundles || [];
      if (!bundles.length) {
        bundlesTbody.innerHTML = '<tr><td colspan="5" class="empty-row">No bundles recorded yet.</td></tr>';
        return;
      }
      bundlesTbody.innerHTML = "";
      for (const b of bundles) {
        const tr = document.createElement("tr");
        tr.dataset.id = b.id;
        if (b.id === selectedBundleId) tr.classList.add("selected");
        const meta = b.session_meta || {};
        tr.innerHTML = [
          "<td>" + fmtDate(meta.started_at) + "</td>",
          "<td>" + (meta.username || "–") + "</td>",
          "<td title=\"" + (meta.root_path || "") + "\">" + (meta.root_path || "–") + "</td>",
          "<td>" + (b.line_count != null ? b.line_count : "–") + "</td>",
          "<td>" + fmtBytes(b.size_bytes || 0) + "</td>",
        ].join("");
        if (b.error) {
          tr.title = "Could not fully parse this bundle: " + b.error;
          tr.style.opacity = "0.6";
        }
        tr.addEventListener("click", () => loadDetail(b.id));
        bundlesTbody.appendChild(tr);
      }
    } catch (e) {
      bundlesTbody.innerHTML = '<tr><td colspan="5" class="empty-row">Failed to load bundles.</td></tr>';
      showToast("Failed to load bundles: " + e.message, "error");
    }
  }

  function opLabel(op) {
    return op.replace("_", " ");
  }

  function opSummary(operation, details) {
    details = details || {};
    switch (operation) {
      case "read": return details.path || "";
      case "glob": return (details.pattern || "") + (details.path ? "  in " + details.path : "");
      case "grep": return (details.pattern || "") + (details.path ? "  in " + details.path : "");
      case "web_fetch": return details.url || "";
      case "web_search": return details.query || "";
      default: return JSON.stringify(details);
    }
  }

  async function loadDetail(bundleId) {
    selectedBundleId = bundleId;
    Array.from(bundlesTbody.querySelectorAll("tr")).forEach((tr) => {
      tr.classList.toggle("selected", tr.dataset.id === bundleId);
    });

    detailTitle.textContent = "Bundle: " + bundleId;
    detailEmpty.hidden = true;
    detailContent.hidden = false;
    detailStats.textContent = "";
    detailPrompts.innerHTML = "<li>Loading…</li>";
    detailOps.innerHTML = "";

    try {
      const plan = await api("/api/bundles/" + encodeURIComponent(bundleId));
      const stats = plan.stats || {};
      detailStats.innerHTML = [
        "<span><strong>" + stats.total_lines + "</strong> lines</span>",
        "<span><strong>" + stats.malformed + "</strong> malformed</span>",
        "<span><strong>" + stats.deduped_from + "</strong> deduplicated</span>",
        "<span><strong>" + stats.excluded + "</strong> non-replayable</span>",
      ].join("");

      detailPrompts.innerHTML = "";
      if (!plan.prompts.length) {
        detailPrompts.innerHTML = "<li><em>No prompts recorded.</em></li>";
      }
      for (const p of plan.prompts) {
        const li = document.createElement("li");
        li.textContent = p.text;
        detailPrompts.appendChild(li);
      }

      detailOps.innerHTML = "";
      if (!plan.context_operations.length) {
        detailOps.innerHTML = "<li class=\"empty-state\">No replayable read/search/fetch operations.</li>";
      }
      for (const op of plan.context_operations) {
        const li = document.createElement("li");
        li.className = "op-item" + (op.stale ? " stale" : "");
        li.innerHTML =
          '<span class="op-type">' + opLabel(op.operation) + "</span>" +
          "<span>" + opSummary(op.operation, op.details) + "</span>";
        detailOps.appendChild(li);
      }
    } catch (e) {
      detailPrompts.innerHTML = "";
      detailOps.innerHTML = "";
      detailStats.textContent = "";
      showToast("Failed to load bundle: " + e.message, "error");
    }
  }

  el("save-destination-btn").addEventListener("click", async () => {
    const destination = destinationInput.value.trim();
    if (!destination) {
      showToast("Enter a destination path first", "error");
      return;
    }
    try {
      await api("/api/config", { method: "POST", body: JSON.stringify({ destination }) });
      showToast("Destination saved", "success");
      refreshStatus();
    } catch (e) {
      showToast("Failed to save destination: " + e.message, "error");
    }
  });

  el("enable-btn").addEventListener("click", async () => {
    try {
      await api("/api/enable", { method: "POST" });
      showToast("Recording enabled for new sessions", "success");
      refreshStatus();
    } catch (e) {
      showToast("Failed to enable: " + e.message, "error");
    }
  });

  el("disable-btn").addEventListener("click", async () => {
    try {
      await api("/api/disable", { method: "POST" });
      showToast("Recording disabled", "success");
      refreshStatus();
    } catch (e) {
      showToast("Failed to disable: " + e.message, "error");
    }
  });

  el("load-latest-btn").addEventListener("click", () => loadDetail("latest"));

  el("refresh-btn").addEventListener("click", () => {
    refreshStatus();
    refreshBundles();
  });

  refreshStatus();
  refreshBundles();
})();
