import datetime
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import ProgrammingError, OperationalError
from dateutil.relativedelta import relativedelta
import logging

# Try to import psycopg2 errorcodes, fail gracefully if psycopg2 is not the backend
try:
    from psycopg2 import errorcodes as psycopg2_errorcodes
except ImportError:
    psycopg2_errorcodes = None # Define as None if import fails

# Configure logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Creates kline partitions for the current month and N future months.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--months',
            type=int,
            default=3,
            help='Number of future months to create partitions for (default: 3). Includes the current month in the count.'
        )

    def handle(self, *args, **options):
        months_to_create = options['months']
        if months_to_create <= 0:
            self.stdout.write(self.style.ERROR('Please provide a positive number for --months.'))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting kline partition creation for {months_to_create} months (including current)."))

        current_date = datetime.date.today()

        for i in range(months_to_create):
            target_date = current_date + relativedelta(months=i)
            target_year = target_date.year
            target_month = target_date.month

            self.stdout.write(f"Attempting to create/ensure partitions for {target_year}-{target_month:02d}...")
            try:
                with connection.cursor() as cursor:
                    # The PL/pgSQL function is expected to handle "IF NOT EXISTS" logic internally
                    # and provide its own notices.
                    cursor.execute("SELECT create_klines_partitions_for_month(%s, %s);", [target_year, target_month])
                
                # If the PL/pgSQL function correctly handles "already exists" with a NOTICE and no error,
                # this success message will be accurate.
                self.stdout.write(self.style.SUCCESS(f"Successfully processed partitions for {target_year}-{target_month:02d}. Check DB notices for details (e.g., 'partition already exists' or 'created partition')."))
            except (ProgrammingError, OperationalError) as e: # Catch specific DB errors
                if psycopg2_errorcodes and hasattr(e, 'pgcode') and e.pgcode == psycopg2_errorcodes.DUPLICATE_TABLE:
                    self.stdout.write(self.style.SUCCESS(f"Partitions for {target_year}-{target_month:02d} already exist (confirmed by database)."))
                    logger.info(f"Partitions for {target_year}-{target_month:02d} already exist: {e}")
                else:
                    # Log the full error details for other DB errors
                    logger.error(f"Database error while processing partitions for {target_year}-{target_month:02d}: {e} (pgcode: {getattr(e, 'pgcode', 'N/A')})", exc_info=True)
                    self.stderr.write(self.style.ERROR(f"A database error occurred for {target_year}-{target_month:02d}. See logs for details. Error: {e}"))
            except Exception as e:
                logger.error(f"Unexpected error while creating partitions for {target_year}-{target_month:02d}: {e}", exc_info=True)
                self.stderr.write(self.style.ERROR(f"An unexpected error occurred for {target_year}-{target_month:02d}. Error: {e}"))

        self.stdout.write(self.style.SUCCESS("Partition creation process finished.")) 