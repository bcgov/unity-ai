// chat.service.ts
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class ChatService {
  constructor() {}
  
  stream(prompt: string, chatId: number, mode: string): Observable<string> {
  return new Observable<string>(observer => {

    fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ "prompt": prompt, "chatId": chatId, "mode": mode })
    })
    .then(resp => {
      if (!resp.ok) throw new Error(resp.statusText);

      const reader  = resp.body!.getReader();
      const decoder = new TextDecoder();
      let carry = '';                     // holds an incomplete event

      const pump = (): any => reader.read().then(({ value, done }) => {
        if (done) { observer.complete(); return; }

        carry += decoder.decode(value, { stream: true });

        /* ----- 1. split into complete SSE events ----- */
        const events = carry.split('\n\n');
        carry = events.pop()!;            // last fragment (maybe partial)

        events.forEach(ev => {
          
          let eventType = 'message';

          ev.split('\n').forEach(line => {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
              return;
            }
            if (!line.startsWith('data:')) return;

            const payload = line.slice(5);

            // --- skip control chunks ---------------------------
            if (eventType === 'done' || payload === '[DONE]') {
              // you already complete() when fetch finishes, so just ignore
              return;
            }
            // ----------------------------------------------------

            observer.next(payload === '' ? '\n' : payload);
          });
        });

        return pump();                    // loop
      });
      pump();
    })
    .catch(err => observer.error(err));

    return () => {};                      // teardown
  });
}

}