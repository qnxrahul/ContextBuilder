import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AguiService } from '../../core/agui.service';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="row">
      <div class="col-lg-8">
        <div class="card shadow-sm">
          <div class="card-header">Start Session & Upload Financials</div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label">Tenant ID</label>
              <input class="form-control" [(ngModel)]="tenantId" placeholder="tenant_demo" />
            </div>
            <button class="btn btn-primary me-2" (click)="start()" [disabled]="loading">Start Session</button>
            <span *ngIf="sessionId" class="badge text-bg-secondary">Session: {{sessionId}}</span>
            <form class="mt-3" *ngIf="sessionId" (submit)="onUpload($event)">
              <input class="form-control" type="file" (change)="onFile($event)" required />
              <button class="btn btn-outline-primary mt-2" type="submit" [disabled]="!file || loading">Upload</button>
            </form>
            <div *ngIf="sessionId" class="mt-3">
              <div class="form-check">
                <input class="form-check-input" id="demoBox" type="checkbox" [(ngModel)]="loadDemoEnterprise" />
                <label class="form-check-label" for="demoBox">Load demo enterprise source before running</label>
              </div>
              <button class="btn btn-success mt-2" (click)="runAgent()" [disabled]="loading">Run Disclosure Review</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: ``
})
export class UploadComponent {
  loading = false;
  file?: File;
  sessionId: string | null = null;
  tenantId = '';
  loadDemoEnterprise = true;

  constructor(private agui: AguiService, private router: Router) {}

  async start() {
    this.loading = true;
    const res = await fetch('http://localhost:8000/sessions', { method: 'POST' });
    const js = await res.json();
    this.sessionId = js.sessionId;
    this.agui.connect(this.sessionId!);
    this.loading = false;
  }

  onFile(e: any) {
    const f = e.target.files?.[0];
    if (f) this.file = f;
  }

  async onUpload(e: Event) {
    e.preventDefault();
    if (!this.file || !this.sessionId) return;
    this.loading = true;
    const fd = new FormData();
    fd.append('sessionId', this.sessionId);
    fd.append('file', this.file);
    await fetch('http://localhost:8000/files', { method: 'POST', body: fd });
    this.router.navigateByUrl('/knowledge');
    this.loading = false;
  }

  runAgent() {
    const tenant = this.tenantId || 'tenant_demo';
    if (this.loadDemoEnterprise) {
      this.agui.send({
        type: 'knowledge.add_source',
        tenantId: tenant,
        source: {
          kind: 'enterprise',
          title: 'IFRS 15 Revenue Disclosure Checklist (Excerpt)',
          text: 'Revenue should be disaggregated by category. Contract balances should include rollforwards. Cash note shall reconcile opening to closing cash.'
        }
      });
    }
    this.agui.send({ type: 'agent.run', task: 'disclosure_review', tenantId: tenant });
    this.router.navigateByUrl('/questions');
  }
}
