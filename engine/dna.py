from __future__ import annotations

import string


class Dna:
    def __init__(self, rng):
        self.rng = rng
        self.my_dna = ""
        self.rule_count = 10
        self.functions = ["count", "approach"]
        self.laws = {}
        for letter in string.ascii_lowercase:
            self.laws[letter] = [rng.choice(string.ascii_lowercase)]
        self.rules = []
        for i in range(self.rule_count):
            self.rules.append(self.make_rule())

    def make_creature(self, word):
        creature = {}
        creature["health"] = 0.1 + calculate(word, self.rules, self.rng)
        creature["damage"] = 0.1 + calculate(word, self.rules, self.rng)
        creature["dna"] = word
        return creature

    def make_rule(self):
        return {"function": self.rng.choice(self.functions)}

    def make_laws(self):
        return {"function": self.rng.choice(self.functions)}


def calculate(word, rules, rng=None):
    useful = []
    total = 0
    best_sum = 0
    best_rule = {}
    for rule in rules:
        if not rule.get("to_word"):
            rule["to_word"] = make_word(len(word), rng)
        ruleout = evaluate(rule["function"], word, rule["to_word"])
        rule["output"] = ruleout
        if ruleout:
            useful.append(rule)
        total += ruleout
        if total > best_sum:
            best_sum = total
            best_rule = rule
    return total


def make_word(length, rng):
    the_word = ""
    for i in range(length):
        random_letter = rng.choice(string.ascii_lowercase)
        the_word += random_letter
    return the_word


def letter_distance(char1, char2):
    char1 = char1.lower()
    char2 = char2.lower()
    distance = abs(ord(char1) - ord(char2))
    return distance


def evaluate(rule, word, to_word):
    total = 0
    match rule:
        case "count":
            i = 1
            for letter in to_word:
                total += word.count(to_word[0:i]) * i * i / 2
                i += 1
        case "approach":
            for i in range(min(len(word), len(to_word))):
                distance = letter_distance(word[i], to_word[i])
                total += (25 - distance) / 25
            total -= 3
            total = max(0, total)
            total = total * total
    return total
