/**
 * Network Visualization using D3.js
 * This script creates a force-directed graph visualization for relationships
 */

// Global variables
let graphInitialized = false;
let nodesData = [];
let linksData = [];
let simulation = null;
let svg = null;
let colorScale = d3.scaleOrdinal(d3.schemeCategory10);
let currentLayout = 'force';
let selectedNode = null; 

// Initialize the network graph
function initializeGraph() {
    // If already initialized, just return
    if (graphInitialized) return;
    
    console.log("Initializing network visualization...");
    
    // Get the container dimensions
    const container = document.getElementById('graph-container');
    if (!container) {
        console.error("Graph container not found");
        return;
    }
    
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    console.log(`Container dimensions: ${width}x${height}`);
    
    // Create SVG element
    svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');
    
    // Add zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.5, 5])
        .on('zoom', (event) => {
            svg.select('g.vis-container').attr('transform', event.transform);
        });
    
    svg.call(zoom);
    
    // Add a main container group for all visualization elements
    const visContainer = svg.append('g')
        .attr('class', 'vis-container');
    
    // Fetch network data
    console.log("Fetching network data...");
    
    d3.json('/api/query_network')
        .then(data => {
            console.log("Network data received:", data);
            
            if (!data || !data.nodes || !data.links) {
                console.error("Invalid data format received");
                return;
            }
            
            // Store data
            nodesData = data.nodes;
            linksData = data.links;
            
            // Add connection count to nodes
            nodesData.forEach(node => {
                node.connectionCount = 0;
            });
            
            linksData.forEach(link => {
                // Find source and target nodes
                const sourceNode = nodesData.find(n => n.id === link.source);
                const targetNode = nodesData.find(n => n.id === link.target);
                
                // Increment connection counts
                if (sourceNode) sourceNode.connectionCount = (sourceNode.connectionCount || 0) + 1;
                if (targetNode) targetNode.connectionCount = (targetNode.connectionCount || 0) + 1;
            });
            
            console.log("Links data before processing:", JSON.stringify(linksData.slice(0, 5)));

            linksData.forEach(link => {
                // Check if source/target are strings or objects
                if (typeof link.source === 'object') link.source = link.source.id;
                if (typeof link.target === 'object') link.target = link.target.id;
            });

            console.log("Links data after processing:", JSON.stringify(linksData.slice(0, 5)));


            // Create the force simulation
            simulation = d3.forceSimulation(nodesData)
                .force('link', d3.forceLink(linksData)
                    .id(d => d.id)
                    .distance(150))
                .force('charge', d3.forceManyBody()
                    .strength(-400))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('x', d3.forceX(width / 2).strength(0.1))
                .force('y', d3.forceY(height / 2).strength(0.1))
                .force('collision', d3.forceCollide().radius(d => calculateNodeSize(d) + 5));
            
            // Create links
            const links = visContainer.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(linksData)
            .enter()
            .append('line')
            .attr('stroke', '#999')
            .attr('stroke-opacity', 0.6)
            .attr('stroke-width', 1.5);
            
            // Create nodes
            const nodes = visContainer.append('g')
                .attr('class', 'nodes')
                .selectAll('.node')
                .data(nodesData)
                .enter()
                .append('g')
                .attr('class', 'node')
                .on('click', (event, d) => {
                    // Clear previous selection
                    d3.selectAll('.node').classed('selected', false);
                    
                    // Add selected class to the clicked node
                    d3.select(event.currentTarget).classed('selected', true);

                    // Show node info
                    showNodeInfo(d);

                    // Select node for layout
                    selectNodeForLayout(d);
                })
                .on('mouseover', function(event, d) {
                    d3.select(this).classed('highlighted', true);
                })
                .on('mouseout', function(event, d) {
                    d3.select(this).classed('highlighted', false);
                })
                .call(d3.drag()
                    .on('start', dragStarted)
                    .on('drag', dragging)
                    .on('end', dragEnded));
            
            // Add circles to nodes
            nodes.append('circle')
                .attr('r', d => calculateNodeSize(d))
                .attr('fill', d => getNodeColor(d, 'none'));
            
            // Add labels to nodes
            nodes.append('text')
                .attr('dy', 4)
                .text(d => d.name)
                .attr('stroke', 'none');
            
            // Update simulation on tick

            simulation.on('tick', () => {
                nodes.attr('transform', d => `translate(${d.x},${d.y})`);                
                links
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
            });
            
            // Set up search functionality
            setupSearch();
            
            // Set up color selection functionality
            setupColorBy();
            
            // Set up reset button
            setupResetButton(zoom);
            
            // Mark as initialized
            graphInitialized = true;
            console.log("Graph visualization initialized successfully");
        })
        .catch(error => {
            console.error("Error loading network data:", error);
        });

        setupLayoutToggle();
}

function setupLayoutToggle() {
    const layoutSelect = document.getElementById('layout-select');
    if (!layoutSelect) return;
    
    layoutSelect.addEventListener('change', () => {
      currentLayout = layoutSelect.value;
      updateLayout();
    });
}

// Calculate node size based on question count
function calculateNodeSize(node) {
    const baseSize = 10;
    const questionCount = node.questionCount || 0;
    return baseSize + (questionCount * 1.5);
}

// Get node color based on different criteria
function getNodeColor(node, colorBy) {
    const blueScale = d3.scaleThreshold()
        .domain([1, 3, 5])
        .range(['#E4EBF5', '#779CCD', '#405A8A']);
        
    const greenScale = d3.scaleThreshold()
        .domain([1, 3, 5])
        .range(['#E8F0E9', '#8AB391', '#5E9066']);
    
    switch(colorBy) {
        case 'tables':
            // Color by number of tables used
            const tableCount = (node.tables && node.tables.length) || 0;
            return blueScale(tableCount);
            
        case 'connections':
            // Color by number of connections
            const connectionCount = node.connectionCount || 0;
            return greenScale(connectionCount);
            
        case 'none':
        default:
            // Default blue color
            return '#779CCD';
    }
}

// Show details for the selected node
function showNodeInfo(node) {
    const nodeInfo = document.getElementById('node-info');
    const nodeTitle = document.getElementById('node-title');
    const nodeDescription = document.getElementById('node-description');
    const viewNodeBtn = document.getElementById('view-node-btn');
    
    nodeInfo.classList.remove('hidden');
    nodeTitle.textContent = node.name || 'Unknown query';
    
    let description = '';
    if (node.tables && node.tables.length > 0) {
        description += `Tables: ${node.tables.join(', ')}\n`;
    }
    
    description += `Questions: ${node.questionCount || 0} | Connections: ${node.connectionCount || 0}`;
    nodeDescription.textContent = description;
    
    // Set up view button to go to detail page
    viewNodeBtn.onclick = () => {
        window.open(`/admin/verified_query/${node.id}`, '_blank');
    };
}

// Setup search functionality
function setupSearch() {
    const searchInput = document.getElementById('graph-search');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', () => {
        const searchTerm = searchInput.value.toLowerCase();
        
        if (!searchTerm) {
            // Reset all nodes if search is cleared
            d3.selectAll('.node').classed('highlighted', false);
            return;
        }
        
        // Highlight matching nodes
        d3.selectAll('.node').classed('highlighted', d => 
            d.name.toLowerCase().includes(searchTerm) || 
            d.id.toLowerCase().includes(searchTerm)
        );
        
        // If there's exactly one match, show its info
        const matchingNodes = nodesData.filter(n => 
            n.name.toLowerCase().includes(searchTerm) || 
            n.id.toLowerCase().includes(searchTerm)
        );
        
        if (matchingNodes.length === 1) {
            showNodeInfo(matchingNodes[0]);
        }
    });
}

// Setup color selection dropdown
function setupColorBy() {
    const colorBySelect = document.getElementById('color-by');
    if (!colorBySelect) return;
    
    colorBySelect.addEventListener('change', () => {
        const colorBy = colorBySelect.value;
        
        // For each node, update a custom property instead of the fill attribute
        d3.selectAll('.node').each(function(d) {
            const color = getNodeColor(d, colorBy);
            // Set a custom property on the node element
            this.style.setProperty('--node-color', color);
        });
    });
}

// Setup reset button
function setupResetButton(zoom) {
    const resetBtn = document.getElementById('reset-graph');
    if (!resetBtn) return;
    
    resetBtn.addEventListener('click', () => {
        // Reset zoom
        svg.transition()
            .duration(750)
            .call(zoom.transform, d3.zoomIdentity);
            
        // Clear node selection
        d3.selectAll('.node').classed('selected', false);
        selectedNode = null;
        
        // Reset layout to force-directed
        currentLayout = 'force';
        document.getElementById('layout-select').value = 'force';
        
        // Update layout - this resets node positions
        updateLayout();
        
        // Reset search
        const searchInput = document.getElementById('graph-search');
        if (searchInput) {
            searchInput.value = '';
            d3.selectAll('.node').classed('highlighted', false);
        }
        
        // Reset color selection
        const colorBySelect = document.getElementById('color-by');
        if (colorBySelect) {
            colorBySelect.value = 'none';
            
            // Reset using CSS variables
            d3.selectAll('.node').each(function(d) {
                this.style.setProperty('--node-color', getNodeColor(d, 'none'));
            });
        }
        
        // Hide node info
        const nodeInfo = document.getElementById('node-info');
        if (nodeInfo) {
            nodeInfo.classList.add('hidden');
        }
    });
}

// Drag event handlers
function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragging(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}



function updateLayout() {
    // Stop current simulation
    if (simulation) simulation.stop();
    
    switch(currentLayout) {
      case 'radial':
        applyRadialLayout();
        break;
      case 'hierarchical':
        applyHierarchicalLayout();
        break;
      case 'clustered':
        applyClusteredLayout();
        break;
      case 'force':
      default:
        applyForceLayout();
        break;
    }
}
  
// Radial layout with selected node in center
function applyRadialLayout() {
    const width = document.getElementById('graph-container').clientWidth;
    const height = document.getElementById('graph-container').clientHeight;
    const center = { x: width / 2, y: height / 2 };
    
    // Get the selected node or use the first node
    const centerNode = selectedNode || nodesData[0];
    
    // Set position for center node
    centerNode.fx = center.x;
    centerNode.fy = center.y;
    
    // Arrange other nodes in a circle around the center
    const radius = Math.min(width, height) * 0.35;
    const angleStep = (2 * Math.PI) / (nodesData.length - 1);
    
    let angleIndex = 0;
    nodesData.forEach(node => {
      if (node !== centerNode) {
        const angle = angleIndex * angleStep;
        node.fx = center.x + radius * Math.cos(angle);
        node.fy = center.y + radius * Math.sin(angle);
        angleIndex++;
      }
    });
    
    // Create a gentle force to move nodes to their fixed positions
    simulation = d3.forceSimulation(nodesData)
      .force('link', d3.forceLink(linksData).id(d => d.id).distance(150))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(center.x, center.y))
      .alpha(0.3)
      .alphaDecay(0.02);
    
    // Update node and link positions on tick
    simulation.on('tick', () => {
      d3.selectAll('.node')
        .attr('transform', d => `translate(${d.x},${d.y})`);
      
      d3.selectAll('.links line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    });
    
    // After layout is complete, allow dragging
    simulation.on('end', () => {
      d3.selectAll('.node').each(d => {
        delete d.fx;
        delete d.fy;
      });
      
      if (centerNode) {
        delete centerNode.fx;
        delete centerNode.fy;
      }
    });
}
  
// Hierarchical layout
function applyHierarchicalLayout() {
    const width = document.getElementById('graph-container').clientWidth;
    const height = document.getElementById('graph-container').clientHeight;
    
    // Choose a root node (selected node or one with most connections)
    const rootNode = selectedNode || 
      nodesData.reduce((max, node) => 
        (node.connectionCount > (max ? max.connectionCount : 0)) ? node : max, null);
    
    // Create a hierarchical structure
    const hierarchyData = createHierarchy(rootNode);
    
    // Position nodes in a tree layout
    const treeLayout = d3.tree()
      .size([width * 0.9, height * 0.9])
      .nodeSize([40, 100]);
    
    const root = d3.hierarchy(hierarchyData);
    treeLayout(root);
    
    // Map positions back to our nodes
    const nodeMap = {};
    nodesData.forEach(node => nodeMap[node.id] = node);
    
    // Set positions from tree layout
    root.descendants().forEach(d => {
      const node = nodeMap[d.data.id];
      if (node) {
        node.fx = d.x + width / 2;
        node.fy = d.y + height * 0.1;
      }
    });
    
    // Create a gentle force to move nodes to their fixed positions
    simulation = d3.forceSimulation(nodesData)
      .force('link', d3.forceLink(linksData).id(d => d.id).distance(20))
      .force('charge', d3.forceManyBody().strength(-50))
      .alpha(0.3)
      .alphaDecay(0.02);
    
    // Update node and link positions on tick
    simulation.on('tick', () => {
      d3.selectAll('.node')
        .attr('transform', d => `translate(${d.x},${d.y})`);
      
      d3.selectAll('.links line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    });
    
    // After layout is complete, allow dragging
    simulation.on('end', () => {
      d3.selectAll('.node').each(d => {
        delete d.fx;
        delete d.fy;
      });
    });
}

// Helper function to create hierarchy data
function createHierarchy(rootNode) {
    const visited = new Set();
    
    function buildHierarchy(node) {
      if (!node || visited.has(node.id)) {
        return null;
      }
      
      visited.add(node.id);
      
      const children = [];
      linksData.forEach(link => {
        let childNode = null;
        
        if (link.source.id === node.id || link.source === node.id) {
          childNode = nodesData.find(n => n.id === (link.target.id || link.target));
        } else if (link.target.id === node.id || link.target === node.id) {
          childNode = nodesData.find(n => n.id === (link.source.id || link.source));
        }
        
        if (childNode && !visited.has(childNode.id)) {
          const childHierarchy = buildHierarchy(childNode);
          if (childHierarchy) {
            children.push(childHierarchy);
          }
        }
      });
      
      return {
        id: node.id,
        name: node.name,
        children: children.length > 0 ? children : null
      };
    }
    
    return buildHierarchy(rootNode);
}


// Clustered layout by tables
function applyClusteredLayout() {
    const width = document.getElementById('graph-container').clientWidth;
    const height = document.getElementById('graph-container').clientHeight;
    const center = { x: width / 2, y: height / 2 };
    
    // Group nodes by tables
    const tableGroups = {};
    
    nodesData.forEach(node => {
      // If node has no tables, put in "other" category
      const tableName = (node.tables && node.tables.length > 0) 
        ? node.tables[0] 
        : 'other';
      
      if (!tableGroups[tableName]) {
        tableGroups[tableName] = [];
      }
      
      tableGroups[tableName].push(node);
    });
    
    // Calculate positions for each group
    const tableNames = Object.keys(tableGroups);
    const angleStep = (2 * Math.PI) / tableNames.length;
    const clusterRadius = Math.min(width, height) * 0.35;
    
    tableNames.forEach((tableName, i) => {
      const angle = i * angleStep;
      const clusterX = center.x + clusterRadius * Math.cos(angle);
      const clusterY = center.y + clusterRadius * Math.sin(angle);
      
      const nodes = tableGroups[tableName];
      const nodeRadius = 120; // Radius for nodes within a cluster
      
      // Position nodes in a circle within their cluster
      const nodeAngleStep = (2 * Math.PI) / nodes.length;
      
      nodes.forEach((node, j) => {
        const nodeAngle = j * nodeAngleStep;
        node.fx = clusterX + nodeRadius * Math.cos(nodeAngle) * 0.5;
        node.fy = clusterY + nodeRadius * Math.sin(nodeAngle) * 0.5;
      });
    });
    
    // Create a gentle force to move nodes to their fixed positions
    simulation = d3.forceSimulation(nodesData)
      .force('link', d3.forceLink(linksData).id(d => d.id).distance(50))
      .force('charge', d3.forceManyBody().strength(-50))
      .force('center', d3.forceCenter(center.x, center.y))
      .alpha(0.3)
      .alphaDecay(0.02);
    
    // Update node and link positions on tick
    simulation.on('tick', () => {
      d3.selectAll('.node')
        .attr('transform', d => `translate(${d.x},${d.y})`);
      
      d3.selectAll('.links line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    });
    
    // After layout is complete, allow dragging
    simulation.on('end', () => {
      d3.selectAll('.node').each(d => {
        delete d.fx;
        delete d.fy;
      });
    });
}


// Regular force-directed layout
function applyForceLayout() {
    const width = document.getElementById('graph-container').clientWidth;
    const height = document.getElementById('graph-container').clientHeight;
    
    // Remove any fixed positions
    nodesData.forEach(node => {
      delete node.fx;
      delete node.fy;
    });
    
    // Create the force simulation
    simulation = d3.forceSimulation(nodesData)
      .force('link', d3.forceLink(linksData)
        .id(d => d.id)
        .distance(150))
      .force('charge', d3.forceManyBody()
        .strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX(width / 2).strength(0.1))
      .force('y', d3.forceY(height / 2).strength(0.1))
      .force('collision', d3.forceCollide().radius(d => 20 + 5));
    
    // Update node and link positions on tick
    simulation.on('tick', () => {
      d3.selectAll('.node')
        .attr('transform', d => `translate(${d.x},${d.y})`);
      
      d3.selectAll('.links line')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    });
}

// Update node selection for centered layouts
function selectNodeForLayout(node) {
    // Update selected node 
    selectedNode = node;
    
    // Update visual selection
    d3.selectAll('.node').classed('selected', false); // Clear previous selection
    d3.selectAll('.node').filter(d => d.id === node.id).classed('selected', true);
    
    // If using a centered layout, update
    if (currentLayout === 'radial' || currentLayout === 'hierarchical') {
        updateLayout();
    }
}

// Initialize the modal and visualization
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('network-modal');
    const showGraphBtn = document.getElementById('view-network-btn');
    const closeBtn = modal.querySelector('.close');
    
    if (!showGraphBtn) {
        console.error("Show graph button not found");
        return;
    }
    
    // Show graph modal
    showGraphBtn.addEventListener('click', () => {
        modal.style.display = 'block';
        
        // Initialize graph if not already initialized
        if (!graphInitialized) {
            setTimeout(() => {
                initializeGraph();
            }, 100); // Short delay to ensure modal is displayed
        }
    });
    
    // Close graph modal
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }
    
    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (graphInitialized && modal.style.display === 'block') {
            // Resize SVG to match container
            const container = document.getElementById('graph-container');
            if (container && svg) {
                const width = container.clientWidth;
                const height = container.clientHeight;
                
                svg.attr('viewBox', `0 0 ${width} ${height}`);
                
                // Update simulation center force
                simulation.force('center')
                    .x(width / 2)
                    .y(height / 2);
                
                simulation.alpha(0.3).restart();
            }
        }
    });
});