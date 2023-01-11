import { Module } from '@nestjs/common';
import { IngestionService } from './service';
import { IngestionController } from './controller';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Asset } from 'src/typeorm';

@Module({
  imports: [IngestionModule, TypeOrmModule.forFeature([Asset])],
  controllers: [IngestionController],
  providers: [IngestionService],
  exports: [IngestionService],
})
export class IngestionModule {}
