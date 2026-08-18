(async function () {
  const canvas = document.getElementById("knowledge-graph");
  const inspector = document.getElementById("graph-inspector");
  const searchInput = document.getElementById("graph-search");
  const searchClear = document.getElementById("graph-search-clear");
  const emptyState = document.getElementById("graph-empty");
  if (!canvas || typeof cytoscape === "undefined") return;

  const response = await fetch("/api/graph");
  if (!response.ok) throw new Error("图谱数据加载失败");
  const graph = await response.json();
  const colors = {
    technology: "#0f6b50",
    candidate: "#eef8eb",
    discovery_category: "#e7ddff",
    capability: "#c9ef75",
    claim: "#9bc9ff",
    evidence: "#ffb38e",
    experiment: "#b9a4ff",
    knowledge: "#fff3b0",
  };
  const typeLabels = {
    technology: "技术",
    candidate: "候选技术",
    discovery_category: "技术路线",
    capability: "能力",
    claim: "结论",
    evidence: "证据",
    experiment: "实验",
    knowledge: "学习笔记",
  };
  const subtypeLabels = {
    concept: "概念",
    question: "追问",
    challenge: "质疑",
    answer: "回答",
    note: "笔记",
  };
  const sourceKindLabels = {
    manual: "手写笔记",
    codex_conversation: "Codex 会话提炼",
    automated_research: "自动研究",
  };
  const verificationLabels = {
    unverified: "待查证",
    researching: "查证中",
    partially_verified: "部分证实",
    verified: "已查证",
    contested: "存在争议",
  };

  const cy = cytoscape({
    container: canvas,
    elements: graph.elements,
    wheelSensitivity: 0.2,
    minZoom: 0.18,
    maxZoom: 2.4,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (node) => colors[node.data("type")] || "#ffffff",
          label: "data(label)",
          color: "#172020",
          "font-size": 10,
          "font-family": "Inter, -apple-system, sans-serif",
          "font-weight": 600,
          "text-wrap": "wrap",
          "text-max-width": 156,
          "text-valign": "center",
          "text-halign": "center",
          shape: "round-rectangle",
          width: 172,
          height: "label",
          padding: 11,
          "border-width": 1,
          "border-color": "rgba(23,32,32,.2)",
          "overlay-opacity": 0,
          "transition-property": "opacity, border-width, border-color",
          "transition-duration": "180ms",
        },
      },
      {
        selector: 'node[type = "technology"]',
        style: {
          color: "#ffffff",
          "font-size": 12,
          "font-weight": 750,
          "text-max-width": 106,
          width: "data(node_size)",
          height: "data(node_size)",
          shape: "ellipse",
          "border-width": 3,
          "border-color": "rgba(255,255,255,.72)",
        },
      },
      {
        selector: 'node[type = "candidate"]',
        style: {
          color: "#0f513d",
          "font-size": 11,
          "font-weight": 750,
          "text-max-width": 106,
          width: "data(node_size)",
          height: "data(node_size)",
          shape: "ellipse",
          "border-width": 3,
          "border-color": "#0f6b50",
        },
      },
      { selector: 'node[type = "discovery_category"]', style: { width: 126, "text-max-width": 108, "background-color": "#e7ddff", "border-color": "#7458a8", "border-width": 2 } },
      { selector: 'node[type = "capability"]', style: { width: 118, "text-max-width": 100 } },
      { selector: 'node[type = "evidence"]', style: { width: 142, "text-max-width": 124, "font-size": 9 } },
      { selector: 'node[type = "experiment"]', style: { width: 146, "text-max-width": 128 } },
      { selector: 'node[type = "knowledge"][subtype = "question"]', style: { "background-color": "#fff3b0", "border-color": "#c69120", "border-style": "dashed" } },
      { selector: 'node[type = "knowledge"][subtype = "challenge"]', style: { "background-color": "#f8d7d2", "border-color": "#d04a3a", "border-width": 2 } },
      { selector: 'node[type = "knowledge"][subtype = "answer"]', style: { "background-color": "#d8f3c0", "border-color": "#0f6b50" } },
      { selector: 'node[type = "knowledge"][subtype = "note"]', style: { "background-color": "#e9e6de", "border-color": "#657270" } },
      {
        selector: "edge",
        style: {
          width: 1.25,
          "line-color": "rgba(23,32,32,.23)",
          "target-arrow-color": "rgba(23,32,32,.3)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "arrow-scale": 0.7,
          opacity: 0.82,
          "transition-property": "opacity, line-color, width",
          "transition-duration": "180ms",
        },
      },
      { selector: 'edge[relation = "supports"], edge[relation = "provides"], edge[relation = "answers"]', style: { "line-color": "#0f6b50", "target-arrow-color": "#0f6b50", width: 2 } },
      { selector: 'edge[relation = "contradicts"], edge[relation = "challenges"], edge[relation = "corrects"]', style: { "line-color": "#d04a3a", "target-arrow-color": "#d04a3a", width: 2 } },
      { selector: 'edge[relation = "about"], edge[relation = "evaluates"], edge[relation = "questions"]', style: { "line-style": "dashed" } },
      { selector: 'edge[relation = "classified_as"]', style: { "line-style": "dotted", "line-color": "#7458a8", "target-arrow-color": "#7458a8", opacity: 0.62 } },
      { selector: 'edge[relation = "documented_by"]', style: { "line-color": "#d78334", "target-arrow-color": "#d78334" } },
      { selector: ":selected", style: { "border-width": 5, "border-color": "#172020" } },
      { selector: ".dimmed", style: { opacity: 0.1 } },
      { selector: ".focused-neighbor", style: { opacity: 1, "border-width": 2.5 } },
      { selector: ".search-match", style: { "border-width": 5, "border-color": "#d78334" } },
      { selector: ".filtered, .search-hidden", style: { display: "none" } },
    ],
    layout: {
      name: "cose",
      animate: false,
      padding: 72,
      nodeRepulsion: 18500,
      idealEdgeLength: 145,
      edgeElasticity: 90,
      nestingFactor: 1.2,
      gravity: 0.18,
      numIter: 1800,
      componentSpacing: 140,
      nodeOverlap: 30,
    },
  });

  function layoutOptions(name, animate = true) {
    if (name === "hierarchy") {
      return { name: "breadthfirst", directed: true, padding: 70, spacingFactor: 1.35, animate, animationDuration: 450 };
    }
    if (name === "rings") {
      return {
        name: "concentric",
        padding: 72,
        minNodeSpacing: 44,
        animate,
        animationDuration: 450,
        concentric: (node) => ({ technology: 7, candidate: 6, discovery_category: 5, capability: 4, claim: 3, knowledge: 2, evidence: 1, experiment: 1 }[node.data("type")] || 1),
        levelWidth: () => 1,
      };
    }
    return {
      name: "cose",
      padding: 72,
      nodeRepulsion: 18500,
      idealEdgeLength: 145,
      edgeElasticity: 90,
      gravity: 0.18,
      numIter: 1500,
      componentSpacing: 140,
      nodeOverlap: 30,
      animate,
      animationDuration: 450,
    };
  }

  function runLayout(name, animate = true) {
    cy.elements().removeClass("dimmed focused-neighbor");
    cy.layout(layoutOptions(name, animate)).run();
    document.querySelectorAll("[data-layout]").forEach((button) => {
      button.classList.toggle("active", button.dataset.layout === name);
    });
  }

  function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  function actionLink(label, href, className = "") {
    const link = element("a", className, label);
    link.href = href;
    return link;
  }

  function knowledgeActionHref(data, nodeType, relationType) {
    const params = new URLSearchParams({
      target_id: data.type === "knowledge" ? (data.target_id || data.id) : data.id,
      node_type: nodeType,
      relation_type: relationType,
    });
    if (data.type === "knowledge") params.set("parent_id", data.id);
    return `/nodes/new?${params.toString()}`;
  }

  function resetInspector() {
    inspector.replaceChildren(
      element("span", "", "选择一个节点"),
      element("h2", "", "从路线开始探索"),
      element("p", "", "这里显示完整内容和直接关联，并可进入 Codex 继续研究。"),
    );
  }

  function showInspector(node) {
    const data = node.data();
    const typeLabel = data.type === "knowledge" ? subtypeLabels[data.subtype] : typeLabels[data.type];
    const relatedCount = node.connectedEdges().connectedNodes().not(node).length;
    const children = [
      element("span", "", `${typeLabel || data.type} · ${data.status || ""}`),
      element("h2", "", data.label),
      element("p", "", data.description || "暂无说明"),
      element("small", "", `${relatedCount} 个直接关联`),
    ];
    if (data.confidence !== undefined) children.push(element("small", "", `置信度 ${data.confidence}%`));
    if (data.type === "knowledge") {
      children.push(
        element(
          "small",
          "inspector-provenance",
          `${sourceKindLabels[data.source_kind] || "学习笔记"} · ${verificationLabels[data.verification_status] || "待查证"}`,
        ),
      );
    }
    if ((data.type === "technology" || data.type === "candidate") && data.github_stars !== null) {
      const popularity = element("div", "inspector-popularity");
      popularity.append(
        element("strong", "", `${data.popularity_tier} · 信号 ${data.popularity_score}`),
        element("p", "", `GitHub ${Number(data.github_stars).toLocaleString()} Stars · ${Number(data.github_forks).toLocaleString()} Forks`),
        element("small", "", `最近活动 ${String(data.last_activity_at).slice(0, 10)} · 只是热度/规模信号`),
      );
      children.push(popularity);
    }
    if (data.type === "candidate") {
      const candidateNotice = element("div", "inspector-candidate-notice");
      candidateNotice.append(
        element("strong", "", "尚未进入正式评估"),
        element("p", "", `${data.ecosystem || "未知生态"} · ${data.relevance || "未判读"}相关。当前只确认它值得进一步查源，不代表已经推荐采用。`),
      );
      children.push(candidateNotice);
    }
    const actions = element("div", "inspector-actions");
    actions.append(
      actionLink("在 Codex 中继续研究", `/research/${encodeURIComponent(data.id)}`, "action-codex"),
      actionLink("记录手写笔记", knowledgeActionHref(data, "note", "extends"), "action-note"),
    );
    children.push(actions);
    if (data.href) {
      const label = data.type === "knowledge" ? "查看笔记与来源 →" : "查看详情 →";
      const link = actionLink(label, data.href, "inspector-detail-link");
      if (data.href.startsWith("http")) {
        link.target = "_blank";
        link.rel = "noreferrer";
      }
      children.push(link);
    }
    if (data.editable) children.push(actionLink("编辑笔记", `/nodes/${encodeURIComponent(data.id)}/edit`, "inspector-edit-link"));
    inspector.replaceChildren(...children);
  }

  function focusNode(node, center = false) {
    cy.elements().removeClass("dimmed focused-neighbor");
    cy.elements().addClass("dimmed");
    const neighborhood = node.closedNeighborhood();
    neighborhood.removeClass("dimmed").addClass("focused-neighbor");
    node.select();
    if (center) cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 0.82), duration: 350 });
    showInspector(node);
  }

  function resetFocus() {
    cy.elements().removeClass("dimmed focused-neighbor");
    cy.$(":selected").unselect();
    resetInspector();
  }

  function updateEdgeVisibility() {
    cy.edges().forEach((edge) => {
      const hidden = edge.source().hasClass("filtered") || edge.target().hasClass("filtered") || edge.source().hasClass("search-hidden") || edge.target().hasClass("search-hidden");
      edge.toggleClass("search-hidden", hidden);
    });
  }

  function applySearch() {
    const query = (searchInput?.value || "").trim().toLocaleLowerCase("zh-CN");
    cy.elements().removeClass("search-hidden search-match");
    if (!query) {
      if (emptyState) emptyState.hidden = true;
      updateEdgeVisibility();
      return;
    }
    const matches = cy.nodes().filter((node) => `${node.data("label") || ""} ${node.data("description") || ""}`.toLocaleLowerCase("zh-CN").includes(query));
    const visible = matches.closedNeighborhood();
    cy.nodes().difference(visible.nodes()).addClass("search-hidden");
    matches.addClass("search-match");
    updateEdgeVisibility();
    if (emptyState) emptyState.hidden = matches.length > 0;
    if (matches.length === 1) focusNode(matches.first(), true);
  }

  cy.on("tap", "node", (event) => focusNode(event.target));
  cy.on("tap", (event) => { if (event.target === cy) resetFocus(); });
  cy.on("dbltap", 'node[type = "technology"], node[type = "candidate"], node[type = "discovery_category"]', (event) => {
    const href = event.target.data("href");
    if (href) window.location.href = href;
  });
  function applyTypeFilter(checkbox) {
      const type = checkbox.dataset.nodeFilter;
      cy.nodes().filter((node) => node.data("type") === type).toggleClass("filtered", !checkbox.checked);
      updateEdgeVisibility();
  }
  document.querySelectorAll("[data-node-filter]").forEach((checkbox) => {
    applyTypeFilter(checkbox);
    checkbox.addEventListener("change", () => {
      applyTypeFilter(checkbox);
      runLayout(document.querySelector("[data-layout].active")?.dataset.layout || "organic");
    });
  });
  document.querySelectorAll("[data-layout]").forEach((button) => button.addEventListener("click", () => runLayout(button.dataset.layout)));
  document.getElementById("graph-fit")?.addEventListener("click", () => { resetFocus(); cy.fit(cy.elements(":visible"), 72); });
  searchInput?.addEventListener("input", applySearch);
  searchInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const first = cy.nodes(".search-match").first();
      if (first.length) focusNode(first, true);
    }
  });
  searchClear?.addEventListener("click", () => {
    searchInput.value = "";
    applySearch();
    searchInput.focus();
    cy.fit(cy.elements(":visible"), 72);
  });

  runLayout("organic", false);

  const focusId = new URLSearchParams(window.location.search).get("focus");
  if (focusId) {
    const target = cy.getElementById(focusId);
    if (target.length) setTimeout(() => focusNode(target, true), 80);
  }
})();
