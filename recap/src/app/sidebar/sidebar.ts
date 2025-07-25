import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../services/api.service';

export interface Chat {
  id: string;
  title: string;
  created_at: Date;
  updated_at: Date;
}

@Component({
  selector: 'app-sidebar',
  imports: [CommonModule],
  templateUrl: './sidebar.html',
  styleUrls: ['./sidebar.css']
})
export class SidebarComponent {
  @Input() isOpen: boolean = false;
  @Output() toggleSidebar = new EventEmitter<void>();
  @Output() chatSelected = new EventEmitter<Chat>();
  @Output() newChat = new EventEmitter<void>();

  chats: Chat[] = [];
  loading: boolean = false;

  constructor(private apiService: ApiService) {}

  async ngOnInit(): Promise<void> {
    await this.loadChats();
  }

  public async loadChats(): Promise<void> {
    try {
      this.loading = true;
      
      this.chats = await firstValueFrom(
        this.apiService.getChats<Chat[]>()
      );
    } catch (error) {
      this.chats = [];
    } finally {
      this.loading = false;
    }
  }

  onToggle(): void {
    this.toggleSidebar.emit();
  }

  onChatSelect(chat: Chat): void {
    this.chatSelected.emit(chat);
  }

  onNewChat(): void {
    this.newChat.emit();
  }

  formatToPST(dateString: Date): string {
    try {
      const date = new Date(dateString);
      
      // Format to PST (Pacific Standard Time)
      const options: Intl.DateTimeFormatOptions = {
        timeZone: 'America/Los_Angeles',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      };
      
      return date.toLocaleString('en-US', options);
    } catch (error) {
      return dateString.toString(); // Fallback to original string
    }
  }

  async deleteChat(chat: Chat, event: Event): Promise<void> {
    event.stopPropagation();
    
    if (!confirm('Are you sure you want to delete this chat?')) {
      return;
    }

    try {
      await firstValueFrom(
        this.apiService.deleteChat(chat.id)
      );

      this.chats = this.chats.filter(c => c.id !== chat.id);
    } catch (error) {
      // Handle error silently
    }
  }
}