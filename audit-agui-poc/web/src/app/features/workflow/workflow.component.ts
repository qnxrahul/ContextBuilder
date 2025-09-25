import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AguiService } from '../../core/agui.service';

@Component({
  selector: 'app-workflow',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="row">
      <div class="col-lg-10">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h3>Workflow</h3>
          <div>
            <button class="btn btn-outline-secondary" (click)="refresh()">Refresh</button>
          </div>
        </div>
        <div class="row">
          <div class="col-md-6">
            <div class="card shadow-sm mb-3" *ngIf="workflow">
              <div class="card-header">Graph</div>
              <div class="card-body">
                <pre class="small mb-0">{{workflow | json}}</pre>
              </div>
            </div>
            <div class="card shadow-sm" *ngIf="metrics">
              <div class="card-header">Token Usage (estimate)</div>
              <div class="card-body">
                <div>AG-UI prompt: {{metrics.agui.prompt}} | output: {{metrics.agui.output}}</div>
                <div>Baseline prompt: {{metrics.baseline.prompt}} | output: {{metrics.baseline.output}}</div>
                <div class="text-success">Prompt savings: {{metrics.baseline.prompt - metrics.agui.prompt}}</div>
              </div>
            </div>
          </div>
          <div class="col-md-6" *ngIf="widget() as w">
            <div class="card shadow-sm">
              <div class="card-header">{{w.title}}</div>
              <div class="card-body">
                <div class="mb-2">
                  <label class="form-label">Group by</label>
                  <input class="form-control" [(ngModel)]="w.params.by" />
                </div>
                <button class="btn btn-primary" (click)="patchWidget(w)">Apply Patch</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: ``
})
export class WorkflowComponent {
  workflow: any;
  metrics: any;

  constructor(private agui: AguiService) {
    this.agui.on<any>('workflow.create').subscribe(e => {
      this.workflow = e.workflow;
    });
    this.agui.on<any>('workflow.update').subscribe(e => {
      this.workflow = e.workflow;
    });
    this.agui.on<any>('metrics.usage').subscribe(e => {
      this.metrics = { agui: e.agui, baseline: e.baseline };
    });
  }

  widget() {
    return this.workflow?.widgets?.[0];
  }

  async refresh() {
    if (!this.agui.sessionId) return;
    const res = await fetch(`http://localhost:8000/workflow/latest?sessionId=${this.agui.sessionId}`);
    if (res.ok) {
      this.workflow = await res.json();
    }
  }

  patchWidget(w: any) {
    this.agui.send({ type: 'widget.patch', patch: { id: w.id, changes: { params: w.params } } });
  }
}
