import { Injectable } from '@angular/core';
import { Observable, Subject, filter, map } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AguiService {
  private ws?: WebSocket;
  private events$ = new Subject<any>();
  sessionId: string | null = null;

  connect(sessionId: string, baseUrl = 'http://localhost:8000') {
    this.sessionId = sessionId;
    const wsUrl = baseUrl.replace('http', 'ws') + `/events?sessionId=${sessionId}`;
    this.ws = new WebSocket(wsUrl);
    this.ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        this.events$.next(data);
      } catch {
        // ignore
      }
    };
  }

  send(event: any) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify(event));
  }

  on<T = any>(type: string): Observable<T> {
    return this.events$.pipe(
      filter((e) => e?.type === type),
      map((e) => e as T)
    );
  }
}
