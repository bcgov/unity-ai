import { Component, ViewChild, ElementRef, NgZone, OnInit, OnDestroy } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { Embed } from './embed';
import { Turn } from './turn';
import { SqlLoaderComponent } from './sql-loader/sql-loader';
import { SqlExplanationComponent } from './sql-explanation/sql-explanation';
import { AuthService } from './services/auth.service';
import { ApiService } from './services/api.service';
import { IframeDetectorService } from './iframe-detector.service';
import { SidebarComponent, Chat } from './sidebar/sidebar';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule, SqlLoaderComponent, SqlExplanationComponent, SidebarComponent],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class App implements OnInit, OnDestroy {
  protected title = 'recap';
  protected api_url = environment.apiUrl;
  question: string = "";
  conversation: Turn[] = [];
  sidebarOpen: boolean = true;
  currentChatId: string | null = null;
  currentTurnIndex: number = 0;
  visualizationDropdownOpen: boolean = false;
  selectedVisualization: string = 'table';

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

    // Add window resize listener to maintain scroll position
    window.addEventListener('resize', this.resizeListener);
    
    // Add click listener to close dropdown when clicking outside
    document.addEventListener('click', this.handleDocumentClick);
  }

  private onWindowResize(): void {
    // Debounce resize events to avoid excessive scrolling
    clearTimeout(this.resizeTimeout);
    this.resizeTimeout = setTimeout(() => {
      if (this.conversation.length > 0) {
        this.scrollToTurn(this.currentTurnIndex);
      }
    }, 150);
  }

  private resizeTimeout: any;
  private resizeListener = () => this.onWindowResize();
  private handleDocumentClick = (event: Event) => this.onDocumentClick(event);

  private onDocumentClick(event: Event): void {
    const target = event.target as HTMLElement;
    const dropdownElement = target.closest('.visualization-dropdown');
    
    // If click is outside the dropdown, close it
    if (!dropdownElement && this.visualizationDropdownOpen) {
      this.visualizationDropdownOpen = false;
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

  private observerMap = new Map<any, IntersectionObserver>();

  // In your component class, add a method:
  onIframeLoad(turn: any) {
    // Start observing the iframe for content stability
    this.observeIframeStability(turn);
  }

  private observeIframeStability(turn: any): void {
    // Clean up any existing observer for this turn
    if (this.observerMap.has(turn)) {
      this.observerMap.get(turn)?.disconnect();
      this.observerMap.delete(turn);
    }

    // Find the iframe element for this turn
    const iframeElement = document.querySelector(`iframe[src*="${turn.embed?.card_id}"]`) as HTMLIFrameElement;
    if (!iframeElement) {
      // Fallback to timeout if iframe not found
      setTimeout(() => turn.iframeLoaded = true, 2000);
      return;
    }

    let stableCount = 0;
    let lastHeight = 0;
    let lastWidth = 0;
    const requiredStableChecks = 3;
    const checkInterval = 500;

    const checkStability = () => {
      try {
        // Check if iframe dimensions have stabilized
        const currentHeight = iframeElement.offsetHeight;
        const currentWidth = iframeElement.offsetWidth;

        // Also check if the iframe has actual content by looking at its document
        let hasContent = false;
        try {
          const iframeDoc = iframeElement.contentDocument || iframeElement.contentWindow?.document;
          if (iframeDoc && iframeDoc.body) {
            // Check if there's meaningful content (not just loading states)
            const bodyContent = iframeDoc.body.innerText || '';
            const hasElements = iframeDoc.body.children.length > 0;
            hasContent = bodyContent.length > 10 || hasElements;
          }
        } catch (crossOriginError) {
          // Cross-origin iframe, can't access content - rely on dimensions only
          hasContent = true;
        }

        if (currentHeight === lastHeight && currentWidth === lastWidth && currentHeight > 0 && hasContent) {
          stableCount++;
          if (stableCount >= requiredStableChecks) {
            // Content appears stable and has actual content
            turn.iframeLoaded = true;
            clearInterval(stabilityChecker);
            return;
          }
        } else {
          stableCount = 0;
        }

        lastHeight = currentHeight;
        lastWidth = currentWidth;
      } catch (error) {
        // If we can't access iframe properties, fall back to timeout
        clearInterval(stabilityChecker);
        setTimeout(() => turn.iframeLoaded = true, 1000);
      }
    };

    // Check stability every 500ms
    const stabilityChecker = setInterval(checkStability, checkInterval);

    // Maximum timeout as fallback (10 seconds)
    setTimeout(() => {
      clearInterval(stabilityChecker);
      if (!turn.iframeLoaded) {
        turn.iframeLoaded = true;
      }
    }, 10000);
  }

  async redirectToMB(turn: Turn) {
    return window.open(`${this.authService.getMetabaseUrl()}/question/${turn.embed.card_id}`, '_blank');
  }

  async deleteQuestion(turn: Turn) {
    try {
      // Delete the card from the backend
      await firstValueFrom(
        this.apiService.deleteCard(turn.embed.card_id)
      );
      
      // Find the index of the turn being deleted
      const deletedIndex = this.conversation.findIndex(t => t === turn);
      
      // Remove the turn from the conversation
      this.conversation = this.conversation.filter(t => t !== turn);
      
      // If this was the last question in the chat, delete the chat entirely
      if (this.conversation.length === 0 && this.currentChatId) {
        try {
          await firstValueFrom(
            this.apiService.deleteChat(this.currentChatId)
          );
          this.currentChatId = null;
          
          // Refresh the sidebar to remove the deleted chat
          if (this.sidebar) {
            this.sidebar.loadChats();
          }
        } catch (deleteError) {
          console.error('Error deleting empty chat:', deleteError);
        }
        return; // Exit early since there's nothing left to update
      }
      
      // Adjust currentTurnIndex if necessary
      if (deletedIndex <= this.currentTurnIndex && this.currentTurnIndex > 0) {
        this.currentTurnIndex = Math.max(0, this.currentTurnIndex - 1);
      } else if (this.currentTurnIndex >= this.conversation.length) {
        this.currentTurnIndex = Math.max(0, this.conversation.length - 1);
      }
      
      // Update dropdown selection for the new current turn
      this.updateDropdownSelection();
      
      // Save the updated conversation to the database
      await this.saveChat();
      
    } catch (error) {
      // Handle error silently or show user feedback
      console.error('Error deleting question:', error);
    }
  }

  async changeDisplay(turn: Turn, mode: string) {
    try {
      const res = await firstValueFrom(
        this.apiService.changeDisplay<Embed>(turn.embed.card_id, mode, turn.embed.x_field, turn.embed.y_field)
      );
      turn.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(res.url + '&cb=' + Date.now());
      // Update the current visualization in the embed
      turn.embed.current_visualization = mode;
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
    
    // Always reset to table visualization for new questions
    this.selectedVisualization = 'table';
    
    const turn = {question: this.question.trim(), embed: {"url": "", "card_id": 0, "x_field": "", "y_field": "", "title": "", "visualization_options": [], "SQL": ""}, safeUrl: 'loading' as 'loading' | 'failure' | SafeResourceUrl, iframeLoaded: false, sqlPanelOpen: false, sql_explanation: ""} as Turn;
    this.conversation.push(turn);
    
    // Set the new turn as the current turn for navigation
    this.currentTurnIndex = this.conversation.length - 1;
    
    this.scrollToBottom();   
    this.question = "";
    try {
      if (! await this.authService.isAuthenticated()) throw new Error('Not authenticated');
      
      turn.embed = await firstValueFrom(
        this.apiService.askQuestion<Embed>(turn.question, this.conversation)
      );

      if (turn.embed.url == "fail") {
        throw new Error;
      }
      
      // Fetch SQL explanation after SQL is generated
      if (turn.embed.SQL) {
        try {
          const explanationResponse = await firstValueFrom(
            this.apiService.explainSql<{ explanation: string }>(turn.embed.SQL)
          );
          turn.embed.sql_explanation = explanationResponse.explanation;
        } catch (error) {
          // If explanation fails, use a default message
          turn.embed.sql_explanation = "This query retrieves and analyzes your data.";
        }
      }
      
      // New questions always start as table view
      turn.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(turn.embed.url);
      turn.embed.current_visualization = 'table';
      
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
    this.selectedVisualization = 'table'; // Reset to default
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
      
      // Update dropdown selection based on the current turn
      this.updateDropdownSelection();
      
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

      // Use the most recent embed's title, or fall back to the first question
      const mostRecentTurn = this.conversation[this.conversation.length - 1];
      const chatTitle = mostRecentTurn?.embed?.title || this.conversation[0]?.question || 'New Chat';

      const response = await firstValueFrom(
        this.apiService.saveChat<{chat_id: string}>(this.currentChatId, this.conversation, chatTitle)
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
      this.updateDropdownSelection();
    }
  }

  scrollToNextTurn(): void {
    if (this.currentTurnIndex < this.conversation.length - 1) {
      this.currentTurnIndex++;
      this.scrollToTurn(this.currentTurnIndex);
      this.updateDropdownSelection();
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

  toggleVisualizationDropdown(): void {
    // Only toggle if there are other options available
    if (this.hasOtherVisualizationOptions()) {
      this.visualizationDropdownOpen = !this.visualizationDropdownOpen;
    }
  }

  async selectVisualization(type: string): Promise<void> {
    this.selectedVisualization = type;
    this.visualizationDropdownOpen = false;
    
    // If we have a current turn, apply the visualization change immediately
    if (this.conversation.length > 0 && this.currentTurnIndex >= 0 && this.currentTurnIndex < this.conversation.length) {
      const currentTurn = this.conversation[this.currentTurnIndex];
      if (currentTurn.embed && currentTurn.embed.card_id) {
        await this.changeDisplay(currentTurn, type);
        // Save the chat to persist the visualization change
        await this.saveChat();
      }
    }
  }

  getVisualizationDisplayName(type: string): string {
    const names: { [key: string]: string } = {
      'table': 'Table',
      'bar': 'Bar Chart',
      'line': 'Line Chart',
      'pie': 'Pie Chart',
      'map': 'Map'
    };
    return names[type] || type;
  }

  getAvailableVisualizationOptions(): string[] {
    // Always include table as it's the default
    const options = ['table'];
    const all_options = ['bar', 'line', 'pie', 'map'];
    
    // If we have a conversation, get options from the current turn
    if (this.conversation.length > 0 && this.currentTurnIndex >= 0 && this.currentTurnIndex < this.conversation.length) {
      const currentTurn = this.conversation[this.currentTurnIndex];
      
      if (currentTurn.embed?.visualization_options) {
        // Add available options from the current turn, avoiding duplicates
        currentTurn.embed.visualization_options.forEach(option => {
          if (!options.includes(option) && all_options.includes(option)) {
            options.push(option);
          }
        });
      }
    } else {
      // If no conversation yet, show all possible options
      options.push(...all_options);
    }
    
    return options;
  }

  hasOtherVisualizationOptions(): boolean {
    const availableOptions = this.getAvailableVisualizationOptions();
    return availableOptions.some(option => option !== this.selectedVisualization);
  }

  updateDropdownSelection(): void {
    if (this.conversation.length > 0 && this.currentTurnIndex >= 0 && this.currentTurnIndex < this.conversation.length) {
      const currentTurn = this.conversation[this.currentTurnIndex];
      if (currentTurn.embed?.current_visualization) {
        this.selectedVisualization = currentTurn.embed.current_visualization;
      } else if (currentTurn.embed) {
        // For older chats without current_visualization, default to table and save it
        this.selectedVisualization = 'table';
        currentTurn.embed.current_visualization = 'table';
      } else {
        // Default to table if no embed data
        this.selectedVisualization = 'table';
      }
    } else {
      // No conversation or invalid turn index
      this.selectedVisualization = 'table';
    }
  }

  ngOnDestroy(): void {
    // Clean up event listeners and timeouts
    window.removeEventListener('resize', this.resizeListener);
    document.removeEventListener('click', this.handleDocumentClick);
    clearTimeout(this.resizeTimeout);
  }

}
