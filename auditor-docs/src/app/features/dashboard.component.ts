import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule } from '@angular/common/http';

@Component({
  standalone: true,
  selector: 'app-dashboard',
  imports: [CommonModule, HttpClientModule],
  template: `
  <div class="container">
    <h2>Document Analyzer</h2>
    <div class="controls">
      <button (click)="createSession()" [disabled]="creating()">New Session</button>
      <input type="file" (change)="onFile($event)" [disabled]="!sessionId()" />
    </div>
    <div *ngIf="sessionId()">Session: {{ sessionId() }}</div>
    <pre *ngIf="state() as s">{{ s | json }}</pre>
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

