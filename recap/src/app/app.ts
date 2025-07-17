import { Component, ViewChild, ElementRef, NgZone } from '@angular/core';
import { HttpHeaders, HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { Embed } from './embed';
import { Turn } from './turn';
import { SqlLoaderComponent } from './sql-loader/sql-loader';
@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule, SqlLoaderComponent],
  templateUrl: './app.html',
  styleUrls: ['./app.css']
})
export class App {
  protected title = 'recap';
  protected api_url = 'https://fluffy-goldfish-69wqj5wg6wwjhrvv4-5000.app.github.dev/api';
  protected mb_url = 'https://test-unity-reporting.apps.silver.devops.gov.bc.ca';
  question: string = "";
  conversation: Turn[] = [];

  constructor(
    private http: HttpClient,
    private sanitizer: DomSanitizer
  ) {}

  @ViewChild('scrollBox') private scrollBox!: ElementRef<HTMLDivElement>;
  @ViewChild('sqlAnimationContainer') private sqlAnimationContainer!: ElementRef<HTMLDivElement>;

  private scrollToBottom(): void {
    // Wait until the DOM update that adds the message is done
    setTimeout(() => {
      if (this.scrollBox) {
        this.scrollBox.nativeElement.scroll({
          top:  this.scrollBox.nativeElement.scrollHeight,
          behavior: 'smooth'          // ↳ animated; drop for instant jump
        });
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
    console.log('Iframe loaded:', turn.embed.card_id);
    setTimeout(() => {
      turn.iframeLoaded = true;
    }, 1000);
    // turn.iframeLoaded = true;
  }

  async redirectToMB(turn: Turn) {
    return window.location.href = `${this.mb_url}/question/${turn.embed.card_id}`;
  }

  async deleteQuestion(turn: Turn) {
    await firstValueFrom(
      this.http.get(`${this.api_url}/delete/${turn.embed.card_id}`)
    );
    this.conversation = this.conversation.filter(t => t !== turn);
  }

  async changeDisplay(turn: Turn, mode: string) {
    try {
      const body = { mode: mode, card_id: turn.embed.card_id, x_field: turn.embed.x_field, y_field: turn.embed.y_field };
      const res = await firstValueFrom(
        this.http.post<Embed>(`${this.api_url}/change_display`, body)
      );
      turn.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(res.url + '&cb=' + Date.now());
      // turn.embed = res;
    } catch (error) {
      console.error(error);
    }
  }

  async resetConversation() {
    this.conversation = [];
  }

  async askQuestion() {
    if (this.question.trim() === "") {
      alert("Please enter a question.");
      return;
    }
    const turn = {question: this.question.trim(), embed: {"url": "", "card_id": 0, "x_field": "", "y_field": "", "visualization_options": [], "SQL": ""}, safeUrl: 'loading' as 'loading' | 'failure' | SafeResourceUrl, iframeLoaded: false, sqlPanelOpen: false} as Turn;
    this.conversation.push(turn);
    this.scrollToBottom();   
    // Logic to handle the question can be added here
    console.log("Question asked:", this.question);
    this.question = "";
    try {
      const body = { question: turn.question };
      turn.embed = await firstValueFrom(
        this.http.post<Embed>(`${this.api_url}/ask`, body, {
          headers: new HttpHeaders({
          'Content-Type': 'application/json'
          })
        })
      );
      console.log(turn.embed);
      turn.safeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(turn.embed.url);
    } catch (error) {
      console.error(error);
    }
  }


}
