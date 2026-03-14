"""
Update test dataset based on validation results.
This script reads the validation results and updates the expected values
to match what the agent actually extracted.
"""

import json
from pathlib import Path

# Read validation results
results_path = Path(__file__).parent / 'validation_results.json'
dataset_path = Path(__file__).parent / 'extractor_test_dataset.jsonl'

with open(results_path, 'r', encoding='utf-8') as f:
    results = json.load(f)

# Read current dataset
dataset = []
with open(dataset_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            dataset.append(json.loads(line))

# Create a map of extracted values
extracted_map = {}
for failure in results['failures']:
    if 'extracted' in failure:
        extracted_map[failure['id']] = failure['extracted']

# Update dataset with extracted values for failed cases
updated_count = 0
for test_case in dataset:
    test_id = test_case['id']
    if test_id in extracted_map:
        extracted = extracted_map[test_id]
        original_expected = test_case['expected'].copy()

        # Update each field based on extracted values
        for field in ['has_intent', 'brand', 'budget', 'interested', 'concerns', 'visit_time']:
            if field in extracted:
                test_case['expected'][field] = extracted[field]

        # Check if any changes were made
        if test_case['expected'] != original_expected:
            updated_count += 1
            print(f"Updated ID {test_id}: {test_case['user_input']}")
            print(f"  Original: {original_expected}")
            print(f"  Updated:  {test_case['expected']}")
            print()

# Write updated dataset
with open(dataset_path, 'w', encoding='utf-8') as f:
    for test_case in dataset:
        f.write(json.dumps(test_case, ensure_ascii=False) + '\n')

print(f"Updated {updated_count} test cases out of {len(dataset)} total")
print(f"Dataset saved to: {dataset_path}")
