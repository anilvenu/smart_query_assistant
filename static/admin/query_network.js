// Global variables
let graph = { nodes: [], links: [] };
let simulation;
let svg, g;
let width, height;
let tooltip;
let searchResults = [];
let selectedNode = null;

// Color schemes for different categories
const colorSchemes = {
    tables: d3.scaleOrdinal([
        "#E4EBF5", // Lightest blue
        "#C5D0E5", 
        "#A6B4D5",
        "#8799C4",
        "#677EB4",
        "#4863A3",
        "#294793",
        "#202C45"  // Darkest blue
    ]),
    
    connections: d3.scaleQuantize()
        .range([
            "#E4EBF5", // Lightest blue
            "#C5D0E5", 
            "#A6B4D5",
            "#8799C4",
            "#677EB4",
            "#4863A3",
            "#294793",
            "#202C45"  // Darkest blue
        ])
};

// Initialize the network visualization
document.addEventListener('DOMContentLoaded', function() {
    // Set up modal
    const modal = document.getElementById('network-modal');
    const viewNetworkBtn = document.getElementById('view-network-btn');
    const closeBtn = document.querySelector('.modal-content .close');
    
    // Open modal
    viewNetworkBtn.addEventListener('click', function() {
        modal.style.display = 'block';
        initializeGraph();
    });
    
    // Close modal
    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });
    
    // Close when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Set up search
    const searchInput = document.getElementById('graph-search');
    searchInput.addEventListener('input', searchNodes);
    
    // Set up coloring options
    const colorBySelect = document.getElementById('color-by');
    colorBySelect.addEventListener('change', updateNodeColors);
    
    // Reset button
    document.getElementById('reset-graph').addEventListener('click', resetGraph);
    
    // View node button
    document.getElementById('view-node-btn').addEventListener('click', function() {
        if (selectedNode) {
            window.location.href = `/admin/verified_query/${selectedNode.id}`;
        }
    });
});

// Initialize the graph
async function initializeGraph() {
    // Set up the SVG container
    const container = document.getElementById('graph-container');
    container.innerHTML = '';
    
    width = container.clientWidth;
    height = container.clientHeight;
    
    svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // Add zoom behavior
    g = svg.append('g');
    
    svg.call(d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        }));
    
    // Create tooltip
    tooltip = d3.select('#graph-container')
        .append('div')
        .attr('class', 'tooltip')
        .style('opacity', 0)
        .style('position', 'absolute')
        .style('background', 'white')
        .style('border', '1px solid #ddd')
        .style('border-radius', '4px')
        .style('padding', '5px')
        .style('pointer-events', 'none');
    
    // Load data
    try {
        const response = await fetch('/api/query_network');
        const data = await response.json();
        
        graph = data;
        
        // Set up color scale based on connections
        const linkCounts = {};
        graph.nodes.forEach(node => { linkCounts[node.id] = 0; });
        
        graph.links.forEach(link => {
            linkCounts[link.source] = (linkCounts[link.source] || 0) + 1;
            linkCounts[link.target] = (linkCounts[link.target] || 0) + 1;
        });
        
        const maxConnections = Math.max(...Object.values(linkCounts));
        colorSchemes.connections.domain([0, maxConnections]);
        
        renderGraph();
    } catch (error) {
        console.error('Error loading graph data:', error);
        container.innerHTML = `<div class="error-message">Error loading graph: ${error.message}</div>`;
    }
}

// Render the graph
function renderGraph() {
    // Create links
    const links = g.selectAll('.link')
        .data(graph.links)
        .enter()
        .append('line')
        .attr('class', 'link')
        .attr('stroke-width', 1.5);
    
    // Create nodes
    const nodes = g.selectAll('.node')
        .data(graph.nodes)
        .enter()
        .append('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded));
    
    // Add circles to nodes
    nodes.append('circle')
        .attr('r', d => 5 + Math.sqrt(d.questionCount * 2))
        .attr('fill', d => getNodeColor(d));
    
    // Add text labels
    nodes.append('text')
        .attr('dx', 12)
        .attr('dy', '.35em')
        .text(d => d.name.length > 20 ? d.name.substring(0, 20) + '...' : d.name);
    
    // Node interactions
    nodes.on('mouseover', showTooltip)
         .on('mousemove', moveTooltip)
         .on('mouseout', hideTooltip)
         .on('click', selectNode);
    
    // Create simulation
    simulation = d3.forceSimulation(graph.nodes)
        .force('link', d3.forceLink(graph.links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => 15 + Math.sqrt(d.questionCount * 2)))
        .on('tick', ticked);
    
    function ticked() {
        links
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        nodes
            .attr('transform', d => `translate(${d.x},${d.y})`);
    }
}

// Drag functions
function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

// Tooltip functions
function showTooltip(event, d) {
    tooltip.transition()
        .duration(200)
        .style('opacity', .9);
    
    tooltip.html(`
        <strong>${d.name}</strong><br/>
        ID: ${d.id}<br/>
        Questions: ${d.questionCount}<br/>
        Tables: ${d.tables ? d.tables.join(', ') : 'None'}
    `)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 28) + 'px');
}

function moveTooltip(event) {
    tooltip
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 28) + 'px');
}

function hideTooltip() {
    tooltip.transition()
        .duration(500)
        .style('opacity', 0);
}

// Node selection
function selectNode(event, d) {
    // Highlight the selected node
    d3.selectAll('.node').classed('highlighted', false);
    d3.select(this).classed('highlighted', true);
    
    selectedNode = d;
    
    // Update the info panel
    const nodeInfo = document.getElementById('node-info');
    const nodeTitle = document.getElementById('node-title');
    const nodeDescription = document.getElementById('node-description');
    
    nodeTitle.textContent = d.name;
    nodeDescription.innerHTML = `
        <strong>ID:</strong> ${d.id}<br/>
        <strong>Tables:</strong> ${d.tables ? d.tables.join(', ') : 'None'}<br/>
        <strong>Questions:</strong> ${d.questionCount}
    `;
    
    nodeInfo.classList.remove('hidden');
}

// Update node colors based on selected attribute
function updateNodeColors() {
    const colorBy = document.getElementById('color-by').value;
    
    g.selectAll('.node circle')
        .transition()
        .duration(500)
        .attr('fill', d => getNodeColor(d, colorBy));
}

// Get color for a node based on selected attribute
function getNodeColor(d, colorAttribute) {
    colorAttribute = colorAttribute || document.getElementById('color-by').value;
    
    if (colorAttribute === 'none') {
        return '#779CCD'; // Default blue
    }
    
    if (colorAttribute === 'tables') {
        // Color by first table
        return d.tables && d.tables.length > 0 ? 
            colorSchemes.tables(d.tables[0]) : '#999';
    }
    
    if (colorAttribute === 'connections') {
        // Count links
        const linkCount = graph.links.filter(
            link => link.source.id === d.id || link.target.id === d.id
        ).length;
        
        return colorSchemes.connections(linkCount);
    }
    
    return '#779CCD'; // Default blue
}

// Search functions
function searchNodes() {
    const searchTerm = document.getElementById('graph-search').value.toLowerCase();
    
    if (!searchTerm) {
        hideSearchResults();
        resetHighlighting();
        return;
    }
    
    // Find matching nodes
    searchResults = graph.nodes.filter(node => 
        node.name.toLowerCase().includes(searchTerm) || 
        node.id.toLowerCase().includes(searchTerm)
    );
    
    if (searchResults.length > 0) {
        showSearchResults();
        highlightSearchResults();
    } else {
        hideSearchResults();
        resetHighlighting();
    }
}

function showSearchResults() {
    let resultsContainer = document.querySelector('.search-results');
    
    if (!resultsContainer) {
        resultsContainer = document.createElement('div');
        resultsContainer.className = 'search-results';
        document.getElementById('graph-container').appendChild(resultsContainer);
    }
    
    let html = '';
    searchResults.forEach(node => {
        html += `<div class="search-result-item" data-id="${node.id}">${node.name}</div>`;
    });
    
    resultsContainer.innerHTML = html;
    resultsContainer.classList.remove('hidden');
    
    // Add click event to result items
    document.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', function() {
            const nodeId = this.getAttribute('data-id');
            const node = graph.nodes.find(n => n.id === nodeId);
            
            if (node) {
                zoomToNode(node);
                highlightNode(node);
                selectNode(null, node);
            }
            
            hideSearchResults();
        });
    });
}

function hideSearchResults() {
    const resultsContainer = document.querySelector('.search-results');
    if (resultsContainer) {
        resultsContainer.classList.add('hidden');
    }
}

function highlightSearchResults() {
    // Dim all nodes first
    g.selectAll('.node')
        .transition()
        .duration(300)
        .style('opacity', 0.3);
    
    // Highlight matching nodes
    const searchIds = searchResults.map(n => n.id);
    
    g.selectAll('.node')
        .filter(d => searchIds.includes(d.id))
        .transition()
        .duration(300)
        .style('opacity', 1);
}

function resetHighlighting() {
    g.selectAll('.node')
        .transition()
        .duration(300)
        .style('opacity', 1);
}

function highlightNode(node) {
    g.selectAll('.node').classed('highlighted', false);
    
    g.selectAll('.node')
        .filter(d => d.id === node.id)
        .classed('highlighted', true);
}

function zoomToNode(node) {
    // Calculate zoom transform
    const scale = 2;
    const x = width / 2 - node.x * scale;
    const y = height / 2 - node.y * scale;
    
    svg.transition()
        .duration(750)
        .call(
            d3.zoom().transform,
            d3.zoomIdentity
                .translate(x, y)
                .scale(scale)
        );
}

// Reset the graph view
function resetGraph() {
    // Reset zoom transform
    svg.transition()
        .duration(750)
        .call(
            d3.zoom().transform,
            d3.zoomIdentity
        );
    
    // Reset the transform on the g element directly
    g.attr("transform", "translate(0,0) scale(1)");
    
    // Reset node positions in the simulation
    if (simulation) {
        simulation.alpha(0.3).restart();
        simulation.force('center', d3.forceCenter(width / 2, height / 2));
        
        // Reset fixed positions
        graph.nodes.forEach(node => {
            node.fx = null;
            node.fy = null;
        });
    }
    
    // Reset highlighting
    resetHighlighting();
    d3.selectAll('.node').classed('highlighted', false);
    
    // Hide node info
    document.getElementById('node-info').classList.add('hidden');
    selectedNode = null;
    
    // Reset search
    document.getElementById('graph-search').value = '';
    hideSearchResults();
    
    // Reset color
    document.getElementById('color-by').value = 'none';
    updateNodeColors();
}