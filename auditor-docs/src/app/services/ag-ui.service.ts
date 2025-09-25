import { Injectable, signal } from '@angular/core';
import { HttpAgent } from '@ag-ui/client';

@Injectable({ providedIn: 'root' })
export class AgUiService {
  private agent = new HttpAgent({ url: 'http://localhost:8080/agent', headers: {} });
  readonly connected = signal<boolean>(false);

  async runOnce(context: any) {
    const result = await this.agent.runAgent({ context });
    return result;
  }
}

