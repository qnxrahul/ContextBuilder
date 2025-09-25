import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AguiService } from '../../core/agui.service';

@Component({
  selector: 'app-questions',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div>
      <h3>Generated Questions</h3>
      <div *ngFor="let q of questions" style="margin:8px 0;">
        <div>{{q.text}}</div>
        <small *ngIf="q.citations?.length">Citations: {{q.citations[0]?.sourceId}} p{{q.citations[0]?.page}}</small>
        <div>
          <input [(ngModel)]="q._answer" placeholder="Your answer" />
          <button (click)="submitAnswer(q)">Submit</button>
        </div>
      </div>
      <button (click)="goWorkflow()" [disabled]="questions.length===0">Go to Workflow</button>
    </div>
  `,
  styles: ``
})
export class QuestionsComponent {
  questions: any[] = [];

  constructor(private agui: AguiService, private router: Router) {
    this.agui.on<any>('question.create').subscribe(e => {
      this.questions = [...this.questions, e.question];
    });
  }

  async submitAnswer(q: any) {
    if (!this.agui.sessionId) return;
    await fetch(`http://localhost:8000/questions/${q.id}/answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: this.agui.sessionId, answer: q._answer })
    });
  }

  goWorkflow() {
    this.router.navigateByUrl('/workflow');
  }
}
