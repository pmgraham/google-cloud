let currentData = null;
let currentSearchQuery = '';
let currentSqlFilter = null;

function setupTabs() {
    const tabs = document.querySelectorAll('.sidebar .nav-links li');
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            // Remove active from all
            tabs.forEach(t => t.classList.remove('active'));
            // Add active to clicked
            tab.classList.add('active');
            
            const tabName = tab.textContent.trim().toLowerCase();
            const listContainer = document.getElementById('matches-list');
            const headerCount = document.getElementById('total-groups-count');
            
            if (tabName !== 'matches') {
                listContainer.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-hammer"></i>
                        <h2>Under Construction</h2>
                        <p>The ${tabName} view is not yet implemented.</p>
                    </div>
                `;
                headerCount.textContent = "0 items";
            } else {
                fetchMatches();
            }
        });
    });
}
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    fetchMatches();
    
    // Setup Search
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchQuery = e.target.value.toLowerCase().trim();
            renderList();
        });
    }

    // Setup Gemini
    const geminiInput = document.getElementById('gemini-input');
    const geminiSubmit = document.getElementById('gemini-submit');
    const geminiClear = document.getElementById('gemini-clear-btn');

    if (geminiSubmit) {
        geminiSubmit.addEventListener('click', handleGeminiCommand);
        geminiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleGeminiCommand();
        });
        geminiClear.addEventListener('click', clearGeminiFilter);
    }
});

async function fetchMatches() {
    try {
        let url = '/api/matches';
        if (currentSqlFilter) {
            url += `?sql_filter=${encodeURIComponent(currentSqlFilter)}`;
        }
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        currentData = data.groups;
        
        document.getElementById('total-groups-count').textContent = 
            currentData ? `${currentData.length} parts in queue` : "0 parts in queue";
            
        renderList();
        
    } catch (error) {
        console.error('Error fetching matches:', error);
        document.getElementById('matches-list').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle" style="color: var(--danger);"></i>
                <h2>Error Loading Data</h2>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function renderList() {
    const listContainer = document.getElementById('matches-list');
    
    if (!currentData || currentData.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-check-circle"></i>
                <h2>All Caught Up!</h2>
                <p>There are no more matches pending review in your queue.</p>
            </div>
        `;
        return;
    }
    
    listContainer.innerHTML = '';
    
    // Filter the data based on search query
    let filteredData = currentData;
    if (currentSearchQuery) {
        filteredData = currentData.map(group => {
            const cpMatches = group.customer_part_number.toLowerCase().includes(currentSearchQuery) || 
                              (group.customer_description && group.customer_description.toLowerCase().includes(currentSearchQuery));
            
            const matchingSuppliers = group.matches.filter(match => {
                return cpMatches || // Give match if Customer Part matches
                       match.supplier_part_number.toLowerCase().includes(currentSearchQuery) ||
                       (match.supplier_description && match.supplier_description.toLowerCase().includes(currentSearchQuery)) ||
                       (match.reasoning && match.reasoning.toLowerCase().includes(currentSearchQuery));
            });

            if (matchingSuppliers.length > 0) {
                return { ...group, matches: matchingSuppliers };
            }
            return null;
        }).filter(Boolean);
    }
    
    if (filteredData.length === 0 && currentSearchQuery) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search" style="color: var(--gray-400);"></i>
                <h2>No matches found</h2>
                <p>No results for "${currentSearchQuery}"</p>
            </div>
        `;
        document.getElementById('total-groups-count').textContent = "0 matches found";
        return;
    }

    document.getElementById('total-groups-count').textContent = 
        filteredData ? `${filteredData.length} parts in queue` : "0 parts in queue";
    
    const groupTemplate = document.getElementById('customer-group-template');
    const rowTemplate = document.getElementById('supplier-row-template');
    
    filteredData.forEach((group, gIndex) => {
        // Skip empty groups
        if (!group.matches || group.matches.length === 0) return;
        
        const groupEl = groupTemplate.content.cloneNode(true);
        const groupWrapper = groupEl.querySelector('.customer-group');
        
        groupEl.querySelector('.cpn-title').textContent = `${group.customer_part_number} (${group.customer_description || 'No description'})`;
        groupEl.querySelector('.match-count-badge').textContent = group.matches.length;
        
        const suppliersContainer = groupEl.querySelector('.supplier-matches');
        
        group.matches.forEach((match, mIndex) => {
            const rowEl = rowTemplate.content.cloneNode(true);
            rowEl.querySelector('.spn-title').textContent = `${match.supplier_part_number}`;
            rowEl.querySelector('.reasoning-snippet').textContent = (match.supplier_description || 'No desc') + " | " + (match.reasoning || "No AI reasoning provided.");
            
            const btn = rowEl.querySelector('.btn-review-sm');
            btn.onclick = (e) => {
                e.stopPropagation(); // Prevent toggling the group
                openReviewModal(group.customer_part_number, match.supplier_part_number);
            };
            
            suppliersContainer.appendChild(rowEl);
        });
        
        listContainer.appendChild(groupEl);
    });
}

function toggleGroup(headerElement) {
    const group = headerElement.closest('.customer-group');
    if (group.classList.contains('expanded')) {
        group.classList.remove('expanded');
    } else {
        group.classList.add('expanded');
    }
}

let activeMatchContext = null;

function openReviewModal(customerPartNumber, supplierPartNumber) {
    let group = null;
    let match = null;
    let gIndex = -1;
    let mIndex = -1;

    for (let i = 0; i < currentData.length; i++) {
        if (currentData[i].customer_part_number === customerPartNumber) {
            group = currentData[i];
            gIndex = i;
            for (let j = 0; j < group.matches.length; j++) {
                if (group.matches[j].supplier_part_number === supplierPartNumber) {
                    match = group.matches[j];
                    mIndex = j;
                    break;
                }
            }
            break;
        }
    }

    if (!match) return;

    activeMatchContext = { gIndex, mIndex, match };
    
    const modalBody = document.getElementById('modal-body');
    const template = document.getElementById('review-card-template');
    const content = template.content.cloneNode(true);
    
    // Fill data
    content.querySelector('.cpn-title').textContent = match.customer_part_number;
    content.querySelector('.spn-title').textContent = match.supplier_part_number;
    
    content.querySelector('.cpn-text').textContent = match.customer_part_number;
    content.querySelector('.spn-text').textContent = match.supplier_part_number;
    
    const generateDetailsHTML = (desc, attrs) => {
        let html = `
            <div class="detail-row">
                <span class="detail-label">Description</span>
                <span class="detail-value">${desc || 'N/A'}</span>
            </div>
        `;
        
        if (attrs) {
            for (const [key, value] of Object.entries(attrs)) {
                if (value) {
                    const formattedKey = key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                    html += `
                        <div class="detail-row">
                            <span class="detail-label">${formattedKey}</span>
                            <span class="detail-value">${value}</span>
                        </div>
                    `;
                }
            }
        }
        return html;
    };
    
    // Add descriptions and attributes
    content.querySelectorAll('.part-details')[0].innerHTML = generateDetailsHTML(match.customer_description, match.c_attributes);
    content.querySelectorAll('.part-details')[1].innerHTML = generateDetailsHTML(match.supplier_description, match.s_attributes);
    
    // Confidence Badge Calculation
    const badge = content.querySelector('.confidence-badge');
    const rrfScore = match.rrf_score || 0;
    
    let confidenceClass = 'low';
    let confidenceText = 'Low Confidence';
    
    // Using empirical RRF thresholds typically > 0.08 is extremely high. 
    if (rrfScore >= 0.08) {
        confidenceClass = 'high';
        confidenceText = 'High Confidence';
    } else if (rrfScore >= 0.03) {
        confidenceClass = 'medium';
        confidenceText = 'Medium Confidence';
    }
    
    badge.className = `confidence-badge ${confidenceClass}`;
    badge.textContent = confidenceText;
    
    // AI Reasoning parsing - ensuring the text matches the raw value
    content.querySelector('.reasoning-text').textContent = match.reasoning || "No reasoning extracted from model for this match.";
    
    modalBody.innerHTML = '';
    modalBody.appendChild(content);
    
    document.getElementById('review-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('review-modal').classList.remove('active');
    activeMatchContext = null;
}

async function handleDecision(isMatch) {
    if (!activeMatchContext) return;
    const { gIndex, mIndex, match } = activeMatchContext;
    
    const decisionText = isMatch ? 'ACCEPTED' : 'REJECTED';
    
    try {
        const response = await fetch('/api/decide', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                customer_part_number: match.customer_part_number,
                supplier_part_number: match.supplier_part_number,
                decision: decisionText,
                is_match: isMatch,
                reasoning: match.reasoning
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Remove the match from local state
        currentData[gIndex].matches.splice(mIndex, 1);
        
        // If no more matches in that group, remove the group
        if (currentData[gIndex].matches.length === 0) {
            currentData.splice(gIndex, 1);
        }
        
        closeModal();
        renderList();
        
        // Update count for the entire dataset
        document.getElementById('total-groups-count').textContent = 
            currentData ? `${currentData.length} parts in queue` : "0 parts in queue";
        
    } catch (error) {
        console.error('Error submitting decision:', error);
        alert(`Failed to submit decision: ${error.message}`);
    }
}

// --- Gemini Integration ---

async function handleGeminiCommand() {
    const geminiInput = document.getElementById('gemini-input');
    const command = geminiInput.value.trim();
    if (!command) return;
    
    const submitBtn = document.getElementById('gemini-submit');
    geminiInput.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    try {
        const response = await fetch('/api/gemini_command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        
        if (!response.ok) throw new Error("Failed to process command.");
        const result = await response.json();
        
        showGeminiResponse(result.message);
        
        if (result.action === 'filter_list') {
            currentSqlFilter = result.sql_filter;
            await fetchMatches();
        } else if (result.action === 'bulk_accept' || result.action === 'bulk_reject') {
            const isMatch = result.action === 'bulk_accept';
            const actionText = isMatch ? 'ACCEPT' : 'REJECT';
            if (confirm(`Are you sure you want to ${actionText} all remaining matches that match your command?`)) {
                await executeBulkDecision(isMatch, result.sql_filter || currentSqlFilter);
            }
        } else if (result.action === 'clear_filter') {
            clearGeminiFilter();
        }
        
    } catch (e) {
        showGeminiResponse(`Error: ${e.message}`);
    } finally {
        geminiInput.disabled = false;
        geminiInput.value = '';
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        geminiInput.focus();
    }
}

function showGeminiResponse(msg) {
    const bubble = document.getElementById('gemini-response-bubble');
    document.getElementById('gemini-response-text').innerHTML = `<i class="fas fa-sparkles"></i> ${msg}`;
    bubble.classList.remove('hidden');
}

function clearGeminiFilter() {
    currentSqlFilter = null;
    document.getElementById('gemini-response-bubble').classList.add('hidden');
    document.getElementById('gemini-input').value = '';
    fetchMatches();
}

async function executeBulkDecision(isMatch, sqlFilter) {
    try {
        const response = await fetch('/api/bulk_decide', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                decision: isMatch ? 'ACCEPTED' : 'REJECTED',
                is_match: isMatch,
                sql_filter: sqlFilter
            })
        });
        if (!response.ok) throw new Error("Failed bulk update");
        
        await fetchMatches();
        showGeminiResponse(`Successfully completed bulk updates.`);
    } catch (e) {
        showGeminiResponse(`Error during bulk update: ${e.message}`);
    }
}
