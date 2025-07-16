import { Component, Input, OnInit } from '@angular/core';

@Component({
  selector: 'sql-loader',
  template: `
    <div class="sql-loader">
      <pre>{{displayedText}}</pre>
    </div>
  `,
  styleUrls: ['./sql-loader.css']
})
export class SqlLoaderComponent implements OnInit {
  @Input() segments: string[] = [
`SELECT
  a."RegionalDistrict",
  SUM(a."ApprovedAmount") AS total_approved
FROM "public"."Applications" AS a
JOIN "public"."ApplicationStatuses" AS s
  ON a."ApplicationStatusId" = s."Id"
WHERE s."ExternalStatus" = 'Approved'
GROUP BY a."RegionalDistrict"
ORDER BY total_approved DESC`,

`SELECT
  EXTRACT(MONTH FROM "SubmissionDate") AS month,
  COUNT(*) AS monthly_count
FROM "public"."Applications"
WHERE "SubmissionDate" IS NOT NULL
GROUP BY month
ORDER BY month`,

`SELECT
  "Status",
  COUNT(*) AS assessment_count
FROM "public"."Assessments"
GROUP BY "Status"
ORDER BY assessment_count DESC`,

`SELECT
  ap."Sector",
  COUNT(*) AS application_count
FROM "public"."Applications" AS a
JOIN "public"."Applicants" AS ap
  ON a."ApplicantId" = ap."Id"
GROUP BY ap."Sector"
ORDER BY application_count DESC`,

`SELECT
  AVG("ApprovedAmount") AS avg_funding_2024
FROM "public"."Applications"
WHERE EXTRACT(YEAR FROM "ProjectEndDate") = 2024`,

`SELECT
  s."ExternalStatus",
  COUNT(*) AS application_count
FROM "public"."Applications" AS a
JOIN "public"."ApplicationStatuses" AS s
  ON a."ApplicationStatusId" = s."Id"
GROUP BY s."ExternalStatus"
ORDER BY application_count DESC`,

`SELECT
  COUNT(*) AS indigenous_app_count
FROM "public"."Applications" AS a
JOIN "public"."Applicants" AS ap
  ON a."ApplicantId" = ap."Id"
WHERE ap."IndigenousOrgInd" = 'Yes'`,

`SELECT
  "City",
  SUM("RequestedAmount") AS total_requested
FROM "public"."Applications"
GROUP BY "City"
ORDER BY total_requested DESC`
  ];
  displayedText = '';
  private segmentIndex = 0;
  private charIndex = 0;
  private typingInterval: any;

  ngOnInit() {
    setTimeout(() => this.startTyping(), 700);
  }

  startTyping() {
    this.displayedText = '';
    this.charIndex = 0;
    this.typingInterval = setInterval(() => {
      const currentSegment = this.segments[this.segmentIndex];
      if (this.charIndex < currentSegment.length) {
        this.displayedText += currentSegment[this.charIndex];
        this.charIndex++;
      } else {
        setTimeout(() => {
          this.segmentIndex = (this.segmentIndex + 1) % this.segments.length;
          this.displayedText = '';
          this.charIndex = 0;
        }, 900);
        clearInterval(this.typingInterval);
        setTimeout(() => this.startTyping(), 900);
      }
    }, 10); // Typing speed
  }
}