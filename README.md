# CommitRank

## Overview
This project is designed to retrieve, export, and rank commit data from GitHub repositories. It connects to the GitHub API, collects commit information, generates a CSV file, and then uses Azure OpenAI to analyze and rank the quality of commit messages.

## Project Structure
```
commitrank/
├── src/
│   ├── airank.py                    # AI-based commit quality ranking
│   ├── config.py                    # Configuration settings
│   ├── github_commits_exporter.py   # Main script for exporting commits
│   └── utils/
│       ├── __init__.py
│       └── csv_helper.py            # Utility functions for CSV operations
├── .env                             # Environment variables (not tracked in git)
├── .gitignore                       # Git ignore file
├── requirements.txt                 # Python dependencies
└── README.md                        # Project documentation
```

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/commitrank.git
   cd commitrank
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration
Before running the script, you need to set up your environment:

1. Create a `.env` file with your API tokens and settings:
   ```
   GITHUB_TOKEN=your_github_token
   GITHUB_ORG=your_github_organization
   AZURE_OPENAI_API_KEY=your_azure_openai_key
   AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
   AZURE_OPENAI_DEPLOYMENT=your_deployment_name
   ```

## Usage
1. To export GitHub commits to CSV:
   ```
   python src/github_commits_exporter.py
   ```

2. To rank commit quality using Azure OpenAI:
   ```
   python src/airank.py
   ```

## Output
- The exporter script generates a CSV file with commit data named `commits_YYYYMMDD_HHMMSS.csv`
- The AI ranking script generates a CSV file with quality scores named `rated_commits_YYYYMMDD_HHMMSS.csv`

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License.