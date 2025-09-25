import { TestBed } from '@angular/core/testing';

import { AguiService } from './agui.service';

describe('AguiService', () => {
  let service: AguiService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AguiService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
