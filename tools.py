import random
import string
import textdistance
import math
def generate_random_integers_summing_to_100(num_count):
    """
    Generates a list of 'num_count' random integers (>= 0) that sum to 100.
    """
    if num_count <= 0:
        return []

    numbers = []
    remaining_sum = 100

    for i in range(num_count - 1):
        # The next random number must be between 0 and the remaining sum
        num = random.randint(0, remaining_sum)
        numbers.append(num)
        remaining_sum -= num

    # The last number is exactly the remaining sum
    numbers.append(remaining_sum)
    return numbers