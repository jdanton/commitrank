import csv
import os

def create_csv_file(file_path, header):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(header)

def write_commit_data_to_csv(file_path, commit_data):
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(commit_data)

def format_commit_data(commits):
    formatted_data = []
    for commit in commits:
        formatted_data.append([
            commit.get('sha'),
            commit.get('commit', {}).get('author', {}).get('name'),
            commit.get('commit', {}).get('author', {}).get('email'),
            commit.get('commit', {}).get('committer', {}).get('name'),
            commit.get('commit', {}).get('committer', {}).get('email'),
            commit.get('commit', {}).get('message'),
            commit.get('commit', {}).get('committer', {}).get('date')
        ])
    return formatted_data

def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def write_commits_to_csv(commits, output_file):
    """
    Write commit data to a CSV file
    
    Args:
        commits (list): List of dictionaries containing commit data
        output_file (str): Path to the output CSV file
    """
    if not commits:
        print("No commits to write.")
        return
    
    fieldnames = commits[0].keys()
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(commits)
    
    print(f"Successfully wrote {len(commits)} commits to {output_file}")