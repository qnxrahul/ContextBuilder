import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AguiService } from '../../core/agui.service';

@Component({
  selector: 'app-workflow',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div>
      <h3>Workflow</h3>
      <button (click)="refresh()">Refresh</button>
      <pre *ngIf="workflow">{{workflow | json}}</pre>
      <div *ngIf="metrics">
        <h4>Token Usage (estimate)</h4>
        <div>AG-UI prompt: {{metrics.agui.prompt}} | output: {{metrics.agui.output}}</div>
        <div>Baseline prompt: {{metrics.baseline.prompt}} | output: {{metrics.baseline.output}}</div>
        <div>Prompt savings: {{metrics.baseline.prompt - metrics.agui.prompt}}</div>
      </div>
      <div *ngIf="widget() as w">
        <h4>{{w.title}}</h4>
        <label>
          Group by: <input [(ngModel)]="w.params.by" />
        </label>
        <button (click)="patchWidget(w)">Apply Patch</button>
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
