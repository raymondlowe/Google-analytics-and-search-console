// Main JavaScript for GA4 & GSC Unified Dashboard

class Dashboard {
    constructor() {
        this.metadata = null;
        this.currentQueryId = null;
        this.pollInterval = null;
        
        this.init();
    }
    
    async init() {
        this.setupEventListeners();
        this.setDefaultDates();
        await this.loadMetadata();
        this.updateFormFields();
    }
    
    setupEventListeners() {
        // Query execution
        document.getElementById('executeQuery').addEventListener('click', () => this.executeQuery());
        document.getElementById('clearQuery').addEventListener('click', () => this.clearForm());
        
        // Export buttons
        document.getElementById('exportCSV').addEventListener('click', () => this.exportResults('csv'));
        document.getElementById('exportExcel').addEventListener('click', () => this.exportResults('xlsx'));
        
        // Source checkboxes
        document.getElementById('sourceGA4').addEventListener('change', () => this.updateFormFields());
        document.getElementById('sourceGSC').addEventListener('change', () => this.updateFormFields());
        
        // Auth identifier change
        document.getElementById('authIdentifier').addEventListener('change', () => this.loadProperties());
        
        // Credentials upload
        document.getElementById('uploadCredentialsBtn').addEventListener('click', () => this.openFileUpload());
        document.getElementById('credentialsUpload').addEventListener('change', (e) => this.uploadCredentials(e));
        
        // Cancel query button (will be added dynamically)
        document.addEventListener('click', (e) => {
            if (e.target && e.target.id === 'cancelQuery') {
                this.cancelQuery();
            }
        });
    }
    
    setDefaultDates() {
        const today = new Date();
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        
        // Use local date instead of UTC to avoid timezone conflicts
        const formatLocalDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };
        
        document.getElementById('endDate').value = formatLocalDate(today);
        document.getElementById('startDate').value = formatLocalDate(weekAgo);
    }
    
    async loadMetadata() {
        try {
            this.showStatus('Loading metadata...', 'info');
            const response = await fetch('/api/meta/all');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.metadata = await response.json();
            this.hideStatus();
        } catch (error) {
            console.error('Error loading metadata:', error);
            this.showStatus(`Error loading metadata: ${error.message}`, 'error');
        }
    }
    
    async loadProperties() {
        if (!this.metadata) return;
        
        const authIdentifier = document.getElementById('authIdentifier').value;
        
        try {
            const response = await fetch(`/api/meta/properties?auth_identifier=${encodeURIComponent(authIdentifier)}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const properties = await response.json();
            this.metadata.properties = properties;
            this.updatePropertiesSelect();
        } catch (error) {
            console.error('Error loading properties:', error);
            this.showStatus(`Error loading properties: ${error.message}`, 'error');
        }
    }
    
    updateFormFields() {
        if (!this.metadata) return;
        
        const selectedSources = this.getSelectedSources();
        
        this.updateDimensionsSelect(selectedSources);
        this.updateMetricsSelect(selectedSources);
        this.updatePropertiesSelect();
        this.updateSortOptions();
    }
    
    getSelectedSources() {
        const sources = [];
        if (document.getElementById('sourceGA4').checked) sources.push('ga4');
        if (document.getElementById('sourceGSC').checked) sources.push('gsc');
        return sources;
    }
    
    updateDimensionsSelect(sources) {
        const select = document.getElementById('dimensionsSelect');
        select.innerHTML = '';
        
        sources.forEach(source => {
            if (this.metadata.dimensions[source]) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = source.toUpperCase();
                
                this.metadata.dimensions[source].forEach(dim => {
                    const option = document.createElement('option');
                    option.value = dim.id;
                    option.textContent = `${dim.name} (${dim.category})`;
                    optgroup.appendChild(option);
                });
                
                select.appendChild(optgroup);
            }
        });
    }
    
    updateMetricsSelect(sources) {
        const select = document.getElementById('metricsSelect');
        select.innerHTML = '';
        
        sources.forEach(source => {
            if (this.metadata.metrics[source]) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = source.toUpperCase();
                
                this.metadata.metrics[source].forEach(metric => {
                    const option = document.createElement('option');
                    option.value = metric.id;
                    option.textContent = `${metric.name} (${metric.category})`;
                    optgroup.appendChild(option);
                });
                
                select.appendChild(optgroup);
            }
        });
    }
    
    updatePropertiesSelect() {
        const select = document.getElementById('propertiesSelect');
        select.innerHTML = '';

        const sources = this.getSelectedSources();

        sources.forEach(source => {
            if (this.metadata.properties && this.metadata.properties[source]) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = source.toUpperCase();

                let properties = this.metadata.properties[source];
                if (source === 'gsc') {
                    // Deduplicate by base domain, prefer https://www., then https://, then any
                    const domainMap = {};
                    properties.forEach(prop => {
                        // Extract base domain (strip protocol and www)
                        let url = prop.id;
                        let base = url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
                        if (!domainMap[base]) domainMap[base] = [];
                        domainMap[base].push(prop);
                    });
                    // For each base, pick best available: https://www. > https:// > anything
                    properties = Object.values(domainMap).map(props => {
                        let best = props.find(p => p.id.startsWith('https://www.'));
                        if (!best) best = props.find(p => p.id.startsWith('https://'));
                        if (!best) best = props[0];
                        return best;
                    });
                }

                properties.forEach(prop => {
                    const option = document.createElement('option');
                    option.value = prop.id;
                    option.textContent = prop.display_name || prop.name;
                    option.selected = true; // Select all by default
                    optgroup.appendChild(option);
                });

                select.appendChild(optgroup);
            }
        });
    }
    
    updateSortOptions() {
        const select = document.getElementById('sortField');
        const currentValue = select.value;
        select.innerHTML = '<option value="">No sorting</option>';
        
        const sources = this.getSelectedSources();
        
        sources.forEach(source => {
            if (this.metadata.metrics[source]) {
                this.metadata.metrics[source].forEach(metric => {
                    const option = document.createElement('option');
                    option.value = metric.id;
                    option.textContent = metric.name;
                    if (metric.id === currentValue) option.selected = true;
                    select.appendChild(option);
                });
            }
        });
    }
    
    async executeQuery() {
        const query = this.buildQuery();
        if (!query) return;
        try {
            this.showLoading();
            this.clearResults();
            const response = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(query)
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const result = await response.json();
            this.currentQueryId = result.query_id;
            this.showStatus(`Query ${result.query_id} started`, 'info');
            // Start polling for progress/results only (WebSocket removed)
            this.pollForResults();
        } catch (error) {
            console.error('Error executing query:', error);
            this.showStatus(`Error executing query: ${error.message}`, 'error');
            this.hideLoading();
        }
    }

    
    buildQuery() {
        const sources = this.getSelectedSources();
        if (sources.length === 0) {
            this.showStatus('Please select at least one data source', 'error');
            return null;
        }
        
        const dimensions = Array.from(document.getElementById('dimensionsSelect').selectedOptions)
            .map(option => option.value);
        
        const metrics = Array.from(document.getElementById('metricsSelect').selectedOptions)
            .map(option => option.value);
            
        if (dimensions.length === 0) {
            this.showStatus('Please select at least one dimension', 'error');
            return null;
        }
        
        if (metrics.length === 0) {
            this.showStatus('Please select at least one metric', 'error');
            return null;
        }
        
        const properties = Array.from(document.getElementById('propertiesSelect').selectedOptions)
            .map(option => option.value);
        
        const query = {
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
            sources: sources,
            dimensions: dimensions,
            metrics: metrics,
            auth_identifier: document.getElementById('authIdentifier').value,
            debug: document.getElementById('debugMode').checked
        };
        
        if (properties.length > 0) {
            query.properties = properties;
        }
        
        const sortField = document.getElementById('sortField').value;
        if (sortField) {
            query.sort = [{
                field: sortField,
                order: document.getElementById('sortOrder').value
            }];
        }
        
        const limit = document.getElementById('limitResults').value;
        if (limit) {
            query.limit = parseInt(limit);
        }
        
        return query;
    }
    
    async pollForResults() {
        if (!this.currentQueryId) return;
        
        this.pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/query/${this.currentQueryId}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const result = await response.json();
                
                // Update progress indicator
                if (result.progress) {
                    this.updateProgress(result.progress);
                }
                
                if (result.status === 'completed') {
                    clearInterval(this.pollInterval);
                    this.hideLoading();
                    this.displayResults(result);
                    
                    const cacheStatus = result.cache_hit ? ' (cached)' : '';
                    this.showStatus(
                        `Query completed: ${result.row_count} rows in ${Math.round(result.execution_time_ms)}ms${cacheStatus}`,
                        'success'
                    );
                    
                } else if (result.status === 'failed') {
                    clearInterval(this.pollInterval);
                    this.hideLoading();
                    this.showStatus(`Query failed: ${result.error}`, 'error');
                    
                } else if (result.status === 'cancelled') {
                    clearInterval(this.pollInterval);
                    this.hideLoading();
                    this.showStatus('Query was cancelled', 'info');
                    
                } else if (result.status === 'running' || result.status === 'queued') {
                    // Show cancel button if cancellation is supported
                    if (result.can_cancel) {
                        this.showCancelButton();
                    }
                }
                
            } catch (error) {
                console.error('Error polling for results:', error);
                clearInterval(this.pollInterval);
                this.hideLoading();
                this.showStatus(`Error getting results: ${error.message}`, 'error');
            }
        }, 1000);
    }
    
    displayResults(result) {
        const container = document.getElementById('resultsContainer');
        
        if (!result.data || result.data.length === 0) {
            container.innerHTML = '<div class="no-results"><p>No results found.</p></div>';
            return;
        }
        
        // Update results info with pagination awareness
        const totalRows = result.row_count || result.data.length;
        const displayedRows = result.data.length;
        let resultsText = `${totalRows} total rows`;
        
        if (totalRows > displayedRows) {
            resultsText += ` (showing first ${displayedRows})`;
        }
        
        resultsText += ` • ${Math.round(result.execution_time_ms)}ms • Sources: ${result.sources_queried.join(', ')}`;
        
        document.getElementById('resultsInfo').textContent = resultsText;
        
        // Show pagination info if needed
        if (totalRows > displayedRows) {
            const paginationInfo = document.createElement('div');
            paginationInfo.className = 'pagination-info';
            paginationInfo.innerHTML = `
                <p><strong>Note:</strong> Showing first ${displayedRows} rows of ${totalRows} total. 
                <button id="loadAllResults" class="btn btn-secondary">Load All Results</button>
                or use Export to download complete dataset.</p>
            `;
            container.appendChild(paginationInfo);
            
            // Add event listener for loading all results
            document.getElementById('loadAllResults').addEventListener('click', () => this.loadAllResults());
        }
        
        // Show export buttons
        document.getElementById('exportButtons').style.display = 'flex';
        
        // Create table
        const table = document.createElement('table');
        table.className = 'results-table';
        
        // Create header
        const headers = Object.keys(result.data[0]);
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        headers.forEach((header, index) => {
            const th = document.createElement('th');
            th.textContent = header;
            th.style.cursor = 'pointer';
            th.style.userSelect = 'none';
            th.className = 'sortable-header';
            th.title = `Click to sort by ${header}`;
            
            // Add sort indicator
            const sortIcon = document.createElement('span');
            sortIcon.className = 'sort-icon';
            sortIcon.innerHTML = ' ⇅'; // Up-down arrow
            th.appendChild(sortIcon);
            
            // Add click handler for sorting
            th.addEventListener('click', () => this.sortTable(table, index, header));
            
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        
        result.data.forEach(row => {
            const tr = document.createElement('tr');
            
            headers.forEach(header => {
                const td = document.createElement('td');
                let value = row[header];
                
                // Format special columns
                if (header === '_source') {
                    const badge = document.createElement('span');
                    badge.className = `source-badge source-${value}`;
                    badge.textContent = value.toUpperCase();
                    td.appendChild(badge);
                } else {
                    // Format numbers to avoid scientific notation
                    if (typeof value === 'number') {
                        if (value % 1 === 0) {
                            // Integer formatting
                            value = value.toLocaleString();
                        } else {
                            // Always use fixed-point decimal, up to 8 decimals, never e-notation
                            value = value.toFixed(8).replace(/\.?0+$/, '');
                        }
                    }
                    td.textContent = value || '';
                }
                
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        container.innerHTML = '';
        container.appendChild(table);
    }
    
    sortTable(table, columnIndex, columnName) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const headers = table.querySelectorAll('th');
        
        // Determine current sort direction
        const currentHeader = headers[columnIndex];
        const currentDirection = currentHeader.getAttribute('data-sort-direction') || 'none';
        let newDirection = 'asc';
        
        if (currentDirection === 'asc') {
            newDirection = 'desc';
        } else if (currentDirection === 'desc') {
            newDirection = 'asc';
        }
        
        // Clear all sort indicators
        headers.forEach(header => {
            header.removeAttribute('data-sort-direction');
            const sortIcon = header.querySelector('.sort-icon');
            if (sortIcon) {
                sortIcon.innerHTML = ' ⇅';
            }
        });
        
        // Set new sort direction and icon
        currentHeader.setAttribute('data-sort-direction', newDirection);
        const sortIcon = currentHeader.querySelector('.sort-icon');
        if (sortIcon) {
            sortIcon.innerHTML = newDirection === 'asc' ? ' ↑' : ' ↓';
        }
        
        // Sort rows
        rows.sort((a, b) => {
            const aValue = a.cells[columnIndex].textContent.trim();
            const bValue = b.cells[columnIndex].textContent.trim();
            
            // Try to parse as numbers first
            const aNum = parseFloat(aValue.replace(/,/g, ''));
            const bNum = parseFloat(bValue.replace(/,/g, ''));
            
            let comparison = 0;
            if (!isNaN(aNum) && !isNaN(bNum)) {
                // Numeric comparison
                comparison = aNum - bNum;
            } else {
                // String comparison
                comparison = aValue.localeCompare(bValue);
            }
            
            return newDirection === 'asc' ? comparison : -comparison;
        });
        
        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    }
    
    async exportResults(format) {
        if (!this.currentQueryId) {
            this.showStatus('No query results to export', 'error');
            return;
        }
        
        try {
            const response = await fetch(`/api/query/${this.currentQueryId}/export/${format}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Create download link
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `query_${this.currentQueryId}.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showStatus(`Results exported as ${format.toUpperCase()}`, 'success');
            
        } catch (error) {
            console.error('Error exporting results:', error);
            this.showStatus(`Error exporting results: ${error.message}`, 'error');
        }
    }
    
    clearForm() {
        document.getElementById('dimensionsSelect').selectedIndex = -1;
        document.getElementById('metricsSelect').selectedIndex = -1;
        document.getElementById('propertiesSelect').selectedIndex = -1;
        document.getElementById('sortField').value = '';
        document.getElementById('limitResults').value = '';
        this.clearResults();
    }
    
    clearResults() {
        document.getElementById('resultsContainer').innerHTML = 
            '<div class="no-results"><p>Execute a query to see results here.</p></div>';
        document.getElementById('resultsInfo').textContent = '';
        document.getElementById('exportButtons').style.display = 'none';
        this.currentQueryId = null;
        // Clear progress and cancel button
        this.hideProgress();
        this.hideCancelButton();
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
    
    showLoading() {
        document.getElementById('loadingContainer').style.display = 'block';
        document.getElementById('resultsContainer').style.display = 'none';
    }
    
    hideLoading() {
        document.getElementById('loadingContainer').style.display = 'none';
        document.getElementById('resultsContainer').style.display = 'block';
        this.hideProgress();
        this.hideCancelButton();
    }
    
    showStatus(message, type = 'info') {
        const panel = document.getElementById('statusPanel');
        const content = document.getElementById('statusContent');
        
        content.textContent = message;
        panel.className = `status-panel ${type}`;
        panel.style.display = 'block';
        
        setTimeout(() => {
            panel.style.display = 'none';
        }, 5000);
    }
    
    hideStatus() {
        document.getElementById('statusPanel').style.display = 'none';
    }
    
    updateProgress(progress) {
        const progressContainer = document.getElementById('progressContainer');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        
        if (progress && progressContainer && progressBar && progressText) {
            const percentage = Math.round((progress.current / progress.total) * 100);
            progressBar.style.width = `${percentage}%`;
            
            // Enhanced progress text with percentage and step indicators
            const stepText = `${progress.current}/${progress.total}`;
            const message = progress.message || 'Processing...';
            progressText.textContent = `${message} (${stepText} - ${percentage}%)`;
            
            progressContainer.style.display = 'block';
        }
    }
    
    hideProgress() {
        const progressContainer = document.getElementById('progressContainer');
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }
    }
    
    showCancelButton() {
        const cancelButton = document.getElementById('cancelQuery');
        if (cancelButton) {
            cancelButton.style.display = 'inline-block';
        }
    }
    
    hideCancelButton() {
        const cancelButton = document.getElementById('cancelQuery');
        if (cancelButton) {
            cancelButton.style.display = 'none';
        }
    }
    
    async cancelQuery() {
        if (!this.currentQueryId) return;
        
        try {
            const response = await fetch(`/api/query/${this.currentQueryId}/cancel`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.showStatus('Query cancellation requested', 'info');
            this.hideCancelButton();
            
        } catch (error) {
            console.error('Error cancelling query:', error);
            this.showStatus(`Error cancelling query: ${error.message}`, 'error');
        }
    }
    
    openFileUpload() {
        document.getElementById('credentialsUpload').click();
    }
    
    async uploadCredentials(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const statusEl = document.getElementById('credentialsStatus');
        
        // Validate file type
        if (!file.name.endsWith('.json')) {
            statusEl.textContent = 'Please select a JSON file';
            statusEl.className = 'upload-status error';
            return;
        }
        
        // Validate file content
        try {
            const text = await file.text();
            const json = JSON.parse(text);
            
            // Basic validation for Google credentials
            if (!json.installed && !json.web) {
                throw new Error('Invalid Google credentials format');
            }
            
            statusEl.textContent = 'Uploading...';
            statusEl.className = 'upload-status';
            
            // Upload file to server
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/upload-credentials', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            statusEl.textContent = '✓ Credentials uploaded successfully';
            statusEl.className = 'upload-status success';
            
            // Refresh metadata to get updated properties
            await this.loadMetadata();
            this.updateFormFields();
            
        } catch (error) {
            console.error('Error uploading credentials:', error);
            statusEl.textContent = `Error: ${error.message}`;
            statusEl.className = 'upload-status error';
        }
        
        // Clear file input
        event.target.value = '';
    }
    
    async loadAllResults() {
        if (!this.currentQueryId) {
            this.showStatus('No query to load results for', 'error');
            return;
        }
        
        try {
            this.showStatus('Loading all results...', 'info');
            
            // Fetch paginated results to get all data
            let allData = [];
            let page = 1;
            const pageSize = 1000; // Large page size for efficiency
            let hasMore = true;
            
            while (hasMore) {
                const response = await fetch(`/api/query/${this.currentQueryId}/results?page=${page}&page_size=${pageSize}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const paginatedResult = await response.json();
                allData = allData.concat(paginatedResult.data);
                
                hasMore = paginatedResult.has_next;
                page++;
                
                // Update progress
                this.showStatus(`Loading results... ${allData.length} rows loaded`, 'info');
            }
            
            // Create a fake result object with all data
            const fullResult = {
                data: allData,
                row_count: allData.length,
                execution_time_ms: 0, // No execution time for loaded results
                sources_queried: ['cached'],
                cache_hit: true
            };
            
            // Display all results
            this.displayResults(fullResult);
            this.showStatus(`All ${allData.length} results loaded successfully`, 'success');
            
        } catch (error) {
            console.error('Error loading all results:', error);
            this.showStatus(`Error loading all results: ${error.message}`, 'error');
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});