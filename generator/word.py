import math

class Word:
    def __init__(self, text, pos, domain, abstraction, complexity, ideology, philosophy, formality, sentiment):
        self.text = text
        self.pos = pos # Part of speech (not piece of shit)
        self.domains = set(domain)  # Fast set lookup
        
        # Raw components map
        self.components = {
            "abstraction": abstraction,
            "complexity": complexity,
            "ideology": ideology,
            "philosophy": philosophy,
            "formality": formality,
            "sentiment": sentiment
        }
        
        # Continuous vector array for standard distance calculations
        self.vector_keys = ["abstraction", "complexity", "ideology", "philosophy", "formality", "sentiment"]
        self.vector = [self.components[k] for k in self.vector_keys]

    def has_domain(self, target_domains):
        """Checks if the word shares any domain with the requested target list/set."""
        if isinstance(target_domains, (list, set, tuple)):
            return bool(self.domains.intersection(target_domains))
        return target_domains in self.domains