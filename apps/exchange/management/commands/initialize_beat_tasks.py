import json

from celery.schedules import crontab
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule

from skyeye.beat_schedules import DEFAULT_BEAT_SCHEDULE


class Command(BaseCommand):
    help = '将默认定时任务同步到数据库，同时保留手动修改过的任务'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制覆盖所有任务，包括手动修改过的任务',
        )
        parser.add_argument(
            '--only-new',
            action='store_true',
            help='只添加新任务，不更新已存在的任务',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始同步默认定时任务到数据库...'))
        beat_schedule = DEFAULT_BEAT_SCHEDULE
        force_update = options.get('force', False)
        only_new = options.get('only_new', False)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        if not beat_schedule:
            self.stdout.write(self.style.WARNING('没有找到默认定时任务配置'))
            return

        # 获取数据库中已存在的任务及其上次修改时间
        existing_tasks = {
            task.name: task
            for task in PeriodicTask.objects.filter(
                name__in=beat_schedule.keys()
            )
        }

        for task_name_from_code, task_config in beat_schedule.items():
            task_str = task_config['task']
            schedule_obj_from_code = task_config['schedule']
            task_options = task_config.get('options', {})
            task_args = task_config.get('args', [])
            task_kwargs = task_config.get('kwargs', {})
            queue = task_options.get('queue', 'celery')
            enabled = task_config.get('enabled', True)

            # 检查任务是否已存在且可能被手动修改过
            existing_task = existing_tasks.get(task_name_from_code)

            # 只添加新任务模式，如果任务已存在则跳过
            if only_new and existing_task:
                self.stdout.write(self.style.NOTICE(f'跳过已存在的任务: {task_name_from_code} (--only-new)'))
                skipped_count += 1
                continue

            # 非强制模式下，检查任务是否被修改过（通过比较参数）
            if not force_update and existing_task:
                # 任务时间安排被修改过
                schedule_modified = False
                if isinstance(schedule_obj_from_code, crontab) and existing_task.crontab:
                    cron_db = existing_task.crontab
                    if (str(schedule_obj_from_code._orig_minute) != cron_db.minute or
                            str(schedule_obj_from_code._orig_hour) != cron_db.hour or
                            str(schedule_obj_from_code._orig_day_of_week) != cron_db.day_of_week or
                            str(schedule_obj_from_code._orig_day_of_month) != cron_db.day_of_month or
                            str(schedule_obj_from_code._orig_month_of_year) != cron_db.month_of_year):
                        schedule_modified = True
                elif isinstance(schedule_obj_from_code, (int, float)) and existing_task.interval:
                    if int(schedule_obj_from_code) != existing_task.interval.every:
                        schedule_modified = True

                # 检查其他属性是否被修改
                args_modified = json.dumps(task_args) != existing_task.args
                kwargs_modified = json.dumps(task_kwargs) != existing_task.kwargs
                queue_modified = queue != existing_task.queue

                if schedule_modified or args_modified or kwargs_modified or queue_modified:
                    self.stdout.write(self.style.NOTICE(
                        f'跳过已手动修改的任务: {task_name_from_code}'
                    ))
                    skipped_count += 1
                    continue

            crontab_db = None
            interval_db = None

            if isinstance(schedule_obj_from_code, crontab):
                def cron_part_to_str(part):
                    if isinstance(part, (set, frozenset)):
                        return ",".join(map(str, sorted(list(part))))
                    return str(part)  # Handles "*", "*/5", "1-5", etc.

                crontab_values = {
                    'minute': cron_part_to_str(schedule_obj_from_code._orig_minute),
                    'hour': cron_part_to_str(schedule_obj_from_code._orig_hour),
                    'day_of_week': cron_part_to_str(schedule_obj_from_code._orig_day_of_week),
                    'day_of_month': cron_part_to_str(schedule_obj_from_code._orig_day_of_month),
                    'month_of_year': cron_part_to_str(schedule_obj_from_code._orig_month_of_year),
                    'timezone': timezone.get_current_timezone()
                }
                crontab_db, created = CrontabSchedule.objects.get_or_create(**crontab_values)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'创建CrontabSchedule: {crontab_values}'))

            elif isinstance(schedule_obj_from_code, (float, int)):
                # Interval schedule (seconds)
                interval_s = int(schedule_obj_from_code)
                interval_db, created = IntervalSchedule.objects.get_or_create(
                    every=interval_s,
                    period=IntervalSchedule.SECONDS
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'创建IntervalSchedule: 每{interval_s}秒'))
            else:
                self.stderr.write(self.style.ERROR(
                    f'不支持的时间表类型 {task_name_from_code}: {type(schedule_obj_from_code)}'
                ))
                continue

            # Create or update PeriodicTask
            defaults = {
                'task': task_str,
                'crontab': crontab_db,
                'interval': interval_db,
                'args': json.dumps(task_args),
                'kwargs': json.dumps(task_kwargs),
                'queue': queue,
                'enabled': enabled,
                'name': task_name_from_code,
                'description': f'从默认配置同步 ({timezone.now().strftime("%Y-%m-%d %H:%M:%S")})'
            }

            if not crontab_db:
                defaults.pop('crontab')
            if not interval_db:
                defaults.pop('interval')

            if existing_task and not force_update:
                # 如果任务存在且未被修改过，只更新描述字段
                existing_task.description = defaults['description']
                existing_task.save(update_fields=['description'])
                self.stdout.write(self.style.NOTICE(f'更新任务描述: {existing_task.name}'))
                updated_count += 1
            else:
                # 创建新任务或强制更新
                periodic_task, created = PeriodicTask.objects.update_or_create(
                    name=task_name_from_code,
                    defaults=defaults
                )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'创建定时任务: {periodic_task.name}'))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.NOTICE(f'更新定时任务: {periodic_task.name}'))

        self.stdout.write(self.style.SUCCESS(
            f'同步完成。创建: {created_count}个, 更新: {updated_count}个, 跳过: {skipped_count}个已修改的任务。'
        ))

        self.stdout.write(self.style.NOTICE(
            '提示：使用 --force 参数可以强制覆盖所有任务，--only-new 参数只添加新任务'
        ))
