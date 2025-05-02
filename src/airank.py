import os
import csv
import glob
import json
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('azure_openai')

# Load environment variables
load_dotenv()

# Best practice: Get configuration from environment variables or use defaults
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://joey-ma5dicct-eastus2.openai.azure.com/")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
api_key = os.getenv("AZURE_OPENAI_API_KEY", "2C23MATrbnuqThzWwYZw56whDuG5FaJ8rlDPJMOQN9wowoFDrij2JQQJ99BEACHYHv6XJ3w3AAAAACOGX9t")

# Best practice: Use a stable API version
api_version = "2023-07-01-preview"  # More stable version than preview versions

def create_azure_openai_client() -> AzureOpenAI:
    """Create Azure OpenAI client with best practices for resilience and security"""
    logger.info(f"Initializing Azure OpenAI client with endpoint: {endpoint}")
    
    # Initialize client with Azure best practices
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
        max_retries=3,               # Add retry logic for resilience
        timeout=30.0,                # Set reasonable timeout
    )
    
    return client

def test_azure_connection() -> bool:
    """Test the Azure OpenAI connection and report status"""
    try:
        logger.info("Testing Azure OpenAI connection...")
        client = create_azure_openai_client()
        
        # Best practice: Use a lightweight API call to test connectivity
        models = client.models.list()
        logger.info("Connection successful. Available models:")
        for model in models:
            logger.info(f" - {model.id}")
        return True
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False

def find_latest_commits_csv() -> str:
    """Find the most recent commits CSV file"""
    csv_files = glob.glob("commits_*.csv")
    if not csv_files:
        raise FileNotFoundError("No commits_*.csv files found in the current directory")
    
    # Sort by modification time (newest first)
    latest_file = max(csv_files, key=os.path.getmtime)
    logger.info(f"Using latest commits file: {latest_file}")
    return latest_file

def read_commits_from_csv(file_path: str) -> List[Dict[str, str]]:
    """Read commits from a CSV file"""
    commits = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                commits.append(row)
        logger.info(f"Successfully read {len(commits)} commits from {file_path}")
        return commits
    except Exception as e:
        logger.error(f"Error reading CSV file: {str(e)}")
        raise

def rate_commit_quality(commits: List[Dict[str, str]], batch_size: int = 10) -> List[Dict[str, Any]]:
    """
    Rate the quality of commits using Azure OpenAI
    
    Args:
        commits: List of commit dictionaries from CSV
        batch_size: Number of commits to process in each API call
        
    Returns:
        List of commits with added quality scores
    """
    logger.info(f"Rating quality of {len(commits)} commits using Azure OpenAI")
    client = create_azure_openai_client()
    
    # Process commits in batches to manage rate limits
    rated_commits = []
    for i in range(0, len(commits), batch_size):
        batch = commits[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(commits) + batch_size - 1)//batch_size}")
        
        # Create a batch of commit messages for evaluation
        commit_messages = []
        for j, commit in enumerate(batch):
            commit_messages.append(f"[{j+1}] {commit.get('commit_message', 'No message')}")
        
        # Prepare system prompt for evaluation
        system_prompt = """
        You are an expert at evaluating Git commit message quality. 
        Rate each commit message on a scale of 1-10 based on:
        - Clarity: Is the purpose of the change clear?
        - Specificity: Does it provide specific details about what changed?
        - Completeness: Does it explain the why behind the change?
        - Format: Does it follow conventional commit format?
        
        Format your response as a JSON object with an array of evaluations:
        {
          "evaluations": [
            {"index": 1, "score": 8, "reason": "Clear and specific with conventional format"},
            {"index": 2, "score": 3, "reason": "Too vague, missing context and rationale"}
          ]
        }
        """
        
        # Use retry logic with exponential backoff
        max_retries = 3
        retry_count = 0
        success = False
        
        while not success and retry_count < max_retries:
            try:
                # Call Azure OpenAI for evaluation
                response = client.chat.completions.create(
                    model=deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "\n".join(commit_messages)}
                    ],
                    temperature=0.0,  # Use deterministic output for consistency
                    max_tokens=4000,
                    response_format={"type": "json_object"}  # Ensure response is valid JSON
                )
                
                # Parse the evaluation results
                result = json.loads(response.choices[0].message.content)
                evaluations = result.get("evaluations", [])
                
                # Add scores to the commits
                for eval_data in evaluations:
                    idx = eval_data.get("index", 0) - 1  # Convert 1-based to 0-based index
                    if 0 <= idx < len(batch):
                        batch[idx]["quality_score"] = eval_data.get("score", 0)
                        batch[idx]["quality_reason"] = eval_data.get("reason", "No reason provided")
                
                rated_commits.extend(batch)
                success = True
                logger.info(f"Successfully rated batch {i//batch_size + 1}")
                
            except Exception as e:
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                
                logger.error(f"Error rating commits: {str(e)}")
                
                if retry_count < max_retries:
                    logger.info(f"Retrying in {wait_time} seconds... (Attempt {retry_count+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error("All retry attempts failed for this batch")
                    
                    # Add unrated commits to preserve data
                    for commit in batch:
                        commit["quality_score"] = 0
                        commit["quality_reason"] = "Rating failed"
                    rated_commits.extend(batch)
    
    return rated_commits

def save_rated_commits(commits: List[Dict[str, Any]]) -> str:
    """Save rated commits to a new CSV file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"rated_commits_{timestamp}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8') as file:
        # Get all fieldnames from the first commit
        fieldnames = list(commits[0].keys())
        
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(commits)
    
    logger.info(f"Saved rated commits to {output_file}")
    return output_file

def display_top_commits(commits: List[Dict[str, Any]], count: int = 10) -> None:
    """Display the top rated commits"""
    print(f"\n===== TOP {count} QUALITY COMMITS =====\n")
    
    # Sort commits by quality score (highest first)
    sorted_commits = sorted(
        commits, 
        key=lambda x: float(x.get("quality_score", 0)), 
        reverse=True
    )
    
    for i, commit in enumerate(sorted_commits[:count], 1):
        print(f"{i}. Score: {commit.get('quality_score', 'N/A')}/10")
        print(f"   Message: {commit.get('commit_message', 'No message')}")
        print(f"   Author: {commit.get('author', 'Unknown')}")
        print(f"   Repository: {commit.get('repository', 'Unknown')}")
        print(f"   Date: {commit.get('date', 'Unknown')}")
        print(f"   Reason: {commit.get('quality_reason', 'No reason provided')}")
        print()

if __name__ == "__main__":
    try:
        # First test the connection
        if not test_azure_connection():
            logger.error("Failed to connect to Azure OpenAI - cannot proceed")
            print("Failed to establish connection to Azure OpenAI. Check logs for details.")
            exit(1)
        
        # Find and read the latest commits file
        commits_file = find_latest_commits_csv()
        commits = read_commits_from_csv(commits_file)
        
        # Rate the commits
        print(f"Rating {len(commits)} commits from {commits_file}...")
        rated_commits = rate_commit_quality(commits)
        
        # Save results
        output_file = save_rated_commits(rated_commits)
        print(f"Saved rated commits to {output_file}")
        
        # Display top commits
        display_top_commits(rated_commits)
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        print(f"Error: {str(e)}")
        print("Check logs for more details.")