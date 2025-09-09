import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private api_url = environment.apiUrl;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getHeaders(): HttpHeaders {
    const headers: any = {
      'Content-Type': 'application/json'
    };

    // Add JWT token to Authorization header if available
    const token = this.authService.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return new HttpHeaders(headers);
  }

  // Wrapper methods for common HTTP operations
  post<T>(endpoint: string, body: any = {}): Observable<T> {
    return this.http.post<T>(`${this.api_url}${endpoint}`, body, {
      headers: this.getHeaders()
    });
  }

  get<T>(endpoint: string, params: any = {}): Observable<T> {
    return this.http.get<T>(`${this.api_url}${endpoint}`, { 
      params: params,
      headers: this.getHeaders()
    });
  }

  put<T>(endpoint: string, body: any = {}): Observable<T> {
    return this.http.put<T>(`${this.api_url}${endpoint}`, body, {
      headers: this.getHeaders()
    });
  }

  delete<T>(endpoint: string, body: any = {}): Observable<T> {
    return this.http.delete<T>(`${this.api_url}${endpoint}`, { 
      body: body,
      headers: this.getHeaders()
    });
  }

  // Convenience methods for specific endpoints
  askQuestion<T>(question: string, conversation: any[]): Observable<T> {
    return this.post<T>('/ask', { 
      question, 
      conversation 
    });
  }

  changeDisplay<T>(cardId: number, mode: string, xField: string, yField: string): Observable<T> {
    return this.post<T>('/change_display', {
      card_id: cardId,
      mode,
      x_field: xField,
      y_field: yField
    });
  }

  deleteCard<T>(cardId: number): Observable<T> {
    return this.post<T>('/delete', {
      card_id: cardId
    });
  }

  explainSql<T>(sql: string): Observable<T> {
    return this.post<T>('/explain_sql', {
      sql: sql
    });
  }

  // Chat-related methods
  getChats<T>(): Observable<T> {
    return this.post<T>('/chats', {});
  }

  getChat<T>(chatId: string): Observable<T> {
    return this.post<T>(`/chats/${chatId}`, {});
  }

  saveChat<T>(chatId: string | null, conversation: any[], title: string): Observable<T> {
    return this.post<T>('/chats/save', {
      chat_id: chatId,
      conversation,
      title
    });
  }

  deleteChat<T>(chatId: string): Observable<T> {
    return this.delete<T>(`/chats/${chatId}`, {});
  }

  // Token validation method
  validateToken<T>(): Observable<T> {
    return this.post<T>('/validate-token', {});
  }
}