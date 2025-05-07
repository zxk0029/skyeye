<!--
parent:
  order: false
-->

<div align="center">
  <h1> skyeye repo </h1>
</div>

<div align="center">
  <a href="https://github.com/SavourDao/skyeye/releases/latest">
    <img alt="Version" src="https://img.shields.io/github/tag/savour-labs/skyeye.svg" />
  </a>
  <a href="https://github.com/SavourDao/skyeye/blob/main/LICENSE">
    <img alt="License: Apache-2.0" src="https://img.shields.io/github/license/savour-labs/skyeye.svg" />
  </a>
</div>

skyeye is the market aggregator of the Savour project, which aggregates the market of centralized and decentralized
transactions. It is written in python and provides grpc interface for upper-layer service access.

**tips**: requirement [python3.12+](https://www.python.org/)

## Install And Local Runing

Follow these steps to set up your local development environment for SkyEye.

### 1. Clone the Repository
First, clone the repository to your local machine:
```bash
git clone https://github.com/dapplink-labs/skyeye.git skyeye
cd skyeye
```

### 2. Initialize Git Submodules
This project uses Git submodules (e.g., for `dapplink-proto`). After cloning, initialize and fetch the submodule content:
```bash
git submodule update --init --recursive
```

### 3. Set up Python Environment

a. **Create and activate a virtual environment:**

   You can use Python's built-in `venv` module or a modern package manager like `uv`.

   *   **Using standard `venv` (Python 3.12+ recommended):**
       ```bash
       python3 -m venv .venv  # Creates a virtual environment named .venv
       source .venv/bin/activate # Or `.\.venv\Scripts\activate` on Windows
       ```

   *   **Recommended: Using `uv` (if installed):**
       `uv` is a very fast Python package installer and resolver, and can also manage virtual environments. If you don't have `uv` installed, you can find installation instructions [here](https://github.com/astral-sh/uv#installation).
       ```bash
       uv venv .venv  # Creates a virtual environment named .venv
       source .venv/bin/activate # Or `.\.venv\Scripts\activate` on Windows
       ```

b. **Install dependencies (after activating the virtual environment):**
   If using `uv`:
   ```bash
   uv pip install -r requirements.txt
   ```
   If using standard `pip` (from the `venv` activated environment):
   ```bash
   pip install -r requirements.txt
   ```

### 4. Configure Database
You'll need to configure your database settings. Typically, this is done in a Django settings file (e.g., `skyeye/settings.py` or a local settings override). Ensure you have a PostgreSQL database set up.
```python
# Example DATABASES configuration (update with your actual credentials)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "skyeye",
        "USER": "your_db_user", # Replace with your DB user
        "PASSWORD": "your_db_password", # Replace with your DB password
        "HOST": "127.0.0.1", # Or your DB host
        "PORT": "5432", # Or your DB port
    },
}
```
Update the `USER`, `PASSWORD`, `NAME`, `HOST`, and `PORT` according to your environment.

### 5. Compile Protocol Buffers (Optional - If Updating Proto Definitions)
The project relies on Python code generated from Protocol Buffer definitions, which are managed in the `external/dapplink-proto` submodule.

**Typically, the repository includes the latest compiled Python gRPC files, so you may not need to run this step initially.**

However, if you have updated the `.proto` files in the `external/dapplink-proto` submodule, or if you suspect the compiled files are outdated or missing, you will need to regenerate them using the following script:
```bash
bash scripts/proto_compile.sh
```
*(Note: Before running this script, ensure the `external/dapplink-proto` submodule is initialized and updated, as described in step 2. If the script fails with an error about the submodule directory being empty or not found, run `git submodule update --init --recursive`.)*

### 6. Apply Database Migrations
Once the database is configured and proto files are compiled, apply the database migrations:
```bash
python3 manage.py makemigrations
python3 manage.py migrate
```

### 7. Run the Development Server
To start the Django development server:
```bash
python3 manage.py runserver
```

### 8. Run Background Workers/Crawlers (Example)
To run specific crawlers or background tasks (this is an example, refer to project-specific commands):
```bash
python3 manage.py broker_crawler crawler_fetch_24tickers
```

## Contribute

### 1.fork repo

fork skyeye to your github

### 2.clone repo

```bash
git@github.com:guoshijiang/skyeye.git
```

### 3.create new branch and commit code

```bash
git branch -C xxx
git checkout xxx

coding

git add .
git commit -m "xxx"
git push origin xxx
```

4.commit PR
Have a pr on your github and submit it to the skyeye repository

5.review
After the skyeye code maintainer has passed the review, the code will be merged into the skyeye repo. At this point,
your PR submission is complete
