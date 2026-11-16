"""Project-wide paths and column-name constants."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
TABLES_DIR = REPORTS_DIR / "tables"
SQL_DIR = ROOT_DIR / "sql"

DATASET_URL = (
    "https://huggingface.co/datasets/Arailym-tleubayeva/KazakhLawCorpus-clean"
    "/resolve/main/data/kazakhlawcorpus_kk_only.csv"
)
RAW_CSV = RAW_DIR / "kazakhlawcorpus_kk_only.csv"
PARQUET_FILE = PROCESSED_DIR / "acts.parquet"
DB_FILE = PROCESSED_DIR / "legislation.db"
SCHEMA_FILE = SQL_DIR / "schema.sql"
AUDIT_FILE = TABLES_DIR / "audit.json"
BENCHMARK_FILE = TABLES_DIR / "benchmarks.json"
FORECAST_FILE = TABLES_DIR / "forecast_mae.csv"
QUERY_RESULTS_DIR = TABLES_DIR / "sql"

CHUNK_SIZE = 50_000
CSV_ENCODING = "utf-8"

COL_SOURCE_ID = "source_id"
COL_LAW_ID = "law_id"
COL_DATE_ADOPTED = "date_adopted"
COL_DATE_MODIFIED = "date_modified"
COL_DATE_PUBLISHED = "date_published"
COL_MINISTRY_REG_DATE = "ministry_registration_date"
COL_STATE_REG_NUMBER = "state_registry_number"
COL_IS_ARCHIVE = "is_archive"
COL_IS_REPEALED = "is_repealed"
COL_TITLE = "title"
COL_DESCRIPTION = "description"
COL_ADILET_URL = "adilet_url"
COL_ACT_FORM = "act_form"
COL_AREA = "legal_relation_area"
COL_LEGAL_FORCE = "legal_force"
COL_ADOPTING_BODY = "adopting_body"
COL_REGULATORY_BODY = "regulatory_body"
COL_DEVELOPER_BODY = "developer_body"
COL_REGION = "region"
COL_PLACE = "place_of_adoption"
COL_SECTION = "database_section"

DATE_COLUMNS = [COL_DATE_ADOPTED, COL_DATE_MODIFIED, COL_DATE_PUBLISHED, COL_MINISTRY_REG_DATE]
BOOL_COLUMNS = [COL_IS_ARCHIVE, COL_IS_REPEALED]
CATEGORY_COLUMNS = [
    COL_ACT_FORM, COL_AREA, COL_LEGAL_FORCE, COL_ADOPTING_BODY, COL_REGULATORY_BODY,
    COL_DEVELOPER_BODY, COL_REGION, COL_PLACE, COL_SECTION,
]
MULTI_VALUE_COLUMNS = [COL_ACT_FORM, COL_AREA]
TRUE_FLAG = "t"
DATE_FORMAT = "%Y-%m-%d"

SOURCE_PLACEHOLDERS = ["ЖОҚ", "НЕТ", "N/A", "-", "---", "Some()", "None"]
PLACEHOLDER_VALUES = SOURCE_PLACEHOLDERS + [""]

FIRST_FULL_YEAR = 1992
LAST_FULL_YEAR = 2025
FORECAST_TEST_START = "2023-01-01"
SEASONAL_PERIOD = 12
ROLLING_WINDOW = 12
