import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { LoggerService } from './logger.service';
import { ConfigService } from './config.service';

export interface JwtPayload {
  user_id?: string;
  tenant?: string;
  jti?: string;
  exp?: number;
  iss?: string;
  aud?: string;
  [key: string]: any;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly tokenSubject = new BehaviorSubject<string | null>(null);
  public token$ = this.tokenSubject.asObservable();

  private _initializationPromise: Promise<void> | null = null;

  constructor(
    private readonly logger: LoggerService,
    private readonly configService: ConfigService
  ) {
    this.initializeFromUrl();
    this.initializePostMessageListener();
  }

  private async initializeAsync(): Promise<void> {
    try {
      console.log('🔧 AUTH SERVICE: Loading iframe origins...');
      await this.configService.loadIframeOrigins();
      console.log('🔧 AUTH SERVICE: Iframe origins loaded, registering postMessage listener');
      this.initializePostMessageListener();
      this.sendReadyMessageToParent();
      console.log('🔧 AUTH SERVICE: Initialization complete');
    } catch (error) {
      console.error('❌ AUTH SERVICE: Initialization failed:', error);
      // Fail secure - register listener anyway but with no origins
      this.initializePostMessageListener();
      this.sendReadyMessageToParent();
    }
  }

  /**
   * Ensure initialization is complete before proceeding.
   * Lazily triggers async initialization on first call.
   */
  private async ensureInitialized(): Promise<void> {
    this._initializationPromise ??= this.initializeAsync();
    await this._initializationPromise;
  }

  private initializeFromUrl(): void {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (token) {
      // For local development, mark URL tokens as authorized
      const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      this.setToken(token, isLocalDev); // Mark as authorized only for localhost
      console.log('🔧 AUTH SERVICE: URL token loaded, authorized:', isLocalDev);
      
      // Clean up URL to remove token from address bar
      const url = new URL(window.location.href);
      url.searchParams.delete('token');
      window.history.replaceState({}, document.title, url.toString());
    } else {
      // No URL token - check if we have a stored token
      const storedToken = this.getToken();
      if (storedToken && !this.isInIframe()) {
        console.log('🔍 AUTH SERVICE: Direct access detected with stored token - checking if still valid');
        
        // If accessing directly (not in iframe) and we have a token, 
        // this might be after a Unity Grant Manager logout
        // Clear the token unless explicitly authorized
        const isAuthorized = localStorage.getItem('ai_reporting_authorized') === 'true';
        if (!isAuthorized) {
          console.log('❌ AUTH SERVICE: Direct access with unauthorized token - clearing');
          this.clearToken();
        }
      }
    }
  }
  
  private isInIframe(): boolean {
    try {
      return window.self !== window.top;
    } catch (e) {
      console.warn('Could not determine iframe status, assuming iframe for security:', e);
      return true;
    }
  }

  private initializePostMessageListener(): void {
    console.log('AUTH SERVICE: Registering postMessage listener');
    // Listen for token from parent window (when embedded in iframe)
    window.addEventListener('message', (event: MessageEvent) => this.handlePostMessage(event));
  }

  private handlePostMessage(event: MessageEvent): void {
    console.log('AI Reporting: Received postMessage from origin:', event.origin);

    if (!this.isAllowedOrigin(event.origin)) {
      return;
    }

    if (!event.data?.type) {
      return;
    }

    switch (event.data.type) {
      case 'AUTH_TOKEN':
        if (event.data.token) {
          this.handleAuthToken(event);
        }
        break;
      case 'LOGOUT':
        console.log('🚪 AI Reporting: Received LOGOUT signal from Unity Grant Manager');
        this.clearToken();
        setTimeout(() => { window.location.href = '/access-denied'; }, 100);
        break;
      case 'PARENT_LOGOUT':
        console.log('🚪 AI Reporting: Received PARENT_LOGOUT signal');
        this.clearToken();
        window.location.href = '/access-denied';
        break;
    }
  }

  private isAllowedOrigin(origin: string): boolean {
    const allowedOrigins = this.configService.iframeOriginUrls;
    const originsLoaded = this.configService.iframeOriginsLoaded;
    const currentOrigin = window.location.origin;

    if (origin === currentOrigin) {
      console.log('❌ AI Reporting AUTH SERVICE: Rejected self-origin postMessage (security bypass attempt)');
      return false;
    }

    if (!originsLoaded) {
      console.log('❌ AI Reporting AUTH SERVICE: Origins not loaded yet - rejecting for security');
      return false;
    }

    if (allowedOrigins.length > 0 && !allowedOrigins.includes(origin)) {
      console.log('❌ AI Reporting AUTH SERVICE: Rejected token from unconfigured origin:', origin);
      return false;
    }

    console.log('✅ AI Reporting AUTH SERVICE: Origin validation passed');
    return true;
  }

  private handleAuthToken(event: MessageEvent): void {
    console.log('AI Reporting: Received JWT token via postMessage');
    this.setToken(event.data.token, true);

    if (event.source && typeof (event.source as Window).postMessage === 'function') {
      (event.source as Window).postMessage(
        { type: 'AUTH_TOKEN_RECEIVED', success: true },
        event.origin
      );
    }

    if (window.location.pathname === '/' || window.location.pathname.includes('access-denied')) {
      this.navigateToApp();
    }
  }

  private navigateToApp(): void {
    setTimeout(() => {
      try {
        const windowAny = window as any;
        if (windowAny.ng?.getComponent) {
          window.location.hash = '#/app';
        } else {
          window.history.pushState(null, '', '/app');
          window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
        }
      } catch (error) {
        window.location.href = '/app';
      }
    }, 200);
  }

  private sendReadyMessageToParent(): void {
    if (window.self !== window.top && window.parent) {
      try {
        const allowedOrigins = this.configService.iframeOriginUrls;
        for (const origin of allowedOrigins) {
          window.parent.postMessage({ type: 'READY' }, origin);
        }
        this.logger.info(`Sent READY message to ${allowedOrigins.length} allowed origin(s)`);
        this.setupParentLogoutDetection();
      } catch (error) {
        this.logger.error('Failed to send READY message to parent:', error);
      }
    }
  }

  private setupParentLogoutDetection(): void {
    try {
      if (window.parent && window.parent !== window) {
        let parentCheckCount = 0;
        const checkParentStatus = () => {
          try {
            if (window.parent?.location) {
              parentCheckCount = 0;
            }
          } catch (e) {
            parentCheckCount++;
            if (parentCheckCount >= 3) {
              this.clearToken();
              return;
            }
          }
        };
        setInterval(checkParentStatus, 10000);
      }
    } catch (error) {
      console.warn('AUTH SERVICE: Cannot access parent window for logout detection:', error);
    }

    window.addEventListener('beforeunload', () => {
      if (this.isInIframe() && !document.referrer.includes(window.location.hostname)) {
        this.clearToken();
      }
    });
  }

  setToken(token: string, fromPostMessage: boolean = false): void {

    this.tokenSubject.next(token);
    localStorage.setItem('ai_reporting', token);
    
    // Track when token was set for session management
    localStorage.setItem('ai_reporting_timestamp', Date.now().toString());
    
    // Track if token came from authorized postMessage
    if (fromPostMessage) {
      localStorage.setItem('ai_reporting_authorized', 'true');
      console.log('✅ Token marked as authorized (from postMessage)');
    } else {
      console.log('⚠️ Token set but not authorized (awaiting postMessage validation)');
    }
  }

  getToken(): string | null {
    return this.tokenSubject.value ?? localStorage.getItem('ai_reporting');
  }

  clearToken(): void {
    console.log('❌ AUTH SERVICE: Clearing token', {
      hadToken: !!this.getToken(),
      wasAuthorized: localStorage.getItem('ai_reporting_authorized') === 'true',
      timestamp: new Date().toISOString()
    });
    
    this.tokenSubject.next(null);
    localStorage.removeItem('ai_reporting');
    localStorage.removeItem('ai_reporting_authorized');
    localStorage.removeItem('ai_reporting_timestamp');
  }

  async isAuthenticated(): Promise<boolean> {
    console.log('🔍 isAuthenticated() called at:', new Date().toISOString());
    
    // Wait for initialization to complete
    await this.ensureInitialized();
    console.log('🔍 Initialization complete, proceeding with auth check');
    
    const token = this.getToken();
    console.log('🔍 Token retrieved:', {
      hasToken: !!token,
      tokenLength: token?.length ?? 0,
      tokenPreview: token?.substring(0, 20) + '...' || 'none'
    });

    // Check for null, undefined, empty string, or whitespace-only strings
    if (!token || token.trim() === '') {
      console.log('❌ No token found or empty token');
      return false;
    }

    // Check token age for session management
    const tokenTimestamp = localStorage.getItem('ai_reporting_timestamp');
    console.log('🔍 Token timestamp check:', {
      timestamp: tokenTimestamp,
      timestampDate: tokenTimestamp ? new Date(parseInt(tokenTimestamp)).toISOString() : null
    });
    
    if (tokenTimestamp) {
      const tokenAge = Date.now() - parseInt(tokenTimestamp);
      const maxAge = 8 * 60 * 60 * 1000; // 8 hours in milliseconds
      
      console.log('🔍 Token age check:', {
        tokenAge: tokenAge,
        tokenAgeMinutes: Math.floor(tokenAge / (60 * 1000)),
        maxAgeMinutes: Math.floor(maxAge / (60 * 1000)),
        isExpired: tokenAge > maxAge
      });
      
      if (tokenAge > maxAge) {
        console.log('❌ Token expired due to age (8+ hours old) - clearing');
        this.clearToken();
        return false;
      }
    }
    
    // Check if token was authorized via ORIGIN_URL validation
    const isAuthorized = localStorage.getItem('ai_reporting_authorized') === 'true';
    console.log('🔍 Authorization check:', {
      isAuthorized: isAuthorized,
      authValue: localStorage.getItem('ai_reporting_authorized'),
      authTimestamp: localStorage.getItem('ai_reporting_timestamp')
    });
    
    if (!isAuthorized) {
      console.log('❌ Token not authorized via ORIGIN_URL validation');
      console.log('🕰️ AUTH DEBUG: Token present but not authorized - allowing postMessage system time to authorize');
      // Don't clear token immediately - might be a race condition
      // Let the postMessage system have a chance to authorize it
      return false;
    }
    console.log('✅ Token authorization check passed');

    console.log('🔍 Token found, validating format...');

    // Check if token has the correct JWT format (three parts separated by dots)
    const parts = token.split('.');
    console.log('🔍 Token parts check:', {
      partsCount: parts.length,
      expectedParts: 3,
      isValidFormat: parts.length === 3
    });
    
    if (parts.length !== 3) {
      console.log('❌ Invalid token format - does not have 3 parts');
      return false;
    }

    // Check that each part is not empty
    const hasEmptyParts = parts.some(part => !part || part.trim() === '');
    console.log('🔍 Token parts content check:', {
      hasEmptyParts: hasEmptyParts,
      partLengths: parts.map(p => p.length)
    });
    
    if (hasEmptyParts) {
      console.log('❌ Invalid token format - has empty parts');
      return false;
    }

    console.log('✓ Token format is valid');

    // Decode and check expiration
    const payload = this.decodeToken(token);
    console.log('🔍 Token decode result:', {
      payloadDecoded: !!payload,
      payloadPreview: payload ? {
        userId: payload.user_id,
        tenant: payload.tenant,
        exp: payload.exp,
        isAdmin: payload['is_it_admin']
      } : null
    });
    
    if (!payload) {
      console.log('❌ Failed to decode token payload');
      return false;
    }

    // Check if token has expired
    if (payload.exp) {
      const currentTime = Math.floor(Date.now() / 1000); // Current time in seconds
      const expirationTime = payload.exp;

      console.log('🔍 Token expiration check:');
      console.log('  Current time:', currentTime, '(' + new Date(currentTime * 1000).toISOString() + ')');
      console.log('  Expiration time:', expirationTime, '(' + new Date(expirationTime * 1000).toISOString() + ')');

      if (currentTime >= expirationTime) {
        console.log('❌ Token has expired');
        // Clear expired token
        this.clearToken();
        return false;
      }

      const timeRemaining = expirationTime - currentTime;
      console.log('✓ Token is valid for', timeRemaining, 'more seconds');
    } else {
      console.log('⚠ Token has no expiration field (exp)');
    }

    // Validate token signature and authenticity with backend
    // To remove backend validation and only validate structure and expiry in frontend return true here
    console.log('🔍 Validating token with backend...');
    const isValidOnBackend = await this.validateTokenWithBackend();
    console.log('🔍 Backend validation result:', isValidOnBackend);

    if (!isValidOnBackend) {
      console.log('❌ Backend rejected token (invalid signature or unauthorized)');
      this.clearToken();
      return false;
    }

    console.log('✓ Backend confirmed token is valid');
    console.log('🎉 isAuthenticated() returning TRUE at:', new Date().toISOString());
    return true;
  }

  isAuthenticatedSync(): boolean {
    const token = this.getToken();
    
    // Check for null, undefined, empty string, or whitespace-only strings
    if (!token || token.trim() === '') {
      return false;
    }
    
    // Check if token has the correct JWT format (three parts separated by dots)
    const parts = token.split('.');
    if (parts.length !== 3) {
      return false;
    }
    
    // Check that each part is not empty
    if (parts.some(part => !part || part.trim() === '')) {
      return false;
    }
    
    // Basic token presence and format validation only
    return true;
  }

  async validateTokenWithBackend(): Promise<boolean> {
    const token = this.getToken();
    console.log('🔍 validateTokenWithBackend() starting:', {
      hasToken: !!token,
      tokenLength: token?.length ?? 0
    });
    
    if (!token) {
      console.log('❌ validateTokenWithBackend: No token available');
      return false;
    }

    try {
      // Make request to backend validation endpoint using configured API URL
      const apiUrl = this.configService.apiUrl;
      console.log('🔍 Backend validation request:', {
        apiUrl: apiUrl,
        endpoint: `${apiUrl}/validate-token`,
        hasAuthHeader: true
      });
      
      const response = await fetch(`${apiUrl}/validate-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      console.log('🔍 Backend validation response:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries())
      });

      if (response.ok) {
        const data = await response.json();
        console.log('🔍 Backend validation response data:', data);
        const isValid = data.valid === true;
        console.log('🔍 Backend validation result:', isValid);
        return isValid;
      } else {
        console.log('❌ Backend validation failed with status:', response.status);
        try {
          const errorData = await response.text();
          console.log('❌ Backend validation error response:', errorData);
        } catch (e) {
          console.warn('Could not read error response body:', e);
        }
      }

      return false;
    } catch (error) {
      console.error('❌ Token validation network error:', error);
      this.logger.error('Token validation error:', error);
      return false;
    }
  }

  decodeToken(token?: string): JwtPayload | null {
    const jwtToken = token ?? this.getToken();
    
    // Strict validation
    if (!jwtToken || jwtToken.trim() === '') {
      return null;
    }
    
    try {
      // Split JWT into parts
      const parts = jwtToken.split('.');
      if (parts.length !== 3) {
        return null;
      }
      
      // Validate each part exists and is not empty
      const [header, payload, signature] = parts;
      if (!header || !payload || !signature) {
        return null;
      }
      
      // Decode base64url payload (second part)
      const base64 = this.base64urlDecode(payload);
      const decodedPayload = JSON.parse(base64);
      
      // Validate payload is an object
      if (typeof decodedPayload !== 'object' || decodedPayload === null) {
        return null;
      }
      
      return decodedPayload as JwtPayload;
    } catch (error) {
      this.logger.error('Token decode error:', error);
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


  getTenantId(): string | null {
    const payload = this.decodeToken();
    return payload?.tenant ?? null;
  }

  getUserId(): string | null {
    const payload = this.decodeToken();
    return payload?.user_id ?? null;
  }

  /**
   * Get current authentication state for debugging
   */
  getAuthDebugInfo(): any {
    const token = this.getToken();
    const payload = token ? this.decodeToken(token) : null;
    
    return {
      hasToken: !!token,
      tokenLength: token?.length ?? 0,
      isAuthorized: localStorage.getItem('ai_reporting_authorized') === 'true',
      originsLoaded: this.configService.iframeOriginsLoaded,
      allowedOrigins: this.configService.iframeOriginUrls,
      currentOrigin: window.location.origin,
      isLocalDev: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1',
      tokenPayload: payload ? {
        userId: payload.user_id,
        tenant: payload.tenant,
        isAdmin: payload['is_it_admin'],
        exp: payload.exp,
        expiresAt: payload.exp ? new Date(payload.exp * 1000).toISOString() : null
      } : null,
      timestamp: new Date().toISOString()
    };
  }
}