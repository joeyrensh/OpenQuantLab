// assets/window_events.js
(function () {
    const monthLabel = /^\d{4}-\d{2}$/;
    let annualScanQueued = false;

    function restoreBaseTransform(node, key) {
        const current = node.getAttribute("transform") || "";
        if (current !== node.dataset[`${key}Applied`]) {
            node.dataset[`${key}Base`] = current;
        }
        const base = node.dataset[`${key}Base`] ?? current;
        if (base) node.setAttribute("transform", base);
        else node.removeAttribute("transform");
        return base;
    }

    function alignAnnualReturn(metrics, graph) {
        if (!metrics.isConnected || !graph.isConnected) return;

        const svg = graph.querySelector(".main-svg");
        const viewBox = svg && svg.viewBox && svg.viewBox.baseVal;
        const svgRect = svg && svg.getBoundingClientRect();
        const svgHeight = viewBox?.height || Number.parseFloat(svg?.getAttribute("height"));
        if (!svg || !svgHeight || !svgRect.height) return;

        const labels = Array.from(graph.querySelectorAll(".main-svg text"))
            .filter((node) => monthLabel.test((node.textContent || "").trim()));
        const groups = labels.map((label) => label.closest("g.cursor-pointer"));
        if (!groups.length || groups.some((group) => !group)) return;

        const plotLayers = [".bglayer", ".cartesianlayer", ".layer-below", ".draglayer"]
            .map((selector) => svg.querySelector(selector))
            .filter(Boolean);
        const baseLayerTransforms = plotLayers.map((layer) => restoreBaseTransform(layer, "annualReturnPlot"));

        const metricsTop = metrics.getBoundingClientRect().top;
        const scaleY = svgRect.height / svgHeight;
        const labelBaseTransforms = groups.map((group) => restoreBaseTransform(group, "annualReturnLabel"));
        const labelRects = labels.map((label) => label.getBoundingClientRect());
        const gap = metricsTop - Math.max(...labelRects.map((rect) => rect.bottom));
        const labelShift = gap / scaleY;
        const labelTargetTop = Math.min(...labelRects.map((rect) => rect.top)) + gap;

        const plotRects = Array.from(svg.querySelectorAll(".bglayer rect.bg"));
        if (plotRects.length && plotLayers.length) {
            const plotTop = Math.min(...plotRects.map((rect) => Number(rect.getAttribute("y") || 0)));
            const plotBottom = Math.max(...plotRects.map((rect) =>
                Number(rect.getAttribute("y") || 0) + Number(rect.getAttribute("height") || 0)
            ));
            const targetBottom = (labelTargetTop - svgRect.top) / scaleY;
            const plotScale = (targetBottom - plotTop) / (plotBottom - plotTop);
            if (Number.isFinite(plotScale) && plotScale > 0) {
                const translateY = plotTop * (1 - plotScale);
                const matrix = `matrix(1 0 0 ${plotScale} 0 ${translateY})`;
                plotLayers.forEach((layer, index) => {
                    const base = baseLayerTransforms[index];
                    const next = base ? `${base} ${matrix}` : matrix;
                    layer.setAttribute("transform", next);
                    layer.dataset.annualReturnPlotApplied = next;
                });
            }
        }

        groups.forEach((group, index) => {
            const match = labelBaseTransforms[index].match(/translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)/);
            if (!match) return;

            const next = `translate(${match[1]},${Number(match[2]) + labelShift})`;
            group.setAttribute("transform", next);
            group.dataset.annualReturnLabelApplied = next;
        });
    }

    function scheduleAnnualReturnScan() {
        if (annualScanQueued) return;
        annualScanQueued = true;
        requestAnimationFrame(() => {
            annualScanQueued = false;
            document.querySelectorAll(".annual-return-metrics").forEach((metrics) => {
                const graph = metrics.parentElement &&
                    metrics.parentElement.querySelector(".chart-container .js-plotly-plot");
                if (!graph) return;

                if (!graph.__annualReturnAlignBound) {
                    graph.__annualReturnAlignBound = true;
                    if (typeof graph.on === "function") {
                        graph.on("plotly_afterplot", () => alignAnnualReturn(metrics, graph));
                    }
                    if (window.ResizeObserver) {
                        graph.__annualReturnResizeObserver = new ResizeObserver(() => alignAnnualReturn(metrics, graph));
                        graph.__annualReturnResizeObserver.observe(graph);
                        graph.__annualReturnResizeObserver.observe(metrics);
                    }
                }
                alignAnnualReturn(metrics, graph);
            });
        });
    }

    function dispatchClientEvent() {
        const store = document.getElementById("client-event");
        if (store) {
            store.click();
        }
    }

    function dispatchAfterLayout() {
        // 延迟一帧，等 viewport 真正更新
        requestAnimationFrame(() => {
            requestAnimationFrame(dispatchClientEvent);
        });
    }

    // 初始
    window.addEventListener("load", dispatchClientEvent);
    window.addEventListener("load", scheduleAnnualReturnScan);

    // resize（桌面 & 安卓 OK）
    window.addEventListener("resize", dispatchAfterLayout);
    window.addEventListener("resize", scheduleAnnualReturnScan);

    // iOS 专用：屏幕旋转
    window.addEventListener("orientationchange", dispatchAfterLayout);
    window.addEventListener("orientationchange", scheduleAnnualReturnScan);

    // 更可靠的 viewport 监听（iOS 13+）
    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", dispatchAfterLayout);
        window.visualViewport.addEventListener("resize", scheduleAnnualReturnScan);
    }

    // 主题切换
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    mql.addEventListener("change", dispatchClientEvent);

    if (window.MutationObserver && document.body) {
        new MutationObserver(scheduleAnnualReturnScan).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }
})();
