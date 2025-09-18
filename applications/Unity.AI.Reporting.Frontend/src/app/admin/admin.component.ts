import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { ApiService } from '../services/api.service';

interface FeedbackItem {
  feedback_id: string;
  chat_id: string;
  user_id: string;
  tenant_id: string;
  feedback_type: string;
  message: string;
  user_agent: string;
  metadata: any;
  status: string;
  created_at: string;
  updated_at: string;
  chat_title: string;
  current_question: string;
  current_sql: string;
  current_sql_explanation: string;
  previous_question: string;
  previous_sql: string;
  previous_sql_explanation: string;
}

interface FeedbackResponse {
  feedback: FeedbackItem[];
  limit: number;
  offset: number;
  count: number;
}

interface FeedbackSummary {
  total: number;
  open: number;
  inProgress: number;
  resolved: number;
}

@Component({
  selector: 'app-admin',
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.component.html',
  styleUrls: ['./admin.component.css']
})
export class AdminComponent implements OnInit {
  feedbackList: FeedbackItem[] = [];
  filteredFeedback: FeedbackItem[] = [];
  isLoading = false;
  errorMessage = '';
  selectedStatus = '';
  selectedType = '';
  feedbackSummary: FeedbackSummary | null = null;

  constructor(
    private readonly router: Router,
    private readonly authService: AuthService,
    private readonly apiService: ApiService
  ) {}

  async ngOnInit(): Promise<void> {
    await this.loadFeedback();
  }

  async loadFeedback(): Promise<void> {
    this.isLoading = true;
    this.errorMessage = '';

    try {
      const response = await firstValueFrom(
        this.apiService.getAllFeedback<FeedbackResponse>()
      );

      this.feedbackList = response.feedback;
      this.filteredFeedback = [...this.feedbackList];
      this.calculateSummary();
      this.filterFeedback();

    } catch (error) {
      console.error('Error loading feedback:', error);
      this.errorMessage = 'Failed to load feedback. Please try again.';
    } finally {
      this.isLoading = false;
    }
  }

  filterFeedback(): void {
    this.filteredFeedback = this.feedbackList.filter(feedback => {
      const statusMatch = !this.selectedStatus || feedback.status === this.selectedStatus;
      const typeMatch = !this.selectedType || feedback.feedback_type === this.selectedType;
      return statusMatch && typeMatch;
    });
  }

  calculateSummary(): void {
    this.feedbackSummary = {
      total: this.feedbackList.length,
      open: this.feedbackList.filter(f => f.status === 'open').length,
      inProgress: this.feedbackList.filter(f => f.status === 'in_progress').length,
      resolved: this.feedbackList.filter(f => f.status === 'resolved').length
    };
  }

  async updateFeedbackStatus(feedbackId: string, event: Event): Promise<void> {
    const target = event.target as HTMLSelectElement;
    const newStatus = target.value;

    try {
      // Update in the local array immediately for better UX
      const feedback = this.feedbackList.find(f => f.feedback_id === feedbackId);
      if (feedback) {
        feedback.status = newStatus;
        this.calculateSummary();
        this.filterFeedback();
      }

      // TODO: Add API call to update status in backend
      // await firstValueFrom(this.apiService.updateFeedbackStatus(feedbackId, newStatus));

    } catch (error) {
      console.error('Error updating feedback status:', error);
      // Revert the change on error
      await this.loadFeedback();
    }
  }

  formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  }

  formatMetadata(metadata: any): string {
    if (!metadata) return '';
    return JSON.stringify(metadata, null, 2);
  }

  logout(): void {
    this.authService.clearToken();
    window.location.href = '/';
  }

  goToMainApp(): void {
    this.router.navigate(['/app']);
  }
}