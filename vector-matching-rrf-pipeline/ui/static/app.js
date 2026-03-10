let currentData = null;

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
});

async function fetchMatches() {
    try {
        const response = await fetch('/api/matches');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        currentData = data.groups;
        
        document.getElementById('total-groups-count').textContent = 
            currentData ? `${currentData.length} parts pending list` : "0 parts pending";
            
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
    
    const groupTemplate = document.getElementById('customer-group-template');
    const rowTemplate = document.getElementById('supplier-row-template');
    
    currentData.forEach((group, gIndex) => {
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
                openReviewModal(gIndex, mIndex);
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

function openReviewModal(gIndex, mIndex) {
    const group = currentData[gIndex];
    const match = group.matches[mIndex];
    activeMatchContext = { gIndex, mIndex, match };
    
    const modalBody = document.getElementById('modal-body');
    const template = document.getElementById('review-card-template');
    const content = template.content.cloneNode(true);
    
    // Fill data
    content.querySelector('.cpn-title').textContent = match.customer_part_number;
    content.querySelector('.spn-title').textContent = match.supplier_part_number;
    
    content.querySelector('.cpn-text').textContent = match.customer_part_number;
    content.querySelector('.spn-text').textContent = match.supplier_part_number;
    
    // Add descriptions
    content.querySelectorAll('.part-details')[0].innerHTML = `
        <div class="detail-row">
            <span class="detail-label">Desc</span>
            <span class="detail-value">${match.customer_description || 'N/A'}</span>
        </div>
    `;
    content.querySelectorAll('.part-details')[1].innerHTML = `
        <div class="detail-row">
            <span class="detail-label">Desc</span>
            <span class="detail-value">${match.supplier_description || 'N/A'}</span>
        </div>
    `;
    
    content.querySelector('.reasoning-text').textContent = match.reasoning || "No AI reasoning provided.";
    
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
        
        // Update count
        document.getElementById('total-groups-count').textContent = 
            currentData ? `${currentData.length} parts pending list` : "0 parts pending";
        
    } catch (error) {
        console.error('Error submitting decision:', error);
        alert(`Failed to submit decision: ${error.message}`);
    }
}
