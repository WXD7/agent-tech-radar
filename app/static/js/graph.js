(async function () {
  const canvas = document.getElementById("knowledge-graph");
  const inspector = document.getElementById("graph-inspector");
  const searchInput = document.getElementById("graph-search");
  const searchClear = document.getElementById("graph-search-clear");
  const emptyState = document.getElementById("graph-empty");
  const mapSelect = document.getElementById("knowledge-map-select");
  const documentPreview = document.getElementById("graph-document-preview");
  const previewClose = document.getElementById("graph-preview-close");
  const previewStatus = document.getElementById("graph-preview-status");
  const previewKind = document.getElementById("graph-preview-kind");
  const previewTitle = document.getElementById("graph-preview-title");
  const previewDescription = document.getElementById("graph-preview-description");
  const previewOpen = document.getElementById("graph-preview-open");
  const previewResearch = document.getElementById("graph-preview-research");
  const previewScroll = document.getElementById("graph-preview-scroll");
  const previewLoading = document.getElementById("graph-preview-loading");
  const previewContent = document.getElementById("graph-preview-content");
  if (!canvas || typeof cytoscape === "undefined") return;

  const HOVER_DELAY_MS = 450;
  const documentPreviewCache = new Map();
  let hoverTimer = null;
  let hoverPendingNode = null;
  let previewRequestId = 0;
  const mapId = canvas.dataset.mapId || "";
  const response = await fetch(`/api/graph?map_id=${encodeURIComponent(mapId)}`);
  if (!response.ok) throw new Error("图谱数据加载失败");
  const graph = await response.json();
  const colors = {
    document: "#172020",
    section: "#e9e6de",
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
    document: "研究文档",
    section: "文档章节",
    technology: "技术",
    candidate: "候选技术",
    discovery_category: "技术路线",
    capability: "能力",
    claim: "结论",
    evidence: "证据",
    experiment: "实验",
    knowledge: "认知片段",
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

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function readGraphVisualScale() {
    const bounds = canvas.getBoundingClientRect();
    const widthScale = bounds.width / 900;
    const heightScale = bounds.height / 680;
    return clamp(Math.min(widthScale, heightScale), 1, 1.7);
  }

  let graphVisualScale = readGraphVisualScale();
  const scaled = (value) => Math.round(value * graphVisualScale * 10) / 10;
  canvas.dataset.visualScale = graphVisualScale.toFixed(2);

  function labelDisplayUnits(label) {
    return Array.from(String(label || "")).reduce((total, character) => {
      if (/\s/.test(character)) return total + 0.35;
      if (/[\u3400-\u9fff\uf900-\ufaff]/.test(character)) return total + 1;
      if (/[A-Z0-9]/.test(character)) return total + 0.68;
      return total + 0.56;
    }, 0);
  }

  function wrappedLineCount(node, maxTextWidth, fontSize) {
    const lineCapacity = Math.max(1, maxTextWidth / fontSize);
    return Math.max(1, Math.ceil(labelDisplayUnits(node.data("label")) / lineCapacity));
  }

  function wrappedNodeHeight(node, minimumHeight, maxTextWidth, fontSize, verticalPadding = 34) {
    const lines = wrappedLineCount(node, maxTextWidth, fontSize);
    return scaled(Math.max(minimumHeight, lines * fontSize * 1.24 + verticalPadding));
  }

  function circularNodeSize(node, fontSize) {
    const signalSize = (Number(node.data("node_size")) || 72) * 1.28;
    const textHeight = Math.min(4, wrappedLineCount(node, 166, fontSize)) * fontSize * 1.2 + 58;
    return scaled(Math.max(156, signalSize, textHeight));
  }

  const cy = cytoscape({
    container: canvas,
    elements: graph.elements,
    minZoom: 0.18,
    maxZoom: 2.4,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (node) => colors[node.data("type")] || "#ffffff",
          label: "data(label)",
          color: "#172020",
          "font-size": () => scaled(22),
          "font-family": "Inter, -apple-system, sans-serif",
          "font-weight": 800,
          "text-wrap": "wrap",
          "text-overflow-wrap": "anywhere",
          "text-max-width": () => scaled(220),
          "line-height": 1.24,
          "text-valign": "center",
          "text-halign": "center",
          "text-justification": "center",
          "text-outline-color": "#ffffff",
          "text-outline-width": () => scaled(2.4),
          "text-outline-opacity": 0.96,
          shape: "round-rectangle",
          width: () => scaled(250),
          height: (node) => wrappedNodeHeight(node, 80, 220, 22),
          padding: () => scaled(16),
          "border-width": 2,
          "border-color": "rgba(23,32,32,.3)",
          "overlay-opacity": 0,
          "transition-property": "opacity, border-width, border-color",
          "transition-duration": "180ms",
        },
      },
      {
        selector: 'node[type = "technology"]',
        style: {
          color: "#ffffff",
          "font-size": () => scaled(24),
          "font-weight": 800,
          "text-max-width": () => scaled(166),
          "text-outline-color": "#083c2e",
          "text-outline-width": () => scaled(2.8),
          width: (node) => circularNodeSize(node, 24),
          height: (node) => circularNodeSize(node, 24),
          shape: "ellipse",
          "border-width": 3,
          "border-color": "rgba(255,255,255,.72)",
        },
      },
      {
        selector: 'node[type = "document"]',
        style: {
          color: "#ffffff",
          "font-size": () => scaled(28),
          "font-weight": 900,
          "text-max-width": () => scaled(300),
          "text-outline-color": "#0a1412",
          "text-outline-width": () => scaled(3.2),
          width: () => scaled(340),
          height: (node) => wrappedNodeHeight(node, 112, 300, 28, 42),
          padding: () => scaled(22),
          shape: "round-rectangle",
          "border-width": 4,
          "border-color": "#c9ef75",
        },
      },
      {
        selector: 'node[type = "section"]',
        style: {
          width: () => scaled(286),
          height: (node) => wrappedNodeHeight(node, 88, 250, 22, 36),
          "text-max-width": () => scaled(250),
          "font-size": () => scaled(22),
          "font-weight": 800,
          "border-width": 3,
          "border-color": "#0f6b50",
          shape: "round-rectangle",
        },
      },
      {
        selector: 'node[type = "candidate"]',
        style: {
          color: "#0f513d",
          "font-size": () => scaled(22),
          "font-weight": 800,
          "text-max-width": () => scaled(166),
          width: (node) => circularNodeSize(node, 22),
          height: (node) => circularNodeSize(node, 22),
          shape: "ellipse",
          "border-width": 3,
          "border-color": "#0f6b50",
        },
      },
      { selector: 'node[type = "discovery_category"]', style: { width: () => scaled(210), height: (node) => wrappedNodeHeight(node, 84, 178, 20), "text-max-width": () => scaled(178), "font-size": () => scaled(20), "background-color": "#e7ddff", "border-color": "#7458a8", "border-width": 3 } },
      { selector: 'node[type = "capability"]', style: { width: () => scaled(210), height: (node) => wrappedNodeHeight(node, 82, 180, 20), "text-max-width": () => scaled(180), "font-size": () => scaled(20) } },
      { selector: 'node[type = "evidence"]', style: { width: () => scaled(224), height: (node) => wrappedNodeHeight(node, 80, 194, 18), "text-max-width": () => scaled(194), "font-size": () => scaled(18) } },
      { selector: 'node[type = "experiment"]', style: { width: () => scaled(224), height: (node) => wrappedNodeHeight(node, 82, 194, 19), "text-max-width": () => scaled(194), "font-size": () => scaled(19) } },
      { selector: 'node[type = "knowledge"][subtype = "question"]', style: { "background-color": "#fff3b0", "border-color": "#c69120", "border-style": "dashed" } },
      { selector: 'node[type = "knowledge"][subtype = "challenge"]', style: { "background-color": "#f8d7d2", "border-color": "#d04a3a", "border-width": 2 } },
      { selector: 'node[type = "knowledge"][subtype = "answer"]', style: { "background-color": "#d8f3c0", "border-color": "#0f6b50" } },
      { selector: 'node[type = "knowledge"][subtype = "note"]', style: { "background-color": "#e9e6de", "border-color": "#657270" } },
      { selector: 'node[orphan]', style: { "border-color": "#d78334", "border-style": "dashed", "border-width": 4 } },
      {
        selector: "edge",
        style: {
          width: 1.25,
          "line-color": "rgba(23,32,32,.23)",
          "target-arrow-color": "rgba(23,32,32,.3)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "arrow-scale": 0.7,
          opacity: 0.56,
          "transition-property": "opacity, line-color, width",
          "transition-duration": "180ms",
        },
      },
      { selector: 'edge[relation = "supports"], edge[relation = "provides"], edge[relation = "answers"]', style: { "line-color": "#0f6b50", "target-arrow-color": "#0f6b50", width: 2 } },
      { selector: 'edge[relation = "contradicts"], edge[relation = "challenges"], edge[relation = "corrects"]', style: { "line-color": "#d04a3a", "target-arrow-color": "#d04a3a", width: 2 } },
      { selector: 'edge[relation = "about"], edge[relation = "evaluates"], edge[relation = "questions"]', style: { "line-style": "dashed" } },
      { selector: 'edge[relation = "classified_as"]', style: { "line-style": "dotted", "line-color": "#7458a8", "target-arrow-color": "#7458a8", opacity: 0.62 } },
      { selector: 'edge[relation = "documented_by"]', style: { "line-color": "#d78334", "target-arrow-color": "#d78334" } },
      { selector: 'edge[relation = "contains"]', style: { "line-color": "#0f6b50", "target-arrow-color": "#0f6b50", width: 2.4 } },
      { selector: 'edge[relation = "discusses"], edge[relation = "covers"]', style: { "line-style": "dashed", "line-color": "#657270", "target-arrow-color": "#657270" } },
      { selector: ":selected", style: { "border-width": 5, "border-color": "#172020" } },
      { selector: ".hover-pending", style: { "border-width": 5, "border-color": "#d78334" } },
      { selector: ".dimmed", style: { opacity: 0.1 } },
      { selector: ".focused-neighbor", style: { opacity: 1, "border-width": 2.5 } },
      { selector: ".search-match", style: { "border-width": 5, "border-color": "#d78334" } },
      { selector: ".filtered, .search-hidden", style: { display: "none" } },
    ],
    layout: {
      name: "cose",
      fit: false,
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
  canvas.agentRadarGraph = cy;

  function applyResponsiveVisualScale() {
    const nextScale = readGraphVisualScale();
    cy.resize();
    if (Math.abs(nextScale - graphVisualScale) < 0.04) return;
    graphVisualScale = nextScale;
    canvas.dataset.visualScale = graphVisualScale.toFixed(2);
    cy.elements().updateStyle();
    runLayout(document.querySelector("[data-layout].active")?.dataset.layout || "organic", false);
  }

  function layoutOptions(name, animate = true) {
    if (name === "hierarchy") {
      return { name: "breadthfirst", directed: true, fit: false, padding: 70, spacingFactor: 1.35, animate, animationDuration: 450 };
    }
    if (name === "rings") {
      return {
        name: "concentric",
        fit: false,
        padding: 72,
        minNodeSpacing: 44,
        animate,
        animationDuration: 450,
        concentric: (node) => ({ document: 9, section: 8, technology: 7, candidate: 6, discovery_category: 5, capability: 4, claim: 3, knowledge: 2, evidence: 1, experiment: 1 }[node.data("type")] || 1),
        levelWidth: () => 1,
      };
    }
    return {
      name: "cose",
      fit: false,
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

  function balanceOrganicLayout(nodes) {
    if (nodes.length < 3) return;
    const bounds = nodes.boundingBox({ includeLabels: true });
    const canvasBounds = canvas.getBoundingClientRect();
    if (!bounds.w || !bounds.h || !canvasBounds.width || !canvasBounds.height) return;
    const graphAspect = bounds.w / bounds.h;
    const targetAspect = clamp((canvasBounds.width / canvasBounds.height) * 0.82, 0.72, 1.42);
    const stretch = clamp(Math.sqrt(targetAspect / graphAspect), 0.78, 1.32);
    if (Math.abs(stretch - 1) < 0.04) return;
    const centerX = bounds.x1 + bounds.w / 2;
    const centerY = bounds.y1 + bounds.h / 2;
    nodes.positions((node) => {
      const position = node.position();
      return {
        x: centerX + (position.x - centerX) * stretch,
        y: centerY + (position.y - centerY) / stretch,
      };
    });
  }

  function fitGraphForReading(elements, keepMinimumLabelSize = true) {
    const canvasWidth = canvas.getBoundingClientRect().width;
    cy.fit(elements, clamp(scaled(46), 38, 76));
    if (!keepMinimumLabelSize || canvasWidth < 900) return;
    const targetLabelPixels = clamp(11.5 + (canvasWidth - 900) / 800, 11.5, 14.5);
    const minimumZoom = targetLabelPixels / scaled(22);
    if (cy.zoom() < minimumZoom) {
      cy.zoom(minimumZoom);
      cy.center(elements);
    }
  }

  function runLayout(name, animate = true) {
    cy.elements().removeClass("dimmed focused-neighbor");
    const visibleElements = cy.elements(":visible");
    if (visibleElements.nodes().length) {
      cy.one("layoutstop", () => {
        if (name === "organic") balanceOrganicLayout(visibleElements.nodes());
        fitGraphForReading(visibleElements);
      });
      visibleElements.layout(layoutOptions(name, animate)).run();
    }
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
      map_id: mapId,
    });
    if (data.type === "knowledge") params.set("parent_id", data.id);
    return `/nodes/new?${params.toString()}`;
  }

  function closeDocumentPreview() {
    previewRequestId += 1;
    if (documentPreview) documentPreview.hidden = true;
    inspector.classList.remove("previewing-document");
  }

  function documentIdFor(data) {
    if (data.type === "document") return data.id;
    if (data.type === "section") return data.document_id;
    return null;
  }

  function scrollPreviewTo(sectionAnchor, sectionTitle) {
    if (!previewScroll || !previewContent) return;
    previewContent.querySelectorAll(".preview-target-section").forEach((item) => item.classList.remove("preview-target-section"));
    const target = sectionAnchor ? previewContent.querySelector(`#${sectionAnchor}`) : null;
    if (target) {
      target.classList.add("preview-target-section");
      previewScroll.scrollTo({ top: Math.max(0, target.offsetTop - 18), behavior: "smooth" });
      if (previewStatus) previewStatus.textContent = `已定位：${sectionTitle || "所选章节"} · 滚轮上下阅读`;
    } else {
      previewScroll.scrollTo({ top: 0, behavior: "smooth" });
      if (previewStatus) previewStatus.textContent = "完整文档 · 滚轮上下阅读";
    }
  }

  function loadDocumentPreview(documentId) {
    if (!documentPreviewCache.has(documentId)) {
      const request = fetch(`/api/documents/${encodeURIComponent(documentId)}/preview`)
        .then((response) => {
          if (!response.ok) throw new Error("文档预览加载失败");
          return response.json();
        })
        .catch((error) => {
          documentPreviewCache.delete(documentId);
          throw error;
        });
      documentPreviewCache.set(documentId, request);
    }
    return documentPreviewCache.get(documentId);
  }

  async function openDocumentPreview(data) {
    const documentId = documentIdFor(data);
    if (!documentId || !documentPreview || !previewContent || !previewScroll) return;
    const requestId = ++previewRequestId;
    const sectionAnchor = data.type === "section" ? data.section_anchor : null;
    documentPreview.hidden = false;
    inspector.classList.add("previewing-document");
    if (previewKind) previewKind.textContent = data.type === "section" ? "文档章节 · 自动定位" : "完整研究文档";
    if (previewTitle) previewTitle.textContent = data.label;
    if (previewDescription) previewDescription.textContent = data.description || "打开侧边阅读器查看完整上下文。";
    if (previewOpen) previewOpen.href = data.href || `/documents/${encodeURIComponent(documentId)}`;
    if (previewResearch) previewResearch.href = data.research_href || `/documents/${encodeURIComponent(documentId)}/research`;

    if (documentPreview.dataset.documentId === documentId && previewContent.childElementCount) {
      scrollPreviewTo(sectionAnchor, data.label);
      return;
    }

    documentPreview.dataset.documentId = documentId;
    if (previewStatus) previewStatus.textContent = "正在加载完整文档…";
    if (previewLoading) previewLoading.hidden = false;
    previewContent.hidden = true;
    try {
      const payload = await loadDocumentPreview(documentId);
      if (requestId !== previewRequestId) return;
      previewContent.innerHTML = payload.html;
      previewContent.querySelectorAll('a[href^="http"]').forEach((link) => {
        link.target = "_blank";
        link.rel = "noreferrer";
      });
      if (window.AgentRadarDiagrams) await window.AgentRadarDiagrams.render(previewContent);
      if (previewLoading) previewLoading.hidden = true;
      previewContent.hidden = false;
      requestAnimationFrame(() => scrollPreviewTo(sectionAnchor, data.label));
    } catch (error) {
      if (requestId !== previewRequestId) return;
      if (previewLoading) {
        previewLoading.hidden = false;
        previewLoading.replaceChildren(
          element("strong", "", "文档预览暂时无法加载"),
          element("span", "", "你仍可以使用上方的独立阅读页。"),
        );
      }
    }
  }

  function resetInspector() {
    inspector.replaceChildren(
      element("span", "", "悬停约 0.45 秒"),
      element("h2", "", "从文档目录开始"),
      element("p", "", "稍作停留即可看摘要；文档与章节会自动打开左侧阅读器。"),
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
          `${sourceKindLabels[data.source_kind] || "认知片段"} · ${verificationLabels[data.verification_status] || "待查证"}`,
        ),
      );
    }
    if (data.orphan) {
      const orphanNotice = element("div", "inspector-orphan-notice");
      orphanNotice.append(
        element("strong", "", "待归类节点"),
        element("p", "", "当前专题中还没有已登记的关系。请补充关联对象，或确认它确实是一个独立入口。"),
      );
      children.push(orphanNotice);
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
    if (data.type === "document" || data.type === "section") {
      actions.append(
        actionLink("阅读完整文档", data.href, "action-document"),
        actionLink("在 Codex 中继续研究", data.research_href, "action-codex"),
      );
    } else {
      actions.append(
        actionLink("在 Codex 中继续研究", `/research/${encodeURIComponent(data.id)}?map_id=${encodeURIComponent(mapId)}`, "action-codex"),
        actionLink("记录认知片段", knowledgeActionHref(data, "note", "extends"), "action-note"),
      );
    }
    children.push(actions);
    if (data.href && data.type !== "document" && data.type !== "section") {
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
    const data = node.data();
    if (data.type === "document" || data.type === "section") openDocumentPreview(data);
    else closeDocumentPreview();
  }

  function resetFocus() {
    cy.elements().removeClass("dimmed focused-neighbor");
    cy.$(":selected").unselect();
    closeDocumentPreview();
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

  function cancelHoverPreview() {
    if (hoverTimer) window.clearTimeout(hoverTimer);
    hoverTimer = null;
    if (hoverPendingNode) hoverPendingNode.removeClass("hover-pending");
    hoverPendingNode = null;
  }

  cy.on("mouseover", "node", (event) => {
    cancelHoverPreview();
    hoverPendingNode = event.target;
    hoverPendingNode.addClass("hover-pending");
    hoverTimer = window.setTimeout(() => {
      const target = hoverPendingNode;
      cancelHoverPreview();
      if (target && target.length) focusNode(target);
    }, HOVER_DELAY_MS);
  });
  cy.on("mouseout", "node", cancelHoverPreview);
  cy.on("tap", "node", (event) => {
    cancelHoverPreview();
    focusNode(event.target);
  });
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
  document.getElementById("graph-fit")?.addEventListener("click", () => { resetFocus(); fitGraphForReading(cy.elements(":visible")); });
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
    fitGraphForReading(cy.elements(":visible"));
  });
  mapSelect?.addEventListener("change", () => {
    const params = new URLSearchParams({ map_id: mapSelect.value });
    window.location.href = `/graph?${params.toString()}`;
  });
  previewClose?.addEventListener("click", closeDocumentPreview);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && documentPreview && !documentPreview.hidden) closeDocumentPreview();
  });

  runLayout("organic", false);

  if (typeof ResizeObserver !== "undefined") {
    let resizeTimer = null;
    const graphResizeObserver = new ResizeObserver(() => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(applyResponsiveVisualScale, 160);
    });
    graphResizeObserver.observe(canvas);
  }

  const focusId = new URLSearchParams(window.location.search).get("focus");
  if (focusId) {
    const target = cy.getElementById(focusId);
    if (target.length) setTimeout(() => focusNode(target, true), 80);
  }
})();
