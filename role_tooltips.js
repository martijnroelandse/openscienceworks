/* Shared inferred-role tooltips (labels + descriptions from about.html) */
(function (global) {
  "use strict";

  const ROLE_DESCRIPTIONS = {
    "Scholarly Uptake":
      "Foundational building block cited heavily in core academic journals and monographs.",
    "Rapid Uptake":
      "Accumulated strong citations or usage signals in an unusually short period — indicating immediate relevance in the field.",
    "Reference Point for Synthesis":
      "Frequently cited in literature reviews and meta-analyses as a shorthand reference for a specific finding or framework.",
    "Methodological Anchor":
      "A standard protocol or tool used by other researchers, inferred from reproducibility-oriented uptake patterns.",
    "Evidence-bearing Reference":
      "Explicitly applied as hard data or methodology, often accompanied by stewardship, reuse, or supporting citation context.",
    "Public Visibility & Knowledge Base":
      "Integrated into durable open-knowledge surfaces and scholarly discussion layers, indicating broad interpretive uptake.",
    "Usage-Driven Uptake":
      "Value through direct consumption: high downloads, HTML views, or library holdings rather than formal citation.",
    "Pedagogical Anchor":
      "Teaching adoption signal spanning OCW, syllabi/OER, open textbook matches, and educational video usage across story types.",
    "Active Public Discourse":
      "Sustained engagement across open-web channels, calculated from normalized attention sources with legacy fallbacks for continuity.",
    "High-Visibility Uptake":
      "Mentioned in mainstream news or broadsheets — the work has reached beyond academia into public awareness.",
    "Sustainability & Policy Relevance":
      "Connected to SDG/policy-oriented signals that indicate potential governance and societal relevance.",
    "Commercial Linkage":
      "Present on Amazon, Goodreads, or in patents — indicating consumer interest or industry application.",
    "Dataset Reference Backbone":
      "Foundational dataset reuse reflected in sustained downstream citations.",
    "Benchmark Resource":
      "Dataset appears repeatedly in benchmark-style analytical and methodological usage.",
    "Infrastructure Dataset":
      "Broad, cross-venue dataset utility across multiple communities and workflows.",
    "Software Method Anchor":
      "Software is repeatedly relied on as part of downstream research methods.",
    "Computational Reproducibility Enabler":
      "Software supports transparent, repeatable computation and method reuse.",
    "Community Tooling Uptake":
      "Adoption in open teaching/practice channels and broader community usage.",
  };

  const LABEL_ALIASES = {
    "scholarly uptake": "Scholarly Uptake",
    "rapid uptake": "Rapid Uptake",
    "reference point for synthesis": "Reference Point for Synthesis",
    "methodological anchor": "Methodological Anchor",
    "evidence-bearing reference": "Evidence-bearing Reference",
    "evidence bearing reference": "Evidence-bearing Reference",
    "public visibility & knowledge base": "Public Visibility & Knowledge Base",
    "usage-driven uptake": "Usage-Driven Uptake",
    "usage driven uptake": "Usage-Driven Uptake",
    "pedagogical anchor": "Pedagogical Anchor",
    "active public discourse": "Active Public Discourse",
    "active discussion signal": "Active Public Discourse",
    "high-visibility uptake": "High-Visibility Uptake",
    "high visibility uptake": "High-Visibility Uptake",
    "sustainability & policy relevance": "Sustainability & Policy Relevance",
    "commercial linkage": "Commercial Linkage",
    "dataset reference backbone": "Dataset Reference Backbone",
    "benchmark resource": "Benchmark Resource",
    "infrastructure dataset": "Infrastructure Dataset",
    "software method anchor": "Software Method Anchor",
    "reproducibility standard": "Computational Reproducibility Enabler",
    "computational reproducibility enabler": "Computational Reproducibility Enabler",
    "community tooling uptake": "Community Tooling Uptake",
  };

  function canonicalRoleLabel(raw) {
    if (!raw) return "";
    const s = String(raw).trim().replace(/\s+/g, " ");
    if (ROLE_DESCRIPTIONS[s]) return s;
    const key = s.toLowerCase().replace(/&amp;/g, "&");
    return LABEL_ALIASES[key] || s;
  }

  function parseRoleTip(raw) {
    if (!raw) return { label: "", score: null };
    const m = String(raw).match(/^(.+?)\s*[—–-]\s*heuristic signal\s*\(score\s*([\d.]+)\)\s*$/i);
    if (m) return { label: m[1].trim(), score: m[2] };
    return { label: raw.trim(), score: null };
  }

  function pillLabel(pill) {
    const strength = pill.querySelector(".role-strength, .role-score");
    let text = pill.textContent || "";
    if (strength) text = text.replace(strength.textContent, "");
    return text.replace(/\s+/g, " ").trim();
  }

  function buildRoleTip(label, score) {
    const canonical = canonicalRoleLabel(label);
    const desc = ROLE_DESCRIPTIONS[canonical];
    let tip = canonical;
    if (desc) tip += "\n\n" + desc;
    if (score != null && score !== "") {
      tip += "\n\nHeuristic signal (score " + score + ")";
    }
    return tip;
  }

  function ensureTooltipEl() {
    let tip = document.getElementById("role-tooltip");
    if (tip) return tip;
    tip = document.createElement("div");
    tip.id = "role-tooltip";
    tip.style.cssText =
      "position:fixed;display:none;z-index:9999;background:#111827;color:white;" +
      "padding:.5rem .75rem;border-radius:.5rem;font-size:.72rem;width:260px;" +
      "line-height:1.5;white-space:pre-wrap;font-weight:400;pointer-events:none;" +
      "box-shadow:0 4px 16px rgba(0,0,0,.25);";
    document.body.appendChild(tip);
    return tip;
  }

  function bindRoleTipTarget(el, tipText) {
    if (!el || el.dataset.roleTipBound === "1") return;
    el.dataset.roleTipBound = "1";
    el.setAttribute("data-tip", tipText);
    if (!el.classList.contains("role-pill")) el.style.cursor = "help";

    const tip = ensureTooltipEl();
    el.addEventListener("mouseenter", function () {
      tip.textContent = tipText;
      tip.style.top = "-9999px";
      tip.style.display = "block";
      const r = el.getBoundingClientRect();
      const th = tip.offsetHeight;
      const top =
        window.innerHeight - r.bottom > th + 16 ? r.bottom + 8 : r.top - th - 8;
      let left = Math.min(r.left, window.innerWidth - 268);
      left = Math.max(left, 8);
      tip.style.top = top + "px";
      tip.style.left = left + "px";
    });
    el.addEventListener("mouseleave", function () {
      tip.style.display = "none";
    });
  }

  function initRoleTooltips(root) {
    const scope = root && root.querySelectorAll ? root : document;

    scope.querySelectorAll(".role-pill").forEach(function (pill) {
      const parsed = parseRoleTip(pill.getAttribute("data-tip"));
      const label = pillLabel(pill) || parsed.label;
      const score = parsed.score;
      bindRoleTipTarget(pill, buildRoleTip(label, score));
    });

    scope.querySelectorAll(".tag-role[data-role-label], label.facet-opt-role").forEach(function (el) {
      const parsed = parseRoleTip(el.getAttribute("data-tip"));
      const label = (el.getAttribute("data-role-label") || parsed.label || pillLabel(el)).trim();
      bindRoleTipTarget(el, buildRoleTip(label, parsed.score));
    });
  }

  global.ROLE_DESCRIPTIONS = ROLE_DESCRIPTIONS;
  global.canonicalRoleLabel = canonicalRoleLabel;
  global.buildRoleTip = buildRoleTip;
  global.initRoleTooltips = initRoleTooltips;
})(typeof window !== "undefined" ? window : globalThis);
