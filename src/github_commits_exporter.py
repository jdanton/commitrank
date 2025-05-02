import requests
import csv
import os
import time
from datetime import datetime
from config import GITHUB_ORG, GITHUB_TOKEN
from utils.csv_helper import write_commits_to_csv
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Azure OpenAI configuration from environment variables
api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Azure OpenAI best practices:
# 1. Use the latest stable API version
# 2. Enable logging and telemetry
# 3. Configure proper timeouts
# 4. Implement retry logic for resilience
client = AzureOpenAI(
    api_key=api_key,
    api_version="2023-09-15-preview",  # Stable API version for Azure OpenAI
    azure_endpoint=azure_endpoint,
    max_retries=3,  # Add retry logic
)

print(f"Attempting to connect to Azure OpenAI at: {azure_endpoint}")
print(f"Using deployment: {deployment_name}")

try:
    # First test: list available models
    models = client.models.list()
    print("Successfully connected! Available models:")
    for model in models:
        print(f" - {model.id}")
    
    # Second test: create a simple completion
    response = client.chat.completions.create(
        model=deployment_name,  # Use the deployment name from .env
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, can you confirm you're working?"}
        ],
        max_tokens=100
    )
    
    print("\nChat completion test:")
    print(response.choices[0].message.content)
    
except Exception as e:
    print(f"\nError connecting to Azure OpenAI: {str(e)}")
    
    # Provide troubleshooting guidance
    print("\nTroubleshooting steps:")
    print("1. Verify your API key is correct")
    print("2. Ensure your Azure OpenAI resource exists in the specified region")
    print("3. Check that your deployment name matches exactly what's in Azure Portal")
    print("4. Verify the endpoint format:")
    print("   - Azure OpenAI resources: https://<resource-name>.openai.azure.com/")
    print("   - Cognitive Services resources: https://<resource-name>.cognitiveservices.azure.com/")
    print("5. Ensure your Azure subscription is active and has quota for the model")

def get_repositories(org):
    url = f"https://api.github.com/orgs/{org}/repos"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    params = {'per_page': 100}  # Maximum allowed by GitHub
    repos = []
    
    print(f"Fetching repositories for {org}...")
    while url:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_time = max(reset_time - time.time(), 0) + 1
            print(f"Rate limit exceeded. Waiting for {wait_time:.0f} seconds...")
            time.sleep(wait_time)
            continue
            
        response.raise_for_status()
        repos.extend(response.json())
        url = response.links.get('next', {}).get('url')
        # Remove params as they're already in the next URL
        params = {}
    
    print(f"Found {len(repos)} repositories")
    return repos

def get_commits(repo_full_name):
    """
    Gets ALL historical commits for a repository (not just pending ones)
    """
    url = f"https://api.github.com/repos/{repo_full_name}/commits"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    params = {'per_page': 100}  # Maximum allowed by GitHub
    commits = []
    
    print(f"Fetching commits for {repo_full_name}...")
    page_count = 0
    
    while url:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_time = max(reset_time - time.time(), 0) + 1
            print(f"Rate limit exceeded. Waiting for {wait_time:.0f} seconds...")
            time.sleep(wait_time)
            continue
            
        response.raise_for_status()
        page_commits = response.json()
        commits.extend(page_commits)
        
        page_count += 1
        print(f"  Retrieved page {page_count} with {len(page_commits)} commits. Total: {len(commits)}")
        
        url = response.links.get('next', {}).get('url')
        # Remove params as they're already in the next URL
        params = {}
    
    print(f"Total commits for {repo_full_name}: {len(commits)}")
    return commits

def main():
    start_time = datetime.now()
    print(f"Starting commit collection at {start_time}")
    
    repositories = get_repositories(GITHUB_ORG)
    all_commits = []
    
    for i, repo in enumerate(repositories):
        print(f"\nProcessing repository {i+1}/{len(repositories)}")
        repo_full_name = repo['full_name']
        commits = get_commits(repo_full_name)
        for commit in commits:
            all_commits.append({
                'repository': repo_full_name,
                'commit_sha': commit['sha'],
                'commit_message': commit['commit']['message'].replace('\n', ' ').replace('\r', ''),
                'author': commit['commit']['author']['name'],
                'date': commit['commit']['author']['date'],
                'url': commit['html_url'] if 'html_url' in commit else ''
            })

    output_file = os.path.join(os.getcwd(), f'commits_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    write_commits_to_csv(all_commits, output_file)
    
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\nCollection completed at {end_time}")
    print(f"Total time: {duration}")
    print(f"Total commits collected: {len(all_commits)}")
    print(f"Results saved to: {output_file}")

if __name__ == "__main__":
    main()