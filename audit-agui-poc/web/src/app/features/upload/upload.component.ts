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
    <div>
      <h3>Start Session & Upload Financials</h3>
      <button (click)="start()" [disabled]="loading">Start Session</button>
      <div *ngIf="sessionId">Session: {{sessionId}}</div>
      <form *ngIf="sessionId" (submit)="onUpload($event)">
        <input type="file" (change)="onFile($event)" required />
        <button type="submit" [disabled]="!file || loading">Upload</button>
      </form>
    </div>
  `,
  styles: ``
})
export class UploadComponent {
  loading = false;
  file?: File;
  sessionId: string | null = null;

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
    this.agui.send({ type: 'agent.run', task: 'disclosure_review' });
    this.router.navigateByUrl('/questions');
    this.loading = false;
  }
}
