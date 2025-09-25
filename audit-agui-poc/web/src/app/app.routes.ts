import { Routes } from '@angular/router';
import { UploadComponent } from './features/upload/upload.component';
import { QuestionsComponent } from './features/questions/questions.component';
import { WorkflowComponent } from './features/workflow/workflow.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'upload' },
  { path: 'upload', component: UploadComponent },
  { path: 'questions', component: QuestionsComponent },
  { path: 'workflow', component: WorkflowComponent },
];
