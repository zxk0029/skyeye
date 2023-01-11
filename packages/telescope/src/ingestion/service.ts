import { Injectable, Logger } from '@nestjs/common';

@Injectable()
export class IngestionService {
  async Test() {
    console.log('framework');
  }
}
