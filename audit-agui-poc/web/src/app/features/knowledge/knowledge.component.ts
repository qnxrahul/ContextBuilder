import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AguiService } from '../../core/agui.service';

@Component({
  selector: 'app-knowledge',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div>
      <h3>Knowledge Sources</h3>
      <div>
        <label>Tenant ID <input [(ngModel)]="tenantId" placeholder="tenant_demo" /></label>
      </div>
      <div>
        <label>Kind
          <select [(ngModel)]="kind">
            <option value="enterprise">enterprise</option>
            <option value="customer">customer</option>
          </select>
        </label>
      </div>
      <div>
        <label>Title <input [(ngModel)]="title" placeholder="Policy / Checklist" /></label>
      </div>
      <div>
        <label>Text</label>
        <textarea [(ngModel)]="text" rows="8" cols="60" placeholder="Paste content..."></textarea>
      </div>
      <button (click)="addSource()" [disabled]="!text">Add Source</button>
      <button (click)="loadDemo()">Load Demo Enterprise Source</button>
      <div *ngIf="status">{{status}}</div>
    </div>
  `,
  styles: ``
})
export class KnowledgeComponent {
  tenantId = '';
  kind: 'enterprise' | 'customer' = 'enterprise';
  title = '';
  text = '';
  status = '';

  constructor(private agui: AguiService) {}

  addSource() {
    const source = { id: undefined, kind: this.kind, title: this.title || 'Untitled', text: this.text };
    this.agui.send({ type: 'knowledge.add_source', tenantId: this.tenantId || 'tenant_demo', source });
    this.status = 'Sent knowledge.add_source';
  }

  loadDemo() {
    this.kind = 'enterprise';
    this.title = 'IFRS 15 Revenue Disclosure Checklist (Excerpt)';
    this.text = 'Revenue should be disaggregated by category. Contract balances should include rollforwards. Cash note shall reconcile opening to closing cash.';
  }
}
