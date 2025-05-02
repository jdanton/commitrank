import requests
import csv
import os
import time
import logging
from datetime import datetime
from config import GITHUB_ORG, GITHUB_TOKEN, GITHUB_REPO
from utils.csv_helper import write_commits_to_csv
from openai import AzureOpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get Azure OpenAI configuration from environment variables
api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Azure OpenAI best practices:
# 1. Use the latest stable API version (not preview versions in production)
# 2. Configure proper timeouts and retries
# 3. Implement structured error handling
# 4. Use logging for monitoring and diagnostics
client = AzureOpenAI(
    api_key=api_key,
    api_version="2023-12-01",  # Use the latest stable (non-preview) API version
    azure_endpoint=azure_endpoint,
    max_retries=3,  # Implement automatic retries for transient failures
    timeout=30.0,   # Set appropriate timeout
)

print(f"Attempting to connect to Azure OpenAI at: {azure_endpoint}")
print(f"Using deployment: {deployment_name}")

try:
    # Test connection to Azure OpenAI
    models = client.models.list()
    print("Successfully connected! Available models:")
    for model in models:
        print(f" - {model.id}")
    
    # Test completion
    response = client.chat.completions.create(
        model=deployment_name,
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
    print("\nTroubleshooting steps:")
    print("1. Verify your API key is correct")
    print("2. Ensure your Azure OpenAI resource exists in the specified region")
    print("3. Check that your deployment name matches exactly what's in Azure Portal")
    print("4. Verify the endpoint format is correct")
    print("5. Ensure your Azure subscription is active and has quota for the model")

def is_organization(name):
    """Check if the provided name is a GitHub organization or a user"""
    url = f"https://api.github.com/orgs/{name}"
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    return response.status_code == 200

def get_repositories(name):
    """
    Gets repositories from either an organization or a user
    """
    # First check if it's an organization
    if is_organization(name):
        url = f"https://api.github.com/orgs/{name}/repos"
        source_type = "organization"
    else:
        # If not an organization, try as a user
        url = f"https://api.github.com/users/{name}/repos"
        source_type = "user"
    
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    params = {'per_page': 100}  # Maximum allowed by GitHub
    repos = []
    
    print(f"Fetching repositories for {name} (treated as {source_type})...")
    
    try:
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
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching repositories: {e}")
        if response.status_code == 404:
            print(f"The {source_type} '{name}' was not found on GitHub.")
            print("Please check the spelling and ensure you have the correct access permissions.")
        return []

def get_commits(repo_full_name):
    """
    Gets ALL historical commits for a repository
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
    
    all_commits = []
    
    # If a specific repo is provided, process only that repo
    if GITHUB_REPO:
        try:
            repo_full_name = f"{GITHUB_ORG}/{GITHUB_REPO}"
            print(f"\nProcessing specific repository: {repo_full_name}")
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
        except requests.exceptions.HTTPError as e:
            print(f"Error processing repository {repo_full_name}: {e}")
            if "404" in str(e):
                print(f"Repository {repo_full_name} does not exist or you don't have access to it.")
    else:
        # Process all repositories for the organization/user
        repositories = get_repositories(GITHUB_ORG)
        for i, repo in enumerate(repositories):
            try:
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
            except requests.exceptions.HTTPError as e:
                print(f"Error processing repository {repo_full_name}: {e}")
                continue

    if all_commits:
        output_file = os.path.join(os.getcwd(), f'commits_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        write_commits_to_csv(all_commits, output_file)
        
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"\nCollection completed at {end_time}")
        print(f"Total time: {duration}")
        print(f"Total commits collected: {len(all_commits)}")
        print(f"Results saved to: {output_file}")
    else:
        print("\nNo commits were collected. Please check your GitHub configuration.")

if __name__ == "__main__":
    main()