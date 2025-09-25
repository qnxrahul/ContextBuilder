import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { AdaptiveCardComponent } from '../shared/adaptive-card.component';

@Component({
  standalone: true,
  selector: 'app-dashboard',
  imports: [CommonModule, HttpClientModule, AdaptiveCardComponent],
  template: `
  <div class="container">
    <h2>Document Analyzer</h2>
    <div class="controls">
      <button (click)="createSession()" [disabled]="creating()">New Session</button>
      <input type="file" (change)="onFile($event)" [disabled]="!sessionId()" />
    </div>
    <div *ngIf="sessionId()">Session: {{ sessionId() }}</div>
    <section *ngIf="state() as s">
      <h3>Executive Summary</h3>
      <adaptive-card [templateJson]="execTemplate" [data]="s.summary"></adaptive-card>

      <h3>Financial Metrics & Ratios</h3>
      <adaptive-card [templateJson]="metricsTemplate" [data]="s.metrics"></adaptive-card>

      <h3>Compliance & Risk</h3>
      <adaptive-card [templateJson]="complianceTemplate" [data]="s.compliance"></adaptive-card>

      <h3>Trend Analysis</h3>
      <adaptive-card [templateJson]="trendsTemplate" [data]="s.trends"></adaptive-card>

      <h3>Anomaly Detection</h3>
      <adaptive-card [templateJson]="anomaliesTemplate" [data]="s.anomalies"></adaptive-card>

      <h3>Document Structure</h3>
      <adaptive-card [templateJson]="structureTemplate" [data]="s.structure"></adaptive-card>

      <h3>Audit Highlights</h3>
      <adaptive-card [templateJson]="highlightsTemplate" [data]="s.highlights"></adaptive-card>

      <h3>Supporting Links</h3>
      <adaptive-card [templateJson]="referencesTemplate" [data]="{items: s.references}"></adaptive-card>

      <h3>AI Suggestions</h3>
      <adaptive-card [templateJson]="suggestionsTemplate" [data]="s.suggestions"></adaptive-card>
    </section>
  </div>
  `,
  styles: [`.container{padding:1rem}`]
})
export class DashboardComponent {
  private readonly http = inject(HttpClient);
  readonly baseUrl = signal<string>("http://localhost:8080");
  readonly sessionId = signal<string | null>(null);
  readonly state = signal<any>(null);
  readonly creating = signal<boolean>(false);

  // Minimal Adaptive Card templates for each section
  readonly execTemplate = {
    type: 'AdaptiveCard', version: '1.5', body: [
      { type: 'TextBlock', text: 'Purpose: ${purpose}', wrap: true },
      { type: 'TextBlock', text: 'Reporting Period: ${reportingPeriod}', wrap: true },
      { type: 'TextBlock', text: 'Highlights: ${notes}', wrap: true }
    ]
  };
  readonly metricsTemplate = {
    type: 'AdaptiveCard', version: '1.5', body: [
      { type: 'TextBlock', text: 'Profitability', weight: 'Bolder' },
      { type: 'FactSet', facts: [
        { title: 'Gross Margin', value: '${profitability.grossMargin}' },
        { title: 'Net Margin', value: '${profitability.netMargin}' },
        { title: 'ROE', value: '${profitability.roe}' }
      ]},
      { type: 'TextBlock', text: 'Liquidity', weight: 'Bolder' },
      { type: 'FactSet', facts: [
        { title: 'Current Ratio', value: '${liquidity.currentRatio}' },
        { title: 'Quick Ratio', value: '${liquidity.quickRatio}' }
      ]},
      { type: 'TextBlock', text: 'Solvency', weight: 'Bolder' },
      { type: 'FactSet', facts: [
        { title: 'Debt/Equity', value: '${solvency.debtToEquity}' },
        { title: 'Interest Coverage', value: '${solvency.interestCoverage}' }
      ]},
      { type: 'TextBlock', text: 'Efficiency', weight: 'Bolder' },
      { type: 'FactSet', facts: [
        { title: 'Inventory Turnover', value: '${efficiency.inventoryTurnover}' },
        { title: 'Receivables Turnover', value: '${efficiency.receivablesTurnover}' }
      ]}
    ]
  };
  readonly complianceTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'FactSet', facts: [
      { title: 'Missing Data', value: '${missingData}' },
      { title: 'Unusual Transactions', value: '${unusualTransactions}' },
      { title: 'Late Filings', value: '${lateFilings}' },
      { title: 'Standard', value: '${standard}' }
    ]}
  ] };
  readonly trendsTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'TextBlock', text: 'Trends (last 4 periods)', weight: 'Bolder' },
    { type: 'TextBlock', text: 'Revenue: ${revenue}' },
    { type: 'TextBlock', text: 'Expenses: ${expenses}' },
    { type: 'TextBlock', text: 'Assets: ${assets}' },
    { type: 'TextBlock', text: 'Liabilities: ${liabilities}' }
  ] };
  readonly anomaliesTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'TextBlock', text: 'Spikes: ${spikes}' },
    { type: 'TextBlock', text: 'Duplicates: ${duplicates}' },
    { type: 'TextBlock', text: 'Related Party: ${relatedParty}' },
    { type: 'TextBlock', text: 'Unusual Entries: ${unusualEntries}' }
  ] };
  readonly structureTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'TextBlock', text: 'File: ${fileName}' },
    { type: 'TextBlock', text: 'TOC: ${toc}' }
  ] };
  readonly highlightsTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'TextBlock', text: 'Judgment Areas: ${judgmentAreas}' },
    { type: 'TextBlock', text: 'Estimates: ${estimates}' },
    { type: 'TextBlock', text: 'Controls: ${controls}' },
    { type: 'TextBlock', text: "Auditor's Opinion: ${auditorsOpinion}" }
  ] };
  readonly referencesTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'Container', items: [
      { type: 'TextBlock', text: 'References', weight: 'Bolder' },
      { type: 'ColumnSet', columns: [
        { type: 'Column', width: 'stretch', items: [
          { type: 'TextBlock', text: '${items}' }
        ]}
      ]}
    ]}
  ] };
  readonly suggestionsTemplate = { type: 'AdaptiveCard', version: '1.5', body: [
    { type: 'TextBlock', text: 'Questions: ${questions}' },
    { type: 'TextBlock', text: 'Deep Dive: ${deepDive}' },
    { type: 'TextBlock', text: 'Risks: ${risks}' },
    { type: 'TextBlock', text: 'Opportunities: ${opportunities}' }
  ] };

  async createSession() {
    try {
      this.creating.set(true);
      const res = await this.http.post<{ sessionId: string }>(`${this.baseUrl()}/session`, {}).toPromise();
      this.sessionId.set(res!.sessionId);
      const snapshot = await this.http.get(`${this.baseUrl()}/session/${res!.sessionId}`).toPromise();
      this.state.set(snapshot);
    } finally {
      this.creating.set(false);
    }
  }

  async onFile(evt: Event) {
    const input = evt.target as HTMLInputElement;
    if (!input.files || input.files.length === 0 || !this.sessionId()) return;
    const file = input.files[0];
    const form = new FormData();
    form.append('file', file);
    await this.http.post(`${this.baseUrl()}/upload/${this.sessionId()}`, form).toPromise();
    const state = await this.http.get(`${this.baseUrl()}/session/${this.sessionId()}`).toPromise();
    this.state.set(state);
  }
}

