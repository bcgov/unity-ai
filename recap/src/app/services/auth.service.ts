import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface JwtPayload {
  tenant_id?: string;
  collection_id?: number;
  metabase_url?: string;
  exp?: number;
  [key: string]: any;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private tokenSubject = new BehaviorSubject<string | null>(null);
  public token$ = this.tokenSubject.asObservable();

  constructor() {
    this.initializeFromUrl();
  }

  private initializeFromUrl(): void {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    if (token) {
      this.setToken(token);
      // Clean up URL to remove token from address bar
      const url = new URL(window.location.href);
      url.searchParams.delete('token');
      window.history.replaceState({}, document.title, url.toString());
    }
  }

  setToken(token: string): void {
    this.tokenSubject.next(token);
    localStorage.setItem('jwt_token', token);
  }

  getToken(): string | null {
    return this.tokenSubject.value || localStorage.getItem('jwt_token');
  }

  clearToken(): void {
    this.tokenSubject.next(null);
    localStorage.removeItem('jwt_token');
  }

  async isAuthenticated(): Promise<boolean> {
    const token = this.getToken();
    if (!token) return false;
    
    try {
      // First validate the signature
      const isValidSignature = await this.validateSignature(token);
      if (!isValidSignature) return false;
      
      const payload = this.decodeToken(token);
      if (!payload || !payload.exp) return false;
      const expiry = payload.exp * 1000;
      return Date.now() < expiry;
    } catch {
      return false;
    }
  }

  decodeToken(token?: string): JwtPayload | null {
    const jwtToken = token || this.getToken();
    if (!jwtToken) return null;
    
    try {
      // Split JWT into parts
      const parts = jwtToken.split('.');
      if (parts.length !== 3) return null;
      
      // Decode base64url payload (second part)
      const base64Payload = parts[1];
      const base64 = this.base64urlDecode(base64Payload);
      const payload = JSON.parse(base64);
      
      return payload as JwtPayload;
    } catch {
      return null;
    }
  }

  private base64urlDecode(base64url: string): string {
    // Convert base64url to base64
    let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
    
    // Add padding if needed
    while (base64.length % 4) {
      base64 += '=';
    }
    
    return atob(base64);
  }

  private base64urlEncode(str: string): string {
    return btoa(str)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }

  async validateSignature(token: string): Promise<boolean> {
    try {
      // You'll need to configure this secret - consider environment variable or configuration
      const secret = 'your-super-secret-key-keep-this-safe'; // TODO: Move to environment config
      
      const parts = token.split('.');
      if (parts.length !== 3) {
        console.error('JWT validation failed: Invalid token format');
        return false;
      }
      
      const [header, payload, signature] = parts;
      const signingInput = `${header}.${payload}`;
      
      console.log('JWT validation debug:', {
        header: JSON.parse(this.base64urlDecode(header)),
        payload: JSON.parse(this.base64urlDecode(payload)),
        signingInput,
        signature
      });
      
      // Import secret key for HMAC
      const key = await crypto.subtle.importKey(
        'raw',
        new TextEncoder().encode(secret),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['verify']
      );
      
      // Decode the signature from base64url
      const signatureBytes = this.base64urlToUint8Array(signature);
      
      // Verify the signature
      const isValid = await crypto.subtle.verify(
        'HMAC',
        key,
        signatureBytes,
        new TextEncoder().encode(signingInput)
      );
      
      console.log('JWT signature validation result:', isValid);
      return isValid;
    } catch (error) {
      console.error('JWT signature validation failed:', error);
      return false;
    }
  }

  private base64urlToUint8Array(base64url: string): Uint8Array {
    // Convert base64url to base64
    let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
    
    // Add padding if needed
    while (base64.length % 4) {
      base64 += '=';
    }
    
    // Decode base64 to binary string
    const binary = atob(base64);
    
    // Convert binary string to Uint8Array
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  getTenantId(): string | null {
    const payload = this.decodeToken();
    return payload?.tenant_id || null;
  }

  getCollectionId(): number | null {
    const payload = this.decodeToken();
    return payload?.collection_id || null;
  }

  getMetabaseUrl(): string | null {
    const payload = this.decodeToken();
    return payload?.metabase_url || null;
  }
}