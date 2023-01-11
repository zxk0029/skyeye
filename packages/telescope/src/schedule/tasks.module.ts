import { CacheModule, Module } from '@nestjs/common';
import { TasksService } from './tasks.service';
import { IngestionModule } from '../ingestion/module';

@Module({
  imports: [CacheModule.register(), IngestionModule],
  providers: [TasksService],
})
export class TasksModule {}
