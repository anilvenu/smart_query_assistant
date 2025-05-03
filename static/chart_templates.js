/**
 * Chart templates for Smart Query Assistant
 * Uses Chart.js for rendering visualizations
 */

// Chart rendering function
function renderChart(chartConfig, containerId) {
    console.log("renderChart called with config:", chartConfig);
    console.log("Chart type:", chartConfig ? chartConfig.chart_type : "undefined");
    console.log("Container exists:", document.getElementById(containerId) !== null);


    // Validate config
    if (!chartConfig || !chartConfig.chart_applicable) {
      console.warn("Chart configuration not applicable");
      return false;
    }
  
    const container = document.getElementById(containerId);
    if (!container) {
      console.error(`Chart container ${containerId} not found`);
      return false;
    }
  
    try {
      // Clear any existing chart
      container.innerHTML = '';
  
      // Create canvas element
      const canvas = document.createElement('canvas');
      canvas.id = `chart-canvas-${Date.now()}`;
      container.appendChild(canvas);
  
      // Get chart type and data
      const chartType = chartConfig.chart_type;
      const data = chartConfig.data;
      const columns = chartConfig.columns;
      const colors = chartConfig.colors;
  
      // Create chart based on type
      switch (chartType) {
        case 'pie':
          createPieChart(canvas, data, columns, colors, chartConfig);
          break;
        case 'bar':
          createBarChart(canvas, data, columns, colors, chartConfig, true); // horizontal
          break;
        case 'column':
          createBarChart(canvas, data, columns, colors, chartConfig, false); // vertical
          break;
        case 'line':
          createLineChart(canvas, data, columns, colors, chartConfig);
          break;
        case 'table':
          // Just use standard table display
          container.innerHTML = '<p class="chart-message">Data displayed as table below</p>';
          return false;
        default:
          console.warn(`Unsupported chart type: ${chartType}`);
          container.innerHTML = '<p class="chart-message">Unable to visualize this data</p>';
          return false;
      }
  
      return true;
    } catch (error) {
      console.error('Error rendering chart:', error);
      container.innerHTML = `
        <div class="chart-error">
          <p>Unable to render chart: ${error.message}</p>
        </div>
      `;
      return false;
    }
  }
  
  // Create a pie chart
  function createPieChart(canvas, data, columns, colors, config) {
    const ctx = canvas.getContext('2d');
    
    // Extract labels and values
    const labelCol = columns.labels[0];
    const valueCol = columns.y_axis[0];
    
    const chartData = {
      labels: data.map(row => row[labelCol]),
      datasets: [{
        data: data.map(row => row[valueCol]),
        backgroundColor: colors,
        borderWidth: 1
      }]
    };
    
    new Chart(ctx, {
      type: 'pie',
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: config.title,
            font: {
              size: 16
            }
          },
          legend: {
            position: 'right'
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                const label = context.label || '';
                const value = context.raw || 0;
                const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                const percentage = ((value / total) * 100).toFixed(1);
                return `${label}: ${value} (${percentage}%)`;
              }
            }
          }
        }
      }
    });
  }
  
  // Create a bar chart (horizontal or vertical)
  function createBarChart(canvas, data, columns, colors, config, horizontal) {
    const ctx = canvas.getContext('2d');
    
    // Extract data
    const xAxisCol = columns.x_axis[0];
    const yAxisCols = columns.y_axis;
    const seriesCol = columns.series.length > 0 ? columns.series[0] : null;
    
    let datasets = [];
    
    if (seriesCol) {
      // Group data by series
      const seriesValues = [...new Set(data.map(row => row[seriesCol]))];
      
      datasets = seriesValues.map((seriesValue, index) => {
        const seriesData = data.filter(row => row[seriesCol] === seriesValue);
        
        return {
          label: String(seriesValue),
          data: yAxisCols.map(col => {
            return data
              .filter(row => row[seriesCol] === seriesValue)
              .reduce((sum, row) => sum + (parseFloat(row[col]) || 0), 0);
          }),
          backgroundColor: colors[index % colors.length],
          borderWidth: 1
        };
      });
    } else {
      // No series - create one dataset per y-axis column
      datasets = yAxisCols.map((col, index) => {
        return {
          label: col,
          data: data.map(row => parseFloat(row[col]) || 0),
          backgroundColor: colors[index % colors.length],
          borderWidth: 1
        };
      });
    }
    
    const chartData = {
      labels: data.map(row => row[xAxisCol]),
      datasets: datasets
    };
    
    new Chart(ctx, {
      type: horizontal ? 'bar' : 'bar', // Both are 'bar' in Chart.js but with different indexAxis
      data: chartData,
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            stacked: config.stacked || false,
            title: {
              display: true,
              text: horizontal ? valueLabel(yAxisCols) : xAxisCol
            }
          },
          y: {
            stacked: config.stacked || false,
            title: {
              display: true,
              text: horizontal ? xAxisCol : valueLabel(yAxisCols)
            }
          }
        },
        plugins: {
          title: {
            display: true,
            text: config.title,
            font: {
              size: 16
            }
          },
          legend: {
            position: 'top'
          }
        }
      }
    });
  }
  
  // Create a line chart
  function createLineChart(canvas, data, columns, colors, config) {
    const ctx = canvas.getContext('2d');
    
    // Extract data
    const xAxisCol = columns.x_axis[0];
    const yAxisCols = columns.y_axis;
    const seriesCol = columns.series.length > 0 ? columns.series[0] : null;
    
    let datasets = [];
    
    if (seriesCol) {
      // Group data by series
      const seriesValues = [...new Set(data.map(row => row[seriesCol]))];
      
      // Sort data by x-axis for proper line rendering
      data.sort((a, b) => {
        if (a[xAxisCol] < b[xAxisCol]) return -1;
        if (a[xAxisCol] > b[xAxisCol]) return 1;
        return 0;
      });
      
      // Create one dataset per series value and y-axis column
      let colorIndex = 0;
      
      for (const seriesValue of seriesValues) {
        for (const yCol of yAxisCols) {
          const seriesData = data.filter(row => row[seriesCol] === seriesValue);
          
          datasets.push({
            label: `${yCol} - ${seriesValue}`,
            data: seriesData.map(row => ({
              x: row[xAxisCol],
              y: parseFloat(row[yCol]) || 0
            })),
            borderColor: colors[colorIndex % colors.length],
            backgroundColor: transparentize(colors[colorIndex % colors.length], 0.8),
            borderWidth: 2,
            tension: 0.1
          });
          
          colorIndex++;
        }
      }
    } else {
      // No series - create one dataset per y-axis column
      
      // Sort data by x-axis for proper line rendering
      data.sort((a, b) => {
        if (a[xAxisCol] < b[xAxisCol]) return -1;
        if (a[xAxisCol] > b[xAxisCol]) return 1;
        return 0;
      });
      
      datasets = yAxisCols.map((col, index) => {
        return {
          label: col,
          data: data.map(row => ({
            x: row[xAxisCol],
            y: parseFloat(row[col]) || 0
          })),
          borderColor: colors[index % colors.length],
          backgroundColor: transparentize(colors[index % colors.length], 0.8),
          borderWidth: 2,
          tension: 0.1
        };
      });
    }
    
    new Chart(ctx, {
      type: 'line',
      data: {
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: 'category',
            title: {
              display: true,
              text: xAxisCol
            }
          },
          y: {
            title: {
              display: true,
              text: valueLabel(yAxisCols)
            }
          }
        },
        plugins: {
          title: {
            display: true,
            text: config.title,
            font: {
              size: 16
            }
          },
          legend: {
            position: 'top'
          }
        }
      }
    });
  }
  
  // Helper function to make a color transparent
  function transparentize(hexColor, opacity) {
    // Convert hex to RGB
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);
    
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  
  // Helper to create a label for Y axis
  function valueLabel(columns) {
    if (columns.length === 1) {
      return columns[0];
    }
    return 'Values';
  }