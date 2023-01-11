import { TasksModule } from './schedule/tasks.module';
import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import entities from './typeorm';
import { ScheduleModule } from '@nestjs/schedule';
import { StatusMonitorModule } from 'nest-status-monitor';
import statusMonitorConfig from './config/statusMonitor';
import { IngestionService } from './ingestion/service';

@Module({
  imports: [
    StatusMonitorModule.setUp(statusMonitorConfig),
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        type: 'mysql',
        host: configService.get('DB_HOST'),
        port: +configService.get<number>('DB_PORT'),
        username: configService.get('DB_USERNAME'),
        password: configService.get('DB_PASSWORD'),
        database: configService.get('DB_NAME'),
        entities: entities,
        synchronize: false,
      }),
      inject: [ConfigService],
    }),
    ScheduleModule.forRoot(),
    TasksModule,
    IngestionService,
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
