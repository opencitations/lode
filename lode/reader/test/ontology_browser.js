/**
 * Ontology Browser Scripts
 * Interactive functionality for RDF visualization
 */

/**
 * Toggle accordion per visualizzazione RDF triples
 * @param {string} id - ID del contenitore accordion
 */
function toggleAccordion(id) {
    const content = document.getElementById(id);
    const button = content.previousElementSibling;
    
    if (content.classList.contains('open')) {
        content.classList.remove('open');
        button.classList.remove('active');
    } else {
        content.classList.add('open');
        button.classList.add('active');
    }
}

/**
 * Smooth scroll to element
 * @param {string} elementId - ID dell'elemento target
 */
function smoothScrollTo(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
        });
    }
}

// Initialize page functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log('Ontology Browser loaded');
    
    // Add click handlers for navigation links
    document.querySelectorAll('.nav a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            smoothScrollTo(targetId);
        });
    });
});
