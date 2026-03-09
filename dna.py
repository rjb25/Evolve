import random
import string
import textdistance

word_length = 6
functions = ["count","before"]
def make_rule():
    return {"letter":random.choice(string.ascii_lowercase), "function":random.choice(functions)}
rules = []
def make_word():
    the_word =""
    for i in range(word_length):
        random_letter = random.choice(string.ascii_lowercase)
        the_word += random_letter
    return the_word
word = make_word()
print(word)
for i in range(word_length):
    rules.append(make_rule())


def calculate(word, rules):
    useful = []
    sum = 0
    for rule in rules:
        ruleout = evaluate(rule, word)
        if ruleout:
            useful.append(rule)
        sum += ruleout
    print(useful)
    return sum

def evaluate(rule, word):
    sum = 0
    match rule["function"]:
        case "count":
            sum += word.count(rule["letter"])
        case "before":
            if not rule.get("before"):
                rule["before"] = random.choice(string.ascii_lowercase)
            sum += word.count(rule["letter"]+rule["before"])
        case "close":
            if not rule.get("close"):
                rule["close"] = make_word()
            lev_dist = textdistance.levenshtein.distance(word, rule["close"])

            sum += lev_dist*word_length
    return sum


damage = calculate(word,rules)
print(rules)
print(damage)
class Rule:
    def __init__(self):
        self.name = "shmame"
rulio = Rule()

#sequences
#For each s add 1 damage

