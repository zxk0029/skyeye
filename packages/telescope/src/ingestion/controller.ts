import { IngestionService } from './service';
import { Controller, Get } from '@nestjs/common';

@Controller('/')
export class IngestionController {
  constructor(private readonly l1IngestionService: IngestionService) {}

  @Get('market')
  getMarket() {
    return '';
  }
}
