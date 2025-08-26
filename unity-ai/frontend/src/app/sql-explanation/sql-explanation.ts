import { Component, Input, OnChanges, SimpleChanges, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-sql-explanation',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="sql-explanation" *ngIf="displayedText || isWaiting">
      <span>{{ displayedText }}</span>
      <span class="cursor" *ngIf="showCursor">█</span>
    </div>
  `,
  styles: [`
    .sql-explanation {
      font-size: 0.8em;
      margin: 8px;
    }
    
    .cursor {
      animation: blink 1s infinite;
      font-weight: normal;
      opacity: 0.8;
    }
    
    @keyframes blink {
      0%, 50% { opacity: 0.8; }
      51%, 100% { opacity: 0; }
    }
  `]
})
export class SqlExplanationComponent implements OnChanges, OnDestroy {
  @Input() explanation: string | undefined;
  displayedText: string = '';
  showCursor: boolean = false;
  isWaiting: boolean = false;
  private streamingInterval: any;
  private delayTimeout: any;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['explanation'] && this.explanation) {
      this.startDelayedStream();
    }
  }

  private startDelayedStream(): void {
    // Clear any existing intervals/timeouts
    this.clearTimers();
    
    this.displayedText = '';
    this.showCursor = true;
    this.isWaiting = true;
    
    // Wait 2 seconds before starting to stream
    this.delayTimeout = setTimeout(() => {
      this.streamText();
    }, 4000);
  }

  private streamText(): void {
    let currentIndex = 0;
    const fullText = this.explanation || '';
    
    // Stream letter by letter with a small delay
    this.streamingInterval = setInterval(() => {
      if (currentIndex < fullText.length) {
        this.displayedText += fullText[currentIndex];
        currentIndex++;
      } else {
        // Hide cursor when done streaming
        this.showCursor = false;
        clearInterval(this.streamingInterval);
      }
    }, 20); // 15ms delay between each letter
  }

  private clearTimers(): void {
    if (this.streamingInterval) {
      clearInterval(this.streamingInterval);
    }
    if (this.delayTimeout) {
      clearTimeout(this.delayTimeout);
    }
  }

  ngOnDestroy(): void {
    this.clearTimers();
  }
}