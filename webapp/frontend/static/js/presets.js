// Presets functionality

class PresetManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.presets = [];
        this.setupPresets();
    }
    
    setupPresets() {
        // Load preset button
        document.getElementById('loadPreset').addEventListener('click', () => this.showPresets());
        
        // Close presets button
        document.getElementById('closePresets').addEventListener('click', () => this.hidePresets());
        
        // Load presets from API
        this.loadPresets();
    }
    
    async loadPresets() {
        try {
            const response = await fetch('/api/presets');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.presets = await response.json();
        } catch (error) {
            console.error('Error loading presets:', error);
            this.dashboard.showStatus(`Error loading presets: ${error.message}`, 'error');
        }
    }
    
    showPresets() {
        if (this.presets.length === 0) {
            this.dashboard.showStatus('No presets available', 'info');
            return;
        }
        
        document.getElementById('presetsSection').style.display = 'block';
        this.renderPresets();
    }
    
    hidePresets() {
        document.getElementById('presetsSection').style.display = 'none';
    }
    
    renderPresets() {
        const container = document.getElementById('presetsList');
        container.innerHTML = '';
        
        // Group presets by category
        const categories = {};
        this.presets.forEach(preset => {
            const category = preset.category || 'general';
            if (!categories[category]) {
                categories[category] = [];
            }
            categories[category].push(preset);
        });
        
        // Render each category
        Object.keys(categories).forEach(category => {
            const categoryHeader = document.createElement('h4');
            categoryHeader.textContent = category.charAt(0).toUpperCase() + category.slice(1);
            categoryHeader.style.cssText = 'margin: 20px 0 10px 0; color: #667eea; border-bottom: 1px solid #eee; padding-bottom: 5px;';
            container.appendChild(categoryHeader);
            
            categories[category].forEach(preset => {
                this.renderPresetItem(container, preset);
            });
        });
    }
    
    renderPresetItem(container, preset) {
        const item = document.createElement('div');
        item.className = 'preset-item';
        
        const title = document.createElement('h4');
        title.textContent = preset.name;
        
        const description = document.createElement('p');
        description.textContent = preset.description;
        
        const category = document.createElement('span');
        category.className = 'preset-category';
        category.textContent = preset.category || 'general';
        
        const details = document.createElement('div');
        details.style.cssText = 'margin-top: 8px; font-size: 12px; color: #666;';
        
        const sourcesText = preset.query.sources.map(s => s.toUpperCase()).join(', ');
        const dimensionsText = preset.query.dimensions.slice(0, 3).join(', ') + 
            (preset.query.dimensions.length > 3 ? '...' : '');
        const metricsText = preset.query.metrics.slice(0, 3).join(', ') + 
            (preset.query.metrics.length > 3 ? '...' : '');
        
        details.innerHTML = `
            <strong>Sources:</strong> ${sourcesText}<br>
            <strong>Dimensions:</strong> ${dimensionsText}<br>
            <strong>Metrics:</strong> ${metricsText}
        `;
        
        item.appendChild(title);
        item.appendChild(description);
        item.appendChild(category);
        item.appendChild(details);
        
        item.addEventListener('click', () => {
            this.loadPreset(preset);
        });
        
        container.appendChild(item);
    }
    
    loadPreset(preset) {
        // Update form with preset data
        this.dashboard.clearForm();
        
        // Set basic fields
        document.getElementById('startDate').value = preset.query.start_date;
        document.getElementById('endDate').value = preset.query.end_date;
        document.getElementById('authIdentifier').value = preset.query.auth_identifier || '';
        
        // Set sources
        document.getElementById('sourceGA4').checked = preset.query.sources.includes('ga4');
        document.getElementById('sourceGSC').checked = preset.query.sources.includes('gsc');
        
        // Update form fields based on selected sources
        this.dashboard.updateFormFields();
        
        // Wait a bit for form fields to update, then set selections
        setTimeout(() => {
            // Set dimensions
            this.setMultiSelectValues('dimensionsSelect', preset.query.dimensions);
            
            // Set metrics
            this.setMultiSelectValues('metricsSelect', preset.query.metrics);
            
            // Set properties if specified
            if (preset.query.properties) {
                this.setMultiSelectValues('propertiesSelect', preset.query.properties);
            }
            
            // Set sorting
            if (preset.query.sort && preset.query.sort.length > 0) {
                document.getElementById('sortField').value = preset.query.sort[0].field || '';
                document.getElementById('sortOrder').value = preset.query.sort[0].order || 'desc';
            }
            
            // Set limit
            if (preset.query.limit) {
                document.getElementById('limitResults').value = preset.query.limit;
            }
            
            // Hide presets panel
            this.hidePresets();
            
            // Show success message
            this.dashboard.showStatus(`Loaded preset: ${preset.name}`, 'success');
            
        }, 500);
    }
    
    setMultiSelectValues(selectId, values) {
        const select = document.getElementById(selectId);
        Array.from(select.options).forEach(option => {
            option.selected = values.includes(option.value);
        });
    }
    
    async saveCurrentAsPreset() {
        // Get current form state
        const formData = window.queryBuilder ? window.queryBuilder.getFormData() : null;
        
        if (!formData || formData.dimensions.length === 0 || formData.metrics.length === 0) {
            this.dashboard.showStatus('Please configure a query before saving as preset', 'error');
            return;
        }
        
        // Prompt for preset details
        const name = prompt('Enter preset name:');
        if (!name) return;
        
        const description = prompt('Enter preset description:');
        if (!description) return;
        
        const category = prompt('Enter preset category (optional):', 'custom') || 'custom';
        
        // Create preset object
        const preset = {
            id: this.generatePresetId(name),
            name: name,
            description: description,
            category: category,
            query: {
                start_date: formData.startDate,
                end_date: formData.endDate,
                sources: formData.sources,
                dimensions: formData.dimensions,
                metrics: formData.metrics,
                auth_identifier: formData.authIdentifier,
                properties: formData.properties.length > 0 ? formData.properties : null,
                sort: formData.sortField ? [{
                    field: formData.sortField,
                    order: formData.sortOrder
                }] : null,
                limit: formData.limit ? parseInt(formData.limit) : null
            }
        };
        
        try {
            const response = await fetch('/api/presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(preset)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            await this.loadPresets(); // Reload presets
            this.dashboard.showStatus(`Preset "${name}" saved successfully`, 'success');
            
        } catch (error) {
            console.error('Error saving preset:', error);
            this.dashboard.showStatus(`Error saving preset: ${error.message}`, 'error');
        }
    }
    
    generatePresetId(name) {
        return name.toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '');
    }
    
    // Add save preset button to the UI
    addSavePresetButton() {
        const buttonGroup = document.querySelector('.button-group');
        
        const saveButton = document.createElement('button');
        saveButton.type = 'button';
        saveButton.className = 'btn btn-secondary';
        saveButton.textContent = 'Save Preset';
        saveButton.addEventListener('click', () => this.saveCurrentAsPreset());
        
        buttonGroup.appendChild(saveButton);
    }
}

// Initialize preset manager when dashboard is ready
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (window.dashboard) {
            window.presetManager = new PresetManager(window.dashboard);
            window.presetManager.addSavePresetButton();
        }
    }, 200);
});