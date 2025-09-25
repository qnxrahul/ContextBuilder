import { Component, ElementRef, Input, OnChanges, SimpleChanges, inject } from '@angular/core';
import * as AdaptiveCards from 'adaptivecards';
import { Template } from 'adaptivecards-templating';

@Component({
  standalone: true,
  selector: 'adaptive-card',
  template: `<div class="ac"></div>`,
  styles: [`.ac{width:100%;}`]
})
export class AdaptiveCardComponent implements OnChanges {
  @Input() templateJson: any;
  @Input() data: any;

  private host = inject(ElementRef<HTMLElement>);

  ngOnChanges(_changes: SimpleChanges): void {
    const container = this.host.nativeElement.querySelector('.ac') as HTMLElement;
    if (!container || !this.templateJson) return;
    container.innerHTML = '';

    const card = new AdaptiveCards.AdaptiveCard();
    const template = new Template(this.templateJson);
    const expanded = template.expand({ $root: this.data ?? {} });
    card.parse(expanded);
    const rendered = card.render();
    container.appendChild(rendered);
  }
}

