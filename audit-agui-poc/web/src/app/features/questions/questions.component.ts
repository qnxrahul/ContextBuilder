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
    <div class="row">
      <div class="col-lg-10">
        <div class="card shadow-sm">
          <div class="card-header">Generated Questions</div>
          <div class="card-body">
            <div *ngFor="let q of questions" class="mb-3">
              <div class="fw-semibold">{{q.text}}</div>
              <div class="text-muted small" *ngIf="q.citations?.length">Citations: {{q.citations[0]?.sourceId}} p{{q.citations[0]?.page}}</div>
              <div class="input-group mt-1">
                <input class="form-control" [(ngModel)]="q._answer" placeholder="Your answer" />
                <button class="btn btn-outline-primary" (click)="submitAnswer(q)">Submit</button>
              </div>
            </div>
            <button class="btn btn-success" (click)="goWorkflow()" [disabled]="questions.length===0">Go to Workflow</button>
          </div>
        </div>
      </div>
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
