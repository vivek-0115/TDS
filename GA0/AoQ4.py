import json
import statistics

# Load the JSON file
with open("GA0/q-calculate-variance.json", "r") as file:
    data = json.load(file)

# Calculate sample variance (uses N-1 denominator)
sample_variance = statistics.variance(data)

# Print rounded answer
print(round(sample_variance, 2))