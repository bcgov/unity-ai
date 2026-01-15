import { Component, Input, OnInit, OnChanges, SimpleChanges, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BaseChartDirective } from 'ng2-charts';
import { ChartConfiguration, ChartData, ChartType } from 'chart.js';

export interface ChartDataInput {
  columns: string[];
  objects: any[];
}

@Component({
  selector: 'app-chart',
  standalone: true,
  imports: [CommonModule, BaseChartDirective],
  template: `
    <div class="chart-wrapper">
      <h3 class="chart-title" *ngIf="title">{{ title }}</h3>
      <div class="chart-container">
        <canvas baseChart
                [data]="chartData"
                [options]="chartOptions"
                [type]="chartType"></canvas>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
      padding: 20px;
      box-sizing: border-box;
    }

    .chart-wrapper {
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .chart-title {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      color: #333;
      text-align: center;
    }

    .chart-container {
      width: 100%;
      height: 300px;
      position: relative;
    }

    canvas {
      max-height: 300px !important;
    }
  `]
})
export class ChartComponent implements OnInit, OnChanges {
  @Input() data!: ChartDataInput;
  @Input() type: 'bar' | 'line' | 'pie' = 'bar';
  @Input() title?: string;
  @ViewChild(BaseChartDirective) chart?: BaseChartDirective;

  chartType: ChartType = 'bar';
  chartData: ChartData = { labels: [], datasets: [] };
  chartOptions: ChartConfiguration['options'] = {};

  ngOnInit(): void {
    this.updateChart();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['data'] || changes['type']) {
      this.updateChart();
    }
  }

  private updateChart(): void {
    if (!this.data || !this.data.columns || !this.data.objects || this.data.objects.length === 0) {
      return;
    }

    this.chartType = this.type as ChartType;

    switch (this.type) {
      case 'bar':
        this.createBarChart();
        break;
      case 'line':
        this.createLineChart();
        break;
      case 'pie':
        this.createPieChart();
        break;
    }

    // Force chart update
    if (this.chart) {
      this.chart.update();
    }
  }

  private createBarChart(): void {
    const columns = this.data.columns;
    const rows = this.data.objects;

    const categoryColumn = columns[0];
    const valueColumns = columns.slice(1);

    const labels = rows.map(row => {
      const value = row[categoryColumn];
      return (value == null || value === '') ? '(Not Specified)' : String(value);
    });

    const datasets = valueColumns.map((col, index) => ({
      label: col,
      data: rows.map(row => {
        const value = row[col];
        return typeof value === 'number' ? value : parseFloat(String(value)) || 0;
      }),
      backgroundColor: this.getColor(index, 0.7),
      borderColor: this.getColor(index, 1),
      borderWidth: 1
    }));

    this.chartData = { labels, datasets };
    this.chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: valueColumns.length > 1,
          position: 'top',
        },
        tooltip: {
          mode: 'index',
          intersect: false,
        }
      },
      scales: {
        x: {
          ticks: {
            maxRotation: labels.length > 5 ? 45 : 0,
            minRotation: 0
          }
        },
        y: {
          beginAtZero: true
        }
      }
    };
  }

  private createLineChart(): void {
    const columns = this.data.columns;
    const rows = this.data.objects;

    const categoryColumn = columns[0];
    const valueColumns = columns.slice(1);

    const labels = rows.map(row => {
      const value = row[categoryColumn];
      return (value == null || value === '') ? '(Not Specified)' : String(value);
    });

    const datasets = valueColumns.map((col, index) => ({
      label: col,
      data: rows.map(row => {
        const value = row[col];
        return typeof value === 'number' ? value : parseFloat(String(value)) || 0;
      }),
      borderColor: this.getColor(index, 1),
      backgroundColor: this.getColor(index, 0.1),
      tension: 0.4,
      fill: true,
      pointRadius: 4,
      pointHoverRadius: 6
    }));

    this.chartData = { labels, datasets };
    this.chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: valueColumns.length > 1,
          position: 'top',
        },
        tooltip: {
          mode: 'index',
          intersect: false,
        }
      },
      scales: {
        x: {
          ticks: {
            maxRotation: labels.length > 5 ? 45 : 0,
            minRotation: 0
          }
        },
        y: {
          beginAtZero: true
        }
      }
    };
  }

  private createPieChart(): void {
    const columns = this.data.columns;
    const rows = this.data.objects;

    if (columns.length < 2) {
      console.error('Pie chart requires at least 2 columns (label and value)');
      return;
    }

    const labelColumn = columns[0];
    const valueColumn = columns[1];

    const labels = rows.map(row => {
      const value = row[labelColumn];
      return (value == null || value === '') ? '(Not Specified)' : String(value);
    });

    const data = rows.map(row => {
      const value = row[valueColumn];
      return typeof value === 'number' ? value : parseFloat(String(value)) || 0;
    });

    const backgroundColor = data.map((_, index) => this.getColor(index, 0.7));
    const borderColor = data.map((_, index) => this.getColor(index, 1));

    this.chartData = {
      labels,
      datasets: [{
        data,
        backgroundColor,
        borderColor,
        borderWidth: 1
      }]
    };

    this.chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: {
          left: 10,
          right: 10,
          top: 10,
          bottom: 10
        }
      },
      plugins: {
        legend: {
          display: true,
          position: 'right',
          align: 'center',
          labels: {
            padding: 10,
            boxWidth: 15,
            font: {
              size: 12
            }
          }
        },
        tooltip: {
          callbacks: {
            label: (context) => {
              const label = context.label || '';
              const value = context.parsed || 0;
              const total = (context.dataset.data as number[]).reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: ${value} (${percentage}%)`;
            }
          }
        }
      }
    };
  }

  private getColor(index: number, alpha: number): string {
    const colors = [
      `rgba(54, 162, 235, ${alpha})`,   // Blue
      `rgba(255, 99, 132, ${alpha})`,   // Red
      `rgba(255, 206, 86, ${alpha})`,   // Yellow
      `rgba(75, 192, 192, ${alpha})`,   // Green
      `rgba(153, 102, 255, ${alpha})`,  // Purple
      `rgba(255, 159, 64, ${alpha})`,   // Orange
      `rgba(199, 199, 199, ${alpha})`,  // Gray
      `rgba(83, 102, 255, ${alpha})`,   // Indigo
      `rgba(255, 99, 255, ${alpha})`,   // Pink
      `rgba(99, 255, 132, ${alpha})`    // Light Green
    ];
    return colors[index % colors.length];
  }
}
