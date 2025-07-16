import { Embed } from './embed';
import { SafeResourceUrl } from '@angular/platform-browser';

export interface Turn {
  question: string;
  embed: Embed;
  safeUrl: SafeResourceUrl | null; 
  iframeLoaded: boolean; // Optional property to track if the iframe has loaded
}