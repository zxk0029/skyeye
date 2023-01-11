import { Injectable, Logger, Inject, CACHE_MANAGER } from '@nestjs/common';
import { Cache } from 'cache-manager';
import { Interval } from '@nestjs/schedule';
import { IngestionService } from '../ingestion/service';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class TasksService {
  constructor(
    private configService: ConfigService,
    private readonly IngestionService: IngestionService,
    @Inject(CACHE_MANAGER) private cacheManager: Cache,
  ) {
    this.initCache();
  }
  private readonly logger = new Logger(TasksService.name);
  async initCache() {
    console.log('you can handle cache here');
  }
  @Interval(2000)
  async uniswap() {
    console.log('uniswap');
  }
  @Interval(2000)
  async pancakeswap() {
    console.log('pancakeswap');
  }
  @Interval(2000)
  async sushiswap() {
    console.log('sushiswap');
  }
}
