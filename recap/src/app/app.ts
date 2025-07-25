import { Component, ViewChild, ElementRef, NgZone, OnInit } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { Embed } from './embed';
import { Turn } from './turn';
import { SqlLoaderComponent } from './sql-loader/sql-loader';
import { AuthService } from './services/auth.service';
import { ApiService } from './services/api.service';
import { IframeDetectorService } from './iframe-detector.service';
import { SidebarComponent, Chat } from './sidebar/sidebar';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule, SqlLoaderComponent, SidebarComponent],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class App implements OnInit {
  protected title = 'recap';
  protected api_url = environment.apiUrl;
  protected mb_url = environment.mbUrl;
  question: string = "";
  conversation: Turn[] = [];
  sidebarOpen: boolean = true;
  currentChatId: string | null = null;
  currentTurnIndex: number = 0;

  constructor(
    private sanitizer: DomSanitizer,
    private authService: AuthService,
    private apiService: ApiService,
    private iframeDetector: IframeDetectorService
  ) {}

  @ViewChild('turnsContainer') private turnsContainer!: ElementRef<HTMLDivElement>;
  @ViewChild('sqlAnimationContainer') private sqlAnimationContainer!: ElementRef<HTMLDivElement>;
  @ViewChild('sidebar') private sidebar!: SidebarComponent;

  async ngOnInit(): Promise<void> {
    // Add iframe-specific styling
    this.iframeDetector.addIframeClass();
    
    // Check if running in iframe and authenticated
    if (this.iframeDetector.isInIframe()) {
      const isAuthenticated = await this.authService.isAuthenticated();
      if (!isAuthenticated) {
        // Block the application from functioning
        document.body.innerHTML = '<div style="text-align: center; padding: 50px; font-family: Arial;"><h2>Authentication Required</h2><p>Invalid or missing authentication token.</p></div>';
        return;
      }
    }
  }

  private scrollToBottom(): void {
    // Wait until the DOM update that adds the message is done
    setTimeout(() => {
      if (this.turnsContainer) {
        this.turnsContainer.nativeElement.scroll({
          top:  this.turnsContainer.nativeElement.scrollHeight,
          behavior: 'smooth'          // ↳ animated; drop for instant jump
        });
      }
    }, 0);
  }

  private scrollToBottomInstant(): void {
    // Wait until the DOM update that adds the message is done
    setTimeout(() => {
      if (this.turnsContainer) {
        this.turnsContainer.nativeElement.scrollTop = this.turnsContainer.nativeElement.scrollHeight;
      }
    }, 0);
  }

  scrollSqlToBottom(): void {
    if (this.sqlAnimationContainer) {
      this.sqlAnimationContainer.nativeElement.scrollTop = this.sqlAnimationContainer.nativeElement.scrollHeight;
    }
  }

  toggleSqlPanel(turn: Turn): void {
    turn.sqlPanelOpen = !turn.sqlPanelOpen;
  }

  // In your component class, add a method:
  onIframeLoad(turn: any) {
    // Give more time for the Metabase embed to fully render
    setTimeout(() => {
      turn.iframeLoaded = true;
    }, 3000);
  }

  async redirectToMB(turn: Turn) {
    return window.open(`${this.mb_url}/question/${turn.embed.card_id}`, '_blank');
  }

  async deleteQuestion(turn: Turn) {
    await firstValueFrom(
      this.apiService.deleteCard(turn.embed.card_id)
    );
    this.conversation = this.conversation.filter(t => t !== turn);
  }

  async changeDisplay(turn: Turn, mode: string) {
    try {
      const res = await firstValueFrom(
        this.apiService.changeDisplay<Embed>(turn.embed.card_id, mode, turn.embed.x_field, turn.embed.y_field)
      );
      turn.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(res.url + '&cb=' + Date.now());
      // turn.embed = res;
    } catch (error) {
      // Handle error silently
    }
  }

  async resetConversation() {
    this.conversation = [];
    this.currentTurnIndex = 0;
  }

  async askQuestion() {
    if (this.question.trim() === "") {
      alert("Please enter a question.");
      return;
    }
    const turn = {question: this.question.trim(), embed: {"url": "", "card_id": 0, "x_field": "", "y_field": "", "visualization_options": [], "SQL": ""}, safeUrl: 'loading' as 'loading' | 'failure' | SafeResourceUrl, iframeLoaded: false, sqlPanelOpen: false} as Turn;
    this.conversation.push(turn);
    this.scrollToBottom();   
    this.question = "";
    try {
      if (! await this.authService.isAuthenticated()) throw new Error('Not authenticated');
      
      turn.embed = await firstValueFrom(
        this.apiService.askQuestion<Embed>(turn.question, this.conversation)
      );
      turn.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(turn.embed.url);
      await this.saveChat();
    } catch (error) {
      turn.iframeLoaded = true;
      turn.safeUrl = "failure";
      // Error is handled by setting failure state
    }
  }

  retryQuestion(turn: Turn): void {
    // Reset the turn state and retry the question
    turn.safeUrl = "loading";
    turn.iframeLoaded = false;
    turn.sqlPanelOpen = false;
    
    // Retry the question with the existing turn
    this.question = turn.question;
    this.conversation = this.conversation.filter(t => t !== turn);
    this.askQuestion();
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
    
    // Refresh chat list when opening sidebar
    if (this.sidebarOpen && this.sidebar) {
      this.sidebar.loadChats();
    }
  }

  onChatSelected(chat: Chat): void {
    this.loadChat(chat.id);
  }

  onNewChat(): void {
    this.conversation = [];
    this.currentChatId = null;
    this.currentTurnIndex = 0;
  }

  async loadChat(chatId: string): Promise<void> {
    try {
      if (!await this.authService.isAuthenticated()) {
        throw new Error('Not authenticated');
      }

      const chatData = await firstValueFrom(
        this.apiService.getChat<{conversation: Turn[]}>(chatId)
      );

      this.conversation = chatData.conversation.map(turn => ({
        ...turn,
        safeUrl: turn.embed?.url ? this.sanitizer.bypassSecurityTrustResourceUrl(turn.embed.url) : 'failure',
        iframeLoaded: !turn.embed?.url // If no URL (failure), mark as loaded
      }));
      
      this.currentChatId = chatId;
      this.currentTurnIndex = Math.max(0, this.conversation.length - 1);
      
      // Scroll to bottom instantly after loading chat
      this.scrollToBottomInstant();
    } catch (error) {
      // Handle error silently
    }
  }

  async saveChat(): Promise<void> {
    if (this.conversation.length === 0) return;

    try {
      if (!await this.authService.isAuthenticated()) {
        throw new Error('Not authenticated');
      }

      const response = await firstValueFrom(
        this.apiService.saveChat<{chat_id: string}>(this.currentChatId, this.conversation, this.conversation[0]?.question || 'New Chat')
      );

      this.currentChatId = response.chat_id;
      
      // Refresh the chat list in the sidebar
      if (this.sidebar) {
        this.sidebar.loadChats();
      }
    } catch (error) {
      // Handle error silently
    }
  }

  scrollToPreviousTurn(): void {
    if (this.currentTurnIndex > 0) {
      this.currentTurnIndex--;
      this.scrollToTurn(this.currentTurnIndex);
    }
  }

  scrollToNextTurn(): void {
    if (this.currentTurnIndex < this.conversation.length - 1) {
      this.currentTurnIndex++;
      this.scrollToTurn(this.currentTurnIndex);
    }
  }

  private scrollToTurn(index: number): void {
    if (this.turnsContainer) {
      const turnElements = this.turnsContainer.nativeElement.querySelectorAll('.turn');
      if (turnElements[index]) {
        const turnElement = turnElements[index] as HTMLElement;
        const containerElement = this.turnsContainer.nativeElement;
        
        // Get the turn's position relative to the container's scroll area
        const containerRect = containerElement.getBoundingClientRect();
        const turnRect = turnElement.getBoundingClientRect();
        
        // Calculate the scroll position needed
        const scrollTop = containerElement.scrollTop + (turnRect.top - containerRect.top);
        
        // Scroll the container to show the turn at the top
        containerElement.scrollTo({
          top: scrollTop,
          behavior: 'smooth'
        });
      }
    }
  }

}
