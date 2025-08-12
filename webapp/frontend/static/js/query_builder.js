// Query builder specific functionality

class QueryBuilder {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.setupQueryBuilder();
    }
    
    setupQueryBuilder() {
        // Add quick date range buttons
        this.addDateRangeButtons();
        
        // Add dimension/metric search
        this.addSearchFilters();
        
        // Add validation
        this.addValidation();
    }
    
    addDateRangeButtons() {
        const dateGroup = document.querySelector('.date-inputs');
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'date-presets';
        buttonContainer.style.marginTop = '10px';
        buttonContainer.style.display = 'flex';
        buttonContainer.style.gap = '5px';
        buttonContainer.style.flexWrap = 'wrap';
        
        const presets = [
            { label: 'Today', days: 0 },
            { label: 'Yesterday', days: 1 },
            { label: 'Last 7 days', days: 7 },
            { label: 'Last 30 days', days: 30 },
            { label: 'Last 90 days', days: 90 }
        ];
        
        presets.forEach(preset => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn-date-preset';
            button.textContent = preset.label;
            button.style.cssText = `
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #ddd;
                background: #f8f9fa;
                border-radius: 3px;
                cursor: pointer;
            `;
            
            button.addEventListener('click', () => {
                const endDate = new Date();
                const startDate = new Date(endDate.getTime() - preset.days * 24 * 60 * 60 * 1000);
                
                document.getElementById('endDate').value = endDate.toISOString().split('T')[0];
                document.getElementById('startDate').value = startDate.toISOString().split('T')[0];
            });
            
            buttonContainer.appendChild(button);
        });
        
        dateGroup.parentNode.appendChild(buttonContainer);
    }
    
    addSearchFilters() {
        // Add search for dimensions
        this.addSelectSearch('dimensionsSelect', 'Search dimensions...');
        
        // Add search for metrics
        this.addSelectSearch('metricsSelect', 'Search metrics...');
        
        // Add search for properties
        this.addSelectSearch('propertiesSelect', 'Search properties...');
    }
    
    addSelectSearch(selectId, placeholder) {
        const select = document.getElementById(selectId);
        const container = select.parentNode;
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = placeholder;
        searchInput.style.marginBottom = '5px';
        
        container.insertBefore(searchInput, select);
        
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const options = select.querySelectorAll('option');
            
            options.forEach(option => {
                const text = option.textContent.toLowerCase();
                const visible = text.includes(searchTerm);
                option.style.display = visible ? '' : 'none';
            });
            
            // Handle optgroups
            const optgroups = select.querySelectorAll('optgroup');
            optgroups.forEach(optgroup => {
                const visibleOptions = Array.from(optgroup.children).some(option => 
                    option.style.display !== 'none'
                );
                optgroup.style.display = visibleOptions ? '' : 'none';
            });
        });
    }
    
    addValidation() {
        const form = document.querySelector('.query-builder');
        
        // Real-time validation
        form.addEventListener('change', () => {
            this.validateForm();
        });
        
        // Validate before submission
        document.getElementById('executeQuery').addEventListener('click', (e) => {
            if (!this.validateForm()) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    }
    
    validateForm() {
        const errors = [];
        
        // Check date range
        const startDate = new Date(document.getElementById('startDate').value);
        const endDate = new Date(document.getElementById('endDate').value);
        
        if (startDate > endDate) {
            errors.push('Start date must be before end date');
        }
        
        if (endDate > new Date()) {
            errors.push('End date cannot be in the future');
        }
        
        // Check if at least one source is selected
        const sources = this.dashboard.getSelectedSources();
        if (sources.length === 0) {
            errors.push('Please select at least one data source');
        }
        
        // Check dimensions and metrics
        const dimensions = document.getElementById('dimensionsSelect').selectedOptions.length;
        const metrics = document.getElementById('metricsSelect').selectedOptions.length;
        
        if (dimensions === 0) {
            errors.push('Please select at least one dimension');
        }
        
        if (metrics === 0) {
            errors.push('Please select at least one metric');
        }
        
        // Display validation errors
        this.displayValidationErrors(errors);
        
        return errors.length === 0;
    }
    
    displayValidationErrors(errors) {
        // Remove existing error display
        const existingErrors = document.querySelector('.validation-errors');
        if (existingErrors) {
            existingErrors.remove();
        }
        
        if (errors.length === 0) return;
        
        const errorContainer = document.createElement('div');
        errorContainer.className = 'validation-errors';
        errorContainer.style.cssText = `
            background: #ffebee;
            border: 1px solid #e57373;
            border-radius: 4px;
            padding: 10px;
            margin: 10px 0;
            color: #c62828;
        `;
        
        const errorList = document.createElement('ul');
        errorList.style.margin = '0';
        errorList.style.paddingLeft = '20px';
        
        errors.forEach(error => {
            const errorItem = document.createElement('li');
            errorItem.textContent = error;
            errorList.appendChild(errorItem);
        });
        
        errorContainer.appendChild(errorList);
        document.querySelector('.button-group').parentNode.insertBefore(
            errorContainer, 
            document.querySelector('.button-group')
        );
    }
    
    // Helper method to get form data
    getFormData() {
        return {
            startDate: document.getElementById('startDate').value,
            endDate: document.getElementById('endDate').value,
            sources: this.dashboard.getSelectedSources(),
            dimensions: Array.from(document.getElementById('dimensionsSelect').selectedOptions)
                .map(option => option.value),
            metrics: Array.from(document.getElementById('metricsSelect').selectedOptions)
                .map(option => option.value),
            properties: Array.from(document.getElementById('propertiesSelect').selectedOptions)
                .map(option => option.value),
            authIdentifier: document.getElementById('authIdentifier').value,
            sortField: document.getElementById('sortField').value,
            sortOrder: document.getElementById('sortOrder').value,
            limit: document.getElementById('limitResults').value
        };
    }
    
    // Helper method to set form data
    setFormData(data) {
        if (data.startDate) document.getElementById('startDate').value = data.startDate;
        if (data.endDate) document.getElementById('endDate').value = data.endDate;
        if (data.authIdentifier) document.getElementById('authIdentifier').value = data.authIdentifier;
        if (data.sortField) document.getElementById('sortField').value = data.sortField;
        if (data.sortOrder) document.getElementById('sortOrder').value = data.sortOrder;
        if (data.limit) document.getElementById('limitResults').value = data.limit;
        
        // Set sources
        if (data.sources) {
            document.getElementById('sourceGA4').checked = data.sources.includes('ga4');
            document.getElementById('sourceGSC').checked = data.sources.includes('gsc');
        }
        
        // Set multi-selects
        if (data.dimensions) {
            this.setMultiSelectValues('dimensionsSelect', data.dimensions);
        }
        
        if (data.metrics) {
            this.setMultiSelectValues('metricsSelect', data.metrics);
        }
        
        if (data.properties) {
            this.setMultiSelectValues('propertiesSelect', data.properties);
        }
    }
    
    setMultiSelectValues(selectId, values) {
        const select = document.getElementById(selectId);
        Array.from(select.options).forEach(option => {
            option.selected = values.includes(option.value);
        });
    }
}

// Initialize query builder when dashboard is ready
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (window.dashboard) {
            window.queryBuilder = new QueryBuilder(window.dashboard);
        }
    }, 100);
});