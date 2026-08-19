(function () {
  const mermaidApi = window.mermaid;
  let diagramSequence = 0;

  if (!mermaidApi) return;

  mermaidApi.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "base",
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
    flowchart: {
      htmlLabels: true,
      useMaxWidth: true,
      curve: "basis",
      nodeSpacing: 42,
      rankSpacing: 58,
    },
    themeVariables: {
      background: "#ffffff",
      primaryColor: "#eef8d8",
      primaryTextColor: "#172020",
      primaryBorderColor: "#0f6b50",
      secondaryColor: "#e9f4ff",
      tertiaryColor: "#fff0c8",
      lineColor: "#4f6961",
      edgeLabelBackground: "#f8f7f2",
      fontSize: "16px",
    },
  });

  async function renderDiagram(figure) {
    if (figure.dataset.mermaidState) return;
    const source = figure.querySelector("code")?.textContent?.trim();
    const canvas = figure.querySelector("[data-mermaid-canvas]");
    if (!source || !canvas) return;
    figure.dataset.mermaidState = "rendering";
    canvas.setAttribute("aria-busy", "true");
    try {
      diagramSequence += 1;
      const diagramId = `agent-radar-mermaid-${Date.now()}-${diagramSequence}`;
      const { svg, bindFunctions } = await mermaidApi.render(diagramId, source);
      canvas.innerHTML = svg;
      bindFunctions?.(canvas);
      figure.dataset.mermaidState = "rendered";
      canvas.removeAttribute("aria-busy");
    } catch (error) {
      figure.dataset.mermaidState = "error";
      canvas.removeAttribute("aria-busy");
      canvas.replaceChildren();
      const message = document.createElement("div");
      message.className = "document-diagram-error";
      message.textContent = "流程图渲染失败，已保留下方源码供检查。";
      canvas.append(message);
      const sourcePanel = figure.querySelector("details");
      if (sourcePanel) sourcePanel.open = true;
    }
  }

  async function render(root = document) {
    const diagrams = Array.from(root.querySelectorAll("[data-mermaid-diagram]"));
    await Promise.all(diagrams.map(renderDiagram));
  }

  window.AgentRadarDiagrams = { render };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => render(document));
  } else {
    render(document);
  }
})();
