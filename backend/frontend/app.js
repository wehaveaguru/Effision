/**
 * Effision PIM — Application Logic
 * Integrates with FastAPI / Supabase backend + pgvector semantic search
 */

// Fallback seed catalog in case backend is loading
const FALLBACK_PRODUCTS = [
  {
    id: 3,
    content: "Diablo DCB518ASTS06G 1/2\" x 18\" Sanding Belt - 6 pcs\nBrand: Diablo\nHigh‑performance Diablo sanding belt from Freud, 1/2\" width and 18\" length...",
    metadata: {
      title: "Diablo DCB518ASTS06G 1/2\" x 18\" Sanding Belt (6-Pack)",
      brand: "Diablo",
      category_hierarchy: ["Abrasives", "Sanding Belts", "Industrial"],
      summary: "High-performance Diablo sanding belt for aggressive stock removal on wood, metal, and composites.",
      enriched_description: "The DCB518ASTS06G Diablo sanding belt is designed for heavy-duty material removal in fabrication and woodworking. Featuring premium aluminum zirconia grain and a heavy-duty cloth backing, it delivers maximum life and consistent surface finish under high heat.",
      key_features: ["1/2\" Width x 18\" Length", "6 Belts per pack", "Clog-resistant abrasive blend", "Compatible with standard handheld belt sanders"],
      technical_specifications: { "Part Number": "DCB518ASTS06G", "Dimensions": "1/2 in x 18 in", "Quantity": "6 Belts", "Backing": "Heavy Fabric", "Abrasive": "Zirconia Alumina" },
      attributes: { "part_number": "DCB518ASTS06G", "manufacturer": "Freud Inc", "material": "Zirconia Alumina", "application": "Metal, Wood, Composites" },
      search_keywords: ["diablo", "sanding belt", "freud", "1/2x18", "abrasive"]
    }
  },
  {
    id: 4,
    content: "3M Cubitron II 775L Stikit Film P150 Grinding Disc - 50 pcs\nBrand: 3M\n3M Precision Shaped Grain technology...",
    metadata: {
      title: "3M Cubitron II 775L Stikit Film Disc P150 (50 Discs/Box)",
      brand: "3M",
      category_hierarchy: ["Abrasives", "Film Discs", "Precision Grinding"],
      summary: "Revolutionary 3M Precision-Shaped Grain cuts 2x faster and lasts up to 6x longer than conventional ceramic abrasives.",
      enriched_description: "3M Cubitron II Stikit Film Disc 775L features triangular shaped ceramic grains that continually fracture into sharp points. Ideal for stainless steel, cobalt alloys, and aerospace finishes requiring minimal heat discoloration.",
      key_features: ["P150 Fine Grit Finish", "Stikit Adhesive Backing", "50 Discs per box", "Precision-Shaped Ceramic Grain"],
      technical_specifications: { "Part Number": "3MABR-7100075678", "Grit": "P150", "Disc Diameter": "5 in", "Attachment": "Stikit (PSA)", "Quantity": "50 Discs" },
      attributes: { "part_number": "3MABR-7100075678", "manufacturer": "3M", "material": "Precision Ceramic Grain", "application": "Stainless Steel, Titanium" },
      search_keywords: ["3M", "cubitron II", "stikit", "P150", "grinding disc"]
    }
  },
  {
    id: 12,
    content: "Abranet 2.75x30 (9A-570-240)\nBrand: Mirka\nMirka Abranet net sanding roll for dust-free sanding...",
    metadata: {
      title: "Mirka Abranet 2.75\" x 30ft Net Sanding Roll P240",
      brand: "Mirka",
      category_hierarchy: ["Abrasives", "Net Sanding", "Dust-Free"],
      summary: "Original net sanding abrasive providing virtually dust-free sanding and superior surface uniformness.",
      enriched_description: "The open mesh construction of Mirka Abranet allows dust to be drawn directly through the abrasive surface, preventing clogging and pilling. Essential for automotive refinishing, composite manufacturing, and cleanroom environments.",
      key_features: ["Dust-Free Net Mesh Technology", "2.75\" x 30 ft Continuous Roll", "P240 Ultra-Fine Finishing", "Resists High Heat & Clogging"],
      technical_specifications: { "Part Number": "9A-570-240", "Width": "2.75 in", "Length": "30 ft", "Grit": "P240", "Backing": "Polyamide Fabric" },
      attributes: { "part_number": "9A-570-240", "manufacturer": "Mirka Abrasives", "material": "Aluminum Oxide on Net", "application": "Automotive, Composites" },
      search_keywords: ["mirka", "abranet", "net mesh", "dust free", "P240"]
    }
  }
];

let allProducts = [];
let currentFilterBrand = "";
let currentSearchQuery = "";
let activeViewMode = "grid";

// API Base URL (Relative for seamless reverse proxy / static mount)
const API_BASE = "";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initSearch();
  initCommandPalette();
  initDrawer();
  initProductForm();
  initBulkUpload();
  initGraphCanvas();
  initAnalytics();
  fetchCatalogData();
  fetchStats();
  fetchReviewQueue();
});

/* ==========================================================================
   Navigation & Tabs
   ========================================================================== */
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const targetViewId = `view-${tab.dataset.tab}`;
      document.querySelectorAll(".tab-content").forEach(view => {
        view.classList.remove("active");
      });
      const activeView = document.getElementById(targetViewId);
      if (activeView) activeView.classList.add("active");

      if (tab.dataset.tab === "graph") {
        renderGraph();
      }
    });
  });
}

/* ==========================================================================
   Catalog & Data Fetching
   ========================================================================== */
async function fetchCatalogData() {
  try {
    const res = await fetch(`${API_BASE}/api/products?limit=100`);
    if (!res.ok) throw new Error("API offline");
    const json = await res.json();
    allProducts = json.data && json.data.length > 0 ? json.data : FALLBACK_PRODUCTS;
    setConnectedState(true);
  } catch (err) {
    console.warn("Backend API offline or loading, using catalog cache:", err);
    allProducts = FALLBACK_PRODUCTS;
    setConnectedState(false);
  }
  renderCatalog();
}

async function fetchStats() {
  try {
    const res = await fetch(`${API_BASE}/api/products/stats`);
    if (res.ok) {
      const stats = await res.json();
      document.getElementById("stat-total-products").textContent = stats.total_products || allProducts.length;
      document.getElementById("stat-total-brands").textContent = stats.total_brands || 3;
      if (stats.brands_list && stats.brands_list.length > 0) {
        document.getElementById("stat-top-brands").textContent = stats.brands_list.slice(0, 3).join(", ");
        updateBrandFilterPills(stats.brands_list);
      }
      document.getElementById("stat-pending-reviews").textContent = stats.proposed_edges || 0;
      document.getElementById("badge-review-count").textContent = stats.proposed_edges || 0;
      return;
    }
  } catch (e) { }

  // Fallback stats
  document.getElementById("stat-total-products").textContent = allProducts.length;
  document.getElementById("stat-total-brands").textContent = "3";
  document.getElementById("stat-pending-reviews").textContent = "0";
}

function updateBrandFilterPills(brands) {
  const container = document.getElementById("brand-filter-container");
  if (!container) return;

  let html = `<button class="pill-btn ${currentFilterBrand === '' ? 'active' : ''}" data-brand="">All Brands</button>`;
  brands.forEach(b => {
    if (!b) return;
    html += `<button class="pill-btn ${currentFilterBrand === b ? 'active' : ''}" data-brand="${escapeHtml(b)}">${escapeHtml(b)}</button>`;
  });
  container.innerHTML = html;

  container.querySelectorAll(".pill-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".pill-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilterBrand = btn.dataset.brand;
      renderCatalog();
    });
  });
}

function setConnectedState(isConnected) {
  const pill = document.getElementById("connection-pill");
  const dot = pill.querySelector(".status-dot");
  const label = pill.querySelector(".status-label");

  if (isConnected) {
    dot.style.background = "var(--accent-green)";
    label.textContent = "Supabase Connected";
  } else {
    dot.style.background = "var(--accent-orange)";
    label.textContent = "Local Mock Cache";
  }
}

/* ==========================================================================
   Catalog Rendering
   ========================================================================== */
function renderCatalog() {
  const container = document.getElementById("products-container");
  if (!container) return;

  const filterInput = document.getElementById("catalog-filter-input");
  const query = filterInput ? filterInput.value.toLowerCase().trim() : "";

  const filtered = allProducts.filter(p => {
    const meta = p.metadata || {};
    const title = (meta.title || p.content || "").toLowerCase();
    const brand = (meta.brand || "").toLowerCase();
    const summary = (meta.summary || "").toLowerCase();

    const matchesQuery = !query || title.includes(query) || brand.includes(query) || summary.includes(query);
    const matchesBrand = !currentFilterBrand || (meta.brand || "").toLowerCase() === currentFilterBrand.toLowerCase();

    return matchesQuery && matchesBrand;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </div>
        <h3>No matching products found</h3>
        <p>Try refining your search keyword or clearing the brand filter.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(p => {
    const meta = p.metadata || {};
    const title = meta.title || "Industrial Part #" + p.id;
    const brand = meta.brand || "Industrial";
    const summary = meta.summary || (p.content || "").slice(0, 120) + "...";
    const partNum = meta.attributes?.part_number || meta.technical_specifications?.["Part Number"] || `ID-${p.id}`;

    const specs = Object.entries(meta.technical_specifications || {})
      .slice(0, 3)
      .map(([k, v]) => `<span class="spec-chip">${escapeHtml(k)}: ${escapeHtml(String(v))}</span>`)
      .join("");

    return `
      <div class="product-card" onclick="openProductDrawer(${p.id})">
        <div class="product-card-top">
          <div class="card-badges">
            <span class="pill-tag blue">${escapeHtml(brand)}</span>
            <span class="pill-tag gray">${escapeHtml(partNum)}</span>
          </div>
          <h3 class="product-title">${escapeHtml(title)}</h3>
          <p class="product-summary">${escapeHtml(summary)}</p>
          <div class="product-specs-preview">
            ${specs || '<span class="spec-chip">384-dim Vector Indexed</span>'}
          </div>
        </div>
        <div class="product-card-bottom">
          <div class="provenance-tag">
            <span class="status-dot"></span>
            <span>AI Enriched</span>
          </div>
          <button class="btn-inspect">
            <span>Inspect Spec</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
          </button>
        </div>
      </div>
    `;
  }).join("");
}

// Live filter input binding
const catalogFilterInput = document.getElementById("catalog-filter-input");
if (catalogFilterInput) {
  catalogFilterInput.addEventListener("input", () => renderCatalog());
}

/* ==========================================================================
   Semantic Vector Search Studio
   ========================================================================== */
function initSearch() {
  const searchInput = document.getElementById("semantic-search-input");
  const searchBtn = document.getElementById("btn-run-search");

  if (searchBtn && searchInput) {
    searchBtn.addEventListener("click", () => executeSemanticSearch(searchInput.value));
    searchInput.addEventListener("keydown", e => {
      if (e.key === "Enter") executeSemanticSearch(searchInput.value);
    });
  }

  // Quick Chips
  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      if (searchInput) {
        searchInput.value = chip.dataset.query;
        executeSemanticSearch(chip.dataset.query);
      }
    });
  });
}

async function executeSemanticSearch(queryText) {
  if (!queryText || !queryText.trim()) return;
  const container = document.getElementById("search-results-container");
  if (!container) return;

  container.innerHTML = `
    <div class="empty-state">
      <div class="status-dot" style="margin: 0 auto 1rem; width: 12px; height: 12px;"></div>
      <h3>Encoding Vector & Querying Supabase...</h3>
      <p>Executing match_documents RPC with cosine similarity calculation across 384 dimensions.</p>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/api/products/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: queryText, match_threshold: 0.15, match_count: 8 })
    });

    if (!res.ok) throw new Error("Search request failed");
    const json = await res.json();
    renderSearchResults(json.results, queryText);
  } catch (err) {
    console.warn("Vector search endpoint unavailable, executing client-side cosine fallback:", err);
    // Fallback client simulation
    const simulated = allProducts.map(p => {
      const matchWords = queryText.toLowerCase().split(" ");
      const text = (p.content + " " + JSON.stringify(p.metadata)).toLowerCase();
      let matches = 0;
      matchWords.forEach(w => { if (text.includes(w)) matches++; });
      const sim = Math.min(0.92, 0.45 + (matches / matchWords.length) * 0.45);
      return { ...p, similarity: sim };
    }).sort((a, b) => b.similarity - a.similarity);

    renderSearchResults(simulated.slice(0, 5), queryText);
  }
}

function renderSearchResults(results, queryText) {
  const container = document.getElementById("search-results-container");
  if (!container) return;

  if (!results || results.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
        </div>
        <h3>No semantic matches above threshold</h3>
        <p>Try searching for broader terms like 'abrasives', 'discs', or 'belts'.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="search-results-list">
      ${results.map((r, idx) => {
    const meta = r.metadata || {};
    const title = meta.title || "Product #" + r.id;
    const brand = meta.brand || "Industrial";
    const sim = r.similarity || 0.85;
    const simPercent = (sim * 100).toFixed(1);
    const excerpt = meta.summary || (r.content || "").slice(0, 150) + "...";

    return `
          <div class="search-result-row" onclick="openProductDrawer(${r.id})">
            <div class="result-main-col">
              <div class="card-badges" style="margin-bottom: 0.35rem;">
                <span class="pill-tag blue">${escapeHtml(brand)}</span>
                <span class="pill-tag gray">Rank #${idx + 1}</span>
              </div>
              <h3 class="result-title">${escapeHtml(title)}</h3>
              <p class="result-excerpt">${escapeHtml(excerpt)}</p>
            </div>
            <div class="result-score-col">
              <div class="score-percentage">${simPercent}%</div>
              <div class="score-label">Cosine Match</div>
            </div>
          </div>
        `;
  }).join("")}
    </div>
  `;
}

/* ==========================================================================
   Product Detail Drawer (Slide-Over Inspector)
   ========================================================================== */
function initDrawer() {
  const overlay = document.getElementById("product-drawer-overlay");
  const closeBtn = document.getElementById("btn-close-drawer");

  if (overlay && closeBtn) {
    closeBtn.addEventListener("click", closeProductDrawer);
    overlay.addEventListener("click", e => {
      if (e.target === overlay) closeProductDrawer();
    });
  }

  window.addEventListener("keydown", e => {
    if (e.key === "Escape") closeProductDrawer();
  });
}

function openProductDrawer(productId) {
  const product = allProducts.find(p => p.id === productId);
  if (!product) return;

  const meta = product.metadata || {};

  document.getElementById("drawer-brand").textContent = meta.brand || "Industrial";
  document.getElementById("drawer-id").textContent = `SKU: ${meta.attributes?.part_number || product.id}`;
  document.getElementById("drawer-title").textContent = meta.title || product.content.slice(0, 60);
  document.getElementById("drawer-summary").textContent = `"${meta.summary || 'Enriched specification profile.'}"`;
  document.getElementById("drawer-description").textContent = meta.enriched_description || product.content;

  // Categories
  const catContainer = document.getElementById("drawer-categories");
  if (catContainer) {
    const cats = meta.category_hierarchy || ["Industrial", "Abrasives"];
    catContainer.innerHTML = cats.map(c => `<span class="pill-tag gray">${escapeHtml(c)}</span>`).join("");
  }

  // Key Features
  const featContainer = document.getElementById("drawer-features");
  if (featContainer) {
    const feats = meta.key_features || ["Heavy-duty formulation", "Precision grade tolerance"];
    featContainer.innerHTML = feats.map(f => `<li>${escapeHtml(f)}</li>`).join("");
  }

  // Specs Table
  const specsTableBody = document.querySelector("#drawer-specs-table tbody");
  if (specsTableBody) {
    const specs = meta.technical_specifications || meta.attributes || {};
    specsTableBody.innerHTML = Object.entries(specs).map(([k, v]) => `
      <tr>
        <td>${escapeHtml(k)}</td>
        <td>${escapeHtml(String(v))}</td>
      </tr>
    `).join("");
  }

  // Keywords
  const keyContainer = document.getElementById("drawer-keywords");
  if (keyContainer) {
    const keywords = meta.search_keywords || ["industrial", "procurement", "abrasive"];
    keyContainer.innerHTML = keywords.map(k => `<span class="spec-chip">${escapeHtml(k)}</span>`).join("");
  }

  // Draw 384-dim Vector Sparkline
  drawVectorCanvas();

  document.getElementById("product-drawer-overlay").classList.add("open");
}

function closeProductDrawer() {
  const overlay = document.getElementById("product-drawer-overlay");
  if (overlay) overlay.classList.remove("open");
}

function drawVectorCanvas() {
  const canvas = document.getElementById("vectorCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "rgba(41, 151, 255, 0.85)";

  const bars = 96;
  const barWidth = width / bars;
  for (let i = 0; i < bars; i++) {
    // Deterministic pseudo-random wave representing high-dim embedding
    const val = Math.sin(i * 0.25) * 0.4 + Math.cos(i * 0.6) * 0.4 + 0.5;
    const barHeight = Math.max(3, val * (height - 10));
    ctx.fillRect(i * barWidth, height - barHeight, barWidth - 1, barHeight);
  }
}

/* ==========================================================================
   Human-in-the-Loop Review Queue
   ========================================================================== */
async function fetchReviewQueue() {
  const container = document.getElementById("review-queue-container");
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/edges/queue?limit=20`);
    if (res.ok) {
      const items = await res.json();
      renderReviewQueue(items);
      return;
    }
  } catch (e) { }

  // Fallback demo items
  const demoReviews = [
    {
      edge: { id: "edge-1", confidence: 0.96, relation: "has_specification", status: "proposed" },
      source_node: { label: "Diablo DCB518ASTS06G" },
      target_node: { label: "Width: 1/2 in (12.7 mm)" },
      source_document: { file_name: "Unihack_ Sample.csv" }
    },
    {
      edge: { id: "edge-2", confidence: 0.88, relation: "supplied_by", status: "proposed" },
      source_node: { label: "3M Cubitron II 775L" },
      target_node: { label: "Jam Industrial Supply LLC" },
      source_document: { file_name: "Unihack_ Sample.csv" }
    }
  ];
  renderReviewQueue(demoReviews);
}

function renderReviewQueue(items) {
  const container = document.getElementById("review-queue-container");
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
        </div>
        <h3>Review Queue is Clear</h3>
        <p>All AI-proposed edges and specs have been reviewed and approved.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="review-card" id="review-card-${item.edge.id}">
      <div class="review-info-col">
        <div class="review-top-meta">
          <span class="pill-tag blue">${escapeHtml(item.edge.relation || 'has_attribute')}</span>
          <span class="pill-tag gray">Source: ${escapeHtml(item.source_document?.file_name || 'CSV')}</span>
        </div>
        <h4 class="review-product-name">${escapeHtml(item.source_node?.label || 'Product')}</h4>
        <div class="review-extraction-preview">
          Proposed Spec: <strong>${escapeHtml(item.target_node?.label || 'Value')}</strong>
        </div>
      </div>
      <div class="review-confidence-meter">
        <div class="conf-number">${(item.edge.confidence * 100).toFixed(0)}%</div>
        <div class="conf-label">Confidence</div>
      </div>
      <div class="review-actions-group">
        <button class="btn-approve" onclick="handleReviewDecision('${item.edge.id}', 'approved')">Approve Spec</button>
        <button class="btn-reject" onclick="handleReviewDecision('${item.edge.id}', 'rejected')">Reject</button>
      </div>
    </div>
  `).join("");
}

async function handleReviewDecision(edgeId, decision) {
  try {
    await fetch(`${API_BASE}/edges/${edgeId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: decision, reviewed_by: "ProductManager" })
    });
  } catch (e) { }

  const card = document.getElementById(`review-card-${edgeId}`);
  if (card) {
    card.style.opacity = "0";
    card.style.transform = "translateX(20px)";
    setTimeout(() => {
      card.remove();
      showToast(`Spec successfully ${decision}.`);
    }, 250);
  }
}

/* ==========================================================================
   Product Direct Ingestion Form
   ========================================================================== */
function initProductForm() {
  const form = document.getElementById("form-add-product");
  const resultBox = document.getElementById("add-product-result");
  if (!form) return;

  form.addEventListener("submit", async e => {
    e.preventDefault();

    const partName = document.getElementById("inp-part-name").value.trim();
    const partNum = document.getElementById("inp-part-num")?.value.trim() || "";
    const brand = document.getElementById("inp-brand")?.value.trim() || "";
    const notes = document.getElementById("inp-notes")?.value.trim() || "";

    if (!partName) {
      showToast("Please enter a product name or description.");
      return;
    }

    const payload = {
      part_name: partName,
      part_num: partNum,
      brand: brand,
      manufacturer: brand,
      notes_or_specs: notes,
    };

    const submitBtn = document.getElementById("btn-submit-product");
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>🧠 AI Enriching & Generating Vectors...</span>`;

    if (resultBox) {
      resultBox.style.display = "block";
      resultBox.innerHTML = `
        <div class="ingest-stat-pill" style="text-align: left; padding: 1rem;">
          <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--accent-blue);">
            <span class="status-dot"></span>
            <strong>Running Autonomous Pipeline:</strong>
          </div>
          <p style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.4rem;">
            1. Groq LLM enriching title, specs & summary<br/>
            2. Generating 384-dim vector embedding<br/>
            3. Inserting into Supabase Vector DB (documents)<br/>
            4. Updating Knowledge Graph (nodes & edges)
          </p>
        </div>
      `;
    }

    try {
      const res = await fetch(`${API_BASE}/api/products/auto-add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Auto-add request failed");
      }

      const json = await res.json();
      const product = json.product || {};
      const graphUpdates = json.graph_updates || { nodes_created: 0, edges_created: 0 };

      showToast("✨ Product auto-enriched, embedded, & added to Knowledge Graph!");
      form.reset();

      if (resultBox) {
        resultBox.innerHTML = `
          <div class="ingest-success-card">
            <div class="ingest-success-header">
              <span class="pill-tag green">✓ Ingestion & Graph Update Complete</span>
              <span class="pill-tag gray">ID: #${json.document_id || 'new'}</span>
            </div>
            <h4 class="ingest-success-title">${escapeHtml(product.title || partName)}</h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem;">
              ${escapeHtml(product.summary || 'Specification profile created.')}
            </p>
            <div class="ingest-stats-row">
              <div class="ingest-stat-pill">
                <div class="ingest-stat-val">384</div>
                <div class="ingest-stat-label">Vector Dims</div>
              </div>
              <div class="ingest-stat-pill">
                <div class="ingest-stat-val">${graphUpdates.nodes_created}</div>
                <div class="ingest-stat-label">Nodes Created</div>
              </div>
              <div class="ingest-stat-pill">
                <div class="ingest-stat-val">${graphUpdates.edges_created}</div>
                <div class="ingest-stat-label">Proposed Edges</div>
              </div>
            </div>
            <div class="ingest-card-actions">
              <button class="pill-btn active" onclick="document.getElementById('tab-catalog').click()">View in Catalog</button>
              <button class="pill-btn" onclick="document.getElementById('tab-review').click()">Review in Queue</button>
              <button class="pill-btn" onclick="document.getElementById('tab-graph').click()">View in Graph</button>
            </div>
          </div>
        `;
      }

      // Refresh catalog, stats, review queue, and graph
      fetchCatalogData();
      fetchStats();
      fetchReviewQueue();
      if (typeof fetchGraphData === "function") fetchGraphData(currentGraphStatus || "approved");

    } catch (err) {
      console.warn("API auto-add failed, using local session fallback:", err);
      const fallbackTitle = `${brand ? brand + ' ' : ''}${partName}${partNum ? ' (' + partNum + ')' : ''}`;
      const fallbackMeta = {
        title: fallbackTitle,
        brand: brand || "Industrial",
        summary: `Industrial specification for ${partName}.`,
        enriched_description: notes || `${fallbackTitle} high-durability specification.`,
        key_features: ["Industrial grade standard", "Precision tolerance"],
        category_hierarchy: ["Industrial", "Hardware"],
        technical_specifications: { "Part Number": partNum || "N/A", "Brand": brand || "Industrial" },
        attributes: { "part_number": partNum || "N/A", "brand": brand || "Industrial" },
        search_keywords: [partName, brand, partNum].filter(Boolean),
      };

      allProducts.unshift({ id: Date.now(), metadata: fallbackMeta, content: `${fallbackTitle} ${notes}` });
      renderCatalog();
      showToast("Product added to local session!");
      form.reset();

      if (resultBox) {
        resultBox.innerHTML = `
          <div class="ingest-success-card">
            <span class="pill-tag blue">Added to Local Session</span>
            <h4 class="ingest-success-title">${escapeHtml(fallbackTitle)}</h4>
            <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.25rem;">
              Enriched locally and indexed in session catalog.
            </p>
          </div>
        `;
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <span>Auto-Enrich & Ingest Product</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M5 12h14" />
          <path d="m12 5 7 7-7 7" />
        </svg>
      `;
    }
  });
}

/* ==========================================================================
   Bulk Upload (CSV / PDF Drag-and-Drop)
   ========================================================================== */
function initBulkUpload() {
  const dropZone = document.getElementById("bulk-drop-zone");
  const fileInput = document.getElementById("bulk-file-input");
  const browseBtn = document.getElementById("btn-browse-file");
  const removeBtn = document.getElementById("btn-remove-file");
  const uploadBtn = document.getElementById("btn-bulk-upload");
  const resultBox = document.getElementById("bulk-upload-result");
  const previewBox = document.getElementById("bulk-file-preview");

  if (!dropZone) return;

  let selectedFile = null;

  // -- Helpers --
  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function fileTypeIcon(filename) {
    const ext = (filename || "").split(".").pop().toLowerCase();
    if (ext === "pdf") return "📑";
    if (ext === "csv") return "📊";
    if (ext === "xlsx") return "📊";
    if (ext === "docx") return "📝";
    return "📄";
  }

  function applyFile(file) {
    selectedFile = file;

    document.getElementById("bulk-file-name").textContent = file.name;
    document.getElementById("bulk-file-meta").textContent = formatBytes(file.size);
    document.getElementById("bulk-file-type-icon").textContent = fileTypeIcon(file.name);

    previewBox.style.display = "flex";
    dropZone.style.display = "none";
    uploadBtn.disabled = false;

    // Clear old result
    resultBox.style.display = "none";
    resultBox.innerHTML = "";
  }

  function clearFile() {
    selectedFile = null;
    fileInput.value = "";
    previewBox.style.display = "none";
    dropZone.style.display = "block";
    uploadBtn.disabled = true;
    resultBox.style.display = "none";
    resultBox.innerHTML = "";
  }

  // -- Browse button --
  if (browseBtn) browseBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) applyFile(fileInput.files[0]);
  });

  if (removeBtn) removeBtn.addEventListener("click", clearFile);

  // -- Drag-and-drop --
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", (e) => {
    if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove("drag-over");
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) applyFile(file);
  });

  // -- Upload --
  if (uploadBtn) uploadBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    uploadBtn.disabled = true;
    uploadBtn.innerHTML = `<span>Uploading & Ingesting...</span>`;

    resultBox.style.display = "block";
    resultBox.innerHTML = `
      <div class="bulk-uploading-state">
        <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--accent-blue);">
          <span class="status-dot"></span>
          <strong>Running Ingestion Pipeline...</strong>
        </div>
        <div class="bulk-upload-progress-bar">
          <div class="bulk-upload-progress-fill"></div>
        </div>
        <p style="font-size: 0.78rem; color: var(--text-secondary);">
          ${selectedFile.name.endsWith(".pdf") || selectedFile.name.endsWith(".docx")
        ? "1. Parsing document via LlamaParse<br/>2. Generating 384-dim embedding<br/>3. Storing in Supabase Vector DB"
        : "1. Extracting rows via LlamaCloud Extract<br/>2. Groq AI enriching each product<br/>3. Generating embeddings &amp; inserting to pgvector"
      }
        </p>
      </div>
    `;

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await fetch(`${API_BASE}/api/products/bulk-upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed (${res.status})`);
      }

      const json = await res.json();
      const count = json.products_ingested || 0;
      const errors = json.errors || [];
      const ftype = (json.file_type || "").toUpperCase();

      showToast(`✨ ${count} product${count !== 1 ? "s" : ""} ingested from ${escapeHtml(json.file || selectedFile.name)}!`);

      resultBox.innerHTML = `
        <div class="bulk-result-card">
          <div class="bulk-result-header">
            <span class="pill-tag green">✓ Ingestion Complete</span>
            <span class="pill-tag gray">${escapeHtml(ftype)} · ${escapeHtml(json.file || selectedFile.name)}</span>
          </div>
          <div class="bulk-result-body">
            <div class="bulk-result-stats">
              <div class="bulk-stat-pill">
                <div class="bulk-stat-val">${count}</div>
                <div class="bulk-stat-label">Products Added</div>
              </div>
              <div class="bulk-stat-pill">
                <div class="bulk-stat-val">384</div>
                <div class="bulk-stat-label">Vector Dims</div>
              </div>
              <div class="bulk-stat-pill">
                <div class="bulk-stat-val" style="${errors.length > 0 ? 'color:var(--accent-orange)' : ''}">${errors.length}</div>
                <div class="bulk-stat-label">Errors</div>
              </div>
            </div>
            ${errors.length > 0 ? `
              <ul class="bulk-error-list">
                ${errors.map(e => `<li>${escapeHtml(e)}</li>`).join("")}
              </ul>
            ` : ""}
            <div class="ingest-card-actions" style="margin-top: 0.85rem;">
              <button class="pill-btn active" onclick="document.getElementById('tab-catalog').click()">View Catalog</button>
              <button class="pill-btn" onclick="document.getElementById('tab-search').click()">Search Products</button>
            </div>
          </div>
        </div>
      `;

      fetchCatalogData();
      fetchStats();

    } catch (err) {
      resultBox.innerHTML = `
        <div class="bulk-result-card" style="border-color: rgba(255,69,58,0.3);">
          <div class="bulk-result-header">
            <span class="pill-tag" style="background: rgba(255,69,58,0.15); color: var(--accent-red); border-color: rgba(255,69,58,0.3);">⚠ Upload Failed</span>
          </div>
          <div class="bulk-result-body">
            <p style="font-size: 0.82rem; color: var(--text-secondary);">${escapeHtml(err.message)}</p>
            <p style="font-size: 0.75rem; color: var(--text-tertiary); margin-top: 0.4rem;">
              Make sure LLAMA_CLOUD_API_KEY and GROQ_API_KEY are set, and the backend is running.
            </p>
          </div>
        </div>
      `;
      showToast("Upload failed: " + err.message);
    } finally {
      uploadBtn.disabled = false;
      uploadBtn.innerHTML = `
        <span>Upload &amp; Ingest File</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      `;
    }
  });
}

/* ==========================================================================
   Knowledge Graph Visualizer (HTML5 Canvas, fed by live /graph data)
   ========================================================================== */
let currentGraphStatus = "approved";
let currentGraphNodes = [];
let currentGraphEdges = [];

function nodeColor(nodeType) {
  const t = (nodeType || "").toLowerCase();
  if (t === "product") return "#2997ff";
  if (t === "brand" || t === "supplier") return "#af52de";
  if (t === "category") return "#30d158";
  return "#ff9f0a"; // attribute/spec and anything else
}

async function fetchGraphData(status) {
  const res = await fetch(`${API_BASE}/graph?status=${status}`);
  if (!res.ok) throw new Error(`Graph fetch failed: ${res.status}`);
  return res.json(); // { nodes: [...], edges: [...] }
}

function layoutNodesInCircle(nodes, w, h) {
  const cx = w / 2, cy = h / 2;
  const radius = Math.min(w, h) * 0.35;
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    return {
      ...n,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      r: n.node_type === "product" ? 18 : 13,
    };
  });
}

function drawGraph(canvas, nodes, edges) {
  const ctx = canvas.getContext("2d");
  const w = (canvas.width = canvas.parentElement.clientWidth);
  const h = (canvas.height = canvas.parentElement.clientHeight);
  ctx.clearRect(0, 0, w, h);

  if (!nodes.length) {
    ctx.fillStyle = "#8e8e93";
    ctx.font = "14px 'Instrument Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No edges yet for this status — review some items first.", w / 2, h / 2);
    currentGraphNodes = [];
    currentGraphEdges = [];
    return;
  }

  const positioned = layoutNodesInCircle(nodes, w, h);
  currentGraphNodes = positioned;
  currentGraphEdges = edges;
  const byId = Object.fromEntries(positioned.map(n => [n.id, n]));

  // Draw edges first (so nodes sit on top)
  ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
  ctx.lineWidth = 1.5;
  edges.forEach(e => {
    const s = byId[e.source_node_id];
    const t = byId[e.target_node_id];
    if (!s || !t) return;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.stroke();
  });

  // Draw nodes
  positioned.forEach(n => {
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n.node_type);
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#f5f5f7";
    ctx.font = "11px 'Instrument Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(n.label, n.x, n.y + n.r + 14);
  });
}

function initGraphCanvas() {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = canvas.parentElement.clientHeight;

  const tooltip = document.getElementById("graph-tooltip");

  canvas.addEventListener("mousemove", (e) => {
    if (!currentGraphNodes || !currentGraphNodes.length) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    let hoveredNode = null;
    for (let i = currentGraphNodes.length - 1; i >= 0; i--) {
      const n = currentGraphNodes[i];
      if (Math.hypot(n.x - mouseX, n.y - mouseY) <= n.r) {
        hoveredNode = n;
        break;
      }
    }

    if (hoveredNode) {
      canvas.style.cursor = "pointer";
      let tooltipText = hoveredNode.label;

      const type = (hoveredNode.node_type || "").toLowerCase();
      if (type === "attribute" || type === "spec") {
        const edge = currentGraphEdges.find(ed => ed.target_node_id === hoveredNode.id);
        if (edge) {
          const sourceNode = currentGraphNodes.find(n => n.id === edge.source_node_id);
          if (sourceNode) {
            tooltipText = `${hoveredNode.label} — part of ${sourceNode.label}`;
          }
        }
      }

      if (tooltip) {
        tooltip.textContent = tooltipText;
        tooltip.style.display = "block";
        tooltip.style.left = (e.pageX + 15) + "px";
        tooltip.style.top = (e.pageY + 15) + "px";
      }
    } else {
      canvas.style.cursor = "default";
      if (tooltip) tooltip.style.display = "none";
    }
  });

  canvas.addEventListener("mouseleave", () => {
    canvas.style.cursor = "default";
    if (tooltip) tooltip.style.display = "none";
  });

  window.addEventListener("resize", () => {
    if (tooltip) tooltip.style.display = "none";
  });

  const approvedBtn = document.getElementById("btn-graph-approved");
  const proposedBtn = document.getElementById("btn-graph-proposed");
  if (approvedBtn && proposedBtn) {
    approvedBtn.addEventListener("click", () => {
      currentGraphStatus = "approved";
      approvedBtn.classList.add("active");
      proposedBtn.classList.remove("active");
      renderGraph();
    });
    proposedBtn.addEventListener("click", () => {
      currentGraphStatus = "proposed";
      proposedBtn.classList.add("active");
      approvedBtn.classList.remove("active");
      renderGraph();
    });
  }
}

async function renderGraph() {
  const canvas = document.getElementById("graphCanvas");
  if (!canvas) return;
  try {
    const { nodes, edges } = await fetchGraphData(currentGraphStatus);
    drawGraph(canvas, nodes, edges);
  } catch (err) {
    console.error("Failed to load graph:", err);
    const ctx = canvas.getContext("2d");
    const w = (canvas.width = canvas.parentElement.clientWidth);
    const h = (canvas.height = canvas.parentElement.clientHeight);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#ff6b6b";
    ctx.font = "14px 'Instrument Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Couldn't load graph data from the backend.", w / 2, h / 2);
  }
}

/* ==========================================================================
   Command Palette (⌘K)
   ========================================================================== */
function initCommandPalette() {
  const overlay = document.getElementById("cmd-palette-overlay");
  const input = document.getElementById("cmd-input");
  const triggerBtn = document.getElementById("cmd-k-btn");

  if (triggerBtn) triggerBtn.addEventListener("click", openCmdPalette);

  window.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      openCmdPalette();
    }
  });

  if (overlay && input) {
    overlay.addEventListener("click", e => {
      if (e.target === overlay) closeCmdPalette();
    });

    input.addEventListener("keydown", e => {
      if (e.key === "Escape") closeCmdPalette();
      if (e.key === "Enter") {
        const q = input.value.trim();
        if (q) {
          closeCmdPalette();
          // Switch to search tab
          const searchTab = document.getElementById("tab-search");
          if (searchTab) searchTab.click();
          const searchInp = document.getElementById("semantic-search-input");
          if (searchInp) {
            searchInp.value = q;
            executeSemanticSearch(q);
          }
        }
      }
    });
  }
}

function openCmdPalette() {
  const overlay = document.getElementById("cmd-palette-overlay");
  const input = document.getElementById("cmd-input");
  if (overlay) {
    overlay.classList.add("open");
    setTimeout(() => { if (input) input.focus(); }, 50);
  }
}

function closeCmdPalette() {
  const overlay = document.getElementById("cmd-palette-overlay");
  if (overlay) overlay.classList.remove("open");
}

/* ==========================================================================
   Catalogue Analytics Dashboard
   ========================================================================== */

let _analyticsData = null;

function initAnalytics() {
  const refreshBtn = document.getElementById("btn-refresh-analytics");
  if (refreshBtn) refreshBtn.addEventListener("click", fetchAnalysis);

  // Auto-load when tab is activated
  const analyticsTab = document.getElementById("tab-analytics");
  if (analyticsTab) {
    analyticsTab.addEventListener("click", () => {
      if (!_analyticsData) fetchAnalysis();
      else renderAnalytics(_analyticsData); // re-draw charts (canvas sizes may have changed)
    });
  }
}

async function fetchAnalysis() {
  // Show skeleton shimmer while loading
  ["analytics-kpi-row", "analytics-charts-grid", "analytics-card-fillrates",
    "analytics-card-keywords"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.opacity = "0.4";
    });

  try {
    const res = await fetch(`${API_BASE}/api/products/analysis`);
    if (!res.ok) throw new Error("Analysis API error");
    const data = await res.json();
    _analyticsData = data;
    renderAnalytics(data);
  } catch (err) {
    console.warn("[analytics] Backend unavailable, using demo data:", err);
    // Fallback demo so the UI is always illustrative
    _analyticsData = _demoAnalyticsData();
    renderAnalytics(_analyticsData);
  } finally {
    ["analytics-kpi-row", "analytics-charts-grid", "analytics-card-fillrates",
      "analytics-card-keywords"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.opacity = "1";
      });
  }
}

function renderAnalytics(data) {
  if (!data || data.total_products === 0) {
    document.getElementById("analytics-empty").style.display = "block";
    return;
  }
  document.getElementById("analytics-empty").style.display = "none";

  // ── KPI Cards ──────────────────────────────────────────────────────────────
  _setText("akpi-total", data.total_products);
  _setText("akpi-completeness", (data.avg_completeness_pct || 0) + "%");
  _setText("akpi-brands", data.brand_distribution?.length || 0);
  _setText("akpi-categories", data.category_breakdown?.length || 0);

  // ── Bar Charts ─────────────────────────────────────────────────────────────
  requestAnimationFrame(() => {
    drawHorizontalBarChart("chartBrands",
      (data.brand_distribution || []).slice(0, 10),
      d => d.brand, d => d.count,
      ["#2997ff", "#5fb3ff", "#0a7aff", "#38b6ff", "#1a8aff",
        "#2997ff", "#5fb3ff", "#0a7aff", "#38b6ff", "#1a8aff"]
    );
    _renderFooterLegend("analytics-brands-footer", data.brand_distribution, d => d.brand, d => d.count);

    drawHorizontalBarChart("chartCategories",
      (data.category_breakdown || []).slice(0, 10),
      d => d.category, d => d.count,
      ["#30d158", "#34e760", "#20bb48", "#28d155", "#22c84f",
        "#30d158", "#34e760", "#20bb48", "#28d155", "#22c84f"]
    );
    _renderFooterLegend("analytics-categories-footer", data.category_breakdown, d => d.category, d => d.count);
  });

  // ── Quality Distribution ───────────────────────────────────────────────────
  const qd = data.quality_distribution || {};
  const qBody = document.getElementById("analytics-quality-body");
  if (qBody) {
    const complPct = qd.complete_pct || 0;
    const partPct = qd.partial_pct || 0;
    const sparPct = qd.sparse_pct || 0;
    qBody.innerHTML = `
      <div style="padding: 0 1rem;">
        <div class="quality-segmented-bar">
          <div class="quality-seg complete" style="width:${complPct}%" title="Complete: ${qd.complete}"></div>
          <div class="quality-seg partial"  style="width:${partPct}%"  title="Partial: ${qd.partial}"></div>
          <div class="quality-seg sparse"   style="width:${sparPct}%"  title="Sparse: ${qd.sparse}"></div>
        </div>
        <div class="quality-legend">
          <div class="quality-legend-item">
            <span class="quality-dot complete"></span>
            <span class="quality-legend-label">Complete</span>
            <span class="quality-legend-val">${qd.complete || 0} <span style="color:var(--text-tertiary)">(${complPct}%)</span></span>
          </div>
          <div class="quality-legend-item">
            <span class="quality-dot partial"></span>
            <span class="quality-legend-label">Partial</span>
            <span class="quality-legend-val">${qd.partial || 0} <span style="color:var(--text-tertiary)">(${partPct}%)</span></span>
          </div>
          <div class="quality-legend-item">
            <span class="quality-dot sparse"></span>
            <span class="quality-legend-label">Sparse</span>
            <span class="quality-legend-val">${qd.sparse || 0} <span style="color:var(--text-tertiary)">(${sparPct}%)</span></span>
          </div>
        </div>
        <div style="margin-top: 1rem; font-size: 0.8rem; color: var(--text-secondary); padding-top: 0.75rem; border-top: 1px solid var(--border-subtle);">
          <strong style="color: var(--text-primary);">Complete</strong> = ≥ 7 of 8 fields filled &nbsp;·&nbsp;
          <strong style="color: var(--text-primary);">Partial</strong> = 4–6 fields &nbsp;·&nbsp;
          <strong style="color: var(--text-primary);">Sparse</strong> = ≤ 3 fields
        </div>
      </div>
    `;
  }

  // ── Source Provenance ──────────────────────────────────────────────────────
  const srcBody = document.getElementById("analytics-sources-body");
  const sources = data.source_files || [];
  if (srcBody) {
    if (!sources.length) {
      srcBody.innerHTML = `<p style="padding: 1rem; font-size:0.82rem; color: var(--text-secondary);">No source provenance data recorded yet.</p>`;
    } else {
      const maxCount = Math.max(...sources.map(s => s.count), 1);
      srcBody.innerHTML = sources.map(s => {
        const pct = Math.round(s.count / maxCount * 100);
        const icon = (s.file || "").endsWith(".pdf") ? "📑"
          : (s.file || "").endsWith(".csv") ? "📊"
            : "✍️";
        return `
          <div class="source-row">
            <span class="source-icon">${icon}</span>
            <div class="source-info">
              <div class="source-name">${escapeHtml(s.file || "Unknown")}</div>
              <div class="source-bar-wrap">
                <div class="source-bar-fill" style="width:${pct}%"></div>
              </div>
            </div>
            <span class="source-count">${s.count}</span>
          </div>
        `;
      }).join("");
    }
  }

  // ── Field Fill Rates ───────────────────────────────────────────────────────
  const frBody = document.getElementById("analytics-fillrates-body");
  const fillRates = data.field_fill_rates || [];
  if (frBody && fillRates.length) {
    frBody.innerHTML = `
      <div class="fillrates-grid">
        ${fillRates.map(f => {
      const pct = f.fill_rate || 0;
      const color = pct >= 80 ? "var(--accent-green)"
        : pct >= 50 ? "var(--accent-blue)"
          : "var(--accent-orange)";
      return `
            <div class="fillrate-row">
              <div class="fillrate-label">${escapeHtml(f.field)}</div>
              <div class="fillrate-bar-wrap">
                <div class="fillrate-bar-fill" style="width:${pct}%; background:${color}"></div>
              </div>
              <div class="fillrate-pct" style="color:${color}">${pct}%</div>
            </div>
          `;
    }).join("")}
      </div>
    `;
  }

  // ── Keyword Cloud ──────────────────────────────────────────────────────────
  const kwCloud = document.getElementById("analytics-keyword-cloud");
  const keywords = (data.top_keywords || []).slice(0, 30);
  if (kwCloud && keywords.length) {
    const maxCount = Math.max(...keywords.map(k => k.count), 1);
    const COLORS = ["#2997ff", "#30d158", "#af52de", "#ff9f0a", "#5fb3ff", "#34e760"];
    kwCloud.innerHTML = keywords.map((k, i) => {
      const ratio = k.count / maxCount;
      const size = 0.72 + ratio * 0.7; // 0.72rem → 1.42rem
      const weight = ratio > 0.6 ? 700 : ratio > 0.3 ? 600 : 500;
      const color = COLORS[i % COLORS.length];
      const opacity = 0.55 + ratio * 0.45;
      return `<span class="kw-chip"
        style="font-size:${size.toFixed(2)}rem; font-weight:${weight}; color:${color}; opacity:${opacity.toFixed(2)};"
        title="${k.count} occurrence${k.count !== 1 ? 's' : ''}">${escapeHtml(k.keyword)}</span>`;
    }).join(" ");
  } else if (kwCloud) {
    kwCloud.innerHTML = `<p style="font-size:0.82rem; color:var(--text-secondary);">No keywords indexed yet.</p>`;
  }
}

/* ── Canvas bar chart renderer ─────────────────────────────────────────────── */
function drawHorizontalBarChart(canvasId, data, labelFn, valueFn, colors) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data || !data.length) return;

  const wrapper = canvas.parentElement;
  const W = wrapper.clientWidth || 400;
  const BAR_H = 22;
  const GAP = 10;
  const LABEL_W = 110;
  const VAL_W = 36;
  const H = data.length * (BAR_H + GAP) + 20;

  canvas.width = W;
  canvas.height = H;

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  const maxVal = Math.max(...data.map(valueFn), 1);
  const barAreaW = W - LABEL_W - VAL_W - 16;

  data.forEach((item, i) => {
    const y = i * (BAR_H + GAP) + 10;
    const val = valueFn(item);
    const barW = Math.max(4, (val / maxVal) * barAreaW);
    const color = colors[i % colors.length];

    // Label
    ctx.fillStyle = "#86868b";
    ctx.font = "12px 'Instrument Sans', sans-serif";
    ctx.textAlign = "right";
    const label = labelFn(item);
    const truncLabel = label.length > 14 ? label.slice(0, 13) + "…" : label;
    ctx.fillText(truncLabel, LABEL_W - 8, y + BAR_H / 2 + 4);

    // Bar track
    ctx.fillStyle = "rgba(255,255,255,0.04)";
    ctx.beginPath();
    ctx.roundRect(LABEL_W, y, barAreaW, BAR_H, 5);
    ctx.fill();

    // Bar fill with gradient
    const grad = ctx.createLinearGradient(LABEL_W, 0, LABEL_W + barW, 0);
    grad.addColorStop(0, color);
    grad.addColorStop(1, color + "99");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(LABEL_W, y, barW, BAR_H, 5);
    ctx.fill();

    // Value label
    ctx.fillStyle = "#f5f5f7";
    ctx.font = "bold 11px 'Instrument Sans', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(val, LABEL_W + barW + 8, y + BAR_H / 2 + 4);
  });
}

function _renderFooterLegend(containerId, data, labelFn, valueFn) {
  const el = document.getElementById(containerId);
  if (!el || !data) return;
  const total = data.reduce((s, d) => s + valueFn(d), 0) || 1;
  el.innerHTML = `<span style="font-size:0.75rem; color: var(--text-secondary);">${data.length} unique entries &nbsp;·&nbsp; ${total} total products</span>`;
}

function _setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function _demoAnalyticsData() {
  return {
    total_products: 12,
    avg_completeness_pct: 87.5,
    brand_distribution: [
      { brand: "Diablo", count: 4 }, { brand: "3M", count: 3 },
      { brand: "Mirka", count: 3 }, { brand: "Bosch", count: 2 },
    ],
    category_breakdown: [
      { category: "Abrasives", count: 7 }, { category: "Power Tools", count: 3 },
      { category: "Accessories", count: 2 },
    ],
    top_keywords: [
      { keyword: "abrasive", count: 9 }, { keyword: "sanding", count: 8 },
      { keyword: "industrial", count: 7 }, { keyword: "belt", count: 6 },
      { keyword: "3M", count: 5 }, { keyword: "grinding", count: 5 },
      { keyword: "diablo", count: 4 }, { keyword: "mirka", count: 4 },
      { keyword: "disc", count: 4 }, { keyword: "P150", count: 3 },
      { keyword: "ceramic", count: 3 }, { keyword: "metal", count: 3 },
      { keyword: "woodworking", count: 2 }, { keyword: "precision", count: 2 },
    ],
    quality_distribution: {
      complete: 9, complete_pct: 75.0,
      partial: 2, partial_pct: 16.7,
      sparse: 1, sparse_pct: 8.3,
    },
    source_files: [
      { file: "Unihack_ Sample.csv", count: 8 },
      { file: "Manual Entry", count: 3 },
      { file: "Annual_Procurement_Report.pdf", count: 1 },
    ],
    field_fill_rates: [
      { field: "Title", fill_rate: 100 }, { field: "Brand", fill_rate: 100 },
      { field: "Summary", fill_rate: 91.7 }, { field: "Description", fill_rate: 83.3 },
      { field: "Key Features", fill_rate: 91.7 }, { field: "Tech Specs", fill_rate: 83.3 },
      { field: "Keywords", fill_rate: 91.7 }, { field: "Categories", fill_rate: 100 },
    ],
  };
}

/* ==========================================================================
   Utilities
   ========================================================================== */
function showToast(msg) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "apple-toast";
  toast.innerHTML = `
    <span class="status-dot"></span>
    <span>${escapeHtml(msg)}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function copySnippet(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast("Command copied to clipboard!");
  });
}

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
