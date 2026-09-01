/**
 * galaxy.js — 2D visualization of the vschk workspace (Habr-Obsidian style).
 *
 * Block 8 rewrite: swapped ForceGraph3D → ForceGraph (2D canvas),
 * micro dot nodes, hard charge repulsion, ALL edges visible as fine mesh,
 * violet hover highlight with harsh dim contrast, no intro animation,
 * no pulse — Obsidian-graph aesthetic.
 */

(function () {
  'use strict';

  // ── State ────────────────────────────────────────────────────────
  let Graph = null;
  let currentLevel = 1;
  let currentData = null;
  let enabledProjects = new Set();
  let searchQuery = '';
  let hoveredNode = null;
  let selectedNode = null;   // Block 8 round 2: persistent selection via click
  let highlightNodes = new Set();
  let highlightLinks = new Set();

  const GRAPH_EL = document.getElementById('graph');
  const LOADING_EL = document.getElementById('loading');
  const META_EL = document.getElementById('meta');
  const SP_EL = document.getElementById('sidepanel');
  const SP_TITLE = document.getElementById('sp-title');
  const SP_BODY = document.getElementById('sp-body');
  const SP_CLOSE = document.getElementById('sp-close');
  const FILTER_LIST = document.getElementById('filter-list');
  const SEARCH_INPUT = document.getElementById('search-input');
  const BTN_RESET = document.getElementById('btn-reset');
  const BTN_LEVEL = document.getElementById('btn-level');

  // ── Utilities ────────────────────────────────────────────────────

  function updateMeta(meta) {
    if (!META_EL) return;
    META_EL.textContent =
      `${meta.node_count} nodes · ${meta.edge_count} edges · ${meta.project_count} projects · L${meta.level}`;
  }

  function showLoading(text) {
    if (!LOADING_EL) return;
    LOADING_EL.textContent = text;
    LOADING_EL.style.display = 'block';
    LOADING_EL.classList.remove('error');
  }

  function hideLoading() {
    if (LOADING_EL) LOADING_EL.style.display = 'none';
  }

  function failLoading(err) {
    if (!LOADING_EL) return;
    LOADING_EL.textContent = 'failed to load galaxy — ' + (err.message || err);
    LOADING_EL.classList.add('error');
    LOADING_EL.style.display = 'block';
    console.error('[galaxy]', err);
  }

  function debounce(fn, ms) {
    let t;
    return function () {
      clearTimeout(t);
      const args = arguments;
      t = setTimeout(() => fn.apply(null, args), ms);
    };
  }

  // ── Filter UI ────────────────────────────────────────────────────

  function renderFilters(projects) {
    FILTER_LIST.innerHTML = '';
    projects.forEach(p => {
      enabledProjects.add(p.id);
      const label = document.createElement('label');
      label.innerHTML =
        `<input type="checkbox" checked data-project="${p.id}">` +
        `<span class="swatch" style="background:${p.color}"></span>` +
        `<span>${p.name}</span>`;
      const cb = label.querySelector('input');
      cb.addEventListener('change', () => {
        if (cb.checked) enabledProjects.add(p.id);
        else enabledProjects.delete(p.id);
        refreshVisibility();
      });
      FILTER_LIST.appendChild(label);
    });
  }

  // ── Visibility + search ─────────────────────────────────────────

  function nodeVisible(node) {
    if (node.project && !enabledProjects.has(node.project)) return false;
    if (searchQuery) {
      const label = (node.label || '').toLowerCase();
      if (!label.includes(searchQuery)) return false;
    }
    return true;
  }

  function refreshVisibility() {
    if (!Graph) return;
    Graph.nodeVisibility(nodeVisible);
  }

  // ── Node sizing (micro, Obsidian-style) ─────────────────────────

  function nodeSize(n) {
    if (n.type === 'project') return 6;
    if (n.type === 'task' || n.type === 'fast-track' || n.type === 'epic') return 3;
    return 1.5;
  }

  // ── Custom canvas render: dot + conditional label (round 3) ──────

  function nodeCanvasObject(node, ctx, globalScale) {
    const r = nodeSize(node);
    ctx.fillStyle = nodeColor(node);
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fill();
    // Labels visible only on zoom-in and only for project/task (skip 19K artifacts noise)
    if (globalScale > 2 && node.label && !node.id.startsWith('artifact:')) {
      const fontSize = Math.max(6, 10 / globalScale);
      ctx.font = `${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = 'rgba(237,244,250,0.75)';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, node.x + r + 2, node.y);
    }
  }

  // Larger invisible hit region for easier hover (round 3)
  function nodePointerAreaPaint(node, color, ctx) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeSize(node) + 3, 0, 2 * Math.PI);
    ctx.fill();
  }

  // ── Node color with hover dim ───────────────────────────────────

  function nodeColor(n) {
    const active = selectedNode || hoveredNode;
    if (!active) return n.color;
    if (highlightNodes.has(n.id)) return n.color;
    return 'rgba(255,255,255,0.02)';  // harsh dim per Habr reference
  }

  // ── Link color: parent thin white, arch_ref saffron, hover violet ──

  function linkColor(l) {
    const active = selectedNode || hoveredNode;
    if (active) {
      if (highlightLinks.has(l)) return '#8b5cf6';       // violet for connected
      return 'rgba(255,255,255,0.015)';                   // near-invisible for rest
    }
    if (l.edge_type === 'arch_ref') return 'rgba(244,163,0,0.5)';
    return 'rgba(255,255,255,0.06)';
  }

  function linkWidth(l) {
    const active = selectedNode || hoveredNode;
    if (active && highlightLinks.has(l)) return 2;
    if (l.edge_type === 'arch_ref') return 0.6;
    return 0.3;
  }

  // ── Hover: highlight connected ──────────────────────────────────

  function updateHighlight() {
    highlightNodes.clear();
    highlightLinks.clear();
    const active = selectedNode || hoveredNode;
    if (active && currentData) {
      highlightNodes.add(active.id);
      currentData.edges.forEach(e => {
        const src = typeof e.source === 'object' ? e.source.id : e.source;
        const tgt = typeof e.target === 'object' ? e.target.id : e.target;
        if (src === active.id || tgt === active.id) {
          highlightLinks.add(e);
          if (src === active.id) highlightNodes.add(tgt);
          else highlightNodes.add(src);
        }
      });
    }
  }

  // ── Click: side-panel ────────────────────────────────────────────

  function openSidepanel(node) {
    SP_TITLE.textContent = node.label || node.id;
    const rows = [
      ['type', node.type || '—'],
      ['project', node.project || '—'],
      ['level', String(node.level)],
    ];
    Object.keys(node.meta || {}).forEach(k => {
      if (node.meta[k] != null && node.meta[k] !== '') {
        rows.push([k, String(node.meta[k])]);
      }
    });
    SP_BODY.innerHTML = rows.map(([k,v]) =>
      `<div class="meta-row"><span class="k">${k}</span><span class="v">${v}</span></div>`
    ).join('');

    if (node.id && node.id.startsWith('task:')) {
      const taskId = node.id.slice(5);
      const projectId = node.project || '';
      const link = document.createElement('a');
      link.className = 'deep';
      link.href = `/#/${projectId}?task=${encodeURIComponent(taskId)}`;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Open in Flow →';
      SP_BODY.appendChild(link);
    }

    SP_EL.classList.add('open');
  }

  function closeSidepanel() {
    SP_EL.classList.remove('open');
    selectedNode = null;
    updateHighlight();
  }
  SP_CLOSE.addEventListener('click', closeSidepanel);

  // ESC clears selection (bonus)
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && selectedNode) closeSidepanel();
  });

  // ── Controls ────────────────────────────────────────────────────

  BTN_RESET.addEventListener('click', () => {
    if (Graph) Graph.zoomToFit(500, 40);
  });

  function switchLevel(newLevel) {
    if (newLevel === currentLevel) return;
    currentLevel = newLevel;
    BTN_LEVEL.textContent = 'Level ' + newLevel;
    BTN_LEVEL.classList.toggle('active', newLevel === 2);
    loadAndRender();
  }
  BTN_LEVEL.addEventListener('click', () => switchLevel(currentLevel === 1 ? 2 : 1));

  const runSearch = debounce(() => {
    searchQuery = (SEARCH_INPUT.value || '').trim().toLowerCase();
    refreshVisibility();
  }, 200);
  SEARCH_INPUT.addEventListener('input', runSearch);

  // ── Main render ─────────────────────────────────────────────────

  function render(graph) {
    hideLoading();
    currentData = graph;
    updateMeta(graph.meta);

    if (FILTER_LIST.children.length === 0) {
      renderFilters(graph.meta.projects || []);
    }

    // Round 3: pre-compute anchor positions for each project on a circle
    // Each project gets a fixed (x,y) → cluster force pulls tasks there
    const projectList = graph.meta.projects || [];
    const projectAnchors = {};
    const anchorRadius = 700;   // round 4: wider circle → visible gaps between clusters
    projectList.forEach((p, i) => {
      const angle = (i / Math.max(1, projectList.length)) * Math.PI * 2;
      projectAnchors[p.id] = {
        x: Math.cos(angle) * anchorRadius,
        y: Math.sin(angle) * anchorRadius,
      };
    });
    window.__galaxyAnchors = projectAnchors;

    const nodeCount = graph.nodes.length;
    const isLargeGraph = nodeCount > 5000;
    const chargeStrength = isLargeGraph ? -100 : -50;
    const linkDistance = isLargeGraph ? 30 : 50;
    const linkStrength = 1.5;
    const clusterStrength = 0.35;   // round 4: stronger pull to anchor (was 0.18)
    const cooldownTicks = isLargeGraph ? 5000 : 1500;

    if (Graph) {
      Graph.graphData({
        nodes: graph.nodes,
        links: graph.edges.map(e => ({ ...e })),
      });
      if (typeof Graph.d3Force === 'function') {
        const ch = Graph.d3Force('charge');
        if (ch && ch.strength) ch.strength(chargeStrength);
        const lk = Graph.d3Force('link');
        if (lk && lk.distance) lk.distance(linkDistance);
        if (lk && lk.strength) lk.strength(linkStrength);
      }
      Graph.cooldownTicks(cooldownTicks);
      refreshVisibility();
      return;
    }

    let tickCount = 0;
    Graph = ForceGraph()(GRAPH_EL)
      .backgroundColor('#04070d')
      .graphData({
        nodes: graph.nodes,
        links: graph.edges.map(e => ({ ...e })),
      })
      .nodeId('id')
      .nodeLabel(n => n.label)
      .nodeCanvasObject(nodeCanvasObject)     // round 3: custom render + labels
      .nodePointerAreaPaint(nodePointerAreaPaint)
      .nodeVisibility(nodeVisible)
      .linkColor(linkColor)
      .linkWidth(linkWidth)
      .linkDirectionalParticles(0)
      .enableNodeDrag(false)
      .warmupTicks(200)
      .cooldownTicks(cooldownTicks)
      .d3AlphaDecay(0.008)
      .d3VelocityDecay(0.4)
      .onNodeHover(node => {
        hoveredNode = node || null;
        GRAPH_EL.style.cursor = node ? 'pointer' : null;
        updateHighlight();
      })
      .onNodeClick(node => {
        selectedNode = node;
        updateHighlight();
        openSidepanel(node);
        Graph.centerAt(node.x, node.y, 700).zoom(4, 700);
      })
      .onBackgroundClick(closeSidepanel)
      // round 3: fit early + finalize on settle (no black screen)
      .onEngineTick(() => {
        tickCount++;
        if (tickCount === 5 || tickCount === 30 || tickCount === 100) {
          Graph.zoomToFit(0, 60);
        }
      })
      .onEngineStop(() => { if (Graph) Graph.zoomToFit(500, 60); });

    // Force tuning: weaker charge, stronger link, + per-project cluster anchors
    if (typeof Graph.d3Force === 'function') {
      // Round 4: kill center force → cluster force wins (was competing pull to 0,0)
      Graph.d3Force('center', null);

      const ch = Graph.d3Force('charge');
      if (ch && ch.strength) ch.strength(chargeStrength);
      const lk = Graph.d3Force('link');
      if (lk && lk.distance) lk.distance(linkDistance);
      if (lk && lk.strength) lk.strength(linkStrength);

      // Round 3: cluster force — pull each node to its project anchor
      const d3f = window.d3 || (Graph.d3Force('center') && Graph.d3Force('center').__proto__ && Graph.d3Force('center').__proto__.constructor);
      // force-graph bundles d3-force; access via Graph.d3Force fallback: build closure forces
      const clusterX = alpha => {
        graph.nodes.forEach(n => {
          const anchor = projectAnchors[n.project];
          if (anchor && typeof n.vx === 'number') {
            n.vx += (anchor.x - n.x) * clusterStrength * alpha;
          }
        });
      };
      const clusterY = alpha => {
        graph.nodes.forEach(n => {
          const anchor = projectAnchors[n.project];
          if (anchor && typeof n.vy === 'number') {
            n.vy += (anchor.y - n.y) * clusterStrength * alpha;
          }
        });
      };
      Graph.d3Force('cluster-x', clusterX);
      Graph.d3Force('cluster-y', clusterY);
    }

    window.__galaxyGraph = Graph;
    window.__galaxyMeta = graph.meta;
  }

  function loadAndRender() {
    showLoading('loading galaxy…');
    fetch(`/api/galaxy/graph.json?level=${currentLevel}`, { credentials: 'same-origin' })
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(render)
      .catch(failLoading);
  }

  loadAndRender();
})();
